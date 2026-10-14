# Versión conectable (ejecución real opcional)

Motor: `core.py` (detector puro) → `executor.py` (salvaguardas + ejecución) → `providers.py` (adaptadores).

## Conectar una casa
Solo mediante **API oficial** del operador (Betfair Exchange, Pinnacle, etc.):
1. Obtén tus claves de API en el operador (cuenta propia, términos aceptados).
2. Implementa `OfficialApiProvider.get_quotes/get_balance/place_order` con su SDK.
   Claves en variables de entorno; nunca en el código ni en el `ledger`.
3. `place_order` debe enviar orden con **cuota mínima** y devolver la cuota realmente casada.

No se incluye login web, scraping ni automatización de navegador (prohibido en la mayoría de términos y causa de cierre de cuentas).

## Salvaguardas
- Por defecto solo prueba: nada se envía sin `live=True` **y** `SUREBET_LIVE=1`.
- Confirmación humana (`SI`) por cada surebet.
- Límites: margen mínimo, presupuesto por operación y diario.
- Comisión descontada en el cálculo.
- Si una pierna falla tras apostar otras, se registra `EXPOSURE` y se avisa: queda riesgo abierto, cubrir a mano.
- `ledger.jsonl` registra oportunidades, órdenes y omisiones.

Las surebets no son riesgo cero: cuotas que cambian, límites de apuesta, rechazos y restricciones de cuenta son habituales.

`python app.py` (demo simulada) · `pytest tests`
