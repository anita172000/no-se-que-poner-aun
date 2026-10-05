"""Servidor web de la agencia: API, widget de chat embebible y panel de resultados.

Arranque:  uvicorn app.main:app --reload
"""
import secrets
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db
from .agents import recepcionista, resenas, seguimiento
from .llm import RechazoIA
from .roi import PLANES, calcular_roi

app = FastAPI(title="Agencia IA · Sistema de Conversión 24/7")
# El widget se incrusta en las webs de los clientes, por eso se permite cualquier origen.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
STATIC = config.RAIZ / "app" / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def exigir_token(token: str = Query(...)) -> None:
    if not secrets.compare_digest(token, config.PANEL_TOKEN):
        raise HTTPException(401, "Token incorrecto")


def cliente_valido(cliente_id: str) -> dict:
    try:
        return config.cargar_cliente(cliente_id)
    except KeyError:
        raise HTTPException(404, "Cliente no encontrado")


# ---------- páginas ----------

@app.get("/", response_class=FileResponse)
def inicio():
    return FileResponse(config.RAIZ / "index.html")


@app.get("/demo/{cliente_id}", response_class=HTMLResponse)
def demo(cliente_id: str):
    n = cliente_valido(cliente_id)
    return (STATIC / "demo.html").read_text(encoding="utf-8") \
        .replace("{{CLIENTE}}", cliente_id).replace("{{NOMBRE}}", n["nombre"])


@app.get("/panel", response_class=HTMLResponse, dependencies=[Depends(exigir_token)])
def panel():
    return (STATIC / "panel.html").read_text(encoding="utf-8")


# ---------- API pública (widget) ----------

class EntradaChat(BaseModel):
    cliente_id: str
    mensaje: str = Field(min_length=1, max_length=2000)
    conversacion_id: str | None = None
    canal: str = "web"


@app.post("/api/chat")
def chat(e: EntradaChat):
    cliente_valido(e.cliente_id)
    conv_id = e.conversacion_id or uuid.uuid4().hex
    try:
        r = recepcionista.responder(e.cliente_id, conv_id, e.mensaje, e.canal)
    except RechazoIA:
        r = {"respuesta": "Perdona, eso no lo puedo gestionar por aquí. ¿Te llama alguien del equipo?",
             "lead_id": None, "escalada": True}
    return {"conversacion_id": conv_id, **r}


class LeadEntrante(BaseModel):
    cliente_id: str
    nombre: str
    telefono: str = ""
    email: str = ""
    interes: str = ""
    origen: str = "formulario"


@app.post("/api/leads")
def nuevo_lead(l: LeadEntrante):
    """Webhook para formularios web, Meta Lead Ads, Zapier/Make, etc."""
    cliente_valido(l.cliente_id)
    lead_id = db.insertar("leads", {**l.model_dump(), "creado": db.ahora()})
    primer = [p for p in seguimiento.pendientes(l.cliente_id) if p["lead_id"] == lead_id]
    return {"lead_id": lead_id, "primer_mensaje": primer[0]["mensaje"] if primer else None}


class EntradaROI(BaseModel):
    leads_mes: int = Field(gt=0)
    ticket_medio: float = Field(gt=0)
    plan: str = "crecimiento"


@app.post("/api/roi")
def roi(e: EntradaROI):
    if e.plan not in PLANES:
        raise HTTPException(400, f"Plan desconocido. Opciones: {list(PLANES)}")
    return calcular_roi(e.leads_mes, e.ticket_medio, e.plan)


# ---------- API privada (equipo de la agencia) ----------

@app.get("/api/clientes", dependencies=[Depends(exigir_token)])
def clientes():
    return config.listar_clientes()


@app.get("/api/metricas/{cliente_id}", dependencies=[Depends(exigir_token)])
def metricas(cliente_id: str):
    cliente_valido(cliente_id)
    leads = db.filas("SELECT estado, puntuacion FROM leads WHERE cliente_id = ?", (cliente_id,))
    citas = db.filas("SELECT COUNT(*) AS n FROM citas WHERE cliente_id = ? AND estado != 'cancelada'", (cliente_id,))[0]["n"]
    convs = db.filas("SELECT COUNT(*) AS n, SUM(escalada) AS esc FROM conversaciones WHERE cliente_id = ?", (cliente_id,))[0]
    por_estado: dict[str, int] = {}
    for l in leads:
        por_estado[l["estado"]] = por_estado.get(l["estado"], 0) + 1
    return {
        "leads": len(leads), "citas": citas, "conversaciones": convs["n"], "escaladas": convs["esc"] or 0,
        "conversion_lead_cita": round(citas / len(leads), 3) if leads else 0,
        "leads_calientes": sum(1 for l in leads if (l["puntuacion"] or 0) >= 70),
        "por_estado": por_estado,
    }


@app.get("/api/leads/{cliente_id}", dependencies=[Depends(exigir_token)])
def listar_leads(cliente_id: str):
    return db.filas("SELECT * FROM leads WHERE cliente_id = ? ORDER BY id DESC LIMIT 200", (cliente_id,))


@app.get("/api/citas/{cliente_id}", dependencies=[Depends(exigir_token)])
def listar_citas(cliente_id: str):
    return db.filas("SELECT * FROM citas WHERE cliente_id = ? ORDER BY inicio DESC LIMIT 200", (cliente_id,))


@app.get("/api/seguimiento/{cliente_id}", dependencies=[Depends(exigir_token)])
def seguimientos(cliente_id: str):
    cliente_valido(cliente_id)
    return seguimiento.pendientes(cliente_id)


class Resena(BaseModel):
    cliente_id: str
    autor: str
    estrellas: int = Field(ge=1, le=5)
    texto: str


@app.post("/api/resenas/responder", dependencies=[Depends(exigir_token)])
def responder_resena(r: Resena):
    cliente_valido(r.cliente_id)
    return resenas.responder(r.cliente_id, r.autor, r.estrellas, r.texto)
