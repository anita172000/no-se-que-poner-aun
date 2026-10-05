"""Envoltorio fino sobre el SDK de Anthropic.

- Usa siempre el cliente beta para activar `fallbacks: "default"`: si los
  clasificadores de seguridad rechazan una petición legítima, la API la
  reintenta automáticamente con el modelo de respaldo recomendado.
- Comprueba `stop_reason == "refusal"` antes de leer el contenido.
"""
from typing import Type, TypeVar

import anthropic
from pydantic import BaseModel

from .config import MODELO

BETAS = ["server-side-fallback-2026-07-01"]
T = TypeVar("T", bound=BaseModel)

_cliente: anthropic.Anthropic | None = None


class RechazoIA(RuntimeError):
    """El modelo declinó la petición (stop_reason == 'refusal')."""


def cliente() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic()
    return _cliente


def _comprobar(respuesta) -> None:
    if respuesta.stop_reason == "refusal":
        detalle = getattr(respuesta, "stop_details", None)
        raise RechazoIA(f"La IA declinó la petición: {detalle}")


def mensaje(**kwargs):
    """Llamada genérica (se usa en el bucle de herramientas del agente)."""
    kwargs.setdefault("model", MODELO)
    kwargs.setdefault("max_tokens", 16000)
    respuesta = cliente().beta.messages.create(betas=BETAS, fallbacks="default", **kwargs)
    _comprobar(respuesta)
    return respuesta


def estructurado(sistema: str, prompt: str, esquema: Type[T], esfuerzo: str = "medium") -> T:
    """Devuelve una instancia validada de `esquema` (salidas estructuradas)."""
    respuesta = cliente().beta.messages.parse(
        model=MODELO,
        max_tokens=16000,
        betas=BETAS,
        fallbacks="default",
        system=sistema,
        messages=[{"role": "user", "content": prompt}],
        output_format=esquema,
        output_config={"effort": esfuerzo},
    )
    _comprobar(respuesta)
    return respuesta.parsed_output


def texto(respuesta) -> str:
    return "".join(b.text for b in respuesta.content if b.type == "text").strip()
