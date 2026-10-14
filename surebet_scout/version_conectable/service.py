"""Orquestación: escaneo, operaciones, salvaguardas y registro.

Flujo de una operación:
  1. Se crea desde una oportunidad (con límites de presupuesto).
  2. El usuario hace las patas MANUALES en cada casa y anota la cuota y el
     importe reales. Los importes pendientes se reequilibran solos.
  3. La pata AUTOMÁTICA (Betfair) va la última: se prepara (cuota en vivo,
     importe exacto, beneficio por resultado) y se confirma escribiendo SI.
  4. Tras el partido se liquida con el resultado ganador.
"""
import csv
import io
import time
from datetime import datetime, timezone

from betfair import BetfairError
from core import effective_odds, parse_iso, plan_stakes, round_stake, scan
from feeds import SPANISH_BOOKMAKERS, FeedError
from store import now_iso

DEFAULT_SETTINGS = {
    "bookmakers": list(SPANISH_BOOKMAKERS),
    "auto_bookmaker": "Betfair Exchange",
    "commissions": {"Betfair Exchange": 0.05, "Betfair ES": 0.0},
    "sports": ["*"],    # "*" = todos los deportes
    "markets": ["*"],   # "*" = todos los mercados; o nombres concretos (ML, Totals...)
    "hours_ahead": 48,
    "max_events": 100,
    "budget": 50.0,
    "min_margin": 0.0,
    "max_budget_op": 100.0,
    "max_daily": 300.0,
    "rounding": 0.5,
    "max_odds_age_s": 300,
    "opp_max_age_s": 900,
    # Cuidar las cuentas en casas normales
    "max_manual_stake": 50.0,     # aviso si una apuesta manual supera esto
    "max_margin_warn": 0.05,      # margen tan alto suele ser error de cuota (se anula)
    "book_profit_warn": 150.0,    # aviso cuando llevas mucho ganado en una casa
}
PREPARE_TTL_S = 60


class ServiceError(Exception):
    pass


