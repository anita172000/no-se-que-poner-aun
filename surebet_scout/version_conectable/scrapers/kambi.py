"""Lector de casas con plataforma Kambi (PAF ES, LeoVegas ES...).

Usa los mismos datos JSON públicos que cargan sus webs. Primero la lista de
partidos por deporte y después todos los mercados de cada partido.
"""
import re
from datetime import datetime, timedelta, timezone

from core import parse_iso
from scrapers.base import DEFAULT_SPORTS, PoliteClient, SourceError, market_key, new_market

BASE = "https://eu-offering-api.kambicdn.com/offering/v2018"
# Nombre de la casa (como en Ajustes) -> código de marca en Kambi.
BRANDS = {"PAF ES": "pafes", "LeoVegas ES": "leoes"}

OUTCOME_TYPES = {
    "OT_ONE": "home", "OT_CROSS": "draw", "OT_TWO": "away", "OT_OVER": "over",
    "OT_UNDER": "under", "OT_YES": "yes", "OT_NO": "no", "OT_ODD": "odd", "OT_EVEN": "even",
    "OT_ONE_OR_CROSS": "1X", "OT_ONE_OR_TWO": "12", "OT_CROSS_OR_TWO": "X2",
}
ML_LABELS = {"Full Time", "Match Odds", "Moneyline", "Moneyline - Including Overtime", "Match"}
PERIODS = [(r"\s*-\s*Regular Time$", " Regulation"), (r"\s*-\s*1st Half$", " HT"), (r"\s*-\s*2nd Half$", " 2H"),
           (r"\s*-\s*1st Quarter$", " 1Q"), (r"\s*-\s*1st Set$", " 1st Set"),
           (r"\s*-\s*1st Period$", " 1st Period")]


def _sport_path(slug):
    return slug.replace("-", "_")


# Nombre exacto de Kambi (sin periodo) y tipo -> mercado común. Solo estos se
# comparan con otras plataformas; el resto queda como "Kambi: ..." (solo entre Kambi).
EXACT = {
    ("Total Goals", "Over/Under"): "Totals",
    ("Total Goals", "Asian Over/Under"): "Totals",
    ("Asian Total", "Asian Over/Under"): "Totals",
    ("Total Points", "Over/Under"): "Totals",
    ("Total Points - Including Overtime", "Over/Under"): "Totals",
    ("Total Games", "Over/Under"): "Totals (Games)",
    ("Total Corners", "Over/Under"): "Corners Totals",
    ("Asian Total Corners", "Asian Over/Under"): "Corners Totals",
    ("Handicap", "Handicap"): "Spread",
    ("Asian Handicap", "Asian Handicap"): "Spread",
    ("Handicap - Including Overtime", "Handicap"): "Spread",
    ("Game Handicap", "Handicap"): "Spread (Games)",
    ("3-Way Handicap", "3-Way Handicap"): "European Handicap",
    ("Both Teams To Score", "Yes/No"): "Both Teams To Score",
    ("Total Goals Odd/Even", "Odd/Even"): "Odd/Even",
    ("Double Chance", "Double Chance"): "Double Chance",
}


def canonical_market(label, offer_type, home, away, outcomes):
    """Traduce el criterio de Kambi al nombre de mercado común (estilo odds-api.io).

    Lo que no se reconoce con exactitud queda con un nombre propio de Kambi: solo se
    compara entre casas Kambi y nunca se mezcla con mercados de otras plataformas.
    """
    period = ""
    for pat, suffix in PERIODS:
        if re.search(pat, label):
            label, period = re.sub(pat, "", label), suffix
            break
    t, kinds = offer_type, set(outcomes)
    # "Match" agrupa mercados muy distintos (ganador, empate no válido, primer gol...):
    # solo se aceptan por su nombre exacto para no mezclarlos nunca.
    if t == "Match":
        if label in ML_LABELS:
            return "ML" + period
        if label == "Half Time" and not period:
            return "ML HT"
        if label == "Draw No Bet" and kinds == {"home", "away"}:
            return "Draw No Bet" + period
    elif (label, t) in EXACT:
        return EXACT[(label, t)] + period
    elif t == "Over/Under":
        for prefix in ("Total Goals by ", "Total Points by "):
            if label.startswith(prefix):
                who = label[len(prefix):].replace(" - Including Overtime", "")
                side = "Home" if who == home else "Away" if who == away else None
                if side:
                    return f"Team Total {side}{period}"
    generic = label.replace(home, "{local}").replace(away, "{visitante}") if home and away else label
    return f"Kambi: {generic}{period} [{t}]"


