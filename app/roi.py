"""Calculadora de ROI y planes de precios de la agencia."""

PLANES = {
    "arranque": {"setup": 997, "mensual": 497,
                 "incluye": "Recepcionista IA en web + WhatsApp, agenda, CRM, informe mensual"},
    "crecimiento": {"setup": 1997, "mensual": 997,
                    "incluye": "Arranque + seguimiento automático + no-shows + reseñas + 1 reactivación/trimestre"},
    "dominio": {"setup": 3997, "mensual": 1997,
                "incluye": "Crecimiento + voz IA para llamadas + multi-sede + anuncios gestionados + reunión semanal"},
}


def calcular_roi(leads_mes: int, ticket_medio: float, plan: str = "crecimiento",
                 tasa_cita_actual: float = 0.25, tasa_cita_ia: float = 0.40,
                 tasa_cierre: float = 0.5) -> dict:
    """Supuestos conservadores: responder en <1 min sube la tasa de cita del 25% al 40%."""
    p = PLANES[plan]
    ventas_actuales = leads_mes * tasa_cita_actual * tasa_cierre
    ventas_ia = leads_mes * tasa_cita_ia * tasa_cierre
    ingreso_extra = round((ventas_ia - ventas_actuales) * ticket_medio, 2)
    coste_anual = p["setup"] + 12 * p["mensual"]
    return {
        "plan": plan,
        "ventas_extra_mes": round(ventas_ia - ventas_actuales, 1),
        "ingreso_extra_mes": ingreso_extra,
        "ingreso_extra_anual": round(ingreso_extra * 12, 2),
        "coste_anual": coste_anual,
        "roi_anual_x": round(ingreso_extra * 12 / coste_anual, 1) if coste_anual else None,
        "meses_recuperacion": (round(p["setup"] / (ingreso_extra - p["mensual"]), 1)
                               if ingreso_extra > p["mensual"] else None),
    }
