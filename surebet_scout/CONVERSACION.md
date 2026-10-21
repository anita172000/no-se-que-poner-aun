# Surebet Scout: resumen de la conversación

Resumen de todo lo hablado y construido con Claude en esta sesión.
Repositorio: `anita172000/no-se-que-poner-aun`, rama `claude/new-session-drnz2y`, carpeta `surebet_scout/`.

---

## 1. Punto de partida

- Se subió un resumen (`surebet_scout_resumen.md`) y un ZIP con dos versiones de un detector de surebets:
  - `version_simulada/`: script de consola con cálculo teórico y órdenes ficticias.
  - `version_integracion_preparada/`: interfaz abstracta con un proveedor deshabilitado.
- Se revisó el ZIP (funcionaba) y se añadió al repositorio en `surebet_scout/`.

## 2. Qué se pidió y qué se decidió

| Petición | Decisión |
|---|---|
| Que el programa inicie sesión en las casas y haga las surebets solo | Solo se automatiza **Betfair Exchange**, por su **API oficial**. El resto de casas no tiene API de apuestas para particulares; automatizar su web con usuario y contraseña va contra sus condiciones y acaba en cierre de cuenta. Esas apuestas se hacen a mano, guiadas por la web. |
| Que funcione con todas las casas españolas | Primero con odds-api.io (de pago). Después, a petición del usuario, **gratis**, leyendo las cuotas públicas de cada casa. |
| Una web visual con todo | Hecha (ver apartado 3). |
| Integrar BetOven Scanner | No tiene API ni exportación y sus condiciones prohíben la ingeniería inversa. **No se destripa el programa.** Se hizo un formulario para meter sus surebets a mano. Opciones pendientes: "Pegar de BetOven" si deja copiar texto, o lectura de su pantalla (OCR) con capturas. |
| Repartir importes para que no detecten | Ayudas para cuidar las cuentas (importes redondos, avisos). No se ayuda con cuentas ajenas, varias cuentas en la misma casa ni VPN (es fraude según las casas). |
| Todos los porcentajes, todos los mercados, todos los deportes, ordenado por % | Hecho: sin tope de margen, mínimo 0 %, todos los mercados y líneas, orden por % de beneficio. |
| No pagar la API de cuotas | Lectores gratuitos de las webs de las casas. |

## 3. Lo que está construido: `surebet_scout/version_conectable/`

Web local (FastAPI + HTML/JS) en `http://127.0.0.1:8050`.

### Pestañas
- **Inicio:** modo (simulación o real), fuente de cuotas, saldo de Betfair, gasto del día, beneficio y lista de configuración.
- **Oportunidades:**
  - Surebets ordenadas por % de beneficio, € de beneficio o fecha.
  - Filtros por % mínimo, tipo de mercado y deporte.
  - Búsqueda automática cada 60 s.
  - Formulario para añadir surebets de BetOven u otro escáner.
- **Operaciones:** guía paso a paso.
  1. Primero las apuestas manuales, anotando la cuota real conseguida. Los importes pendientes se reequilibran solos.
  2. Al final, Betfair automático: cuota en vivo, confirmación escribiendo **SI** y orden "todo o nada" (FILL_OR_KILL).
  3. Beneficio por resultado y aviso de riesgo abierto.
- **Historial:** operaciones, liquidación, exportación a CSV y tabla **"Tus casas"** con beneficio y volumen por casa.
- **Ajustes:** casas, comisiones, deportes ("todos"), mercados ("todos" o "principales"), límites de dinero, redondeo y avisos de cuidado de cuentas.
- **Guía:** de dónde salen las cuotas, Betfair, modo real, casas sin API, BetOven, cuidado de cuentas y riesgos.

### De dónde salen las cuotas (`SUREBET_FEED` en `.env`)
- `webs` (por defecto, gratis):
  - **PAF ES y LeoVegas ES** (plataforma Kambi): todos los mercados.
  - **Betway ES**: todos los mercados.
  - **Betfair Exchange**: cuotas por su API oficial si se ponen las claves.
  - Funciona en dos fases: primero la lista de partidos de cada casa y después todos los mercados solo de los partidos que están en dos o más plataformas.
  - Probado con datos reales: unos 1.300 partidos listados y 158 mercados cruzados entre PAF/LeoVegas y Betway. En ese momento no había surebet (la mejor combinación daba -3,2 %).
- `odds-api`: servicio de pago odds-api.io (necesita `ODDS_API_KEY`).
- `demo`: datos de ejemplo.

### Reglas de seguridad del detector
- Solo se comparan grupos de resultados que cubren **todas** las posibilidades:
  - 1X2, local/visitante, más/menos de una línea;
  - sí/no, par/impar, local/visitante/ninguno;
  - doble oportunidad contra el 1X2 del mismo periodo.
- Se descartan "resultado exacto", "goleador" y otros mercados con un precio por opción.
- Emparejado **estricto** de mercados entre casas. Ejemplos de lo que nunca se mezcla:
  - ganador frente a empate no válido o primer gol;
  - goles frente a tiros o tarjetas;
  - tiempo reglamentario frente a prórroga;
  - el "1X2 con 1 gol de ventaja".
