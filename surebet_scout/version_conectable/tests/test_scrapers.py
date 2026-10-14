import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import scan  # noqa: E402
from scrapers.base import PoliteClient, SourceError  # noqa: E402
from scrapers.betfair_odds import BetfairOddsSource, runner_outcome  # noqa: E402
from scrapers.feed import WebsFeed  # noqa: E402
from scrapers.kambi import KambiSource, canonical_market, parse_event  # noqa: E402
from scrapers.merge import merge_events, same_event  # noqa: E402

START = (datetime.now(timezone.utc) + timedelta(hours=5)).replace(microsecond=0)
ISO = START.strftime("%Y-%m-%dT%H:%M:%SZ")


def bo(label, otype, outcomes, tags=("OFFERED_PREMATCH",)):
    return {"criterion": {"englishLabel": label}, "betOfferType": {"englishName": otype},
            "tags": list(tags), "outcomes": [
                {"type": t, "odds": int(o * 1000), "status": "OPEN", **({"line": l} if l is not None else {})}
                for t, o, l in outcomes]}


KAMBI_EVENT = {"id": 1, "homeName": "Real Betis", "awayName": "Villarreal CF", "start": ISO,
               "state": "NOT_STARTED", "path": [{"name": "Fútbol"}, {"name": "España"}, {"name": "LaLiga"}]}
KAMBI_OFFERS = {"betOffers": [
    bo("Full Time", "Match", [("OT_ONE", 2.6, None), ("OT_CROSS", 3.3, None), ("OT_TWO", 2.8, None)]),
    bo("Draw No Bet", "Match", [("OT_ONE", 1.9, None), ("OT_TWO", 2.0, None)]),
    bo("First Goal (Draw: No Goals)", "Match", [("OT_ONE", 1.9, None), ("OT_CROSS", 9.0, None), ("OT_TWO", 2.1, None)]),
    bo("Total Goals", "Over/Under", [("OT_OVER", 2.2, 2500), ("OT_UNDER", 1.7, 2500)]),
    bo("Total Shots", "Over/Under", [("OT_OVER", 1.9, 20500), ("OT_UNDER", 1.9, 20500)]),
    bo("Total Goals - 1st Half", "Over/Under", [("OT_OVER", 1.5, 500), ("OT_UNDER", 2.5, 500)]),
    bo("Total Goals by Real Betis", "Over/Under", [("OT_OVER", 2.0, 1500), ("OT_UNDER", 1.8, 1500)]),
    bo("Handicap", "Handicap", [("OT_ONE", 2.7, -1500), ("OT_TWO", 1.4, 1500)]),
    bo("Both Teams To Score", "Yes/No", [("OT_YES", 1.7, None), ("OT_NO", 2.1, None)]),
    bo("Correct Score", "Correct Score", [("OT_UNTYPED", 7.0, None), ("OT_UNTYPED", 9.0, None)]),
]}


def test_kambi_market_mapping_is_strict():
    m = parse_event(KAMBI_OFFERS, KAMBI_EVENT, "PAF ES")
    assert m["ML"]["prices"]["PAF ES"] == {"home": 2.6, "draw": 3.3, "away": 2.8}
    assert m["Draw No Bet"]["prices"]["PAF ES"] == {"home": 1.9, "away": 2.0}
    assert m["Totals:2.5"]["prices"]["PAF ES"] == {"over": 2.2, "under": 1.7}
    assert m["Totals HT:0.5"]["name"] == "Totals HT"
    assert m["Team Total Home:1.5"]["name"] == "Team Total Home"
    assert m["Spread:-1.5"]["prices"]["PAF ES"] == {"home": 2.7, "away": 1.4}
    assert "Both Teams To Score" in m
    # Primer gol y tiros NO se confunden con ganador ni con goles
    assert not any(k.startswith("Totals:20.5") for k in m)
    assert any("First Goal" in k for k in m) and any("Total Shots" in k for k in m)
    assert all(k.startswith("Kambi:") for k in m if "First Goal" in k or "Total Shots" in k)
    # Resultado exacto se descarta
    assert not any("Correct Score" in k for k in m)


def test_kambi_regular_time_is_not_mixed_with_overtime():
    assert canonical_market("Match Odds - Regular Time", "Match", "A", "B", ["home", "draw", "away"]) == "ML Regulation"
    assert canonical_market("Moneyline - Including Overtime", "Match", "A", "B", ["home", "away"]) == "ML"


