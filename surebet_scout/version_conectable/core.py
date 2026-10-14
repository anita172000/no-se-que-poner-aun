"""Detector puro de surebets: sin red, sin estado, sin órdenes.

Un evento normalizado tiene esta forma (la producen los feeds):
    {"id", "sport", "league", "home", "away", "date", "urls": {casa: url},
     "markets": {
        "ML":          {"type": "ML", "line": None, "prices": {casa: {"home", "draw", "away"}}},
        "Totals:2.5":  {"type": "Totals", "line": 2.5, "prices": {casa: {"over", "under"}}},
        "Spread:-0.5": {"type": "Spread", "line": -0.5, "prices": {casa: {"home", "away"}}},
     },
     "updated": {casa: iso}}
Por compatibilidad, un evento con solo "prices" se trata como mercado ML (1X2).
En Spread, "line" es el hándicap del local; el visitante tiene el contrario.
"""
import itertools
import math
from datetime import datetime, timezone

OUTCOMES = ("home", "draw", "away")
LABELS = {"home": "Local (1)", "draw": "Empate (X)", "away": "Visitante (2)"}
MARKET_OUTCOMES = {"ML": OUTCOMES, "Totals": ("over", "under"), "Spread": ("home", "away")}


def effective_odds(odds: float, commission: float = 0.0) -> float:
    """Cuota neta tras la comisión sobre ganancias (exchanges)."""
    if odds <= 1.0:
        raise ValueError("La cuota decimal debe ser mayor que 1.")
    if not 0 <= commission < 1:
        raise ValueError("La comisión debe estar entre 0 y 1.")
    return 1 + (odds - 1) * (1 - commission)


def round_stake(amount: float, step: float) -> float:
    if step <= 0.01:
        return round(amount, 2)
    return round(round(amount / step) * step, 2)


