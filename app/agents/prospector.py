"""Prospección de la propia agencia: auditoría + secuencia de contacto en frío.

A partir de los datos públicos de un negocio (web, reseñas, redes...) genera
una mini-auditoría con las fugas de dinero detectadas y una secuencia de
3 emails + 1 DM personalizados para conseguir una llamada de diagnóstico.
"""
from pydantic import BaseModel, Field

from .. import llm
from ..roi import calcular_roi


class Fuga(BaseModel):
    problema: str
    impacto_estimado: str = Field(description="Impacto en € o citas/mes, con la hipótesis usada")
    solucion: str


class MensajeFrio(BaseModel):
    dia: int = Field(description="Día de la secuencia en que se envía")
    canal: str
    asunto: str
    cuerpo: str


class AuditoriaProspecto(BaseModel):
    resumen: str
    puntuacion_oportunidad: int = Field(description="0-100: cuánto puede ganar este negocio con nuestro sistema")
    fugas: list[Fuga]
    gancho_personalizado: str = Field(description="Detalle concreto del negocio para abrir la conversación")
    secuencia: list[MensajeFrio]


SISTEMA = """Eres el estratega comercial de una agencia de automatización con IA para negocios locales
de alto ticket (clínicas estéticas, dentales, fisioterapia, inmobiliarias, reformas...).
Vendemos: recepcionista IA 24/7 que responde en <1 minuto y agenda citas, reactivación de bases de datos,
seguimiento automático de presupuestos y no-shows, y gestión de reseñas.
Analiza al prospecto con datos concretos, sin exagerar. Los emails en frío: máximo 90 palabras,
sin adjuntos ni enlaces en el primero, un único CTA de baja fricción ("¿te envío el vídeo de 2 min?"),
asunto en minúsculas de 2-4 palabras. Nada de "espero que estés bien"."""


def auditar(datos_prospecto: str, ticket_medio: float = 300, leads_mes: int = 60) -> AuditoriaProspecto:
    roi = calcular_roi(leads_mes=leads_mes, ticket_medio=ticket_medio)
    prompt = f"""Datos del prospecto (lo que sabemos de su web, reseñas, redes y pruebas de contacto):
{datos_prospecto}

Estimación de ROI con supuestos conservadores (úsala para cuantificar): {roi}

Genera la auditoría y una secuencia de 4 toques (email día 1, email día 3, DM Instagram/LinkedIn día 5, email de cierre día 9)."""
    return llm.estructurado(SISTEMA, prompt, AuditoriaProspecto, esfuerzo="high")
