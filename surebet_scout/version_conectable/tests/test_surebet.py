import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from betfair import BetfairClient, BetfairError, similarity  # noqa: E402
from core import effective_odds, find_opportunity, plan_stakes  # noqa: E402
from exchange import BetfairExchange, SimulatedExchange  # noqa: E402
from feeds import DemoFeed, OddsApiIoFeed, normalize_odds_api_io  # noqa: E402
from service import Service, ServiceError  # noqa: E402
from store import Store  # noqa: E402

BF = "Betfair Exchange"


def event(prices, eid="e1"):
    return {"id": eid, "sport": "football", "league": "L", "home": "Real Betis",
            "away": "Villarreal", "date": "2030-01-01T20:00:00Z", "urls": {},
            "prices": prices, "updated": {}}


# --- detector ---------------------------------------------------------------
def test_commission_reduces_odds():
    assert effective_odds(3.0, 0.05) == pytest.approx(2.9)


def test_detects_three_way_surebet_and_balances_payouts():
    ev = event({"A": {"home": 2.6, "draw": 3.1, "away": 2.9},
                "B": {"home": 2.4, "draw": 3.9, "away": 2.7},
                "C": {"home": 2.5, "draw": 3.2, "away": 3.0}})
    opp = find_opportunity(ev, 100)
    assert opp and opp["margin"] > 0
    assert [l["bookmaker"] for l in opp["legs"]] == ["A", "B", "C"]
    assert max(opp["profit"].values()) - min(opp["profit"].values()) < 0.05


def test_no_surebet_and_commission_can_kill_it():
    assert find_opportunity(event({"A": {"home": 1.9, "away": 1.9}}), 100) is None
    ev = event({"A": {"home": 2.04, "away": 1.5}, BF: {"home": 1.5, "away": 2.04}})
    assert find_opportunity(ev, 100) is not None
    assert find_opportunity(ev, 100, commissions={"A": 0.05, BF: 0.05}) is None


def test_ignores_bookmakers_with_incomplete_market():
    ev = event({"A": {"home": 5.0, "away": 5.0},  # sin empate: no se mezcla con 1X2
                "B": {"home": 2.0, "draw": 3.0, "away": 3.0}})
    assert find_opportunity(ev, 100) is None


def test_only_allowed_bookmakers():
    ev = event({"A": {"home": 2.2, "away": 2.2}, "B": {"home": 1.5, "away": 1.5}})
    assert find_opportunity(ev, 100, bookmakers=["B"]) is None


def test_rounding():
    legs = [{"outcome": "home", "eff": 2.1}, {"outcome": "away", "eff": 2.1}]
    stakes, _ = plan_stakes(legs, 51, rounding=1)
    assert all(s == int(s) for s in stakes)


# --- feed odds-api.io ---------------------------------------------------------
def test_normalize_odds_api_io():
    raw = {"id": 7, "home": "Sevilla", "away": "Valencia", "date": "2030-01-01T20:00:00Z",
           "sport": {"slug": "football"}, "league": {"name": "LaLiga"},
           "urls": {"Bwin ES": "https://bwin"},
           "bookmakers": {"Bwin ES": [{"name": "ML", "updatedAt": "x",
                                       "odds": [{"home": "2.10", "draw": "3.40", "away": "3.20"}]},
                                      {"name": "Totals", "odds": [{"over": "1.9"}]}],
                          "Raro": [{"name": "ML", "odds": [{"home": "N/A"}]}]}}
    ev = normalize_odds_api_io(raw)
    assert ev["markets"]["ML"]["prices"] == {"Bwin ES": {"home": 2.1, "draw": 3.4, "away": 3.2}}
    assert ev["id"] == "7" and ev["league"] == "LaLiga"


