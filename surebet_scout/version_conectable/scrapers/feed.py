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
        groups, warnings = [], []

        def run(item):
            name, src = item
            return name, src.fetch(sports, bookmakers, hours_ahead, max_events)

        # Cada fuente va a un servidor distinto: se leen a la vez.
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.sources) or 1) as pool:
            for name, (events, errors) in pool.map(run, self.sources):
                groups.append(events)
                warnings += errors
                self.last[name] = {"events": len(events), "errors": errors}
        if not any(groups) and warnings:
            raise FeedError("; ".join(warnings))
        merged = merge_events(groups)
        if markets:
            for ev in merged:
                ev["markets"] = {k: m for k, m in ev["markets"].items() if m["name"] in markets}
        self.warnings = warnings
        return merged
