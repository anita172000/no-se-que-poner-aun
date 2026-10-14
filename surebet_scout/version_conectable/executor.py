"""Ejecuta oportunidades con salvaguardas. Separado del detector."""
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Limits:
    min_margin: float = 0.01      # margen mínimo tras comisiones
    max_budget: float = 50.0      # presupuesto máximo por surebet
    max_daily_budget: float = 200.0


class Executor:
    def __init__(self, providers, limits=None, live=False, confirm=input,
                 ledger=Path("ledger.jsonl")):
        self.providers = {p.name: p for p in providers}
        self.limits = limits or Limits()
        self.live = live and os.environ.get("SUREBET_LIVE") == "1"
        self.confirm, self.ledger, self.spent = confirm, Path(ledger), 0.0

    def _log(self, kind, **data):
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **data}
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def execute(self, opp):
        self._log("opportunity", event=opp.event, margin=opp.margin, budget=opp.budget,
                  legs=[(asdict(q), s) for q, s in opp.legs])
        if opp.margin < self.limits.min_margin:
            return self._skip("margen insuficiente")
        if opp.budget > self.limits.max_budget:
            return self._skip("presupuesto > límite por operación")
        if self.spent + opp.budget > self.limits.max_daily_budget:
            return self._skip("límite diario superado")
        if not self.live:
            return self._skip("modo prueba (sin --live y SUREBET_LIVE=1): no se envía nada")
        if self.confirm(f"Apostar {opp.budget} en '{opp.event}' (beneficio teórico "
                        f"{opp.profit})? escribe SI: ").strip() != "SI":
            return self._skip("rechazado por el usuario")

        placed = []
        # Primero la pierna con mayor stake; si falla, se aborta antes de cubrir el resto.
        for quote, stake in sorted(opp.legs, key=lambda l: -l[1]):
            res = self.providers[quote.provider].place_order(quote, stake)
            self._log("order", provider=quote.provider, selection=quote.selection,
                      stake=stake, **asdict(res))
            if not res.accepted or res.matched_odds < quote.odds:
                self._log("EXPOSURE", placed=[r.reference for r in placed],
                          failed=quote.selection, message=res.message)
                return {"ok": False, "exposed": bool(placed),
                        "reason": f"pierna fallida: {quote.selection} ({res.message}). "
                                  f"Hay {len(placed)} piernas ya apostadas: cubrir a mano."}
            placed.append(res)
        self.spent += opp.budget
        return {"ok": True, "refs": [r.reference for r in placed]}

    def _skip(self, reason):
        self._log("skipped", reason=reason)
        return {"ok": False, "exposed": False, "reason": reason}