def test_odds_api_feed_batches_and_reports_errors():
    calls = []

    def handler(req):
        calls.append(req.url.path)
        if req.url.path.endswith("/events"):
            return httpx.Response(200, json=[{"id": i} for i in range(12)],
                                  headers={"x-ratelimit-remaining": "99"})
        if req.url.path.endswith("/odds/multi"):
            ids = req.url.params["eventIds"].split(",")
            assert "markets" not in req.url.params  # sin filtro = todos los mercados
            return httpx.Response(200, json=[{"id": i, "bookmakers": {}} for i in ids])
        return httpx.Response(404)

    feed = OddsApiIoFeed("k", http=httpx.Client(transport=httpx.MockTransport(handler)))
    evs = feed.fetch(["football"], ["Bwin ES", "Codere ES"], 24, 50)
    assert len(evs) == 12 and calls.count("/v3/odds/multi") == 2
    assert feed.status()["remaining"] == "99"

    bad = OddsApiIoFeed("k", http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(401))))
    with pytest.raises(Exception, match="clave"):
        bad.fetch(["football"], ["A", "B"])


# --- Betfair (respuestas simuladas, sin red) ---------------------------------
class FakeBetfair:
    def __init__(self, place_result=None, fail_place=False):
        self.place_result = place_result
        self.fail_place = fail_place
        self.placed = []

    def __call__(self, req):
        if req.url.path.endswith("/api/login"):
            assert req.headers["X-Application"] == "APPKEY"
            return httpx.Response(200, json={"token": "TOK", "status": "SUCCESS", "error": ""})
        body = json.loads(req.content)
        assert req.headers["X-Authentication"] == "TOK"
        m = body["method"]
        if m.endswith("getAccountFunds"):
            return httpx.Response(200, json={"result": {"availableToBetBalance": 123.45}})
        if m.endswith("listMarketCatalogue"):
            return httpx.Response(200, json={"result": [
                {"marketId": "1.999", "marketName": "Match Odds", "event": {"name": "Otro v Equipo"},
                 "runners": [{"selectionId": 1, "runnerName": "Otro"},
                             {"selectionId": 2, "runnerName": "Equipo"},
                             {"selectionId": 3, "runnerName": "The Draw"}]},
                {"marketId": "1.234", "marketName": "Match Odds", "event": {"name": "Betis v Villarreal"},
                 "runners": [{"selectionId": 11, "runnerName": "Betis"},
                             {"selectionId": 12, "runnerName": "Villarreal"},
                             {"selectionId": 13, "runnerName": "The Draw"}]}]})
        if m.endswith("listMarketBook"):
            return httpx.Response(200, json={"result": [{"status": "OPEN", "runners": [
                {"selectionId": 13, "ex": {"availableToBack": [{"price": 3.9, "size": 500}]}}]}]})
        if m.endswith("placeOrders"):
            if self.fail_place:
                raise httpx.ReadTimeout("timeout")
            lo = body["params"]["instructions"][0]["limitOrder"]
            assert lo["timeInForce"] == "FILL_OR_KILL"
            self.placed.append(body["params"])
            return httpx.Response(200, json={"result": self.place_result or {
                "status": "SUCCESS", "instructionReports": [
                    {"status": "SUCCESS", "betId": "B1", "sizeMatched": lo["size"],
                     "averagePriceMatched": lo["price"]}]}})
        return httpx.Response(404)


def bf_client(fake):
    return BetfairClient("APPKEY", "user", "pwd",
                         http=httpx.Client(transport=httpx.MockTransport(fake)))


def test_similarity_handles_prefixes_and_accents():
    assert similarity("Real Betis", "Betis") > 0.9
    assert similarity("Atlético de Madrid", "Atletico Madrid") > 0.9
    assert similarity("Sevilla", "Valencia") < 0.6


def test_betfair_find_and_place():
    fake = FakeBetfair()
    c = bf_client(fake)
    assert c.balance() == 123.45
    sel = c.find_selection("Real Betis", "Villarreal", "2030-01-01T20:00:00Z", "draw")
    assert sel["market_id"] == "1.234" and sel["selection_id"] == 13
    assert c.best_back("1.234", 13) == (3.9, 500.0)
    res = c.place_back_fok("1.234", 13, 3.9, 10, "ref")
    assert res["ok"] and res["matched"] == 10


def test_betfair_rejects_unknown_match():
    c = bf_client(FakeBetfair())
    with pytest.raises(BetfairError):
        c.find_selection("Getafe", "Osasuna", "2030-01-01T20:00:00Z", "home")


