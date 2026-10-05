"""Pruebas sin llamar a la API real: se simula la respuesta de Claude."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app import db, llm
from app.agents import recepcionista, seguimiento
from app.config import cargar_cliente
from app.main import app
from app.roi import calcular_roi

CLIENTE = "clinica-lumiere"


class Bloque:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump(self, exclude_none=False):
        return dict(self.__dict__)


class Respuesta:
    def __init__(self, bloques, stop_reason):
        self.content, self.stop_reason = bloques, stop_reason


def proximo_dia_laborable() -> str:
    d = datetime.now().date() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


def test_roi_positivo():
    r = calcular_roi(leads_mes=60, ticket_medio=300)
    assert r["ventas_extra_mes"] == 4.5
    assert r["ingreso_extra_mes"] == 1350
    assert r["roi_anual_x"] > 1


def test_huecos_respetan_horario_y_reservas():
    negocio = cargar_cliente(CLIENTE)
    fecha = proximo_dia_laborable()
    libres = recepcionista.huecos_libres(CLIENTE, negocio, fecha)
    assert libres[0].endswith("10:00")
    db.insertar("citas", {"cliente_id": CLIENTE, "servicio": "x", "inicio": libres[0], "creado": db.ahora()})
    assert libres[0] not in recepcionista.huecos_libres(CLIENTE, negocio, fecha)


def test_agente_reserva_cita(monkeypatch):
    hueco = f"{proximo_dia_laborable()}T11:00"
    guion = [
        Respuesta([Bloque(type="tool_use", id="t1", name="registrar_lead", input={
            "nombre": "Ana Pérez", "telefono": "600000000", "email": "", "interes": "labios",
            "presupuesto": "300", "urgencia": "alta", "puntuacion": 85, "notas": ""})], "tool_use"),
        Respuesta([Bloque(type="tool_use", id="t2", name="reservar_cita", input={
            "nombre": "Ana Pérez", "telefono": "600000000", "servicio": "Primera valoración", "inicio": hueco})], "tool_use"),
        Respuesta([Bloque(type="text", text="¡Listo Ana! Te esperamos.")], "end_turn"),
    ]
    monkeypatch.setattr(llm, "mensaje", lambda **kw: guion.pop(0))

    r = recepcionista.responder(CLIENTE, "conv1", "Quiero cita para labios")
    assert r["respuesta"] == "¡Listo Ana! Te esperamos."
    citas = db.filas("SELECT * FROM citas")
    assert len(citas) == 1 and citas[0]["inicio"] == hueco
    assert db.filas("SELECT estado FROM leads")[0]["estado"] == "cita_reservada"
    assert len(db.cargar_conversacion("conv1")["historial"]) == 6


def test_no_reserva_hueco_ocupado():
    ctx = {"cliente_id": CLIENTE, "negocio": cargar_cliente(CLIENTE), "canal": "t", "lead_id": None}
    hueco = f"{proximo_dia_laborable()}T12:00"
    args = {"nombre": "A", "telefono": "1", "servicio": "x", "inicio": hueco}
    assert recepcionista.ejecutar_herramienta("reservar_cita", args, ctx)["ok"]
    assert not recepcionista.ejecutar_herramienta("reservar_cita", args, ctx)["ok"]


def test_seguimiento_dia_cero():
    db.insertar("leads", {"cliente_id": CLIENTE, "nombre": "Luis Gómez", "telefono": "1",
                          "interes": "láser", "creado": db.ahora()})
    msgs = seguimiento.pendientes(CLIENTE)
    assert len(msgs) == 1 and "Luis" in msgs[0]["mensaje"] and "láser" in msgs[0]["mensaje"]


def test_api():
    c = TestClient(app)
    assert c.get("/").status_code == 200
    assert c.get(f"/demo/{CLIENTE}").status_code == 200
    assert c.get("/demo/no-existe").status_code == 404
    assert c.post("/api/roi", json={"leads_mes": 60, "ticket_medio": 300}).json()["ingreso_extra_mes"] == 1350
    r = c.post("/api/leads", json={"cliente_id": CLIENTE, "nombre": "Eva", "telefono": "1", "interes": "botox"})
    assert r.json()["primer_mensaje"]
    assert c.get(f"/api/metricas/{CLIENTE}?token=mal").status_code == 401
    m = c.get(f"/api/metricas/{CLIENTE}?token=secreto").json()
    assert m["leads"] == 1
    assert c.get("/panel?token=secreto").status_code == 200
