"""Utilidades comunes: cliente HTTP educado (pausas, reintentos) y nombres de deportes."""
import threading
import time

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Deportes por defecto cuando se pide "todos" (slug estilo odds-api.io).
DEFAULT_SPORTS = ["football", "tennis", "basketball", "ice-hockey", "handball", "volleyball",
                  "esports", "american-football", "baseball", "darts", "table-tennis"]


class SourceError(Exception):
    pass


class PoliteClient:
    """GET con una pausa mínima entre peticiones y reintentos ante 429/5xx.

    Así no se satura a nadie y se evita que el proveedor corte el acceso.
    """

    def __init__(self, min_interval=0.4, retries=3, http=None, sleep=time.sleep):
        self.min_interval, self.retries = min_interval, retries
        self.http = http or httpx.Client(timeout=20, headers={"User-Agent": UA},
                                         follow_redirects=True)
        self._last, self._lock, self._sleep = 0.0, threading.Lock(), sleep
        self.requests = 0

    def get_json(self, url, params=None):
        for attempt in range(self.retries + 1):
            with self._lock:
                wait = self.min_interval - (time.monotonic() - self._last)
                if wait > 0:
                    self._sleep(wait)
                self._last = time.monotonic()
            try:
                r = self.http.get(url, params=params)
                self.requests += 1
            except httpx.HTTPError as exc:
                if attempt == self.retries:
                    raise SourceError(f"sin conexión ({exc.__class__.__name__})")
                self._sleep(2 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == self.retries:
                    raise SourceError(f"respuesta {r.status_code}")
                self._sleep(5 * (attempt + 1))
                continue
            if r.status_code in (403, 451):
                raise SourceError(f"acceso bloqueado ({r.status_code}); ¿estás fuera de España?")
            if r.status_code >= 400:
                raise SourceError(f"respuesta {r.status_code}")
            try:
                return r.json()
            except ValueError:
                raise SourceError("respuesta no es JSON")
        raise SourceError("sin respuesta")


def new_market(markets, key, name, line=None, label=None):
    return markets.setdefault(key, {"name": name, "line": line, "label": label,
                                    "prices": {}, "links": {}, "updated": {}})


def market_key(name, line=None, label=None):
    return name + (f"|{label}" if label else "") + (f":{line:g}" if line is not None else "")
