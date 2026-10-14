"""Fuente "webs de las casas": junta todos los lectores gratuitos en un único feed."""
import concurrent.futures

from feeds import FeedError
from scrapers.base import DEFAULT_SPORTS
from scrapers.merge import merge_events

SPORT_NAMES = {"football": "Fútbol", "tennis": "Tenis", "basketball": "Baloncesto",
               "ice-hockey": "Hockey hielo", "handball": "Balonmano", "volleyball": "Voleibol",
               "esports": "Esports", "american-football": "Fútbol americano",
               "baseball": "Béisbol", "darts": "Dardos", "table-tennis": "Tenis de mesa"}


class WebsFeed:
    name = "webs"

    def __init__(self, sources):
        self.sources = sources  # [(nombre, lector)]
        self.last = {}

    @property
    def label(self):
        return "Webs: " + ", ".join(n for n, _ in self.sources)

    def status(self):
        return {"feed": self.name, "label": self.label, "remaining": None, "sources": self.last}

    def sports(self):
        return [{"slug": s, "name": SPORT_NAMES.get(s, s)} for s in DEFAULT_SPORTS]

    def bookmakers(self):
        return [b for _, src in self.sources for b in src.bookmakers()]

    def fetch(self, sports, bookmakers, hours_ahead=48, max_events=50, markets=None):
        """Dos fases para no perder tiempo en partidos que solo tiene una casa:

        1. Cada plataforma da su lista de partidos (rápido) y se unen entre sí.
        2. Se piden TODOS los mercados solo de los partidos que están en dos o más
           plataformas (los únicos donde puede haber surebet), los más próximos primero.
        """
        warnings, lists, full = [], [], []
        staged = [(n, s) for n, s in self.sources if hasattr(s, "list")]
        direct = [(n, s) for n, s in self.sources if not hasattr(s, "list")]
        direct_names = {n for n, _ in direct}

        def run_list(item):
            name, src = item
            return name, src.list(sports, bookmakers, hours_ahead)

        def run_direct(item):
            name, src = item
            return name, src.fetch(sports, bookmakers, hours_ahead, max_events)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(self.sources))) as pool:
            jobs = [pool.submit(run_list, i) for i in staged] + [pool.submit(run_direct, i) for i in direct]
            for job in jobs:
                name, (events, errors) = job.result()
                warnings += errors
                self.last[name] = {"events": len(events), "errors": errors}
                if name in direct_names:  # las fuentes por fases ya traen sus refs
                    for ev in events:
                        ev.setdefault("refs", {}).setdefault(name.lower(), [ev["id"]])
                (full if name in direct_names else lists).append(events)
        merged = merge_events(lists + full)
        platforms = {len(ev.get("refs", {})) for ev in merged}
        if max(platforms, default=0) >= 2:
            chosen = [ev for ev in merged if len(ev.get("refs", {})) >= 2]
        else:
            chosen = merged  # una sola plataforma: no hay cruce posible, se miran igual
        chosen.sort(key=lambda e: e.get("date", ""))
        chosen = chosen[:max_events]

        def run_details(item):
            name, src = item
            refs = [r for ev in chosen for r in src.detail_refs(ev)]
            return name, src.details(refs) if refs else ([], [])

        detailed = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(staged))) as pool:
            for name, (events, errors) in pool.map(run_details, staged):
                warnings += errors
                detailed.append(events)
                self.last.setdefault(name, {})["detailed"] = len(events)
        if not merged and warnings:
            raise FeedError("; ".join(warnings))
        # Detalles + cuotas directas (Betfair) de los partidos elegidos.
        chosen_full = [[ev for ev in grp if any(self._same(ev, c) for c in chosen)] for grp in full]
        result = merge_events(detailed + chosen_full) if (detailed or chosen_full) else chosen
        self.matched = len(chosen)
        if markets:
            for ev in result:
                ev["markets"] = {k: m for k, m in ev["markets"].items() if m["name"] in markets}
        for ev in result:
            ev.pop("_raw", None)
        self.warnings = warnings
        return result

    @staticmethod
    def _same(a, b):
        from scrapers.merge import same_event
        return same_event(a, b)
