"""Detector puro de surebets. No conoce operadores ni órdenes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    provider: str      # nombre del adaptador
    event: str
    selection: str
    odds: float        # cuota decimal
    market_id: str = ""
    selection_id: str = ""


@dataclass(frozen=True)
class Opportunity:
    event: str
    legs: tuple        # tuple[(Quote, stake)]
    margin: float      # beneficio teórico / presupuesto, antes de comisiones
    budget: float

    @property
    def profit(self) -> float:
        q, s = self.legs[0]
        return round(q.odds * s - self.budget, 2)


def find_surebet(best_quotes, budget, commission=0.0):
    """best_quotes: una Quote por resultado excluyente (la mejor cuota de cada uno).
    commission: fracción sobre ganancias (p. ej. 0.02) para descontar de la cuota."""
    if budget <= 0 or len(best_quotes) < 2:
        raise ValueError("Presupuesto positivo y al menos 2 resultados.")
    eff = []
    for q in best_quotes:
        if q.odds <= 1.0:
            raise ValueError("Cuota decimal debe ser > 1.")
        eff.append(1 + (q.odds - 1) * (1 - commission))
    total = sum(1 / o for o in eff)
    if total >= 1:
        return None
    legs = tuple((q, round(budget / o / total, 2)) for q, o in zip(best_quotes, eff))
    return Opportunity(best_quotes[0].event, legs, round(1 / total - 1, 6), budget)
