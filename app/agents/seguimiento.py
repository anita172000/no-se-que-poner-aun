"""Seguimiento automático: leads sin cita, presupuestos sin aceptar y no-shows.

Devuelve el siguiente mensaje que toca enviar a cada lead según su estado y
los días transcurridos. Las plantillas son deterministas (sin coste de IA);
la IA solo se usa en conversación cuando el lead responde.
"""
from datetime import datetime

from .. import db
from ..config import cargar_cliente

# (estado, días desde creación) -> plantilla
SECUENCIAS = {
    "nuevo": [
        (0, "Hola {nombre}, soy {asistente} de {negocio}. Vi que te interesaba {interes}. ¿Te viene mejor que te llamemos hoy o mañana?"),
        (1, "{nombre}, te guardo un hueco esta semana para {interes}. ¿Mañana por la tarde te va bien?"),
        (3, "Hola {nombre}, ¿sigues interesada/o en {interes}? Si ahora no es buen momento, dímelo y no te molesto más 🙂"),
        (7, "Último mensaje, {nombre}: {oferta}. Si te interesa, responde SÍ y te paso horarios."),
    ],
    "no_show": [
        (0, "Hola {nombre}, te echamos de menos hoy. ¿Todo bien? Te recoloco la cita sin coste, ¿qué día te va mejor?"),
        (2, "{nombre}, aún tengo huecos esta semana para {interes}. ¿Te reservo uno?"),
    ],
    "presupuesto_enviado": [
        (2, "Hola {nombre}, ¿pudiste revisar el presupuesto de {interes}? Si tienes cualquier duda te la resuelvo por aquí."),
        (5, "{nombre}, te recuerdo que tenemos financiación sin intereses. ¿Quieres que te calcule la cuota?"),
        (10, "Hola {nombre}, cierro tu ficha esta semana. ¿Lo dejamos para más adelante o te reservo fecha?"),
    ],
}


def pendientes(cliente_id: str, hoy: datetime | None = None) -> list[dict]:
    hoy = hoy or datetime.now()
    n = cargar_cliente(cliente_id)
    salida = []
    for lead in db.filas("SELECT * FROM leads WHERE cliente_id = ?", (cliente_id,)):
        pasos = SECUENCIAS.get(lead["estado"])
        if not pasos:
            continue
        dias = (hoy - datetime.fromisoformat(lead["creado"])).days
        for dia, plantilla in pasos:
            if dia == dias:
                salida.append({
                    "lead_id": lead["id"], "telefono": lead["telefono"], "dia": dia,
                    "mensaje": plantilla.format(
                        nombre=(lead["nombre"] or "").split(" ")[0] or "hola",
                        asistente=n["asistente"], negocio=n["nombre"],
                        interes=lead["interes"] or "tu consulta",
                        oferta=n.get("oferta_actual", "tenemos huecos esta semana"),
                    ),
                })
    return salida
