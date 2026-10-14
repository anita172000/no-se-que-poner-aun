"""Adaptadores para la pata automática (exchange).

Mismo contrato para el simulado y el real:
    status() -> dict
    quote(op, leg) -> dict con market_id, selection_id, price, size_available...
    place(quote, stake, ref) -> dict(ok, matched, avg_price, bet_id, message)
"""
from betfair import BetfairClient, BetfairError, BetfairNetworkError


class SimulatedExchange:
    live = False
    label = "Betfair simulado"

    def __init__(self, store, start_balance=1000.0):
        self.store, self.start_balance = store, start_balance

    def balance(self):
        return round(self.start_balance - float(self.store.get_kv("sim_spent", 0.0)), 2)

    def status(self, refresh=False):
        return {"live": False, "connected": True, "label": self.label,
                "balance": self.balance(), "error": ""}

    def quote(self, op, leg):
        return {"market_id": "SIM", "selection_id": leg["outcome"],
                "event_name": f"{op['home']} v {op['away']}", "market_name": "Match Odds",
                "runner_name": leg["label"], "price": leg["planned_odds"],
                "size_available": 9999.0, "match_score": 1.0}

    def place(self, quote, stake, ref):
        if stake > self.balance():
            return {"ok": False, "matched": 0.0, "avg_price": 0.0, "bet_id": "",
                    "message": "Saldo virtual insuficiente."}
        self.store.set_kv("sim_spent", float(self.store.get_kv("sim_spent", 0.0)) + stake)
        return {"ok": True, "matched": stake, "avg_price": quote["price"],
                "bet_id": f"SIM-{ref}", "message": "Simulada: no se ha enviado nada."}


class BetfairExchange:
    live = True
    label = "Betfair Exchange (REAL)"

    def __init__(self, client: BetfairClient, min_stake=2.0):
        self.client, self.min_stake = client, min_stake
        self._last = {"live": True, "connected": False, "label": self.label,
                      "balance": None, "error": "Sin comprobar todavía."}

    def status(self, refresh=False):
        if refresh:
            try:
                self._last = {**self._last, "connected": True, "error": "",
                              "balance": self.client.balance()}
            except BetfairError as exc:
                self._last = {**self._last, "connected": False, "error": str(exc)}
        return self._last

    def quote(self, op, leg):
        sel = self.client.find_selection(op["home"], op["away"], op["date"], leg["outcome"])
        price, size = self.client.best_back(sel["market_id"], sel["selection_id"])
        return {**sel, "price": price, "size_available": size}

    def place(self, quote, stake, ref):
        if stake < self.min_stake:
            return {"ok": False, "matched": 0.0, "avg_price": 0.0, "bet_id": "",
                    "message": f"Betfair exige un mínimo de {self.min_stake} €."}
        try:
            return self.client.place_back_fok(quote["market_id"], quote["selection_id"],
                                              quote["price"], stake, ref)
        except BetfairNetworkError as exc:
            # La orden pudo llegar a Betfair aunque falle la respuesta: estado desconocido.
            return {"ok": False, "unknown": True, "matched": 0.0, "avg_price": 0.0,
                    "bet_id": "", "message": str(exc)}
        except BetfairError as exc:
            return {"ok": False, "matched": 0.0, "avg_price": 0.0, "bet_id": "",
                    "message": str(exc)}