def parse_event(data, ev, bookmaker):
    """betoffer/event -> mercados normalizados de una casa."""
    home, away = ev.get("homeName", ""), ev.get("awayName", "")
    markets = {}
    for bo in data.get("betOffers", []):
        if "OFFERED_PREMATCH" not in bo.get("tags", ["OFFERED_PREMATCH"]):
            continue
        crit = bo.get("criterion", {})
        label = crit.get("englishLabel") or crit.get("label") or ""
        otype = (bo.get("betOfferType") or {}).get("englishName", "")
        outs = {}
        line = None
        player = None
        ok = True
        for o in bo.get("outcomes", []):
            kind = OUTCOME_TYPES.get(o.get("type"))
            if not kind or o.get("status") != "OPEN" or not o.get("odds"):
                ok = False
                break
            outs[kind] = round(o["odds"] / 1000, 3)
            if o.get("line") is not None and kind in ("home", "over"):
                line = o["line"] / 1000
            elif o.get("line") is not None and line is None and kind in ("away", "under"):
                line = -o["line"] / 1000 if kind == "away" else o["line"] / 1000
        if not ok or len(outs) < 2:
            continue
        name = canonical_market(label, otype, home, away, outs)
        if not name:
            continue
        if name.startswith("Kambi:") and "Player" in otype:
            player = label
        key = market_key(name, line, player)
        mk = new_market(markets, key, name, line, player)
        mk["prices"][bookmaker] = outs
    return markets


class KambiSource:
    def __init__(self, brands=None, client=None):
        self.brands = brands or BRANDS
        self.client = client or PoliteClient(min_interval=0.4)

    def bookmakers(self):
        return list(self.brands)

    def fetch(self, sports, bookmakers, hours_ahead, max_events):
        now = datetime.now(timezone.utc)
        until = now + timedelta(hours=hours_ahead)
        sports = DEFAULT_SPORTS if "*" in sports else sports
        out, errors = [], []
        for bk, brand in self.brands.items():
            if bookmakers and bk not in bookmakers:
                continue
            listed = []
            for sport in sports:
                try:
                    d = self.client.get_json(f"{BASE}/{brand}/listView/{_sport_path(sport)}.json",
                                             {"lang": "es_ES", "market": "ES"})
                except SourceError as exc:
                    if "400" in str(exc) or "404" in str(exc):
                        continue  # ese deporte no existe en la marca
                    errors.append(f"{bk}: {exc}")
                    break
                for item in d.get("events", []):
                    ev = item.get("event", {})
                    start = parse_iso(ev.get("start"))
                    if ev.get("state") != "NOT_STARTED" or not start or not now < start <= until:
                        continue
                    if not ev.get("homeName") or not ev.get("awayName"):
                        continue  # torneos/apuestas a largo plazo
                    listed.append((start, sport, ev))
            listed.sort(key=lambda x: x[0])
            for start, sport, ev in listed[:max_events]:
                try:
                    data = self.client.get_json(f"{BASE}/{brand}/betoffer/event/{ev['id']}.json",
                                                {"lang": "es_ES", "market": "ES"})
                except SourceError as exc:
                    errors.append(f"{bk}: {exc}")
                    break
                out.append({
                    "id": f"kambi-{ev['id']}", "sport": sport,
                    "league": " - ".join(p.get("name", "") for p in ev.get("path", [])[1:]),
                    "home": ev["homeName"], "away": ev["awayName"], "date": ev["start"],
                    "urls": {bk: ""}, "markets": parse_event(data, ev, bk),
                    "updated": {bk: now.strftime("%Y-%m-%dT%H:%M:%SZ")},
                })
        return out, errors
