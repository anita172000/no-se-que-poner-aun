"""Demo de surebets con ejecución 100% simulada."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path

STARTING_BALANCE = 1000.0
ORDERS_FILE = Path("orders.json")

@dataclass
class SimulatedOrder:
    event: str
    outcome: str
    bookmaker_label: str
    odds: float
    stake: float
    status: str = "SIMULATED"
    created_at: str = ""

def implied_probability(odds: float) -> float:
    if odds <= 1.0:
        raise ValueError("Las cuotas decimales deben ser mayores que 1.")
    return 1.0 / odds

def find_two_way_surebet(event: str, outcome_a: str, odds_a: float,
                         outcome_b: str, odds_b: float, budget: float = 100.0):
    if budget <= 0:
        raise ValueError("El presupuesto debe ser positivo.")
    total = implied_probability(odds_a) + implied_probability(odds_b)
    if total >= 1:
        return None
    stake_a = budget * implied_probability(odds_a) / total
    stake_b = budget * implied_probability(odds_b) / total
    payout = stake_a * odds_a
    return {
        "event": event,
        "implied_probability_sum": round(total, 6),
        "stake_a": round(stake_a, 2),
        "stake_b": round(stake_b, 2),
        "guaranteed_payout_before_fees": round(payout, 2),
        "theoretical_profit_before_fees": round(payout - budget, 2),
        "warning": "Cálculo teórico: no considera cambios de cuota, límites, comisiones ni aceptación parcial."
    }

def save_orders(orders):
    ORDERS_FILE.write_text(json.dumps([asdict(o) for o in orders], indent=2), encoding="utf-8")

def main():
    print("=== Surebet Scout: simulación ===")
    print("Solo datos ficticios; no se envían órdenes externas.\n")
    event = "Evento de demostración"
    odds_a, odds_b = 2.10, 2.10
    result = find_two_way_surebet(event, "Resultado A", odds_a, "Resultado B", odds_b, 100)
    if result is None:
        print("No se detectó oportunidad teórica.")
        return
    print(json.dumps(result, indent=2, ensure_ascii=False))
    now = datetime.now(timezone.utc).isoformat()
    orders = [
        SimulatedOrder(event, "Resultado A", "Operador ficticio A", odds_a, result["stake_a"], created_at=now),
        SimulatedOrder(event, "Resultado B", "Operador ficticio B", odds_b, result["stake_b"], created_at=now),
    ]
    save_orders(orders)
    print(f"\nGuardadas {len(orders)} órdenes ficticias en {ORDERS_FILE.resolve()}")
    print("Saldo virtual inicial:", STARTING_BALANCE)

if __name__ == "__main__":
    main()
