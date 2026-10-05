"""Respuestas a reseñas de Google y solicitud de reseñas tras cada cita."""
from pydantic import BaseModel

from .. import llm
from ..config import cargar_cliente


class RespuestaResena(BaseModel):
    sentimiento: str
    respuesta: str
    requiere_atencion_humana: bool
    motivo: str


SISTEMA = """Respondes reseñas en nombre de un negocio local. Agradece de forma específica (menciona algo
concreto de la reseña), sin copiar y pegar fórmulas. Reseñas negativas: empatía, sin excusas ni datos
personales o de salud, invita a continuar por teléfono. Máximo 80 palabras. Marca requiere_atencion_humana
si hay amenaza legal, problema de salud o acusación grave."""


def responder(cliente_id: str, autor: str, estrellas: int, texto: str) -> RespuestaResena:
    n = cargar_cliente(cliente_id)
    prompt = f"Negocio: {n['nombre']} ({n['sector']}). Teléfono: {n['telefono']}. Firma: Equipo de {n['nombre']}.\n" \
             f"Reseña de {autor} ({estrellas}/5): {texto}"
    return llm.estructurado(SISTEMA, prompt, RespuestaResena, esfuerzo="low")


def mensaje_pedir_resena(cliente_id: str, nombre: str, servicio: str) -> str:
    n = cargar_cliente(cliente_id)
    enlace = n.get("enlace_resenas", "")
    return (f"¡Hola {nombre}! Gracias por venir hoy a {n['nombre']} para tu {servicio.lower()}. "
            f"¿Nos ayudas con una reseña de 30 segundos? Nos ayuda muchísimo: {enlace}")
