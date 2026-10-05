"""Reactivación de base de datos: convierte clientes antiguos en citas nuevas.

Es la oferta de entrada más rentable de la agencia: el negocio ya tiene
cientos o miles de contactos que no vuelven. La IA redacta un mensaje
personalizado por contacto (SMS/WhatsApp/email) a partir de su historial.
Se suele cobrar por resultado (p. ej. 50-100 € por cita conseguida).
"""
import csv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .. import db, llm
from ..config import cargar_cliente


class MensajeReactivacion(BaseModel):
    contacto: str = Field(description="Nombre del contacto tal y como viene en el CSV")
    canal: Literal["whatsapp", "sms", "email"]
    asunto: str = Field(description="Solo para email; vacío en otros canales")
    mensaje: str
    prioridad: Literal["alta", "media", "baja"]
    motivo_prioridad: str


class LoteReactivacion(BaseModel):
    mensajes: list[MensajeReactivacion]


SISTEMA = """Eres copywriter experto en reactivación de clientes para negocios locales.
Escribes mensajes cortos, cercanos y personales que suenan escritos por una persona del negocio,
nunca como publicidad masiva. Cumplen el RGPD: solo a contactos con consentimiento, e incluyen
una forma sencilla de darse de baja ("responde BAJA si no quieres más mensajes").
Estructura que mejor convierte: saludo por nombre + referencia a su último servicio + motivo
para volver ahora (oferta o novedad real del negocio) + pregunta de sí/no fácil de responder.
WhatsApp/SMS: máximo 320 caracteres. Email: asunto de menos de 50 caracteres y cuerpo de menos de 120 palabras.
Prioridad alta = alto valor histórico o tratamiento que requiere mantenimiento periódico."""


def leer_contactos(ruta_csv: str | Path) -> list[dict]:
    with open(ruta_csv, newline="", encoding="utf-8") as f:
        return [fila for fila in csv.DictReader(f)]


def generar(cliente_id: str, contactos: list[dict], campana: str, tam_lote: int = 25) -> list[MensajeReactivacion]:
    negocio = cargar_cliente(cliente_id)
    resultado: list[MensajeReactivacion] = []
    for i in range(0, len(contactos), tam_lote):
        lote = contactos[i:i + tam_lote]
        lineas = "\n".join(", ".join(f"{k}={v}" for k, v in c.items()) for c in lote)
        prompt = f"""Negocio: {negocio['nombre']} ({negocio['sector']}, {negocio['ubicacion']}). Tono: {negocio['tono']}.
Firma como: {negocio['asistente']} de {negocio['nombre']}.
Oferta de la campaña "{campana}": {negocio.get('oferta_reactivacion') or negocio.get('oferta_actual', 'sin oferta')}.
Servicios: {', '.join(s['nombre'] for s in negocio['servicios'])}.

Escribe un mensaje para CADA uno de estos {len(lote)} contactos (usa el canal preferido si viene; si no, whatsapp si hay teléfono, si no email):
{lineas}"""
        salida = llm.estructurado(SISTEMA, prompt, LoteReactivacion)
        for m in salida.mensajes:
            db.insertar("mensajes_campana", {
                "cliente_id": cliente_id, "campana": campana, "contacto": m.contacto,
                "canal": m.canal, "mensaje": (m.asunto + "\n\n" if m.asunto else "") + m.mensaje,
                "creado": db.ahora(),
            })
        resultado.extend(salida.mensajes)
    return resultado


def exportar_csv(mensajes: list[MensajeReactivacion], ruta: str | Path) -> None:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(MensajeReactivacion.model_fields))
        w.writeheader()
        for m in mensajes:
            w.writerow(m.model_dump())
