"""Detector puro de surebets: sin red, sin estado, sin órdenes.

Un evento normalizado (lo producen los feeds) tiene esta forma:
    {"id", "sport", "league", "home", "away", "date", "urls": {casa: url},
     "updated": {casa: iso},
     "markets": {
        clave: {"name": "Totals", "line": 2.5, "label": None,
                "prices": {casa: {"over": 1.9, "under": 1.95}},
                "links": {casa: {"over": url}}, "updated": {casa: iso}},
        ...}}
La clave es única por mercado + jugador/etiqueta + línea. En los mercados con
línea de hándicap, "line" es el hándicap del local (el visitante tiene el contrario).
Por compatibilidad, un evento con solo "prices" se trata como mercado "ML" (1X2).

Solo se comparan conjuntos de resultados que cubren TODAS las posibilidades
(EXHAUSTIVE); si no, una "surebet" podría perder. Además se cruza la doble
oportunidad con el 1X2 del mismo periodo (1X-2, 12-X, X2-1).
"""
import itertools
import math
from datetime import datetime, timezone

OUTCOMES = ("home", "draw", "away")
LABELS = {"home": "Local (1)", "draw": "Empate (X)", "away": "Visitante (2)"}
OUTCOME_ORDER = ("home", "draw", "away", "over", "under", "yes", "no", "odd", "even", "none")
EXHAUSTIVE = (
    frozenset({"home", "draw", "away"}),
    frozenset({"home", "away"}),
    frozenset({"over", "under"}),
    frozenset({"yes", "no"}),
    frozenset({"odd", "even"}),
    frozenset({"home", "away", "none"}),
)
DOUBLE_CHANCE = (("1X", "away"), ("12", "draw"), ("X2", "home"))
MAIN_MARKETS = {"ML", "Totals", "Spread"}

# Traducción de los nombres de mercado más comunes (el resto se muestra tal cual).
_MARKET_ES = [
    ("Both Teams To Score", "Ambos marcan"), ("Draw No Bet", "Empate no válido"),
    ("Double Chance", "Doble oportunidad"), ("European Handicap", "Hándicap europeo"),
    ("Corners Totals", "Córners más/menos"), ("Corners Spread", "Hándicap de córners"),
    ("Bookings Totals", "Tarjetas más/menos"), ("Bookings Spread", "Hándicap de tarjetas"),
    ("Team Total Home", "Total del local"), ("Team Total Away", "Total del visitante"),
    ("Goals Over/Under", "Goles más/menos"), ("First Team To Score", "Primero en marcar"),
    ("Last Team To Score", "Último en marcar"), ("Odd/Even", "Par/impar"),
    ("3-Way Result", "Resultado 1X2"), ("Totals", "Más/menos"), ("Spread", "Hándicap"),
    ("ML", "Ganador"),
]
_PERIOD_ES = [(" HT", " (1ª parte)"), (" 2H", " (2ª parte)"), (" 1Q", " (1er cuarto)"),
              (" 2Q", " (2º cuarto)"), (" 3Q", " (3er cuarto)"), (" 4Q", " (4º cuarto)"),
              (" 1st Set", " (1er set)"), (" 2nd Set", " (2º set)"), (" 3rd Set", " (3er set)"),
              (" 1st Period", " (1er periodo)"), (" 2nd Period", " (2º periodo)"),
              (" 3rd Period", " (3er periodo)"), (" Regulation", " (tiempo reglamentario)")]
_GROUPS = [("Corner", "Córners"), ("Booking", "Tarjetas"), ("Card", "Tarjetas"),
           ("Player", "Jugadores"), ("Goalscorer", "Jugadores"), ("Both Teams", "Ambos marcan"),
           ("Team Total", "Totales de equipo"), ("Total", "Más/menos"), ("Over/Under", "Más/menos"),
           ("Spread", "Hándicap"), ("Handicap", "Hándicap"), ("Double Chance", "Doble oportunidad"),
           ("Odd/Even", "Par/impar"), ("Maps", "Más/menos"),
           ("ML", "Ganador"), ("3-Way", "Ganador"), ("Draw No Bet", "Ganador")]


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


