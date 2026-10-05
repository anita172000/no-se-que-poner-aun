"""Persistencia mínima en SQLite: leads, citas, conversaciones y campañas."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from . import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id TEXT NOT NULL,
    nombre TEXT, telefono TEXT, email TEXT,
    interes TEXT, presupuesto TEXT, urgencia TEXT,
    puntuacion INTEGER DEFAULT 0,
    estado TEXT DEFAULT 'nuevo',
    origen TEXT DEFAULT 'chat',
    notas TEXT,
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS citas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id TEXT NOT NULL,
    lead_id INTEGER,
    servicio TEXT NOT NULL,
    inicio TEXT NOT NULL,
    estado TEXT DEFAULT 'confirmada',
    creado TEXT NOT NULL,
    UNIQUE (cliente_id, inicio)
);
CREATE TABLE IF NOT EXISTS conversaciones (
    id TEXT PRIMARY KEY,
    cliente_id TEXT NOT NULL,
    lead_id INTEGER,
    historial TEXT NOT NULL,
    escalada INTEGER DEFAULT 0,
    actualizado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mensajes_campana (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id TEXT NOT NULL,
    campana TEXT NOT NULL,
    contacto TEXT NOT NULL,
    canal TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    estado TEXT DEFAULT 'pendiente',
    creado TEXT NOT NULL
);
"""


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def conexion():
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(ESQUEMA)
        yield con
        con.commit()
    finally:
        con.close()


def filas(sql: str, params: tuple = ()) -> list[dict]:
    with conexion() as con:
        return [dict(f) for f in con.execute(sql, params).fetchall()]


def insertar(tabla: str, datos: dict) -> int:
    cols = ", ".join(datos)
    marcas = ", ".join("?" for _ in datos)
    with conexion() as con:
        cur = con.execute(f"INSERT INTO {tabla} ({cols}) VALUES ({marcas})", tuple(datos.values()))
        return cur.lastrowid


def actualizar(tabla: str, id_: int, datos: dict) -> None:
    sets = ", ".join(f"{c} = ?" for c in datos)
    with conexion() as con:
        con.execute(f"UPDATE {tabla} SET {sets} WHERE id = ?", (*datos.values(), id_))


def cargar_conversacion(conv_id: str) -> dict | None:
    res = filas("SELECT * FROM conversaciones WHERE id = ?", (conv_id,))
    if not res:
        return None
    conv = res[0]
    conv["historial"] = json.loads(conv["historial"])
    return conv


def guardar_conversacion(conv_id: str, cliente_id: str, historial: list, lead_id=None, escalada=False) -> None:
    with conexion() as con:
        con.execute(
            """INSERT INTO conversaciones (id, cliente_id, lead_id, historial, escalada, actualizado)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET lead_id = COALESCE(excluded.lead_id, lead_id),
                 historial = excluded.historial, escalada = MAX(escalada, excluded.escalada),
                 actualizado = excluded.actualizado""",
            (conv_id, cliente_id, lead_id, json.dumps(historial, ensure_ascii=False), int(escalada), ahora()),
        )
