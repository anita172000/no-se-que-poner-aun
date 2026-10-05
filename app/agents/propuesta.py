"""Genera la propuesta comercial tras la llamada de diagnóstico."""
from .. import llm
from ..roi import calcular_roi, PLANES

SISTEMA = """Redactas propuestas comerciales para una agencia de automatización con IA.
Formato Markdown, en español, máximo 2 páginas. Estructura:
1. Situación actual (en palabras del cliente)  2. Lo que está costando no actuar (con cifras)
3. Solución propuesta (qué se instala, semana a semana)  4. Resultados esperados y garantía
5. Inversión (plan recomendado + alternativa)  6. Próximos pasos (firma, kickoff en 48 h).
Concreto, sin relleno ni jerga técnica."""


def generar(notas_llamada: str, negocio: str, leads_mes: int, ticket_medio: float, plan: str = "crecimiento") -> str:
    roi = calcular_roi(leads_mes=leads_mes, ticket_medio=ticket_medio, plan=plan)
    prompt = f"""Negocio: {negocio}
Notas de la llamada de diagnóstico:
{notas_llamada}

Cálculo de ROI: {roi}
Planes disponibles: {PLANES}
Plan recomendado: {plan}

Garantía estándar: si en 60 días el sistema no genera al menos el doble de la cuota mensual en citas
atribuibles, trabajamos gratis hasta conseguirlo."""
    r = llm.mensaje(system=SISTEMA, messages=[{"role": "user", "content": prompt}],
                    output_config={"effort": "medium"})
    return llm.texto(r)