def _fmt(x, signed=False):
    return (f"{x:+g}" if signed else f"{x:g}").replace(".", ",")


def market_name_es(name):
    out = name
    for en, es in _PERIOD_ES:
        if out.endswith(en):
            out = out[: -len(en)]
            suffix = es
            break
    else:
        suffix = ""
    for en, es in _MARKET_ES:
        if out == en or out.startswith(en + " "):
            out = es + out[len(en):]
            break
    return out + suffix


def market_group(name):
    for needle, group in _GROUPS:
        if needle in name:
            return group
    return "Otros"


def market_label(name, line=None, label=None):
    txt = market_name_es(name)
    if label:
        txt = f"{label} · {txt}"
    if line is not None:
        txt += f" {_fmt(line, signed=_is_handicap(name))}"
    return txt


def _is_handicap(name):
    return "Spread" in name or "Handicap" in name


def outcome_label(outcome, event, name="ML", line=None, label=None):
    home, away = event.get("home") or "Local", event.get("away") or "Visitante"
    pre = f"{label} · " if label else ""
    hcp = line is not None and _is_handicap(name)
    if outcome == "home":
        return pre + (f"{home} ({_fmt(line, True)})" if hcp else f"{home} (1)")
    if outcome == "away":
        return pre + (f"{away} ({_fmt(-line, True)})" if hcp else f"{away} (2)")
    if outcome == "draw":
        return pre + (f"Empate ({_fmt(line, True)})" if hcp else "Empate (X)")
    if outcome in ("over", "under"):
        word = "Más" if outcome == "over" else "Menos"
        return pre + (f"{word} de {_fmt(line)}" if line is not None else word)
    simple = {"yes": "Sí", "no": "No", "odd": "Impar", "even": "Par", "none": "Ninguno",
              "1X": f"{home} o empate (1X)", "12": f"{home} o {away} (12)",
              "X2": f"Empate o {away} (X2)"}
    return pre + simple.get(outcome, outcome)


def event_markets(event):
    if event.get("markets"):
        return event["markets"]
    return {"ML": {"name": "ML", "line": None, "prices": event.get("prices", {})}}


def _allowed_prices(event, market, bookmakers, max_age_s, now):
    updated = {**event.get("updated", {}), **market.get("updated", {})}
    out = {}
    for bk, prices in market.get("prices", {}).items():
        if bookmakers is not None and bk not in bookmakers:
            continue
        if max_age_s:
            upd = parse_iso(updated.get(bk))
            if upd and (now - upd).total_seconds() > max_age_s:
                continue
        out[bk] = prices
    return out, updated


def _leg(event, market, bk, outcome, odds, commissions, updated):
    name = market.get("name") or market.get("type") or "ML"
    url = (market.get("links", {}).get(bk, {}) or {}).get(outcome) or event.get("urls", {}).get(bk, "")
    return {
        "outcome": outcome,
        "label": outcome_label(outcome, event, name, market.get("line"), market.get("label")),
        "bookmaker": bk, "odds": odds, "commission": commissions.get(bk, 0.0),
        "eff": effective_odds(odds, commissions.get(bk, 0.0)),
        "url": url, "updated": updated.get(bk, ""),
        # Solo el ganador del partido se empareja con Match Odds de Betfair.
        "can_auto": name == "ML" and outcome in OUTCOMES,
    }


