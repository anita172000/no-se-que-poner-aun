"""Agente recepcionista IA 24/7.

Responde a leads entrantes en segundos (web, WhatsApp, Instagram...),
resuelve dudas con la ficha del negocio, califica al lead y reserva la
cita directamente en la agenda. Si detecta algo delicado, escala a un humano.
"""
import json
from datetime import date, datetime, timedelta

from .. import db, llm
from ..config import cargar_cliente

DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
MAX_PASOS = 8

HERRAMIENTAS = [
    {
        "name": "consultar_disponibilidad",
        "description": "Devuelve los huecos libres (inicio ISO) para una fecha concreta. Úsala antes de proponer horas.",
        "input_schema": {
            "type": "object",
            "properties": {"fecha": {"type": "string", "description": "Fecha AAAA-MM-DD"}},
            "required": ["fecha"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "registrar_lead",
        "description": (
            "Guarda o actualiza los datos del lead en el CRM. Llámala en cuanto tengas nombre y teléfono o email, "
            "y de nuevo si aprendes algo relevante. puntuacion: 0-100 según intención de compra, presupuesto y urgencia."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string"},
                "telefono": {"type": "string"},
                "email": {"type": "string"},
                "interes": {"type": "string", "description": "Servicio o tratamiento que le interesa"},
                "presupuesto": {"type": "string"},
                "urgencia": {"type": "string", "enum": ["alta", "media", "baja", "desconocida"]},
                "puntuacion": {"type": "integer"},
                "notas": {"type": "string"},
            },
            "required": ["nombre", "telefono", "email", "interes", "presupuesto", "urgencia", "puntuacion", "notas"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "reservar_cita",
        "description": "Reserva una cita en un hueco libre. Confirma antes servicio, día y hora con la persona.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string"},
                "telefono": {"type": "string"},
                "servicio": {"type": "string"},
                "inicio": {"type": "string", "description": "Inicio ISO AAAA-MM-DDTHH:MM, debe ser un hueco libre"},
            },
            "required": ["nombre", "telefono", "servicio", "inicio"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "escalar_a_humano",
        "description": "Pasa la conversación al equipo humano: quejas, urgencias médicas, peticiones fuera de la ficha o si la persona lo pide.",
        "input_schema": {
            "type": "object",
            "properties": {"motivo": {"type": "string"}},
            "required": ["motivo"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def prompt_sistema(negocio: dict) -> str:
    servicios = "\n".join(
        f"- {s['nombre']}: desde {s['precio_desde']} € ({s['duracion_min']} min). {s.get('descripcion', '')}"
        for s in negocio["servicios"]
    )
    faq = "\n".join(f"P: {f['p']}\nR: {f['r']}" for f in negocio.get("faq", []))
    horario = ", ".join(f"{d}: {'-'.join(h) if h else 'cerrado'}" for d, h in negocio["horario"].items())
    return f"""Eres {negocio['asistente']}, la recepcionista virtual de {negocio['nombre']} ({negocio['sector']}, {negocio['ubicacion']}).
Hablas en nombre del negocio por chat. Tono: {negocio['tono']}. Mensajes breves (1-3 frases), como un WhatsApp humano.

Tu objetivo, en este orden:
1. Responder rápido y con precisión usando SOLO la información de abajo. Si no lo sabes, dilo y ofrece que el equipo le contacte.
2. Entender qué necesita la persona (tratamiento, plazo, presupuesto) con preguntas naturales, de una en una.
3. Conseguir nombre y teléfono, y registrarlos con registrar_lead.
4. Proponer 2-3 huecos concretos (consulta la disponibilidad primero) y reservar la cita con reservar_cita.
Si hay una oferta vigente, menciónala cuando ayude a decidir, sin presionar.

Reglas:
- No des diagnósticos médicos ni prometas resultados. Ante urgencias, dolor fuerte o quejas, usa escalar_a_humano.
- No inventes precios, servicios ni huecos. Los precios son "desde".
- Si la persona pide hablar con alguien, escala.

== FICHA DEL NEGOCIO ==
Servicios:
{servicios}
Horario: {horario}
Teléfono: {negocio['telefono']}
Políticas: {negocio.get('politicas', '')}
Oferta vigente: {negocio.get('oferta_actual', 'ninguna')}
Preguntas frecuentes:
{faq}"""


# ---------- implementación de herramientas ----------

def huecos_libres(cliente_id: str, negocio: dict, fecha: str) -> list[str]:
    try:
        dia = date.fromisoformat(fecha)
    except ValueError:
        return []
    franja = negocio["horario"].get(DIAS[dia.weekday()])
    if not franja:
        return []
    paso = timedelta(minutes=negocio.get("intervalo_citas_min", 30))
    inicio = datetime.combine(dia, datetime.strptime(franja[0], "%H:%M").time())
    fin = datetime.combine(dia, datetime.strptime(franja[1], "%H:%M").time())
    ocupados = {
        f["inicio"]
        for f in db.filas(
            "SELECT inicio FROM citas WHERE cliente_id = ? AND estado != 'cancelada' AND inicio LIKE ?",
            (cliente_id, f"{fecha}%"),
        )
    }
    ahora = datetime.now()
    libres, t = [], inicio
    while t + paso <= fin:
        iso = t.strftime("%Y-%m-%dT%H:%M")
        if iso not in ocupados and t > ahora:
            libres.append(iso)
        t += paso
    return libres


def ejecutar_herramienta(nombre: str, args: dict, ctx: dict) -> dict:
    cliente_id, negocio = ctx["cliente_id"], ctx["negocio"]
    if nombre == "consultar_disponibilidad":
        libres = huecos_libres(cliente_id, negocio, args["fecha"])
        return {"fecha": args["fecha"], "huecos": libres[:12], "total": len(libres)}

    if nombre == "registrar_lead":
        datos = {k: args.get(k, "") for k in ("nombre", "telefono", "email", "interes", "presupuesto", "urgencia", "notas")}
        datos["puntuacion"] = max(0, min(100, int(args.get("puntuacion", 0))))
        if ctx.get("lead_id"):
            db.actualizar("leads", ctx["lead_id"], {k: v for k, v in datos.items() if v not in ("", None)})
        else:
            ctx["lead_id"] = db.insertar("leads", {**datos, "cliente_id": cliente_id, "origen": ctx["canal"], "creado": db.ahora()})
        return {"ok": True, "lead_id": ctx["lead_id"]}

    if nombre == "reservar_cita":
        if args["inicio"] not in huecos_libres(cliente_id, negocio, args["inicio"][:10]):
            return {"ok": False, "error": "Ese hueco no está libre. Consulta la disponibilidad y propone otro."}
        if not ctx.get("lead_id"):
            ctx["lead_id"] = db.insertar("leads", {
                "cliente_id": cliente_id, "nombre": args["nombre"], "telefono": args["telefono"],
                "interes": args["servicio"], "origen": ctx["canal"], "creado": db.ahora(),
            })
        cita_id = db.insertar("citas", {
            "cliente_id": cliente_id, "lead_id": ctx["lead_id"], "servicio": args["servicio"],
            "inicio": args["inicio"], "creado": db.ahora(),
        })
        db.actualizar("leads", ctx["lead_id"], {"estado": "cita_reservada"})
        return {"ok": True, "cita_id": cita_id, "inicio": args["inicio"]}

    if nombre == "escalar_a_humano":
        ctx["escalada"] = True
        if ctx.get("lead_id"):
            db.actualizar("leads", ctx["lead_id"], {"estado": "requiere_humano", "notas": args["motivo"]})
        return {"ok": True, "mensaje": "El equipo ha sido avisado y contactará en breve."}

    return {"ok": False, "error": f"Herramienta desconocida: {nombre}"}


# ---------- bucle del agente ----------

def responder(cliente_id: str, conv_id: str, mensaje_usuario: str, canal: str = "chat") -> dict:
    negocio = cargar_cliente(cliente_id)
    conv = db.cargar_conversacion(conv_id) or {"historial": [], "lead_id": None, "escalada": 0}
    historial = conv["historial"]
    ctx = {"cliente_id": cliente_id, "negocio": negocio, "canal": canal,
           "lead_id": conv["lead_id"], "escalada": bool(conv["escalada"])}

    sistema = [
        {"type": "text", "text": prompt_sistema(negocio), "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": f"Fecha y hora actual: {datetime.now():%A %Y-%m-%d %H:%M}."},
    ]
    historial.append({"role": "user", "content": mensaje_usuario})

    respuesta_final = ""
    for _ in range(MAX_PASOS):
        r = llm.mensaje(
            max_tokens=4000,
            system=sistema,
            tools=HERRAMIENTAS,
            messages=historial,
            output_config={"effort": "low"},
        )
        historial.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in r.content]})
        if r.stop_reason != "tool_use":
            respuesta_final = llm.texto(r)
            break
        resultados = []
        for bloque in r.content:
            if bloque.type != "tool_use":
                continue
            try:
                salida = ejecutar_herramienta(bloque.name, bloque.input, ctx)
                resultados.append({"type": "tool_result", "tool_use_id": bloque.id,
                                   "content": json.dumps(salida, ensure_ascii=False)})
            except Exception as e:  # el error vuelve al modelo para que se recupere
                resultados.append({"type": "tool_result", "tool_use_id": bloque.id,
                                   "content": f"Error: {e}", "is_error": True})
        historial.append({"role": "user", "content": resultados})
    else:
        respuesta_final = "Perdona, ahora mismo no puedo completar esto. Te contactará alguien del equipo enseguida."
        ctx["escalada"] = True

    db.guardar_conversacion(conv_id, cliente_id, historial, ctx["lead_id"], ctx["escalada"])
    return {"respuesta": respuesta_final, "lead_id": ctx["lead_id"], "escalada": ctx["escalada"]}
