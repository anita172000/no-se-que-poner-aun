"""Lector de Betway ES.

Usa los mismos datos que carga su web: la página de calendario de cada deporte
(lista de partidos), la página de cada partido (números de sus mercados) y la
petición de cuotas de esos mercados. Solo lee; nunca inicia sesión ni apuesta.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

from scrapers.base import DEFAULT_SPORTS, PoliteClient, SourceError, market_key, new_market

BOOKMAKER = "Betway ES"
SITE = "https://betway.es/es/es/sports"
API = "https://betway.es/es/api/sports/content/getEventMarkets"
SPORTS = {"football": "soccer"}  # el resto se llama igual que en DEFAULT_SPORTS
CNAME_TO_SPORT = {"soccer": "football"}
# En estos deportes el 1X2 es a tiempo reglamentario (sin prórroga).
REGULATION_3WAY = {"ice-hockey", "basketball", "american-football", "baseball"}
TEAM = {"1": "home", "--home-team-": "home", "x": "draw", "draw": "draw", "2": "away",
        "--away-team-": "away", "over": "over", "under": "under", "yes": "yes", "no": "no",
        "odd": "odd", "even": "even", "1x": "1X", "12": "12", "2x": "X2"}
HT_PREFIX = "1st-half-----"
EXACT = {
    "total-goals": "Totals", "total-points": "Totals", "point-spread": "Spread",
    "total-games": "Totals (Games)", "game---handicap": "Spread (Games)",
    "both-teams-to-score": "Both Teams To Score", "double-chance": "Double Chance",
    "draw-no-bet": "Draw No Bet", "total-goals---odd-even": "Odd/Even",
    "total-goals-odd-even": "Odd/Even", "total-corners": "Corners Totals",
    "handicap---3-way": "European Handicap",
    "{h}---total-goals": "Team Total Home", "{a}---total-goals": "Team Total Away",
}
# Tipo de mercado que debe acompañar a cada nombre (doble comprobación).
TYPES = {"Totals": "over", "Totals (Games)": "over", "Corners Totals": "over",
         "Team Total Home": "over", "Team Total Away": "over"}


def canonical_market(cname, type_cname, home_slug, away_slug, sport):
    """Nombre común (estilo odds-api.io) o None si no se reconoce con exactitud."""
    s = cname.strip("-")
    period = ""
    if s.startswith(HT_PREFIX):
        s, period = s[len(HT_PREFIX):], " HT"
    s = re.sub(r"---?-?\d+(-\d+)?$", "", s).strip("-")  # quita la línea del final (---2-5)
    # Sustituye el equipo solo como segmento completo ("real-betis---total-goals").
    for slug, token in ((home_slug, "{h}"), (away_slug, "{a}")):
        if slug:
            s = re.sub(rf"(^|---){re.escape(slug)}(?=---|$)", lambda m: m.group(1) + token, s)
    if s in ("win-draw-win", "match-winner", "money-line") or \
            (s == "money-line-3-way---excluding-ot"):
        three_way = s in ("win-draw-win", "money-line-3-way---excluding-ot")
        if three_way and sport in REGULATION_3WAY:
            return "ML Regulation" + period
        if s == "money-line-3-way---excluding-ot":
            return None
        return "ML" + period
    name = EXACT.get(s)
    if not name:
        return None
    if TYPES.get(name) == "over" and "over" not in type_cname:
        return None
    return name + period


def parse_markets(data, sport_hint=None, now=None):
    """Respuesta de getEventMarkets -> eventos normalizados (uno por partido)."""
    now = now or datetime.now(timezone.utc)
    events = {e["Id"]: e for e in data.get("Events", [])}
    outs = {o["Id"]: o for o in data.get("Outcomes", [])}
    result = {}
    for m in data.get("Markets", []):
        ev = events.get(m.get("EventId"))
        if not ev or m.get("IsSuspended") or ev.get("IsLive") or ev.get("IsOutright"):
            continue
        sport = CNAME_TO_SPORT.get(ev.get("CategoryCName"), ev.get("CategoryCName") or sport_hint)
        name = canonical_market(m.get("MarketCName", ""), m.get("TypeCName", ""),
                                ev.get("HomeTeamCName"), ev.get("AwayTeamCName"), sport)
        if not name:
            continue
        prices, home_line, ok = {}, None, True
        for row in m.get("Outcomes", []):
            for oid in row:
                o = outs.get(oid)
                kind = TEAM.get((o or {}).get("TeamCName"))
                if not o or not kind or not o.get("IsActive") or not o.get("IsDisplay") \
                        or not o.get("OddsDecimal") or kind in prices:
                    ok = False
                    break
                prices[kind] = float(o["OddsDecimal"])
                if kind == "home" and o.get("Handicap") is not None:
                    home_line = float(o["Handicap"])
        if not ok or len(prices) < 2:
            continue
        if "Spread" in name:
            line = home_line
        elif name.startswith(("Totals", "Corners Totals", "Team Total", "European Handicap")):
            line = float(m.get("Handicap") or 0)
        else:
            line = None
        if ("Spread" in name or "Totals" in name or "Team Total" in name) and line is None:
            continue
        start = datetime.fromtimestamp(ev["Milliseconds"] / 1000, timezone.utc)
        out = result.setdefault(ev["Id"], {
            "id": f"betway-{ev['Id']}", "sport": sport,
            "league": " - ".join(x for x in (ev.get("SubCategoryName"), ev.get("GroupName")) if x),
            "home": ev.get("HomeTeamName", ""), "away": ev.get("AwayTeamName", ""),
            "date": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "urls": {BOOKMAKER: f"{SITE}/event/{ev['Id']}"}, "markets": {},
            "updated": {BOOKMAKER: now.strftime("%Y-%m-%dT%H:%M:%SZ")}})
        mk = new_market(out["markets"], market_key(name, line), name, line)
        mk["prices"][BOOKMAKER] = prices
    return list(result.values())


class BetwaySource:
    def __init__(self, client=None):
        self.client = client or PoliteClient(min_interval=0.5)

    def bookmakers(self):
        return [BOOKMAKER]

    def _market_ids(self, html):
        ids = {int(x) for arr in re.findall(r'MarketIds\\?":\[([0-9,]*)\]', html)
               for x in arr.split(",") if x}
        ids |= {int(x) for x in re.findall(r'data-marketid="(\d+)"', html)}
        return sorted(ids)

    def _get_markets(self, ids):
        body = {"BrandId": 3, "LanguageId": 11, "TerritoryId": 200, "TerritoryCode": "ES",
                "ClientTypeId": 2, "JurisdictionId": 5, "ClientIntegratorId": 1,
                "CorrelationId": str(uuid.uuid4()), "MarketIds": ids}
        return self.client.post_json(API, body)

    def list(self, sports, bookmakers, hours_ahead):
        """Calendario de cada deporte + cuotas de su mercado principal (pocas peticiones)."""
        if bookmakers and BOOKMAKER not in bookmakers:
            return [], []
        now = datetime.now(timezone.utc)
        until = now + timedelta(hours=hours_ahead)
        sports = DEFAULT_SPORTS if "*" in sports else sports
        out, errors = [], []
        for sport in sports:
            try:
                html = self.client.get_text(f"{SITE}/cat/{SPORTS.get(sport, sport)}/calendar")
                ids = sorted({int(x) for x in re.findall(r'data-marketid="(\d+)"', html)})
                evs = []
                for i in range(0, len(ids), 100):
                    evs += parse_markets(self._get_markets(ids[i:i + 100]), sport, now)
            except SourceError as exc:
                if "404" in str(exc):
                    continue
                errors.append(f"{BOOKMAKER}: {exc}")
                break
            for ev in evs:
                start = datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
                if now < start <= until:
                    ev["refs"] = {"betway": [ev["id"].split("-", 1)[1]]}
                    out.append(ev)
        return out, errors

    @staticmethod
    def detail_refs(event):
        return [(eid, event.get("sport")) for eid in (event.get("refs") or {}).get("betway", [])]

    def details(self, refs):
        out, errors = [], []
        now = datetime.now(timezone.utc)
        for eid, sport in refs:
            try:
                ids = self._market_ids(self.client.get_text(f"{SITE}/event/{eid}"))
                if ids:
                    out += parse_markets(self._get_markets(ids[:400]), sport, now)
            except SourceError as exc:
                if "404" in str(exc):
                    continue  # el partido ya no está (empezó o lo retiraron)
                errors.append(f"{BOOKMAKER}: {exc}")
                break
        return out, errors

    def fetch(self, sports, bookmakers, hours_ahead, max_events):
        """Compatibilidad: lista + detalles de los primeros partidos."""
        listed, errors = self.list(sports, bookmakers, hours_ahead)
        listed.sort(key=lambda e: e["date"])
        evs, err2 = self.details([(e["refs"]["betway"][0], e["sport"]) for e in listed[:max_events]])
        return evs, errors + err2
