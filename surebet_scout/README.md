# Surebet Scout — dos versiones

Este proyecto contiene dos variantes educativas:

- `version_simulada/`: análisis de surebets con órdenes y saldo virtual.
- `version_integracion_preparada/`: misma lógica de análisis con una interfaz abstracta para un proveedor autorizado, pero sin conexión real ni ejecución de apuestas.

## Requisitos
Python 3.10+

## Ejecutar la versión simulada
```bash
cd version_simulada
python app.py
```

## Ejecutar la versión preparada
```bash
cd version_integracion_preparada
python app.py
```

Ambas versiones son de consola y usan datos de ejemplo. No inician sesión en casas de apuestas, no se conectan a operadores y no mueven dinero.

- `version_conectable/`: motor con ejecución real opcional vía API oficial, con salvaguardas (ver su README).
