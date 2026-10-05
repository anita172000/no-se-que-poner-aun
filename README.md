# Respuesta 60 · Agencia de automatización con IA

Agencia lista para trabajar en el nicho más rentable para empezar: **captación y conversión de leads con IA
para negocios locales de alto ticket** (clínicas estéticas y dentales primero).

Abre **`index.html`** (o `http://localhost:8000/` con el servidor arrancado) para ver la explicación completa:
nicho, servicios, precios, calculadora de ROI, captación de clientes, entrega y escalado.

## Qué incluye
- **Software** (`app/`): recepcionista IA 24/7 con reserva de citas, widget de chat embebible, webhook de leads,
  seguimiento automático, reactivación de bases de datos, respuestas a reseñas, panel de resultados,
  auditor de prospectos y generador de propuestas. Usa la API de Claude.
- **Negocio** (`docs/`): estrategia y nicho, oferta y precios, prospección, guion de ventas,
  SOP de entrega en 14 días, plantilla de contrato, métricas, cumplimiento y escalado.
- **Ejemplos** (`clientes/clinica-lumiere.json`, `ejemplos/`).

## Arranque rápido
```bash
pip install -r requirements.txt
cp .env.example .env              # añade tu ANTHROPIC_API_KEY y cambia PANEL_TOKEN
export $(cat .env | xargs)
uvicorn app.main:app --reload
```
- Demo del chat: http://localhost:8000/demo/clinica-lumiere
- Panel: http://localhost:8000/panel?token=TU_PANEL_TOKEN

Con Docker: `docker build -t agencia . && docker run -p 8000:8000 --env-file .env agencia`

## Línea de comandos
```bash
python cli.py chat clinica-lumiere
python cli.py reactivar clinica-lumiere ejemplos/contactos_ejemplo.csv --campana otono
python cli.py auditar ejemplos/prospecto_ejemplo.txt --ticket 1500 --leads 80
python cli.py propuesta notas.txt --negocio "Clínica X" --leads 80 --ticket 1500
python cli.py roi --leads 60 --ticket 300
python cli.py seguimiento clinica-lumiere
```

## Añadir un cliente
Copia `clientes/clinica-lumiere.json` a `clientes/<id>.json`, rellena sus datos y pega en su web:
```html
<script src="https://TU-DOMINIO/static/widget.js" data-cliente="<id>" data-color="#0b7a68"></script>
```

## Pruebas
```bash
pip install -r requirements-dev.txt && pytest
```
Las pruebas simulan las respuestas de Claude, así que no necesitan clave de API.