def test_kambi_source_reads_list_and_events():
    def handler(req):
        if "listView/football" in req.url.path:
            return httpx.Response(200, json={"events": [{"event": KAMBI_EVENT},
                                                        {"event": {**KAMBI_EVENT, "id": 2, "state": "STARTED"}}]})
        if "listView" in req.url.path:
            return httpx.Response(404)
        if "betoffer/event/1" in req.url.path:
            return httpx.Response(200, json=KAMBI_OFFERS)
        return httpx.Response(500)
    client = PoliteClient(min_interval=0, http=httpx.Client(transport=httpx.MockTransport(handler)),
                          sleep=lambda s: None)
    src = KambiSource({"PAF ES": "pafes"}, client)
    evs, errors = src.fetch(["football", "tennis"], None, 48, 10)
    assert errors == [] and len(evs) == 1 and evs[0]["home"] == "Real Betis"
    assert evs[0]["league"] == "España - LaLiga"


def test_polite_client_retries_429_and_reports_geoblock():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(429) if len(calls) < 3 else httpx.Response(200, json={"ok": 1})
    c = PoliteClient(min_interval=0, http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    assert c.get_json("https://x/y") == {"ok": 1} and len(calls) == 3
    blocked = PoliteClient(min_interval=0, sleep=lambda s: None,
                           http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(451))))
    with pytest.raises(SourceError, match="España"):
        blocked.get_json("https://x/y")


