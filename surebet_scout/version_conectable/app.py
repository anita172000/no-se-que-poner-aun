"""Demo: usa proveedores simulados. Cambia SimulatedProvider por tus adaptadores oficiales."""
import sys
from core import Quote, find_surebet
from executor import Executor
from providers import SimulatedProvider


def main():
    ev = "Evento demo"
    a = SimulatedProvider("op_a", [Quote("op_a", ev, "A", 2.15), Quote("op_a", ev, "B", 1.80)])
    b = SimulatedProvider("op_b", [Quote("op_b", ev, "A", 1.85), Quote("op_b", ev, "B", 2.20)])
    provs = [a, b]
    best = {}
    for p in provs:
        for q in p.get_quotes(ev):
            if q.selection not in best or q.odds > best[q.selection].odds:
                best[q.selection] = q
    opp = find_surebet(list(best.values()), budget=40, commission=0.0)
    if not opp:
        return print("Sin oportunidad.")
    print(f"Margen {opp.margin:.2%}, beneficio teórico {opp.profit}")
    print(Executor(provs).execute(opp) if "--live" not in sys.argv
          else Executor(provs, live=True).execute(opp))


if __name__ == "__main__":
    main()