def test_betfair_network_failure_on_place_is_unknown():
    ex = BetfairExchange(bf_client(FakeBetfair(fail_place=True)))
    res = ex.place({"market_id": "1.234", "selection_id": 13, "price": 3.9}, 10, "r")
    assert res["unknown"] and not res["ok"]


def test_betfair_min_stake():
    ex = BetfairExchange(bf_client(FakeBetfair()), min_stake=2)
    assert not ex.place({"market_id": "1", "selection_id": 1, "price": 2}, 1.5, "r")["ok"]


# --- servicio / flujo completo ----------------------------------------------
def make_service(exchange_factory=None):
    store = Store(":memory:")
    ex = exchange_factory(store) if exchange_factory else SimulatedExchange(store)
    svc = Service(store, DemoFeed(jitter=False), ex)
    svc.update_settings({"sports": ["football", "tennis"]})
    return svc


def betis_op(svc, budget=50):
    opp = next(o for o in svc.scan() if o["home"] == "Real Betis" and o["market"] == "ML")
    return svc.create_operation(opp["id"], budget)


def test_full_flow_simulated():
    svc = make_service()
    op = betis_op(svc)
    manual = [l for l in op["legs"] if l["mode"] == "manual"]
    auto = next(l for l in op["legs"] if l["mode"] == "auto")
    with pytest.raises(ServiceError, match="manuales"):
        svc.prepare_auto(op["id"], auto["id"])
    for l in manual:
        cur = next(x for x in svc.operation(op["id"])["legs"] if x["id"] == l["id"])
        op = svc.register_manual(op["id"], l["id"], l["planned_odds"], cur["suggested_stake"])
    assert op["exposed"]
    op = svc.prepare_auto(op["id"], auto["id"])
    with pytest.raises(ServiceError, match="SI"):
        svc.place_auto(op["id"], auto["id"], "vale")
    op = svc.place_auto(op["id"], auto["id"], "si")
    assert op["state"] == "completa" and not op["exposed"]
    assert min(op["current"].values()) > 0
    op = svc.settle(op["id"], "home")
    assert op["settled"]["profit"] > 0
    assert "Real Betis" in svc.export_csv()


def test_worse_manual_odds_rebalance_pending_legs():
    svc = make_service()
    op = betis_op(svc)
    first = next(l for l in op["legs"] if l["mode"] == "manual")
    before = {l["id"]: l["suggested_stake"] for l in op["legs"]}
    op = svc.register_manual(op["id"], first["id"], first["planned_odds"] + 0.3, first["planned_stake"])
    after = {l["id"]: l.get("suggested_stake") for l in op["legs"] if l["status"] == "pending"}
    assert all(after[i] >= before[i] for i in after)


def test_skip_after_placing_marks_exposed_and_blocks_cancel():
    svc = make_service()
    op = betis_op(svc)
    a, b = [l for l in op["legs"] if l["mode"] == "manual"]
    svc.register_manual(op["id"], a["id"], a["planned_odds"], a["planned_stake"])
    op = svc.skip_leg(op["id"], b["id"])
    assert op["state"] == "expuesta" and op["exposed"]
    with pytest.raises(ServiceError):
        svc.cancel(op["id"])
    assert op["id"] in svc.status()["exposed_ops"]


def test_limits():
    svc = make_service()
    opp = next(o for o in svc.scan() if o["home"] == "Real Betis" and o["market"] == "ML")
    with pytest.raises(ServiceError, match="máximo por operación"):
        svc.create_operation(opp["id"], 1000)
    svc.update_settings({"max_daily": 60, "budget": 50, "max_budget_op": 60})
    op = svc.create_operation(opp["id"], 50)
    for l in op["legs"]:
        if l["mode"] == "manual":
            svc.register_manual(op["id"], l["id"], l["planned_odds"], 25)
    with pytest.raises(ServiceError, match="diario"):
        svc.create_operation(opp["id"], 50)


