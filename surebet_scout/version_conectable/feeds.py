"""Fuentes de cuotas. Solo LEEN cuotas; nunca apuestan.

- DemoFeed: datos de ejemplo, sin red ni clave (con el mismo formato que la API).
- OddsApiIoFeed: https://odds-api.io (API oficial de datos, cubre casas .es),
  todos los deportes y todos los mercados prepartido.
"""
import math
import random
import time
from datetime import datetime, timedelta, timezone

import httpx

SPANISH_BOOKMAKERS = [
    "Betfair Exchange", "Betfair ES", "Bwin ES", "Codere ES", "Luckia ES", "Retabet ES",
    "Winamax ES", "888Sport ES", "PokerStars ES", "Betway ES", "LeoVegas ES", "PAF ES",
    "Casumo ES",
]
# Campos de precio que entiende el detector (el resto, como lay*/depth*, se ignora).
PRICE_KEYS = ("home", "draw", "away", "over", "under", "yes", "no", "odd", "even", "none",
              "1X", "12", "X2")


class FeedError(Exception):
    pass


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _price(row, key):
    try:
        v = float(row.get(key))
    except (TypeError, ValueError):
        return None
    return v if v > 1 else None


def normalize_odds_api_io(ev):
    """Pasa un evento de odds-api.io al formato de core, con TODOS sus mercados.

    Cada fila de un mercado se convierte en un mercado propio por línea (hdp) y
    etiqueta (jugador, etc.). Las filas con un único precio por etiqueta
    ("odds": resultado exacto, goleador...) no se usan: no garantizan cubrir
    todos los resultados.
    """
    markets, updated = {}, {}
    for bk, mlist in (ev.get("bookmakers") or {}).items():
        for m in mlist or []:
            name, upd = str(m.get("name", "")), m.get("updatedAt", "")
            for row in m.get("odds") or []:
                prices = {k: v for k in PRICE_KEYS if (v := _price(row, k))}
                if len(prices) < 2:
                    continue
                line = row.get("hdp")
                try:
                    line = float(line) if line is not None else None
                except (TypeError, ValueError):
                    continue
                label = row.get("label") or None
                key = name + (f"|{label}" if label else "") + (f":{line:g}" if line is not None else "")
                mk = markets.setdefault(key, {"name": name, "line": line, "label": label,
                                              "prices": {}, "links": {}, "updated": {}})
                mk["prices"][bk] = prices
                links = {k: row[k + "Link"] for k in prices if row.get(k + "Link")}
                if links:
                    mk["links"][bk] = links
                mk["updated"][bk] = upd
                updated[bk] = max(updated.get(bk, ""), upd or "")
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