def parse_iso(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fmt_line(x, signed=False):
    txt = f"{x:+g}" if signed else f"{x:g}"
    return txt.replace(".", ",")


def market_label(mtype, line=None):
    if mtype == "Totals":
        return f"Más/Menos {_fmt_line(line)}"
    if mtype == "Spread":
        return f"Hándicap {_fmt_line(line, True)}"
    return "Ganador del partido"


def outcome_label(outcome, event, mtype="ML", line=None):
    home, away = event.get("home") or "Local", event.get("away") or "Visitante"
    if mtype == "Totals":
        return f"{'Más' if outcome == 'over' else 'Menos'} de {_fmt_line(line)}"
    if mtype == "Spread":
        return f"{home} ({_fmt_line(line, True)})" if outcome == "home" \
            else f"{away} ({_fmt_line(-line, True)})"
    if outcome == "home":
        return f"{home} (1)"
    if outcome == "away":
        return f"{away} (2)"
    return LABELS[outcome]


def event_markets(event):
    if event.get("markets"):
        return event["markets"]
    return {"ML": {"type": "ML", "line": None, "prices": event.get("prices", {})}}


def best_legs(event, bookmakers=None, commissions=None, max_age_s=None, now=None,
              market_key="ML"):
    """Mejor cuota efectiva por resultado de un mercado entre las casas permitidas.

    Solo se comparan casas que cotizan TODOS los resultados del mercado, para no
    mezclar un 1X2 con un mercado de dos resultados.
    """
    commissions = commissions or {}
    now = now or datetime.now(timezone.utc)
    market = event_markets(event).get(market_key)
    if not market:
        return None
    mtype, line = market.get("type", "ML"), market.get("line")
    updated = {**event.get("updated", {}), **market.get("updated", {})}
    allowed = {}
    for bk, prices in market.get("prices", {}).items():
        if bookmakers is not None and bk not in bookmakers:
            continue
        if max_age_s:
            upd = parse_iso(updated.get(bk))
            if upd and (now - upd).total_seconds() > max_age_s:
                continue
        allowed[bk] = prices
    outcomes = [o for o in MARKET_OUTCOMES.get(mtype, OUTCOMES)
                if any(o in p for p in allowed.values())]
    if len(outcomes) < 2:
        return None
    best = {}
    for bk, prices in allowed.items():
        if not all(o in prices for o in outcomes):
            continue
        for o in outcomes:
            odds = prices[o]
            if odds <= 1:
                continue
            eff = effective_odds(odds, commissions.get(bk, 0.0))
            if o not in best or eff > best[o]["eff"]:
                best[o] = {
                    "outcome": o,
                    "label": outcome_label(o, event, mtype, line),
                    "bookmaker": bk,
                    "odds": odds,
                    "commission": commissions.get(bk, 0.0),
                    "eff": eff,
                    "url": event.get("urls", {}).get(bk, ""),
                    "updated": updated.get(bk, ""),
                    # Solo el 1X2 se puede emparejar con el mercado Match Odds de Betfair.
                    "can_auto": mtype == "ML",
                }
    if len(best) != len(outcomes):
        return None
    return [best[o] for o in outcomes]


def plan_stakes(legs, budget: float, rounding: float = 0.01):
    """Reparte el presupuesto para igualar el cobro en todos los resultados.

    Cada pata redondea a su paso (leg["step"] si existe, si no `rounding`). En vez
    de redondear al más cercano, prueba hacia arriba y hacia abajo en cada pata y
    se queda con la combinación que deja más beneficio en el peor resultado.
    """
    if budget <= 0:
        raise ValueError("El presupuesto debe ser positivo.")
    inv = sum(1 / leg["eff"] for leg in legs)
    raw = [budget * (1 / leg["eff"]) / inv for leg in legs]
    options = []
    for x, leg in zip(raw, legs):
        step = leg.get("step", rounding)
        if step <= 0.01:
            options.append([round(x, 2)])
        else:
            lo = round(math.floor(x / step) * step, 2)
            options.append(sorted({lo, round(lo + step, 2)}))
    best = None
    for combo in itertools.product(*options):
        if min(combo) <= 0:
            continue
        pl = profit_by_outcome(legs, combo)
        key = (min(pl.values()), -abs(sum(combo) - budget))
        if best is None or key > best[0]:
            best = (key, list(combo), pl)
    if best is None:
        stakes = [round_stake(x, leg.get("step", rounding)) for x, leg in zip(raw, legs)]
        return stakes, profit_by_outcome(legs, stakes)
    return best[1], best[2]


def profit_by_outcome(legs, stakes):
    total = sum(stakes)
    return {leg["outcome"]: round(s * leg["eff"] - total, 2) for leg, s in zip(legs, stakes)}


def find_opportunities(event, budget, bookmakers=None, commissions=None, rounding=0.01,
                       max_age_s=None, now=None, exact_bookmakers=(), markets=None):
    """Todas las surebets de un evento (una por mercado/línea).

    exact_bookmakers: casas donde se apuesta al céntimo (p. ej. el exchange).
    markets: tipos de mercado a mirar (ML, Totals, Spread); None = todos.
    """
    out = []
    for key, market in event_markets(event).items():
        mtype = market.get("type", "ML")
        if markets is not None and mtype not in markets:
            continue
        legs = best_legs(event, bookmakers, commissions, max_age_s, now, key)
        if not legs:
            continue
        inv = sum(1 / leg["eff"] for leg in legs)
        if inv >= 1:
            continue
        for leg in legs:
            leg["step"] = 0.01 if leg["bookmaker"] in exact_bookmakers else rounding
        stakes, pl = plan_stakes(legs, budget, rounding)
        for leg, s in zip(legs, stakes):
            leg["stake"] = s
        eid = str(event["id"])
        out.append({
            "id": eid if key == "ML" else f"{eid}|{key}",
            "event_id": eid,
            "market": key,
            "market_type": mtype,
            "market_label": market_label(mtype, market.get("line")),
            "sport": event.get("sport", ""),
            "league": event.get("league", ""),
            "home": event.get("home", ""),
            "away": event.get("away", ""),
            "date": event.get("date", ""),
            "margin": round(1 / inv - 1, 6),
            "budget": budget,
            "legs": legs,
            "profit": pl,
            "min_profit": min(pl.values()),
        })
    return out


def find_opportunity(event, budget, **kw):
    """La mejor surebet del evento (o None)."""
    opps = find_opportunities(event, budget, **kw)
    return max(opps, key=lambda o: o["margin"]) if opps else None


def scan(events, budget, min_margin=0.0, **kw):
    """Todas las surebets de todos los eventos, de mayor a menor margen."""
    opps = [o for e in events for o in find_opportunities(e, budget, **kw)
            if o["margin"] >= min_margin]
    return sorted(opps, key=lambda o: -o["margin"])
