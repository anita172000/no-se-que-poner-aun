"""Cuotas de Betfair Exchange por su API oficial (gratis con tu cuenta y tu App Key).

Solo LEE precios (listMarketCatalogue + listMarketBook). Apostar lo hace
exchange.BetfairExchange, siempre con tu confirmación.
"""
import re
from datetime import datetime, timedelta, timezone

from betfair import BetfairError, similarity
from core import parse_iso
from scrapers.base import SourceError, market_key, new_market

BOOKMAKER = "Betfair Exchange"
EVENT_TYPES = {"football": "1", "tennis": "2"}
SIMPLE = {"MATCH_ODDS": "ML", "HALF_TIME": "ML HT", "BOTH_TEAMS_TO_SCORE": "Both Teams To Score",
          "DOUBLE_CHANCE": "Double Chance", "DRAW_NO_BET": "Draw No Bet", "ODD_OR_EVEN": "Odd/Even"}
TOTALS = {f"OVER_UNDER_{n}5": n + 0.5 for n in range(0, 7)}
TOTALS_HT = {f"FIRST_HALF_GOALS_{n}5": n + 0.5 for n in range(0, 3)}
TYPES_BY_SPORT = {"football": list(SIMPLE) + list(TOTALS) + list(TOTALS_HT),
                  "tennis": ["MATCH_ODDS"]}
FMT = "%Y-%m-%dT%H:%M:%SZ"


def runner_outcome(market_type, runner, home, away):
    n = (runner or "").strip().lower()
    if market_type in TOTALS or market_type in TOTALS_HT:
        return "over" if n.startswith("over") else "under" if n.startswith("under") else None
    if market_type == "BOTH_TEAMS_TO_SCORE":
        return {"yes": "yes", "no": "no"}.get(n)
    if market_type == "ODD_OR_EVEN":
        return {"odd": "odd", "even": "even"}.get(n)
    if market_type == "DOUBLE_CHANCE":
        return {"home or draw": "1X", "draw or away": "X2", "home or away": "12"}.get(n)
    if n in ("the draw", "draw", "empate"):
        return "draw"
    sh, sa = similarity(home, runner), similarity(away, runner)
    if max(sh, sa) < 0.6:
        return None
    return "home" if sh >= sa else "away"


class BetfairOddsSource:
    def __init__(self, client):
        self.client = client

    def bookmakers(self):
        return [BOOKMAKER]

    def fetch(self, sports, bookmakers, hours_ahead, max_events):
        if bookmakers and BOOKMAKER not in bookmakers:
            return [], []
        now = datetime.now(timezone.utc)
        wanted = [s for s in EVENT_TYPES if "*" in sports or s in sports]
        out, errors = [], []
        for sport in wanted:
            try:
                cat = self.client._rpc("betting_url", "SportsAPING/v1.0/listMarketCatalogue", {
                    "filter": {"eventTypeIds": [EVENT_TYPES[sport]],
                               "marketTypeCodes": TYPES_BY_SPORT[sport], "inPlayOnly": False,
                               "marketStartTime": {"from": now.strftime(FMT),
                                                   "to": (now + timedelta(hours=hours_ahead)).strftime(FMT)}},
                    "marketProjection": ["EVENT", "RUNNER_DESCRIPTION", "MARKET_START_TIME",
                                         "MARKET_DESCRIPTION"],
                    "sort": "FIRST_TO_START", "maxResults": 1000}) or []
            except BetfairError as exc:
                errors.append(f"Betfair: {exc}")
                break
            events = {}
            for m in cat:
                ev = m.get("event") or {}
                if " v " not in ev.get("name", ""):
                    continue
                events.setdefault(ev["id"], {"event": ev, "markets": []})["markets"].append(m)
            chosen = sorted(events.values(), key=lambda e: e["event"].get("openDate", ""))[:max_events]
            ids = [m["marketId"] for e in chosen for m in e["markets"]]
            books = {}
            try:
                for i in range(0, len(ids), 40):
                    for b in self.client._rpc("betting_url", "SportsAPING/v1.0/listMarketBook", {
                            "marketIds": ids[i:i + 40],
                            "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}}) or []:
                        books[b["marketId"]] = b
            except BetfairError as exc:
                errors.append(f"Betfair: {exc}")
            for e in chosen:
                ev = e["event"]
                home, away = ev["name"].split(" v ", 1)
                markets = {}
                for m in e["markets"]:
                    book = books.get(m["marketId"])
                    if not book or book.get("status") != "OPEN" or book.get("inplay"):
                        continue
                    mtype = (m.get("description") or {}).get("marketType", "")
                    name = SIMPLE.get(mtype) or ("Totals" if mtype in TOTALS else
                                                 "Totals HT" if mtype in TOTALS_HT else None)
                    if not name:
                        continue
                    line = TOTALS.get(mtype, TOTALS_HT.get(mtype))
                    names = {r["selectionId"]: r.get("runnerName", "") for r in m.get("runners", [])}
                    prices = {}
                    for r in book.get("runners", []):
                        backs = (r.get("ex") or {}).get("availableToBack") or []
                        kind = runner_outcome(mtype, names.get(r["selectionId"]), home, away)
                        if kind and backs and r.get("status", "ACTIVE") == "ACTIVE":
                            prices[kind] = float(backs[0]["price"])
                    if len(prices) < 2:
                        continue
                    mk = new_market(markets, market_key(name, line), name, line)
                    mk["prices"][BOOKMAKER] = prices
                    mk["links"][BOOKMAKER] = {k: f"https://www.betfair.es/exchange/plus/market/{m['marketId']}"
                                              for k in prices}
                if markets:
                    out.append({"id": f"bf-{ev['id']}", "sport": sport, "league": "",
                                "home": home.strip(), "away": away.strip(),
                                "date": ev.get("openDate", ""), "urls": {BOOKMAKER: ""},
                                "markets": markets,
                                "updated": {BOOKMAKER: now.strftime(FMT)}})
        return out, errors