class Service:
    def __init__(self, store, feed, exchange):
        self.store, self.feed, self.exchange = store, feed, exchange
        self.last_scan = {"at": None, "events": 0, "error": ""}

    # --- ajustes ----------------------------------------------------------
    def settings(self):
        return {**DEFAULT_SETTINGS, **(self.store.get_kv("settings", {}) or {})}

    def update_settings(self, patch):
        cur = self.settings()
        new = {**cur, **{k: v for k, v in patch.items() if k in DEFAULT_SETTINGS}}
        try:
            for k in ("hours_ahead", "max_events", "max_odds_age_s", "opp_max_age_s"):
                new[k] = int(new[k])
            for k in ("budget", "min_margin", "max_budget_op", "max_daily", "rounding",
                      "max_manual_stake", "max_margin_warn", "book_profit_warn"):
                new[k] = float(new[k])
            new["commissions"] = {str(b): float(c) for b, c in (new["commissions"] or {}).items()}
        except (TypeError, ValueError):
            raise ServiceError("Hay un valor no numérico en los ajustes.")
        if not isinstance(new["bookmakers"], list) or len(new["bookmakers"]) < 2:
            raise ServiceError("Elige al menos dos casas.")
        if len(new["bookmakers"]) > 30:
            raise ServiceError("Máximo 30 casas por búsqueda.")
        if not new["sports"]:
            raise ServiceError("Elige al menos un deporte.")
        if not isinstance(new["markets"], list) or not new["markets"]:
            raise ServiceError("Elige al menos un mercado.")
        if any(not 0 <= c < 0.5 for c in new["commissions"].values()):
            raise ServiceError("Las comisiones van de 0 a 0.5 (p. ej. 0.05 = 5 %).")
        if new["budget"] <= 0 or new["max_budget_op"] <= 0 or new["max_daily"] <= 0:
            raise ServiceError("Los importes deben ser positivos.")
        if new["budget"] > new["max_budget_op"]:
            raise ServiceError("El presupuesto por defecto supera el máximo por operación.")
        if new["max_manual_stake"] <= 0 or new["book_profit_warn"] <= 0 or new["max_margin_warn"] <= 0:
            raise ServiceError("Los avisos de cuidado de cuentas deben ser positivos.")
        if not 1 <= new["max_events"] <= 500 or not 1 <= new["hours_ahead"] <= 336:
            raise ServiceError("Eventos (1-500) u horas (1-336) fuera de rango.")
        self.store.set_kv("settings", new)
        return new

    # --- estado -----------------------------------------------------------
    def status(self, refresh_exchange=False):
        ops = [self.view(o) for o in self.store.operations()]
        st = self.settings()
        ex = self.exchange.status(refresh=True) if refresh_exchange and self.exchange.live \
            else self.exchange.status()
        return {
            "live": self.exchange.live,
            "feed": self.feed.status(),
            "exchange": ex,
            "last_scan": self.last_scan,
            "opportunities": len(self.store.opportunities()),
            "open_ops": sum(o["state"] in ("abierta", "en curso") for o in ops),
            "exposed_ops": [o["id"] for o in ops if o["exposed"]],
            "unknown_ops": [o["id"] for o in ops if o["has_unknown"]],
            "spent_today": self.spent_today(),
            "max_daily": st["max_daily"],
            "realized_profit": round(sum(o["settled"]["profit"] for o in ops if o.get("settled")), 2),
            "staked_total": round(sum(o["staked"] for o in ops), 2),
        }

    def spent_today(self):
        today = datetime.now(timezone.utc).date()
        total = 0.0
        for op in self.store.operations():
            for leg in op["legs"]:
                at = parse_iso(leg.get("placed_at"))
                if leg["status"] == "placed" and at and at.date() == today:
                    total += leg["stake"]
        return round(total, 2)

    # --- oportunidades ----------------------------------------------------
    def scan(self):
        st = self.settings()
        try:
            markets = None if "*" in st["markets"] else st["markets"]
            events = self.feed.fetch(st["sports"], st["bookmakers"], st["hours_ahead"],
                                     st["max_events"], markets)
        except FeedError as exc:
            self.last_scan = {"at": now_iso(), "events": 0, "error": str(exc)}
            raise ServiceError(str(exc))
        opps = scan(events, st["budget"], st["min_margin"], bookmakers=st["bookmakers"],
                    commissions=st["commissions"], rounding=st["rounding"],
                    max_age_s=st["max_odds_age_s"], exact_bookmakers=(st["auto_bookmaker"],),
                    markets=markets)
        self.store.replace_opportunities(opps)
        self.last_scan = {"at": now_iso(), "events": len(events), "error": ""}
        return self.opportunities()

    def opportunities(self):
        auto = self.settings()["auto_bookmaker"]
        out = self.store.opportunities()
        for o in out:
            for leg in o["legs"]:
                leg["mode"] = "auto" if leg["bookmaker"] == auto and leg.get("can_auto", True) \
                    else "manual"
        return out

    # --- operaciones ------------------------------------------------------
    def _check_budget(self, budget):
        st = self.settings()
        try:
            budget = float(budget or st["budget"])
        except (TypeError, ValueError):
            raise ServiceError("El presupuesto debe ser un número.")
        if budget <= 0:
            raise ServiceError("El presupuesto debe ser positivo.")
        if budget > st["max_budget_op"]:
            raise ServiceError(f"Supera tu máximo por operación ({st['max_budget_op']} €).")
        if self.spent_today() + budget > st["max_daily"]:
            raise ServiceError(f"Superarías tu límite diario ({st['max_daily']} €).")
        return budget

    def _new_operation(self, meta, in_legs, budget, margin, msg):
        """in_legs: dicts con outcome, label, bookmaker, odds, commission, url y
        can_auto (si esa pata puede ir por la API de Betfair)."""
        st = self.settings()
        plan_legs = []
        for l in in_legs:
            mode = "auto" if l.get("can_auto", True) and l["bookmaker"] == st["auto_bookmaker"] \
                else "manual"
            plan_legs.append({**l, "mode": mode, "eff": effective_odds(l["odds"], l["commission"]),
                              "step": 0.01 if mode == "auto" else st["rounding"]})
        stakes, _ = plan_stakes(plan_legs, budget)
        legs = []
        for i, (l, stake) in enumerate(zip(plan_legs, stakes)):
            legs.append({
                "id": i, "outcome": l["outcome"], "label": l["label"],
                "bookmaker": l["bookmaker"], "url": l.get("url", ""), "mode": l["mode"],
                "can_auto": l.get("can_auto", True),
                "planned_odds": l["odds"], "commission": l["commission"],
                "planned_stake": stake,
                "status": "pending", "odds": None, "stake": None, "ref": "",
                "placed_at": None, "simulated": None, "note": "", "prepared": None,
            })
        op = {
            "created_at": now_iso(), "event_id": meta.get("event_id", ""),
            "sport": meta.get("sport", ""), "league": meta.get("league", ""),
            "home": meta["home"], "away": meta.get("away", ""), "date": meta.get("date", ""),
            "source": meta.get("source", ""), "market_label": meta.get("market_label", ""),
            "margin": margin, "budget": budget, "legs": legs,
            "cancelled": False, "settled": None,
            "log": [{"at": now_iso(), "msg": msg}],
        }
        return self.view(self.store.add_operation(op))

    def create_operation(self, opp_id, budget=None):
        st = self.settings()
        opp = self.store.opportunity(opp_id)
        if not opp:
            raise ServiceError("Esa oportunidad ya no existe. Vuelve a buscar.")
        age = time.time() - parse_iso(opp["found_at"]).timestamp()
        if age > st["opp_max_age_s"]:
            raise ServiceError("Las cuotas de esta oportunidad son antiguas. Vuelve a buscar.")
        budget = self._check_budget(budget)
        return self._new_operation(opp, opp["legs"], budget, opp["margin"],
                                   f"Operación creada con {budget} €.")

    def create_external_operation(self, data):
        """Surebet vista en otro escáner (p. ej. BetOven) y copiada a mano.

        Admite cualquier mercado (goles, hándicap, córners...). Solo las patas de
        ganador del partido (1/X/2) con fecha pueden ir automáticas en Betfair;
        el resto se hacen a mano.
        """
        st = self.settings()
        data = data or {}
        home = str(data.get("home") or "").strip()[:80]
        away = str(data.get("away") or "").strip()[:80]
        if not home:
            raise ServiceError("Escribe el evento (al menos el equipo local o el nombre del evento).")
        date = str(data.get("date") or "").strip()
        if date and not parse_iso(date):
            raise ServiceError("Fecha no válida.")
        raw_legs = data.get("legs") or []
        if not 2 <= len(raw_legs) <= 4:
            raise ServiceError("Una surebet necesita de 2 a 4 apuestas.")
        legs, seen = [], set()
        for i, l in enumerate(raw_legs):
            kind = l.get("kind") or "other"
            if kind not in ("home", "draw", "away", "other"):
                raise ServiceError("Tipo de resultado no válido.")
            outcome = kind if kind != "other" else f"x{i}"
            if outcome in seen:
                raise ServiceError("Hay dos apuestas al mismo resultado.")
            seen.add(outcome)
            bookmaker = str(l.get("bookmaker") or "").strip()[:60]
            try:
                odds = float(l.get("odds"))
                commission = float(l.get("commission") if l.get("commission") not in (None, "")
                                   else st["commissions"].get(bookmaker, 0.0))
            except (TypeError, ValueError):
                raise ServiceError("Cuotas y comisiones deben ser números.")
            if not bookmaker or odds <= 1 or not 0 <= commission < 0.5:
                raise ServiceError(f"Revisa la apuesta {i + 1}: casa, cuota > 1 y comisión.")
            default_label = {"home": f"{home} (1)", "draw": "Empate (X)",
                             "away": f"{away or 'Visitante'} (2)"}.get(kind, f"Apuesta {i + 1}")
            legs.append({"outcome": outcome, "label": str(l.get("label") or "").strip()[:80] or default_label,
                         "bookmaker": bookmaker, "odds": odds, "commission": commission,
                         "url": "", "can_auto": kind != "other" and bool(away) and bool(date)})
        inv = sum(1 / effective_odds(l["odds"], l["commission"]) for l in legs)
        margin = round(1 / inv - 1, 6)
        if margin <= 0:
            raise ServiceError(f"Con esas cuotas no es surebet (margen {margin * 100:.2f} %). "
                               "Revisa las cuotas o las comisiones.")
        budget = self._check_budget(data.get("budget"))
        source = str(data.get("source") or "Externa").strip()[:40]
        meta = {"home": home, "away": away, "date": date, "source": source,
                "sport": str(data.get("sport") or "")[:30], "league": str(data.get("league") or "")[:60]}
        return self._new_operation(meta, legs, budget, margin,
                                   f"Operación creada desde {source} con {budget} €.")

    def _load(self, op_id, leg_id=None):
        op = self.store.operation(int(op_id))
        if not op:
            raise ServiceError("Operación no encontrada.")
        if leg_id is None:
            return op, None
        legs = [l for l in op["legs"] if l["id"] == int(leg_id)]
        if not legs:
            raise ServiceError("Apuesta no encontrada.")
        return op, legs[0]

    def _guard_editable(self, op):
        if op["cancelled"] or op["settled"]:
            raise ServiceError("La operación está cerrada.")

    def _save(self, op, msg):
        op["log"].append({"at": now_iso(), "msg": msg})
        self.store.save_operation(op)
        return self.view(op)

    def operations(self):
        return [self.view(o) for o in self.store.operations()]

    def operation(self, op_id):
        return self.view(self._load(op_id)[0])

    def register_manual(self, op_id, leg_id, odds, stake, bookmaker=None):
        op, leg = self._load(op_id, leg_id)
        self._guard_editable(op)
        try:
            odds, stake = float(odds), float(stake)
        except (TypeError, ValueError):
            raise ServiceError("Cuota e importe deben ser números.")
        if odds <= 1 or stake <= 0:
            raise ServiceError("La cuota debe ser > 1 y el importe > 0.")
        if bookmaker:
            leg["bookmaker"] = str(bookmaker)[:60]
        leg.update(status="placed", odds=odds, stake=round(stake, 2), placed_at=now_iso(),
                   simulated=None if leg["mode"] == "manual" else (not self.exchange.live),
                   prepared=None, note="Anotada a mano.")
        return self._save(op, f"{leg['label']}: anotada a mano {stake} € a {odds} en {leg['bookmaker']}.")

    def skip_leg(self, op_id, leg_id):
        op, leg = self._load(op_id, leg_id)
        self._guard_editable(op)
        if leg["status"] == "placed":
            raise ServiceError("Esa apuesta ya está hecha.")
        leg.update(status="skipped", prepared=None, note="No se pudo hacer.")
        return self._save(op, f"{leg['label']}: marcada como no realizada.")

    def reopen_leg(self, op_id, leg_id):
        op, leg = self._load(op_id, leg_id)
        self._guard_editable(op)
        if leg["status"] not in ("skipped", "unknown"):
            raise ServiceError("Solo se pueden reabrir apuestas no realizadas o con estado desconocido.")
        leg.update(status="pending", prepared=None, note="")
        return self._save(op, f"{leg['label']}: reabierta (confirmado que no se hizo).")

    def set_mode(self, op_id, leg_id, mode):
        op, leg = self._load(op_id, leg_id)
        self._guard_editable(op)
        if mode not in ("auto", "manual") or leg["status"] != "pending":
            raise ServiceError("Solo se puede cambiar el modo de una apuesta pendiente.")
        if mode == "auto" and (leg["bookmaker"] != self.settings()["auto_bookmaker"]
                               or not leg.get("can_auto", True)):
            raise ServiceError("Solo una apuesta 1X2 en la casa automática (Betfair) puede ir en automático.")
        leg.update(mode=mode, prepared=None)
        return self._save(op, f"{leg['label']}: modo {mode}.")

    def _target_payout(self, op, leg):
        placed = [l for l in op["legs"] if l["status"] == "placed"]
        if placed:
            return min(l["stake"] * effective_odds(l["odds"], l["commission"]) for l in placed)
        return leg["planned_stake"] * effective_odds(leg["planned_odds"], leg["commission"])

    def prepare_auto(self, op_id, leg_id):
        op, leg = self._load(op_id, leg_id)
        self._guard_editable(op)
        if leg["mode"] != "auto" or leg["status"] != "pending":
            raise ServiceError("Esta apuesta no es automática o no está pendiente.")
        if any(l["mode"] == "manual" and l["status"] == "pending" for l in op["legs"]):
            raise ServiceError("Primero haz y anota las apuestas manuales; Betfair va la última.")
        try:
            quote = self.exchange.quote(op, leg)
        except BetfairError as exc:
            raise ServiceError(str(exc))
        target = self._target_payout(op, leg)
        stake = round(target / effective_odds(quote["price"], leg["commission"]), 2)
        stakes = {l["id"]: (l["stake"] if l["status"] == "placed" else 0.0) for l in op["legs"]}
        stakes[leg["id"]] = stake
        projection = self._pl(op, stakes, {leg["id"]: quote["price"]})
        leg["prepared"] = {**quote, "stake": stake, "at": time.time(),
                           "projection": projection,
                           "worse": quote["price"] < leg["planned_odds"]}
        return self._save(op, f"{leg['label']}: preparada a {quote['price']} por {stake} €.")

    def place_auto(self, op_id, leg_id, confirm, accept_worse=False):
        st = self.settings()
        op, leg = self._load(op_id, leg_id)
        self._guard_editable(op)
        prep = leg.get("prepared")
        if leg["mode"] != "auto" or leg["status"] != "pending" or not prep:
            raise ServiceError("Prepara la apuesta antes de enviarla.")
        if time.time() - prep["at"] > PREPARE_TTL_S:
            raise ServiceError("La cuota preparada tiene más de 60 s. Vuelve a preparar.")
        if str(confirm or "").strip().upper() != "SI":
            raise ServiceError("Escribe SI para confirmar.")
        if (prep["worse"] or min(prep["projection"].values()) < 0) and not accept_worse:
            raise ServiceError("La cuota ha empeorado o habría pérdida: marca 'acepto' si aun así quieres cubrir.")
        stake = prep["stake"]
        if stake > st["max_budget_op"]:
            raise ServiceError(f"El importe supera tu máximo por operación ({st['max_budget_op']} €).")
        if self.spent_today() + stake > st["max_daily"]:
            raise ServiceError(f"Superarías tu límite diario ({st['max_daily']} €).")
        if stake > prep.get("size_available", stake):
            raise ServiceError("No hay suficiente dinero disponible a esa cuota en Betfair.")
        ref = f"ss{op['id']}l{leg['id']}t{int(time.time())}"
        res = self.exchange.place(prep, stake, ref)
        leg["prepared"] = None
        if res.get("ok"):
            leg.update(status="placed", odds=res["avg_price"] or prep["price"],
                       stake=round(res["matched"], 2), ref=res.get("bet_id", ""),
                       placed_at=now_iso(), simulated=not self.exchange.live, note=res["message"])
            return self._save(op, f"{leg['label']}: {'SIMULADA' if not self.exchange.live else 'APOSTADA en Betfair'} "
                                  f"{leg['stake']} € a {leg['odds']} (ref {leg['ref']}).")
        if res.get("unknown"):
            leg.update(status="unknown", note=f"Estado desconocido: {res['message']}. Revisa Betfair.")
            return self._save(op, f"{leg['label']}: ESTADO DESCONOCIDO ({res['message']}).")
        leg["note"] = f"No se casó: {res['message']}"
        return self._save(op, f"{leg['label']}: rechazada por Betfair ({res['message']}).")

    def cancel(self, op_id):
        op, _ = self._load(op_id)
        self._guard_editable(op)
        if any(l["status"] in ("placed", "unknown") for l in op["legs"]):
            raise ServiceError("Ya hay apuestas hechas: no se puede cancelar, solo liquidar.")
        op["cancelled"] = True
        return self._save(op, "Operación cancelada.")

    def settle(self, op_id, winner):
        op, _ = self._load(op_id)
        if op["cancelled"]:
            raise ServiceError("Operación cancelada.")
        placed = [l for l in op["legs"] if l["status"] == "placed"]
        if not placed:
            raise ServiceError("No hay apuestas hechas que liquidar.")
        total = sum(l["stake"] for l in placed)
        if winner == "void":
            profit = 0.0
        else:
            win = [l for l in placed if l["outcome"] == winner]
            if winner not in [l["outcome"] for l in op["legs"]]:
                raise ServiceError("Resultado no válido.")
            profit = (win[0]["stake"] * effective_odds(win[0]["odds"], win[0]["commission"])
                      if win else 0.0) - total
        op["settled"] = {"winner": winner, "profit": round(profit, 2), "at": now_iso()}
        return self._save(op, f"Liquidada: resultado {winner}, beneficio {round(profit, 2)} €.")

    # --- cálculos para la vista -------------------------------------------
    @staticmethod
    def _pl(op, stakes, odds_override=None):
        odds_override = odds_override or {}
        total = sum(stakes.values())
        out = {}
        for l in op["legs"]:
            odds = odds_override.get(l["id"]) or (l["odds"] if l["status"] == "placed" else l["planned_odds"])
            out[l["outcome"]] = round(stakes.get(l["id"], 0.0) * effective_odds(odds, l["commission"]) - total, 2)
        return out

    def view(self, op):
        op = {**op, "legs": [dict(l) for l in op["legs"]]}
        st = self.settings()
        placed = [l for l in op["legs"] if l["status"] == "placed"]
        target = min((l["stake"] * effective_odds(l["odds"], l["commission"]) for l in placed),
                     default=None)
        plan = {}
        for l in op["legs"]:
            if l["status"] == "placed":
                plan[l["id"]] = l["stake"]
            elif l["status"] == "pending":
                step = 0.01 if l["mode"] == "auto" else st["rounding"]
                sugg = l["planned_stake"] if target is None else \
                    round_stake(target / effective_odds(l["planned_odds"], l["commission"]), step)
                l["suggested_stake"] = sugg
                plan[l["id"]] = sugg
            else:
                plan[l["id"]] = 0.0
        current = {l["id"]: l["stake"] for l in placed}
        op["projection"] = self._pl(op, plan)
        op["current"] = self._pl(op, current)
        op["staked"] = round(sum(current.values()), 2)
        n_placed, n = len(placed), len(op["legs"])
        op["has_unknown"] = any(l["status"] == "unknown" for l in op["legs"]) and not op["settled"]
        op["exposed"] = 0 < n_placed < n and not op["cancelled"] and not op["settled"]
        if op["cancelled"]:
            state = "cancelada"
        elif op["settled"]:
            state = "liquidada"
        elif n_placed == n:
            state = "completa"
        elif n_placed and any(l["status"] in ("skipped", "unknown") for l in op["legs"]):
            state = "expuesta"
        elif n_placed:
            state = "en curso"
        else:
            state = "abierta"
        op["state"] = state
        op["next_step"] = self._next_step(op)
        return op

    @staticmethod
    def _next_step(op):
        if op["state"] in ("cancelada", "liquidada"):
            return None
        if op["state"] == "completa":
            return "Todas las apuestas hechas. Liquida cuando acabe el evento."
        pending = [l for l in op["legs"] if l["status"] == "pending"]
        manual = [l for l in pending if l["mode"] == "manual"]
        if manual:
            l = manual[0]
            stake = f"{l['suggested_stake']:.2f}".replace(".", ",")
            return f"Apuesta {stake} € a {l['label']} en {l['bookmaker']} y anótalo."
        if pending:
            return "Prepara y confirma la apuesta automática en Betfair."
        if op["has_unknown"]:
            return "Revisa en Betfair si la apuesta se hizo y anótala o reábrela."
        return "Queda riesgo abierto: cubre el resultado que falta en otra casa o liquida."

    # --- exportación ------------------------------------------------------
    def bookmaker_stats(self):
        """Actividad por casa: apuestas, volumen, beneficio liquidado y pendiente.

        Sirve para repartir: las casas tradicionales limitan antes a quien gana
        mucho o mueve mucho volumen en ellas.
        """
        st = self.settings()
        stats = {}
        for op in self.store.operations():
            settled = op.get("settled")
            for l in op["legs"]:
                if l["status"] != "placed":
                    continue
                b = stats.setdefault(l["bookmaker"], {"bookmaker": l["bookmaker"], "bets": 0,
                                                      "staked": 0.0, "profit": 0.0,
                                                      "open_stake": 0.0, "last_at": ""})
                b["bets"] += 1
                b["staked"] += l["stake"]
                b["last_at"] = max(b["last_at"], l.get("placed_at") or "")
                if not settled:
                    b["open_stake"] += l["stake"]
                elif settled["winner"] == l["outcome"]:
                    b["profit"] += l["stake"] * (effective_odds(l["odds"], l["commission"]) - 1)
                elif settled["winner"] != "void":
                    b["profit"] -= l["stake"]
        out = []
        for b in stats.values():
            for k in ("staked", "profit", "open_stake"):
                b[k] = round(b[k], 2)
            b["exchange"] = b["bookmaker"] == st["auto_bookmaker"]
            b["warn"] = not b["exchange"] and b["profit"] >= st["book_profit_warn"]
            out.append(b)
        return sorted(out, key=lambda b: -b["profit"])

    def export_csv(self):
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["operacion", "origen", "creada", "evento", "liga", "fecha_evento", "estado",
                    "resultado_apuesta", "casa", "modo", "simulada", "cuota_plan",
                    "importe_plan", "cuota_real", "importe_real", "estado_apuesta", "ref",
                    "ganador", "beneficio_operacion"])
        for op in self.operations():
            s = op.get("settled") or {}
            for l in op["legs"]:
                w.writerow([op["id"], op.get("source") or "Surebet Scout", op["created_at"], f"{op['home']} - {op['away']}",
                            op["league"], op["date"], op["state"], l["label"], l["bookmaker"],
                            l["mode"], l.get("simulated"), l["planned_odds"], l["planned_stake"],
                            l["odds"], l["stake"], l["status"], l["ref"], s.get("winner", ""),
                            s.get("profit", "")])
        return buf.getvalue()
