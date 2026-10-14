"""Lectores gratuitos de cuotas leídas directamente de las casas.

Cada lector devuelve eventos en el formato normalizado de core (ver core.py).
Solo LEEN cuotas públicas, despacio y con pausas; nunca inician sesión en las
casas ni apuestan. Betfair se lee por su API oficial con tu cuenta.
"""
