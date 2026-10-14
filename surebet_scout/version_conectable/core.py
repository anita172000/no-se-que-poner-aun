"""Detector puro de surebets: sin red, sin estado, sin órdenes.

Un evento normalizado tiene esta forma (la producen los feeds):
    {"id", "sport", "league", "home", "away", "date",
     "urls": {casa: url}, "prices": {casa: {"home": 2.1, "draw": 3.4, "away": 3.2}},
     "updated": {casa: iso}}
"""
import itertools
import math
from datetime import datetime, timezone

OUTCOMES = ("home", "draw", "away")
LABELS = {"home": "Local (1)", "draw": "Empate (X)", "away": "Visitante (2)"}


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


def best_legs(event, bookmakers=None, commissions=None, max_age_s=None, now=None):
    """Mejor cuota efectiva por resultado entre las casas permitidas.

    Solo se comparan casas que cotizan TODOS los resultados del mercado, para no
    mezclar un 1X2 con un mercado de dos resultados.
    """
    commissions = commissions or {}
    now = now or datetime.now(timezone.utc)
    allowed = {}
    for bk, prices in event.get("prices", {}).items():
        if bookmakers is not None and bk not in bookmakers:
            continue
        if max_age_s:
            upd = parse_iso(event.get("updated", {}).get(bk))
            if upd and (now - upd).total_seconds() > max_age_s:
                continue
        allowed[bk] = prices
    outcomes = [o for o in OUTCOMES if any(o in p for p in allowed.values())]
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
                    "label": outcome_label(o, event),
                    "bookmaker": bk,
                    "odds": odds,
                    "commission": commissions.get(bk, 0.0),
                    "eff": eff,
                    "url": event.get("urls", {}).get(bk, ""),
                    "updated": event.get("updated", {}).get(bk, ""),
                }
    if len(best) != len(outcomes):
        return None
    return [best[o] for o in outcomes]


def outcome_label(outcome, event):
    if outcome == "home":
        return f"{event.get('home', 'Local')} (1)"
    if outcome == "away":
        return f"{event.get('away', 'Visitante')} (2)"
    return LABELS[outcome]


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


def find_opportunity(event, budget, bookmakers=None, commissions=None, rounding=0.01,
                     max_age_s=None, now=None, exact_bookmakers=()):
    """exact_bookmakers: casas donde se apuesta al céntimo (p. ej. el exchange)."""
    legs = best_legs(event, bookmakers, commissions, max_age_s, now)
    if not legs:
        return None
    for leg in legs:
        leg["step"] = 0.01 if leg["bookmaker"] in exact_bookmakers else rounding
    inv = sum(1 / leg["eff"] for leg in legs)
    if inv >= 1:
        return None
    stakes, pl = plan_stakes(legs, budget, rounding)
    for leg, s in zip(legs, stakes):
        leg["stake"] = s
    return {
        "id": str(event["id"]),
        "event_id": str(event["id"]),
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


def scan(events, budget, min_margin=0.0, **kw):
    opps = [o for o in (find_opportunity(e, budget, **kw) for e in events)
            if o and o["margin"] >= min_margin]
    return sorted(opps, key=lambda o: -o["margin"])