def test_worse_live_price_requires_acceptance():
    class WorseSim(SimulatedExchange):
        def quote(self, op, leg):
            q = super().quote(op, leg)
            return {**q, "price": round(leg["planned_odds"] - 0.4, 2)}

    svc = make_service(WorseSim)
    op = betis_op(svc)
    for l in op["legs"]:
        if l["mode"] == "manual":
            op = svc.register_manual(op["id"], l["id"], l["planned_odds"], l["planned_stake"])
    auto = next(l for l in op["legs"] if l["mode"] == "auto")
    svc.prepare_auto(op["id"], auto["id"])
    with pytest.raises(ServiceError, match="acepto"):
        svc.place_auto(op["id"], auto["id"], "SI")
    op = svc.place_auto(op["id"], auto["id"], "SI", accept_worse=True)
    assert op["state"] == "completa"


def test_unknown_betfair_result_is_flagged():
    fake = FakeBetfair(fail_place=True)
    svc = make_service(lambda store: BetfairExchange(bf_client(fake)))
    svc.update_settings({"auto_bookmaker": BF})
    op = betis_op(svc)
    for l in op["legs"]:
        if l["mode"] == "manual":
            op = svc.register_manual(op["id"], l["id"], l["planned_odds"], l["planned_stake"])
    auto = next(l for l in op["legs"] if l["mode"] == "auto")
    svc.prepare_auto(op["id"], auto["id"])
    op = svc.place_auto(op["id"], auto["id"], "SI", accept_worse=True)
    leg = next(l for l in op["legs"] if l["id"] == auto["id"])
    assert leg["status"] == "unknown" and op["has_unknown"]
    op = svc.reopen_leg(op["id"], auto["id"])
    assert next(l for l in op["legs"] if l["id"] == auto["id"])["status"] == "pending"


def test_settings_validation():
    svc = make_service()
    with pytest.raises(ServiceError):
        svc.update_settings({"bookmakers": ["Solo una"]})
    with pytest.raises(ServiceError):
        svc.update_settings({"commissions": {"X": 0.9}})