- En fútbol, un "ganador" sin empate nunca cuenta como surebet.
- El mismo partido solo se une entre casas si coinciden deporte, hora (±20 min) y los dos equipos (en el mismo orden).

### Salvaguardas de dinero
- Simulación por defecto. Para apostar de verdad hacen falta `SUREBET_LIVE=1` y las claves de Betfair.
- Confirmación **SI** en cada apuesta de Betfair. La cuota preparada caduca a los 60 s.
- Hay que aceptar de forma explícita si la cuota empeora o habría pérdida.
- Límites por operación y por día. Mínimo de Betfair: 2 €.
- Estado "desconocido" si se corta la conexión al apostar: no se reintenta hasta comprobarlo en Betfair.
- La web solo escucha en tu ordenador (127.0.0.1). Las claves solo están en `.env`.

### Archivos principales
`core.py` (detector) · `feeds.py` (odds-api.io y datos de ejemplo) · `scrapers/` (Kambi, Betway, cuotas de Betfair, unión de partidos, feed por fases) · `betfair.py` y `exchange.py` (apuestas en Betfair) · `service.py` (operaciones) · `store.py` (SQLite) · `web.py` · `static/` · `tests/` (41 tests) · `herramientas/capturar_casas.py` · `Iniciar.bat` · `Capturar_casas.bat`.

## 4. Casas que faltan y por qué

Codere, Bwin, Luckia, Sportium, Retabet, Winamax, Bet365, Kirolbet, Marca Apuestas y otras **bloquean las conexiones de fuera de España**, comprobado una a una. Claude trabaja desde un servidor fuera de España, así que sus lectores hay que escribirlos desde el ordenador del usuario. Hay dos vías:

1. **Windows:** `Iniciar.bat` hace la captura de casas la primera vez y deja `captura_casas_....zip` en el Escritorio. Ese archivo se pasa a Claude.
2. **Claude Code en Ubuntu (WSL)**, recomendado: escribe los lectores él mismo desde España. Se le dio un prompt completo con estos pasos:
   - preparar el entorno;
   - capturar las casas;
   - escribir un lector por casa con emparejado estricto y tests;
   - respetar los límites (solo lectura, sin iniciar sesión, sin saltarse anti-bots, peticiones lentas);
   - hacer commit y push.
   - Para el push: configurar `gh auth login` (opción A) o generar un `.patch` y pasárselo a Claude (opción B).

## 5. Cómo abrir el programa

**Windows**
1. Instalar Python desde python.org marcando "Add python.exe to PATH".
2. Descargar `https://github.com/anita172000/no-se-que-poner-aun/archive/refs/heads/claude/new-session-drnz2y.zip` y extraerlo.
3. Abrir `surebet_scout/version_conectable/Iniciar.bat` con doble clic.

**Ubuntu**
- En `surebet_scout/version_conectable` ejecutar `.venv/bin/python app.py`.

**Betfair (cuando haya cuenta y App Key)**
- Rellenar en `.env`, con el Bloc de notas: `BETFAIR_APP_KEY=`, `BETFAIR_USERNAME=` y `BETFAIR_PASSWORD=`.
- Para apostar de verdad: `SUREBET_LIVE=1`.

## 6. Notas legales comentadas (orientativas, no son asesoramiento)

- **AI Act (Reglamento UE 2024/1689):**
  - No regula en concreto la automatización de pagos ni el acceso a casas de apuestas o bancos.
  - El uso personal y no profesional está excluido (art. 2.10).
  - Un programa de reglas fijas probablemente ni es "sistema de IA" (art. 3.1 y considerando 12).
  - En banca solo es alto riesgo la evaluación de solvencia (Anexo III, 5.b).
  - El Digital Omnibus (junio de 2026) retrasa el alto riesgo del Anexo III al 2 de diciembre de 2027.
- **Bancos:** PSD2 y sus normas de autenticación reforzada. Los terceros necesitan licencia y APIs oficiales; para uso propio mandan las condiciones del banco.
- **Casas de apuestas:**
  - La Ley 13/2011 y la DGOJ regulan a los operadores.
  - Las condiciones de cada casa prohíben bots y arbitraje; la consecuencia es contractual (limitación, cierre o anulación).
  - Betfair permite la API oficial.
- **Leer cuotas de webs:** puede chocar con el derecho sui generis sobre bases de datos (Directiva 96/9/CE). Para uso personal y moderado, el riesgo práctico es que bloqueen el acceso.

## 7. Pendiente

- [ ] Que el Claude Code de Ubuntu escriba los lectores de las casas bloqueadas y los suba a la rama. Después, revisarlos aquí (emparejado de mercados).
- [ ] Cuenta y App Key de Betfair y ponerlas en `.env`.
- [ ] BetOven: mandar capturas del visualizador y, si se puede copiar, el texto, para hacer "Pegar de BetOven" o la lectura por pantalla.
- [ ] Contenido de la carpeta `\\wsl.localhost\Ubuntu\home\anita\analisis` (Claude no puede abrirla desde la nube): pasar los archivos o subirlos al repo.
