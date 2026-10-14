"""Contrato de proveedor + proveedores incluidos.

Un adaptador real debe usar la API OFICIAL del operador, leer sus claves de
variables de entorno y NUNCA guardarlas en disco ni en logs.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from core import Quote


@dataclass
class OrderResult:
    accepted: bool
    reference: str
    matched_odds: float
    matched_stake: float
    message: str = ""


class BettingProvider(ABC):
    name = "base"

    @abstractmethod
    def get_quotes(self, event: str) -> list: ...

    @abstractmethod
    def get_balance(self) -> float: ...

    @abstractmethod
    def place_order(self, quote: Quote, stake: float) -> OrderResult:
        """Debe ser orden con cuota mínima: rechazar si la cuota ya empeoró."""


class DisabledProvider(BettingProvider):
    name = "disabled"

    def get_quotes(self, event): return []
    def get_balance(self): return 0.0

    def place_order(self, quote, stake):
        return OrderResult(False, "", 0.0, 0.0, "Proveedor deshabilitado.")


class SimulatedProvider(BettingProvider):
    """Saldo virtual real: descuenta stakes y registra órdenes."""

    def __init__(self, name, quotes, balance=1000.0):
        self.name, self._quotes, self.balance, self.orders = name, quotes, balance, []

    def get_quotes(self, event): return [q for q in self._quotes if q.event == event]
    def get_balance(self): return self.balance

    def place_order(self, quote, stake):
        if stake > self.balance:
            return OrderResult(False, "", 0.0, 0.0, "Saldo insuficiente.")
        self.balance -= stake
        ref = f"SIM-{len(self.orders) + 1}"
        self.orders.append((ref, quote, stake, datetime.now(timezone.utc).isoformat()))
        return OrderResult(True, ref, quote.odds, stake, "Simulada.")


class OfficialApiProvider(BettingProvider):
    """PLANTILLA para un operador con API oficial (Betfair, Pinnacle, ...).

    Implementa los 3 métodos con su SDK/endpoints documentados. Claves por
    entorno (p. ej. OPERADOR_APP_KEY, OPERADOR_TOKEN). Sin scraping ni login web.
    """
    name = "official-api"

    def get_quotes(self, event): raise NotImplementedError
    def get_balance(self): raise NotImplementedError
    def place_order(self, quote, stake): raise NotImplementedError