def test_merge_joins_same_match_with_different_names_only():
    kambi = {"id": "k", "sport": "football", "home": "Real Betis", "away": "Villarreal CF", "date": ISO,
             "urls": {}, "updated": {}, "markets": {"Totals:2.5": {"name": "Totals", "line": 2.5,
                                                                  "prices": {"PAF ES": {"over": 2.2, "under": 1.7}}}}}
    bf = {"id": "b", "sport": "football", "home": "Betis", "away": "Villarreal",
          "date": (START + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"), "urls": {}, "updated": {},
          "markets": {"Totals:2.5": {"name": "Totals", "line": 2.5,
                                     "prices": {"Betfair Exchange": {"over": 1.8, "under": 2.3}}}}}
    swapped = {**bf, "home": "Villarreal", "away": "Betis"}
    later = {**bf, "date": (START + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    other = {**bf, "home": "Sevilla", "away": "Valencia"}
    assert same_event(kambi, bf)
    assert not same_event(kambi, swapped) and not same_event(kambi, later) and not same_event(kambi, other)
    merged = merge_events([[kambi], [bf, other]])
    assert len(merged) == 2
    prices = merged[0]["markets"]["Totals:2.5"]["prices"]
    assert set(prices) == {"PAF ES", "Betfair Exchange"}
    # Más 2.2 en PAF y menos 2.3 en Betfair: surebet entre plataformas
    opps = scan(merged, 100)
    assert opps and {l["bookmaker"] for l in opps[0]["legs"]} == {"PAF ES", "Betfair Exchange"}


class FakeBfClient:
    def _rpc(self, which, method, params):
        if method.endswith("listMarketCatalogue"):
            if params["filter"]["eventTypeIds"] != ["1"]:
                return []
            ev = {"id": "9", "name": "Betis v Villarreal", "openDate": ISO}
            return [
                {"marketId": "1.1", "event": ev, "description": {"marketType": "MATCH_ODDS"},
                 "runners": [{"selectionId": 1, "runnerName": "Betis"}, {"selectionId": 2, "runnerName": "Villarreal"},
                             {"selectionId": 3, "runnerName": "The Draw"}]},
                {"marketId": "1.2", "event": ev, "description": {"marketType": "OVER_UNDER_25"},
                 "runners": [{"selectionId": 4, "runnerName": "Under 2.5 Goals"},
                             {"selectionId": 5, "runnerName": "Over 2.5 Goals"}]}]
        if method.endswith("listMarketBook"):
            def r(sid, p):
                return {"selectionId": sid, "status": "ACTIVE", "ex": {"availableToBack": [{"price": p, "size": 50}]}}
            return [{"marketId": "1.1", "status": "OPEN", "inplay": False, "runners": [r(1, 2.7), r(2, 2.9), r(3, 3.4)]},
                    {"marketId": "1.2", "status": "OPEN", "inplay": False, "runners": [r(4, 2.3), r(5, 1.75)]}]


def test_betfair_odds_source_maps_markets():
    evs, errors = BetfairOddsSource(FakeBfClient()).fetch(["*"], None, 48, 10)
    assert errors == [] and len(evs) == 1
    m = evs[0]["markets"]
    assert m["ML"]["prices"]["Betfair Exchange"] == {"home": 2.7, "away": 2.9, "draw": 3.4}
    assert m["Totals:2.5"]["prices"]["Betfair Exchange"] == {"under": 2.3, "over": 1.75}
    assert runner_outcome("DOUBLE_CHANCE", "Home or Draw", "A", "B") == "1X"


def test_webs_feed_merges_sources_and_keeps_partial_errors():
    class Ok:
        def bookmakers(self): return ["PAF ES"]
        def fetch(self, *a): return ([{"id": "k", "sport": "football", "home": "Betis", "away": "Sevilla",
                                       "date": ISO, "urls": {}, "updated": {}, "markets": {}}], [])

    class Broken:
        def bookmakers(self): return ["X"]
        def fetch(self, *a): return ([], ["X: acceso bloqueado"])
    feed = WebsFeed([("Kambi", Ok()), ("X", Broken())])
    assert len(feed.fetch(["*"], None, 48, 10)) == 1
    assert feed.warnings == ["X: acceso bloqueado"] and feed.status()["sources"]["X"]["errors"]


# --- Betway ---------------------------------------------------------------------
from scrapers.betway import BetwaySource, canonical_market as bw_canonical, parse_markets  # noqa: E402

MS = int(START.timestamp() * 1000)


def bw_payload():
    ev = {"Id": 7, "CategoryCName": "soccer", "HomeTeamName": "Real Betis", "AwayTeamName": "Villarreal",
          "HomeTeamCName": "real-betis", "AwayTeamCName": "villarreal", "Milliseconds": MS,
          "GroupName": "LaLiga", "SubCategoryName": "España", "IsLive": False, "IsOutright": False}

    def mk(mid, cname, ttype, outs, h=0.0):
        return {"Id": mid, "EventId": 7, "MarketCName": cname, "TypeCName": ttype, "Handicap": h,
                "IsSuspended": False, "Outcomes": [[mid * 10 + i for i in range(len(outs))]]}

    def oc(mid, outs):
        return [{"Id": mid * 10 + i, "TeamCName": t, "OddsDecimal": o, "IsActive": True, "IsDisplay": True,
                 "Handicap": hh} for i, (t, o, hh) in enumerate(outs)]
    spec = [
        (1, "win-draw-win", "win-draw-win", [("1", 2.6, None), ("x", 3.3, None), ("2", 2.8, None)], 0.0),
        (2, "win-draw-win-1up", "win-draw-win", [("--home-team-", 2.4, None), ("draw", 3.6, None), ("--away-team-", 2.6, None)], 0.0),
        (3, "-total-goals---2-5", "handicap-goals-over", [("over", 1.9, 2.5), ("under", 1.9, 2.5)], 2.5),
        (4, "-real-betis---total-goals---1-5", "handicap-goals-over", [("over", 2.1, 1.5), ("under", 1.7, 1.5)], 1.5),
        (5, "-1st-half-----total-goals---0-5", "handicap-goals-over", [("over", 1.4, 0.5), ("under", 2.8, 0.5)], 0.5),
        (6, "both-teams-to-score", "both-teams-to-score", [("yes", 1.7, None), ("no", 2.1, None)], 0.0),
        (7, "either-team-to-score", "both-teams-to-score", [("yes", 1.1, None), ("no", 8.0, None)], 0.0),
        (8, "correct-score", "correct-score", [("1-0", 7.0, None), ("0-0", 9.0, None)], 0.0),
        (9, "double-chance", "double-chance", [("1x", 1.5, None), ("12", 1.3, None), ("2x", 1.6, None)], 0.0),
        (10, "-handicap---3-way", "handicap-wdw", [("--home-team-", 6.0, -2.0), ("draw", 4.5, 2.0), ("--away-team-", 1.4, 2.0)], -2.0),
    ]
    markets = [mk(mid, c, t, o, h) for mid, c, t, o, h in spec]
    outcomes = [x for mid, c, t, o, h in spec for x in oc(mid, o)]
    return {"Events": [ev], "Markets": markets, "Outcomes": outcomes}


def test_betway_mapping_is_strict():
    evs = parse_markets(bw_payload(), "football")
    assert len(evs) == 1
    m = evs[0]["markets"]
    assert m["ML"]["prices"]["Betway ES"] == {"home": 2.6, "draw": 3.3, "away": 2.8}
    assert set(m) == {"ML", "Totals:2.5", "Team Total Home:1.5", "Totals HT:0.5", "Both Teams To Score",
                      "Double Chance", "European Handicap:-2"}
    assert m["Double Chance"]["prices"]["Betway ES"] == {"1X": 1.5, "12": 1.3, "X2": 1.6}
    # el 1X2 "con 1 gol de ventaja" o "cualquier equipo marca" nunca se confunden
    assert bw_canonical("win-draw-win-1up", "win-draw-win", "a", "b", "football") is None
    assert bw_canonical("either-team-to-score", "both-teams-to-score", "a", "b", "football") is None
    assert bw_canonical("win-draw-win", "win-draw-win", "a", "b", "ice-hockey") == "ML Regulation"
    assert bw_canonical("money-line", "to-win", "a", "b", "basketball") == "ML"


def test_betway_source_lists_and_details():
    calendar = '<div data-eventid="7"><div data-marketid="1"></div></div>'
    event_page = r'... MarketIds\":[1,3,6] ...'

    def handler(req):
        if req.url.path.endswith("/cat/soccer/calendar"):
            return httpx.Response(200, text=calendar)
        if "/calendar" in req.url.path:
            return httpx.Response(404)
        if req.url.path.endswith("/event/7"):
            return httpx.Response(200, text=event_page)
        if req.url.path.endswith("getEventMarkets"):
            import json as _j
            wanted = set(_j.loads(req.content)["MarketIds"])
            p = bw_payload()
            p["Markets"] = [x for x in p["Markets"] if x["Id"] in wanted]
            return httpx.Response(200, json=p)
        return httpx.Response(500)
    client = PoliteClient(min_interval=0, http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    src = BetwaySource(client)
    listed, errors = src.list(["football", "tennis"], None, 48)
    assert errors == [] and len(listed) == 1 and set(listed[0]["markets"]) == {"ML"}
    assert listed[0]["refs"] == {"betway": ["7"]}
    full, errors = src.details(src.detail_refs(listed[0]))
    assert errors == [] and {"ML", "Totals:2.5", "Both Teams To Score"} <= set(full[0]["markets"])


def test_webs_feed_only_details_matches_seen_in_two_platforms():
    calls = {"kambi": [], "betway": []}

    def ev(eid, home, away, refs, bk):
        return {"id": eid, "sport": "football", "home": home, "away": away, "date": ISO, "urls": {},
                "updated": {}, "refs": refs, "markets": {"ML": {"name": "ML", "line": None, "prices": {
                    bk: {"home": 2.0, "draw": 3.0, "away": 4.0}}}}}

    class K:
        def bookmakers(self): return ["PAF ES"]
        def list(self, *a): return ([ev("k1", "Real Betis", "Villarreal CF", {"kambi": ["1"]}, "PAF ES"),
                                     ev("k2", "Getafe", "Osasuna", {"kambi": ["2"]}, "PAF ES")], [])
        def detail_refs(self, e): return e["refs"].get("kambi", [])
        def details(self, refs):
            calls["kambi"] += refs
            return ([{**ev("k1", "Real Betis", "Villarreal CF", {}, "PAF ES"), "markets": {"Totals:2.5": {
                "name": "Totals", "line": 2.5, "prices": {"PAF ES": {"over": 2.2, "under": 1.7}}}}}], [])

    class B:
        def bookmakers(self): return ["Betway ES"]
        def list(self, *a): return ([ev("b1", "Betis", "Villarreal", {"betway": ["7"]}, "Betway ES")], [])
        def detail_refs(self, e): return e["refs"].get("betway", [])
        def details(self, refs):
            calls["betway"] += refs
            return ([{**ev("b1", "Betis", "Villarreal", {}, "Betway ES"), "markets": {"Totals:2.5": {
                "name": "Totals", "line": 2.5, "prices": {"Betway ES": {"over": 1.8, "under": 2.3}}}}}], [])
    feed = WebsFeed([("Kambi", K()), ("Betway", B())])
    out = feed.fetch(["*"], None, 48, 10)
    assert calls == {"kambi": ["1"], "betway": ["7"]}  # Getafe-Osasuna solo está en una: no se pide
    assert feed.matched == 1 and len(out) == 1
    assert set(out[0]["markets"]["Totals:2.5"]["prices"]) == {"PAF ES", "Betway ES"}
    assert scan(out, 100)  # 2.2 / 2.3 -> surebet