class DemoFeed:
    """Eventos inventados en el formato de odds-api.io (pasan por el mismo normalizador)."""
    name, label = "demo", "Datos de ejemplo"

    _SPORTS = [{"slug": "football", "name": "Fútbol"}, {"slug": "tennis", "name": "Tenis"},
               {"slug": "basketball", "name": "Baloncesto"},
               {"slug": "ice-hockey", "name": "Hockey hielo"}, {"slug": "esports", "name": "Esports"}]
    BF = "Betfair Exchange"
    # (deporte, liga, local, visitante, horas, {mercado: {casa: filas}})
    _EVENTS = [
        ("football", "España - LaLiga", "Real Betis", "Villarreal", 5, {
            "ML": {"Bwin ES": [(2.55, 3.30, 2.80)], "Codere ES": [(2.50, 3.25, 2.95)],
                   "Winamax ES": [(2.62, 3.20, 2.75)], BF: [(2.58, 3.95, 2.90)]},
            "Totals": {"Bwin ES": [(2.5, 2.18, 1.80), (3.5, 3.30, 1.36)],
                       "Codere ES": [(2.5, 1.95, 1.92), (3.5, 3.05, 1.40)],
                       "Winamax ES": [(2.5, 1.98, 1.97)], BF: [(2.5, 2.02, 1.95)]},
            "Both Teams To Score": {"Bwin ES": [("yes", 1.72, "no", 2.10)],
                                    "Luckia ES": [("yes", 1.80, "no", 2.02)],
                                    "Retabet ES": [("yes", 1.66, "no", 2.28)]},
            "Corners Totals": {"Bwin ES": [(9.5, 1.95, 1.85)], "Codere ES": [(9.5, 1.78, 2.12)]},
            "Double Chance": {"Luckia ES": [("1X", 1.52, "12", 1.30, "X2", 1.58)],
                              "Retabet ES": [("1X", 1.48, "12", 1.33, "X2", 1.55)]},
        }),
        ("football", "España - LaLiga", "Sevilla", "Valencia", 26, {
            "ML": {"Luckia ES": [(2.05, 3.60, 3.70)], "Retabet ES": [(2.20, 3.40, 3.50)],
                   "888Sport ES": [(2.10, 3.50, 3.90)], BF: [(2.12, 3.55, 3.85)]},
            "Spread": {"Luckia ES": [(-0.5, 2.12, 1.75)], "Retabet ES": [(-0.5, 2.05, 1.90)],
                       "888Sport ES": [(-0.5, 2.25, 1.72)]},
            "Totals HT": {"Luckia ES": [(0.5, 1.45, 2.95)], "888Sport ES": [(0.5, 1.38, 3.25)]},
            "Odd/Even": {"Retabet ES": [("odd", 1.95, "even", 1.92)],
                         "Luckia ES": [("odd", 2.02, "even", 1.84)],
                         "888Sport ES": [("odd", 1.88, "even", 2.04)]},
        }),
        ("football", "Inglaterra - Premier League", "Aston Villa", "Newcastle", 30, {
            "ML": {"Bwin ES": [(2.40, 3.40, 2.95)], "PokerStars ES": [(2.38, 3.45, 3.00)],
                   "Codere ES": [(2.35, 3.50, 3.05)], BF: [(2.44, 3.55, 3.10)]},
            "Totals": {"Bwin ES": [(2.5, 1.85, 2.00)], "PokerStars ES": [(2.5, 1.90, 1.95)],
                       "Codere ES": [(2.5, 1.80, 2.25)]},
            "Player Shots": {"Bwin ES": [("O. Watkins", 2.5, 1.90, 1.90)],
                             "Codere ES": [("O. Watkins", 2.5, 2.15, 1.75)]},
        }),
        ("football", "Italia - Serie A", "Atalanta", "Roma", 40, {
            "ML": {"Winamax ES": [(2.00, 3.60, 4.10)], "Luckia ES": [(2.08, 3.45, 3.80)],
                   "Betway ES": [(1.98, 3.70, 4.20)], BF: [(2.10, 3.65, 4.40)]},
            "Totals": {"Winamax ES": [(3.5, 3.40, 1.33)], "Luckia ES": [(3.5, 2.95, 1.70)],
                       "Betway ES": [(3.5, 3.10, 1.38)]},
            "Bookings Totals": {"Winamax ES": [(4.5, 1.90, 1.90)], "Betway ES": [(4.5, 1.80, 2.08)]},
        }),
        ("tennis", "ATP Basilea", "C. Alcaraz", "H. Rune", 8, {
            "ML": {"Bwin ES": [(1.60, None, 2.40)], "Codere ES": [(1.55, None, 2.62)],
                   BF: [(1.70, None, 2.50)]},
            "Spread (Games)": {"Bwin ES": [(-3.5, 2.05, 1.80)], "Codere ES": [(-3.5, 1.85, 2.08)]},
            "Totals (Games)": {"Bwin ES": [(22.5, 1.87, 1.93)], "Winamax ES": [(22.5, 1.97, 1.84)]},
        }),
        ("basketball", "ACB", "Unicaja", "Baskonia", 28, {
            "ML": {"Bwin ES": [(1.75, None, 2.10)], "Luckia ES": [(1.80, None, 2.05)],
                   BF: [(1.82, None, 2.15)]},
            "Totals": {"Bwin ES": [(165.5, 1.95, 1.85)], "Luckia ES": [(165.5, 1.83, 2.07)]},
            "Spread 1Q": {"Bwin ES": [(-1.5, 1.90, 1.90)], "Luckia ES": [(-1.5, 1.95, 1.86)]},
        }),
        ("ice-hockey", "NHL", "Rangers", "Bruins", 20, {
            "ML": {"Bwin ES": [(2.10, None, 1.80)], "888Sport ES": [(2.22, None, 1.74)]},
            "Totals": {"Bwin ES": [(5.5, 1.92, 1.92)], "888Sport ES": [(5.5, 2.06, 1.82)]},
        }),
        ("esports", "LoL - Worlds", "T1", "Gen.G", 12, {
            "ML": {"Bwin ES": [(1.95, None, 1.85)], "Winamax ES": [(2.05, None, 1.80)]},
            "1st Map First Blood": {"Bwin ES": [(1.90, None, 1.90)], "Winamax ES": [(2.08, None, 1.84)]},
            "Total Maps": {"Bwin ES": [(3.5, 2.30, 1.58)], "Winamax ES": [(3.5, 2.05, 1.80)]},
        }),
    ]

    def __init__(self, jitter=True):
        self.jitter = jitter

    def status(self):
        return {"feed": self.name, "label": self.label, "remaining": None}

    def sports(self):
        return self._SPORTS

    def bookmakers(self):
        return SPANISH_BOOKMAKERS

    @staticmethod
    def _row(market, r, j):
        """Convierte una tupla compacta en una fila con el formato de odds-api.io."""
        if isinstance(r[0], str) and r[0] in ("yes", "odd", "1X"):
            return {r[i]: j(r[i + 1]) for i in range(0, len(r), 2)}
        if isinstance(r[0], str):  # (jugador, línea, más, menos)
            return {"label": r[0], "hdp": r[1], "over": j(r[2]), "under": j(r[3])}
        if len(r) == 3 and ("Total" in market or "Maps" in market or "Spread" in market):
            a, b = ("over", "under") if ("Total" in market or "Maps" in market) else ("home", "away")
            return {"hdp": r[0], a: j(r[1]), b: j(r[2])}
        return {k: j(v) for k, v in zip(("home", "draw", "away"), r) if v}

    def fetch(self, sports, bookmakers, hours_ahead=48, max_events=50, markets=None):
        now = datetime.now(timezone.utc)
        rnd = random.Random(int(time.time() // 60))

        def j(v):
            v = round(v * (1 + rnd.uniform(-0.015, 0.015)), 2) if self.jitter else v
            return f"{v:.2f}"

        out = []
        for i, (sport, league, home, away, hours, mk) in enumerate(self._EVENTS):
            if ("*" not in sports and sport not in sports) or hours > hours_ahead:
                continue
            books = {}
            for mname, per_bk in mk.items():
                if markets and mname not in markets:
                    continue
                for bk, rows in per_bk.items():
                    if bookmakers and bk not in bookmakers:
                        continue
                    upd = _iso(now - timedelta(seconds=rnd.randint(5, 40)))
                    books.setdefault(bk, []).append(
                        {"name": mname, "updatedAt": upd, "odds": [self._row(mname, r, j) for r in rows]})
            raw = {"id": f"demo-{i}", "home": home, "away": away,
                   "date": _iso(now + timedelta(hours=hours)), "sport": {"slug": sport},
                   "league": {"name": league}, "urls": {bk: "" for bk in books}, "bookmakers": books}
            out.append(normalize_odds_api_io(raw))
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
        """sports: lista de slugs o ["*"] (todos). markets: nombres o None (todos).

        El tope de eventos se reparte entre deportes para que entren todos. Coste:
        1 petición por deporte + 1 por cada 10 eventos.
        """
        if not bookmakers:
            raise FeedError("Elige al menos dos casas en Ajustes.")
        if "*" in sports:
            sports = [s["slug"] for s in self.sports()]
        per_sport = max(5, math.ceil(max_events / max(1, len(sports))))
        now = datetime.now(timezone.utc)
        events = []
        for sport in sports:
            events += self._get("/events", {
                "sport": sport, "status": "pending", "from": _iso(now),
                "to": _iso(now + timedelta(hours=hours_ahead)), "limit": per_sport})
        out = []
        for i in range(0, len(events), 10):
            params = {"eventIds": ",".join(str(e["id"]) for e in events[i:i + 10]),
                      "bookmakers": ",".join(bookmakers[:30])}
            if markets:  # sin filtro, la API devuelve todos los mercados
                params["markets"] = ",".join(list(markets)[:40])
            out += [normalize_odds_api_io(ev) for ev in self._get("/odds/multi", params)]
        return out
