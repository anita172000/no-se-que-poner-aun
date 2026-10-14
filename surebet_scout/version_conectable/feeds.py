"""Fuentes de cuotas. Solo LEEN cuotas; nunca apuestan.

- DemoFeed: datos de ejemplo, sin red ni clave.
- OddsApiIoFeed: https://odds-api.io (API oficial de datos, cubre casas .es).
"""
import random
import time
from datetime import datetime, timedelta, timezone

import httpx

from core import OUTCOMES

SPANISH_BOOKMAKERS = [
    "Betfair Exchange", "Betfair ES", "Bwin ES", "Codere ES", "Luckia ES", "Retabet ES",
    "Winamax ES", "888Sport ES", "PokerStars ES", "Betway ES", "LeoVegas ES", "PAF ES",
    "Casumo ES",
]


API_MARKETS = ("ML", "Totals", "Spread")


class FeedError(Exception):
    pass


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DemoFeed:
    name, label = "demo", "Datos de ejemplo"

    _SPORTS = [{"slug": "football", "name": "Fútbol"}, {"slug": "tennis", "name": "Tenis"},
               {"slug": "basketball", "name": "Baloncesto"}]
    # (deporte, liga, local, visitante, horas, {casa: (1, X, 2)})
    _EVENTS = [
        ("football", "España - LaLiga", "Real Betis", "Villarreal", 5,
         {"Bwin ES": (2.55, 3.30, 2.80), "Codere ES": (2.50, 3.25, 2.95),
          "Winamax ES": (2.62, 3.20, 2.75), "Betfair Exchange": (2.58, 3.95, 2.90)}),
        ("football", "España - LaLiga", "Sevilla", "Valencia", 26,
         {"Luckia ES": (2.05, 3.60, 3.70), "Retabet ES": (2.20, 3.40, 3.50),
          "888Sport ES": (2.10, 3.50, 3.90), "Betfair Exchange": (2.12, 3.55, 3.85)}),
        ("football", "Inglaterra - Premier League", "Aston Villa", "Newcastle", 30,
         {"Bwin ES": (2.40, 3.40, 2.95), "PokerStars ES": (2.38, 3.45, 3.00),
          "Codere ES": (2.35, 3.50, 3.05), "Betfair Exchange": (2.44, 3.55, 3.10)}),
        ("football", "Italia - Serie A", "Atalanta", "Roma", 40,
         {"Winamax ES": (2.00, 3.60, 4.10), "Luckia ES": (2.08, 3.45, 3.80),
          "Betway ES": (1.98, 3.70, 4.20), "Betfair Exchange": (2.10, 3.65, 4.40)}),
        ("football", "España - LaLiga", "Athletic Club", "Girona", 72,
         {"Bwin ES": (1.95, 3.50, 4.20), "Retabet ES": (1.92, 3.60, 4.30),
          "Betfair Exchange": (1.97, 3.55, 4.40)}),
        ("tennis", "ATP Basilea", "C. Alcaraz", "H. Rune", 8,
         {"Bwin ES": (1.60, None, 2.40), "Codere ES": (1.55, None, 2.62),
          "Betfair Exchange": (1.70, None, 2.50)}),
        ("tennis", "WTA Wuhan", "P. Badosa", "J. Paolini", 20,
         {"Winamax ES": (2.05, None, 1.80), "888Sport ES": (2.10, None, 1.85),
          "Betfair Exchange": (2.08, None, 1.88)}),
        ("basketball", "ACB", "Unicaja", "Baskonia", 28,
         {"Bwin ES": (1.75, None, 2.10), "Luckia ES": (1.80, None, 2.05),
          "Betfair Exchange": (1.82, None, 2.15)}),
    ]
    # Mercados extra de ejemplo: {índice de evento: {clave: (tipo, línea, {casa: (a, b)})}}
    # (a, b) = (más, menos) en Totals y (local, visitante) en Spread.
    _EXTRA = {
        0: {"Totals:2.5": ("Totals", 2.5, {"Bwin ES": (2.18, 1.80), "Codere ES": (1.95, 1.92),
                                            "Winamax ES": (1.98, 1.97), "Betfair Exchange": (2.02, 1.95)})},
        1: {"Spread:-0.5": ("Spread", -0.5, {"Luckia ES": (2.12, 1.75), "Retabet ES": (2.05, 1.90),
                                              "888Sport ES": (2.25, 1.72)})},
        2: {"Totals:2.5": ("Totals", 2.5, {"Bwin ES": (1.85, 2.00), "PokerStars ES": (1.90, 1.95),
                                            "Codere ES": (1.80, 2.25)})},
        3: {"Totals:3.5": ("Totals", 3.5, {"Winamax ES": (3.40, 1.33), "Luckia ES": (2.95, 1.70),
                                            "Betway ES": (3.10, 1.38)})},
        5: {"Spread:-1.5": ("Spread", -1.5, {"Bwin ES": (2.20, 1.66), "Codere ES": (2.05, 1.85),
                                              "Betfair Exchange": (2.30, 1.70)})},
    }

    def __init__(self, jitter=True):
        self.jitter = jitter

    def status(self):
        return {"feed": self.name, "label": self.label, "remaining": None}

    def sports(self):
        return self._SPORTS

    def bookmakers(self):
        return SPANISH_BOOKMAKERS

    def fetch(self, sports, bookmakers, hours_ahead=48, max_events=50, markets=None):
        markets_filter = markets
        now = datetime.now(timezone.utc)
        rnd = random.Random(int(time.time() // 60))
        out = []
        for i, (sport, league, home, away, hours, books) in enumerate(self._EVENTS):
            if sport not in sports or hours > hours_ahead:
                continue
            raw = {"ML": ("ML", None, {bk: dict(zip(OUTCOMES, t)) for bk, t in books.items()})}
            for key, (mtype, line, mb) in self._EXTRA.get(i, {}).items():
                names = ("over", "under") if mtype == "Totals" else ("home", "away")
                raw[key] = (mtype, line, {bk: dict(zip(names, t)) for bk, t in mb.items()})
            markets, updated = {}, {}
            for key, (mtype, line, mb) in raw.items():
                if markets_filter is not None and mtype not in markets_filter:
                    continue
                prices = {}
                for bk, odds in mb.items():
                    if bookmakers and bk not in bookmakers:
                        continue
                    p = {}
                    for o, v in odds.items():
                        if v:
                            if self.jitter:
                                v = round(v * (1 + rnd.uniform(-0.015, 0.015)), 2)
                            p[o] = v
                    prices[bk] = p
                    updated.setdefault(bk, _iso(now - timedelta(seconds=rnd.randint(5, 40))))
                markets[key] = {"type": mtype, "line": line, "prices": prices}
            out.append({"id": f"demo-{i}", "sport": sport, "league": league, "home": home,
                        "away": away, "date": _iso(now + timedelta(hours=hours)),
                        "urls": {bk: "" for bk in updated}, "markets": markets,
                        "updated": updated})
        return out[:max_events]


class OddsApiIoFeed:
    name, label = "odds-api.io", "odds-api.io"
    BASE = "https://api.odds-api.io/v3"

    def __init__(self, api_key, http=None):
        if not api_key:
            raise ValueError("Falta ODDS_API_KEY.")
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=25)
        self.remaining = None
        self.reset = None
        self._cache = {}

    def status(self):
        return {"feed": self.name, "label": self.label, "remaining": self.remaining,
                "reset": self.reset}

    def _get(self, path, params=None, auth=True):
        params = dict(params or {})
        if auth:
            params["apiKey"] = self.api_key
        try:
            r = self.http.get(self.BASE + path, params=params)
        except httpx.HTTPError as exc:
            raise FeedError(f"No se pudo conectar con odds-api.io: {exc.__class__.__name__}")
        if "x-ratelimit-remaining" in r.headers:
            self.remaining = r.headers.get("x-ratelimit-remaining")
            self.reset = r.headers.get("x-ratelimit-reset")
        if r.status_code == 401:
            raise FeedError("odds-api.io: clave no válida (revisa ODDS_API_KEY).")
        if r.status_code == 403:
            raise FeedError("odds-api.io: tu plan no permite esta consulta o esas casas.")
        if r.status_code == 429:
            raise FeedError("odds-api.io: límite de peticiones alcanzado; espera un poco.")
        if r.status_code >= 400:
            raise FeedError(f"odds-api.io respondió {r.status_code}: {r.text[:200]}")
        return r.json()

    def _cached(self, key, fn, ttl=3600):
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        val = fn()
        self._cache[key] = (time.time(), val)
        return val

    def sports(self):
        data = self._cached("sports", lambda: self._get("/sports", auth=False))
        return [{"slug": s["slug"], "name": s["name"]} for s in data]

    def bookmakers(self):
        data = self._cached("bookmakers", lambda: self._get("/bookmakers", auth=False))
        return sorted(b["name"] for b in data if b.get("active"))

    def fetch(self, sports, bookmakers, hours_ahead=48, max_events=50, markets=None):
        if not bookmakers:
            raise FeedError("Elige al menos dos casas en Ajustes.")
        now = datetime.now(timezone.utc)
        events = []
        for sport in sports:
            events += self._get("/events", {
                "sport": sport, "status": "pending", "from": _iso(now),
                "to": _iso(now + timedelta(hours=hours_ahead)), "limit": max_events})
        events = events[:max_events]
        out = []
        for i in range(0, len(events), 10):
            ids = ",".join(str(e["id"]) for e in events[i:i + 10])
            data = self._get("/odds/multi", {"eventIds": ids,
                                             "markets": ",".join(markets or API_MARKETS),
                                             "bookmakers": ",".join(bookmakers[:30])})
            out += [normalize_odds_api_io(ev) for ev in data]
        return out


def _price(row, key):
    try:
        v = float(row.get(key))
    except (TypeError, ValueError):
        return None
    return v if v > 1 else None


def normalize_odds_api_io(ev):
    """Pasa el formato de odds-api.io al de core: ML (1X2), Totals y Spread por línea."""
    markets, updated = {}, {}

    def put(key, mtype, line, bk, prices, upd):
        if len(prices) < 2:
            return
        m = markets.setdefault(key, {"type": mtype, "line": line, "prices": {}, "updated": {}})
        m["prices"][bk] = prices
        m["updated"][bk] = upd
        updated[bk] = max(updated.get(bk, ""), upd or "")

    for bk, mlist in (ev.get("bookmakers") or {}).items():
        for m in mlist or []:
            name, rows, upd = str(m.get("name", "")), m.get("odds") or [], m.get("updatedAt", "")
            if not rows:
                continue
            if name.lower() == "ml":
                put("ML", "ML", None, bk,
                    {o: v for o in OUTCOMES if (v := _price(rows[0], o))}, upd)
            elif name in ("Totals", "Spread"):
                for row in rows:
                    try:
                        line = float(row.get("hdp"))
                    except (TypeError, ValueError):
                        continue
                    names = ("over", "under") if name == "Totals" else ("home", "away")
                    put(f"{name}:{line:g}", name, line, bk,
                        {o: v for o in names if (v := _price(row, o))}, upd)
    return {
        "id": str(ev.get("id")),
        "sport": (ev.get("sport") or {}).get("slug", ""),
        "league": (ev.get("league") or {}).get("name", ""),
        "home": ev.get("home", ""),
        "away": ev.get("away", ""),
        "date": ev.get("date", ""),
        "urls": ev.get("urls") or {},
        "markets": markets,
        "updated": updated,
    }
