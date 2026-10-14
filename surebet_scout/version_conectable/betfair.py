"""Cliente mínimo de la API oficial de Betfair Exchange (API-NG, JSON-RPC).

Usa el inicio de sesión oficial por API (identitysso) con tu Application Key.
Las credenciales llegan por variables de entorno; aquí solo viven en memoria y
nunca se escriben en disco ni en logs.

Las URL son configurables porque Betfair separa jurisdicciones (España usa
identitysso.betfair.es). Comprueba los valores vigentes en
https://developer.betfair.com antes de operar con dinero real.
"""
import difflib
import re
import time
import unicodedata
from datetime import timedelta

import httpx

from core import parse_iso

DEFAULTS = {
    "login_url": "https://identitysso.betfair.es/api/login",
    "keepalive_url": "https://identitysso.betfair.es/api/keepAlive",
    "betting_url": "https://api.betfair.com/exchange/betting/json-rpc/v1",
    "account_url": "https://api.betfair.com/exchange/account/json-rpc/v1",
}
SESSION_REFRESH_S = 10 * 60  # la sesión española caduca a los 20 min
_NOISE = {"fc", "cf", "cd", "ud", "sd", "rcd", "ca", "sc", "ac", "afc", "club", "de", "the"}


class BetfairError(Exception):
    pass


class BetfairNetworkError(BetfairError):
    """La petición pudo llegar o no a Betfair: el resultado es desconocido."""


def _norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    words = [w for w in re.split(r"[^a-z0-9]+", s) if w and w not in _NOISE]
    return " ".join(words)