def best_legs(event, bookmakers=None, commissions=None, max_age_s=None, now=None,
              market_key="ML"):
    """Mejor cuota efectiva por resultado de un mercado entre las casas permitidas.

    Solo cuenta casas que cotizan TODOS los resultados del mercado y solo si esos
    resultados cubren todas las posibilidades (EXHAUSTIVE).
    """
    commissions = commissions or {}
    now = now or datetime.now(timezone.utc)
    market = event_markets(event).get(market_key)
    if not market:
        return None
    allowed, updated = _allowed_prices(event, market, bookmakers, max_age_s, now)
    keys = frozenset(o for p in allowed.values() for o in p)
    if keys not in EXHAUSTIVE:
        return None
    outcomes = [o for o in OUTCOME_ORDER if o in keys]
    best = {}
    for bk, prices in allowed.items():
        if not all(prices.get(o, 0) > 1 for o in outcomes):
            continue
        for o in outcomes:
            leg = _leg(event, market, bk, o, prices[o], commissions, updated)
            if o not in best or leg["eff"] > best[o]["eff"]:
                best[o] = leg
    if len(best) != len(outcomes):
        return None
    return [best[o] for o in outcomes]


def _best_single(event, market, outcome, bookmakers, commissions, max_age_s, now):
    allowed, updated = _allowed_prices(event, market, bookmakers, max_age_s, now)
    best = None
    for bk, prices in allowed.items():
        odds = prices.get(outcome, 0)
        if odds > 1:
            leg = _leg(event, market, bk, outcome, odds, commissions, updated)
            if best is None or leg["eff"] > best["eff"]:
                best = leg
    return best


def _double_chance_legs(event, bookmakers, commissions, max_age_s, now):
    """Combos doble oportunidad + 1X2 del mismo periodo: (1X, 2), (12, X), (X2, 1)."""
    markets = event_markets(event)
    out = []
    for key, dc in markets.items():
        name = dc.get("name", "")
        if not name.startswith("Double Chance"):
            continue
        ml = markets.get(name.replace("Double Chance", "ML", 1))
        if not ml:
            continue
        for dc_out, ml_out in DOUBLE_CHANCE:
            a = _best_single(event, dc, dc_out, bookmakers, commissions, max_age_s, now)
            b = _best_single(event, ml, ml_out, bookmakers, commissions, max_age_s, now)
            if a and b:
                out.append((f"{key}~{dc_out}", name, [a, b]))
    return out


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



def _opportunity(event, key, name, line, label, legs, budget, rounding, exact_bookmakers):
    inv = sum(1 / leg["eff"] for leg in legs)
    if inv >= 1:
        return None
    for leg in legs:
        leg["step"] = 0.01 if leg["bookmaker"] in exact_bookmakers else rounding
    stakes, pl = plan_stakes(legs, budget, rounding)
    for leg, s in zip(legs, stakes):
        leg["stake"] = s
    eid = str(event["id"])
    return {
        "id": eid if key == "ML" else f"{eid}|{key}",
        "event_id": eid,
        "market": key,
        "market_type": name,
        "market_label": "Doble oportunidad + 1X2" + ("" if name == "Double Chance" else
                                                     f" ({market_name_es(name)})")
        if "~" in key else market_label(name, line, label),
        "group": "Doble oportunidad" if "~" in key else market_group(name),
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
    }


def find_opportunities(event, budget, bookmakers=None, commissions=None, rounding=0.01,
                       max_age_s=None, now=None, exact_bookmakers=(), markets=None):
    """Todas las surebets de un evento: una por mercado/línea/jugador + combos de
    doble oportunidad.

    exact_bookmakers: casas donde se apuesta al céntimo (p. ej. el exchange).
    markets: nombres de mercado a mirar (p. ej. {"ML", "Totals"}); None = todos.
    """
    now = now or datetime.now(timezone.utc)
    commissions = commissions or {}
    out = []
    for key, market in event_markets(event).items():
        name = market.get("name") or market.get("type") or "ML"
        if markets is not None and name not in markets:
            continue
        legs = best_legs(event, bookmakers, commissions, max_age_s, now, key)
        if legs:
            opp = _opportunity(event, key, name, market.get("line"), market.get("label"),
                               legs, budget, rounding, exact_bookmakers)
            if opp:
                out.append(opp)
    if markets is None or "Double Chance" in markets:
        for key, name, legs in _double_chance_legs(event, bookmakers, commissions, max_age_s, now):
            opp = _opportunity(event, key, name, None, None, legs, budget, rounding,
                               exact_bookmakers)
            if opp:
                out.append(opp)
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
