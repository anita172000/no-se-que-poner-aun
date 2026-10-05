"""Configuración global leída de variables de entorno."""
import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELO = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
DB_PATH = os.environ.get("DB_PATH", str(RAIZ / "datos" / "agencia.db"))
PANEL_TOKEN = os.environ.get("PANEL_TOKEN", "cambia-esto")
DIR_CLIENTES = RAIZ / "clientes"


def cargar_cliente(cliente_id: str) -> dict:
    """Carga la ficha de un negocio cliente (clientes/<id>.json)."""
    ruta = DIR_CLIENTES / f"{cliente_id}.json"
    if not ruta.is_file() or ruta.parent != DIR_CLIENTES:
        raise KeyError(f"Cliente desconocido: {cliente_id}")
    return json.loads(ruta.read_text(encoding="utf-8"))


def listar_clientes() -> list[str]:
    return sorted(p.stem for p in DIR_CLIENTES.glob("*.json"))