def similarity(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


class BetfairClient:
    def __init__(self, app_key, username, password, http=None, **urls):
        if not (app_key and username and password):
            raise ValueError("Faltan BETFAIR_APP_KEY, BETFAIR_USERNAME o BETFAIR_PASSWORD.")
        self.app_key, self._user, self._pwd = app_key, username, password
        self.urls = {**DEFAULTS, **{k: v for k, v in urls.items() if v}}
        self.http = http or httpx.Client(timeout=20)
        self._token, self._token_at = None, 0.0

    # --- sesión -----------------------------------------------------------
    def _login(self):
        try:
            r = self.http.post(self.urls["login_url"],
                               data={"username": self._user, "password": self._pwd},
                               headers={"X-Application": self.app_key,
                                        "Accept": "application/json"})
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BetfairError(f"No se pudo iniciar sesión en Betfair: {exc.__class__.__name__}")
        if data.get("status") != "SUCCESS" or not data.get("token"):
            raise BetfairError(f"Betfair rechazó el inicio de sesión: {data.get('error') or data.get('status')}")
        self._token, self._token_at = data["token"], time.time()

    def _session(self):
        if not self._token or time.time() - self._token_at > SESSION_REFRESH_S:
            self._login()
        return self._token

    def _rpc(self, which, method, params, retry=True):
        body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        headers = {"X-Application": self.app_key, "X-Authentication": self._session(),
                   "Content-Type": "application/json", "Accept": "application/json"}
        try:
            data = self.http.post(self.urls[which], json=body, headers=headers).json()
        except (httpx.HTTPError, ValueError) as exc:
            raise BetfairNetworkError(f"Error de red con Betfair: {exc.__class__.__name__}")
        if "error" in data:
            err = data["error"]
            code = ((err.get("data") or {}).get("APINGException") or {}).get("errorCode") \
                or err.get("message") or str(err)
            if retry and code in ("INVALID_SESSION_INFORMATION", "NO_SESSION"):
                self._token = None
                return self._rpc(which, method, params, retry=False)
            raise BetfairError(f"Betfair: {code}")
        return data.get("result")

    # --- consultas --------------------------------------------------------
    def balance(self):
        res = self._rpc("account_url", "AccountAPING/v1.0/getAccountFunds", {})
        return float(res.get("availableToBetBalance", 0.0))

    def find_selection(self, home, away, start_iso, outcome):
        """Localiza el mercado MATCH_ODDS y el corredor del resultado pedido."""
        start = parse_iso(start_iso)
        if not start:
            raise BetfairError("Fecha del evento no válida.")
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        markets = self._rpc("betting_url", "SportsAPING/v1.0/listMarketCatalogue", {
            "filter": {"marketTypeCodes": ["MATCH_ODDS"],
                       "marketStartTime": {"from": (start - timedelta(minutes=90)).strftime(fmt),
                                           "to": (start + timedelta(minutes=90)).strftime(fmt)}},
            "marketProjection": ["EVENT", "RUNNER_DESCRIPTION", "MARKET_START_TIME"],
            "sort": "FIRST_TO_START", "maxResults": 500}) or []
        best, best_score = None, 0.0
        for m in markets:
            runners = [r for r in m.get("runners", []) if not _is_draw(r.get("runnerName"))]
            if len(runners) < 2:
                continue
            h = max(runners, key=lambda r: similarity(home, r["runnerName"]))
            a = max((r for r in runners if r is not h),
                    key=lambda r: similarity(away, r["runnerName"]))
            score = min(similarity(home, h["runnerName"]), similarity(away, a["runnerName"]))
            if score > best_score:
                best, best_score = (m, h, a), score
        if not best or best_score < 0.6:
            raise BetfairError(f"No encuentro '{home} - {away}' en Betfair. Hazla manual.")
        m, h, a = best
        if outcome == "home":
            runner = h
        elif outcome == "away":
            runner = a
        else:
            runner = next((r for r in m["runners"] if _is_draw(r.get("runnerName"))), None)
            if not runner:
                raise BetfairError("Ese mercado de Betfair no tiene empate.")
        return {"market_id": m["marketId"], "selection_id": runner["selectionId"],
                "event_name": (m.get("event") or {}).get("name", ""),
                "market_name": m.get("marketName", "Match Odds"),
                "runner_name": runner["runnerName"], "match_score": round(best_score, 2)}

    def best_back(self, market_id, selection_id):
        books = self._rpc("betting_url", "SportsAPING/v1.0/listMarketBook", {
            "marketIds": [market_id],
            "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}}) or []
        if not books:
            raise BetfairError("Mercado no disponible.")
        book = books[0]
        if book.get("status") != "OPEN":
            raise BetfairError(f"Mercado {book.get('status', 'cerrado')}.")
        for r in book.get("runners", []):
            if r.get("selectionId") == selection_id:
                backs = (r.get("ex") or {}).get("availableToBack") or []
                if not backs:
                    raise BetfairError("No hay cuota disponible para apostar ahora.")
                return float(backs[0]["price"]), float(backs[0]["size"])
        raise BetfairError("Selección no encontrada en el mercado.")

    def place_back_fok(self, market_id, selection_id, price, size, ref):
        """Apuesta a favor 'todo o nada' (FILL_OR_KILL): se casa entera a esa
        cuota media o mejor, o se cancela al instante sin dejar nada pendiente."""
        res = self._rpc("betting_url", "SportsAPING/v1.0/placeOrders", {
            "marketId": market_id,
            "customerRef": ref[:32],
            "instructions": [{
                "selectionId": selection_id, "handicap": 0, "side": "BACK",
                "orderType": "LIMIT",
                "limitOrder": {"size": round(size, 2), "price": price,
                               "persistenceType": "LAPSE", "timeInForce": "FILL_OR_KILL"},
            }]}) or {}
        rep = (res.get("instructionReports") or [{}])[0]
        matched = float(rep.get("sizeMatched") or 0.0)
        return {"ok": res.get("status") == "SUCCESS" and matched > 0,
                "matched": matched,
                "avg_price": float(rep.get("averagePriceMatched") or 0.0),
                "bet_id": rep.get("betId", ""),
                "message": rep.get("errorCode") or res.get("errorCode") or res.get("status", "")}


def _is_draw(name):
    n = (name or "").lower()
    return "draw" in n or "empate" in n