def test_web_api_and_local_only():
    from fastapi.testclient import TestClient
    from web import create_app

    client = TestClient(create_app(make_service()))
    assert client.get("/").status_code == 200
    assert client.post("/api/scan", json={}).status_code == 200
    assert client.post("/api/scan", content="x", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 400
    r = client.post("/api/operations", json={"opportunity_id": "nope"})
    assert r.status_code == 400 and "error" in r.json()


# --- surebets externas (BetOven u otro escáner, copiadas a mano) -------------
def test_external_surebet_any_market_is_manual():
    svc = make_service()
    op = svc.create_external_operation({
        "source": "BetOven", "home": "Sevilla", "away": "Valencia", "budget": 40,
        "legs": [{"label": "Más de 2.5", "kind": "other", "bookmaker": "Codere ES", "odds": 2.10},
                 {"label": "Menos de 2.5", "kind": "other", "bookmaker": BF, "odds": 2.05}]})
    assert op["source"] == "BetOven" and op["margin"] > 0
    assert all(l["mode"] == "manual" for l in op["legs"])  # Betfair solo es auto en 1X2
    assert len(op["projection"]) == 2 and min(op["projection"].values()) >= 0
    with pytest.raises(ServiceError):
        svc.set_mode(op["id"], 1, "auto")
    for l in op["legs"]:
        op = svc.register_manual(op["id"], l["id"], l["planned_odds"], l["suggested_stake"])
    assert op["state"] == "completa"
    op = svc.settle(op["id"], op["legs"][0]["outcome"])
    assert op["settled"]["profit"] > 0
    assert "BetOven" in svc.export_csv()


def test_external_1x2_betfair_leg_can_be_auto():
    svc = make_service()
    op = svc.create_external_operation({
        "home": "Real Betis", "away": "Villarreal", "date": "2030-01-01T20:00:00Z", "budget": 50,
        "legs": [{"kind": "home", "bookmaker": "Winamax ES", "odds": 2.62},
                 {"kind": "draw", "bookmaker": BF, "odds": 3.95},
                 {"kind": "away", "bookmaker": "Codere ES", "odds": 2.95}]})
    assert [l["mode"] for l in op["legs"]] == ["manual", "auto", "manual"]
    assert op["legs"][1]["commission"] == 0.05  # toma la comisión de Ajustes


def test_external_rejects_non_surebet_and_bad_input():
    svc = make_service()
    legs = [{"kind": "home", "bookmaker": "A", "odds": 1.9}, {"kind": "away", "bookmaker": "B", "odds": 1.9}]
    with pytest.raises(ServiceError, match="no es surebet"):
        svc.create_external_operation({"home": "X", "legs": legs})
    with pytest.raises(ServiceError):
        svc.create_external_operation({"home": "X", "legs": legs[:1]})
    with pytest.raises(ServiceError, match="mismo resultado"):
        svc.create_external_operation({"home": "X", "legs": [legs[0], legs[0]]})
    with pytest.raises(ServiceError):
        svc.create_external_operation({"home": "", "legs": legs})


# --- cuidado de cuentas -------------------------------------------------------
def test_bookmaker_stats_track_profit_per_house():
    svc = make_service()
    svc.update_settings({"book_profit_warn": 5})
    op = svc.create_external_operation({
        "home": "A", "away": "B", "budget": 40,
        "legs": [{"kind": "home", "bookmaker": "Codere ES", "odds": 2.2},
                 {"kind": "away", "bookmaker": "Bwin ES", "odds": 2.1}]})
    for l in op["legs"]:
        svc.register_manual(op["id"], l["id"], l["planned_odds"], l["planned_stake"])
    pending = {b["bookmaker"]: b for b in svc.bookmaker_stats()}
    assert pending["Codere ES"]["open_stake"] > 0 and pending["Codere ES"]["profit"] == 0
    svc.settle(op["id"], "home")
    stats = {b["bookmaker"]: b for b in svc.bookmaker_stats()}
    codere, bwin = stats["Codere ES"], stats["Bwin ES"]
    assert codere["profit"] == pytest.approx(codere["staked"] * 1.2, abs=0.01)
    assert bwin["profit"] == -bwin["staked"]
    assert codere["warn"] and not bwin["warn"] and codere["open_stake"] == 0


# --- mercados de goles y hándicap --------------------------------------------
def test_totals_and_spread_surebets_are_detected_and_manual():
    from core import find_opportunities, scan
    ev = {"id": "9", "home": "Sevilla", "away": "Valencia", "date": "2030-01-01T20:00:00Z",
          "markets": {
              "ML": {"type": "ML", "line": None, "prices": {
                  "A": {"home": 2.0, "draw": 3.2, "away": 3.5}, BF: {"home": 2.0, "draw": 3.3, "away": 3.6}}},
              "Totals:2.5": {"type": "Totals", "line": 2.5, "prices": {
                  "A": {"over": 2.15, "under": 1.70}, "B": {"over": 1.80, "under": 2.05}}},
              "Spread:-0.5": {"type": "Spread", "line": -0.5, "prices": {
                  "A": {"home": 2.0, "away": 1.8}, "B": {"home": 1.9, "away": 2.1}}}}}
    opps = find_opportunities(ev, 100)
    keys = {o["market"] for o in opps}
    assert keys == {"Totals:2.5", "Spread:-0.5"}
    tot = next(o for o in opps if o["market"] == "Totals:2.5")
    assert [l["label"] for l in tot["legs"]] == ["Más de 2,5", "Menos de 2,5"]
    assert tot["market_label"] == "Más/menos 2,5" and tot["id"] == "9|Totals:2.5"
    sp = next(o for o in opps if o["market"] == "Spread:-0.5")
    assert [l["label"] for l in sp["legs"]] == ["Sevilla (-0,5)", "Valencia (+0,5)"]
    assert not any(l["can_auto"] for o in opps for l in o["legs"])
    # ordenadas de mayor a menor margen y filtrables por mercado
    ranked = scan([ev], 100)
    assert [o["margin"] for o in ranked] == sorted((o["margin"] for o in ranked), reverse=True)
    assert scan([ev], 100, markets=["ML"]) == []


def test_normalize_totals_and_spread_lines():
    raw = {"id": 1, "home": "H", "away": "A", "bookmakers": {"Bwin ES": [
        {"name": "Totals", "updatedAt": "u", "odds": [{"hdp": 2.5, "over": "1.9", "under": "1.9"},
                                                       {"hdp": 3.5, "over": "3.1", "under": "1.35"}]},
        {"name": "Spread", "odds": [{"hdp": -0.5, "home": "2.0", "away": "1.8"}]}]}}
    ev = normalize_odds_api_io(raw)
    assert set(ev["markets"]) == {"Totals:2.5", "Totals:3.5", "Spread:-0.5"}
    assert ev["markets"]["Totals:3.5"]["prices"]["Bwin ES"] == {"over": 3.1, "under": 1.35}
    assert ev["markets"]["Spread:-0.5"]["line"] == -0.5


def test_service_totals_operation_is_manual_even_with_betfair():
    svc = make_service()
    opps = svc.scan()
    assert [o["margin"] for o in opps] == sorted((o["margin"] for o in opps), reverse=True)
    totals = [o for o in opps if o["market_type"] != "ML"]
    assert totals
    op = svc.create_operation(totals[0]["id"], 40)
    assert all(l["mode"] == "manual" for l in op["legs"]) and op["market_label"]


# --- todos los mercados -------------------------------------------------------
def test_generic_markets_from_api_rows():
    from core import scan
    raw = {"id": 5, "home": "Betis", "away": "Sevilla", "date": "2030-01-01T20:00:00Z",
           "sport": {"slug": "football"}, "bookmakers": {
               "A": [{"name": "Both Teams To Score", "odds": [{"yes": "1.80", "no": "2.30", "layYes": "1.9"}]},
                     {"name": "Corners Totals HT", "odds": [{"hdp": 4.5, "over": "2.10", "under": "1.80"}]},
                     {"name": "Player Shots", "odds": [{"label": "Isco", "hdp": 1.5, "over": "2.2", "under": "1.6"}]},
                     {"name": "Correct Score", "odds": [{"label": "1-0", "odds": "7.0"}, {"label": "0-0", "odds": "9.0"}]},
                     {"name": "Double Chance", "odds": [{"1X": "1.60", "12": "1.30", "X2": "1.45"}]},
                     {"name": "ML", "odds": [{"home": "2.0", "draw": "3.3", "away": "4.0"}]}],
               "B": [{"name": "Both Teams To Score", "odds": [{"yes": "1.70", "no": "2.10"}]},
                     {"name": "Corners Totals HT", "odds": [{"hdp": 4.5, "over": "1.85", "under": "2.05"}]},
                     {"name": "Player Shots", "odds": [{"label": "Isco", "hdp": 1.5, "over": "1.9", "under": "2.0",
                                                         "underLink": "https://b/isco-u"}]},
                     {"name": "ML", "odds": [{"home": "2.1", "draw": "3.2", "away": "2.80"}]}]}}
    ev = normalize_odds_api_io(raw)
    assert "Correct Score|1-0" not in ev["markets"]  # precio único por etiqueta: no exhaustivo
    opps = {o["market"]: o for o in scan([ev], 100)}
    assert "Both Teams To Score" in opps and opps["Both Teams To Score"]["group"] == "Ambos marcan"
    assert "Corners Totals HT:4.5" in opps
    shots = opps["Player Shots|Isco:1.5"]
    assert shots["group"] == "Jugadores" and shots["legs"][1]["url"] == "https://b/isco-u"
    # 1X (A, 1.60) contra 2 (A, 4.0): 1/1.6 + 1/4 = 0.875 -> surebet cruzada
    dc = [o for o in opps.values() if o["group"] == "Doble oportunidad"]
    assert dc and {l["outcome"] for l in dc[0]["legs"]} == {"1X", "away"}
    # Solo las patas de 1X2 (incluida la del combo) pueden ir automáticas en Betfair
    assert all(l["can_auto"] == (l["outcome"] in ("home", "draw", "away") and o["market_type"] in ("ML", "Double Chance"))
               for o in opps.values() for l in o["legs"])


def test_all_sports_and_markets_by_default():
    store = Store(":memory:")
    svc = Service(store, DemoFeed(jitter=False), SimulatedExchange(store))
    assert svc.settings()["sports"] == ["*"] and svc.settings()["markets"] == ["*"]
    opps = svc.scan()
    assert {"football", "tennis", "basketball"} <= {o["sport"] for o in opps}
    assert len({o["group"] for o in opps}) >= 5
    assert [o["margin"] for o in opps] == sorted((o["margin"] for o in opps), reverse=True)
