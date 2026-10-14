"""Une el mismo partido visto en distintas casas, aunque escriban distinto los nombres.

Criterio prudente: mismo deporte, inicio a menos de 20 minutos y los dos equipos
parecidos (en el mismo orden local/visitante). Si hay duda no se une: es mejor
perder una surebet que inventar una falsa.
"""
import copy

from betfair import similarity
from core import parse_iso

MAX_START_DIFF_S = 20 * 60
MIN_SIMILARITY = 0.75


def same_event(a, b):
    if a.get("sport") and b.get("sport") and a["sport"] != b["sport"]:
        return False
    ta, tb = parse_iso(a.get("date")), parse_iso(b.get("date"))
    if not ta or not tb or abs((ta - tb).total_seconds()) > MAX_START_DIFF_S:
        return False
    return (similarity(a.get("home"), b.get("home")) >= MIN_SIMILARITY
            and similarity(a.get("away"), b.get("away")) >= MIN_SIMILARITY)


def merge_events(groups):
    """groups: listas de eventos (una por fuente). Devuelve eventos combinados."""
    merged = []
    for events in groups:
        for ev in events:
            target = next((m for m in merged if same_event(m, ev)), None)
            if target is None:
                merged.append(copy.deepcopy(ev))
                continue
            if not target.get("league") and ev.get("league"):
                target["league"] = ev["league"]
            for src, items in (ev.get("refs") or {}).items():
                target.setdefault("refs", {}).setdefault(src, []).extend(items)
            for src, raw in (ev.get("_raw") or {}).items():
                target.setdefault("_raw", {}).setdefault(src, {}).update(raw)
            target.setdefault("urls", {}).update(ev.get("urls", {}))
            target.setdefault("updated", {}).update(ev.get("updated", {}))
            for key, mk in ev.get("markets", {}).items():
                dest = target["markets"].setdefault(key, {**copy.deepcopy(mk), "prices": {},
                                                          "links": {}, "updated": {}})
                for field in ("prices", "links", "updated"):
                    dest.setdefault(field, {}).update(mk.get(field, {}))
    return merged
