"""API web local (FastAPI) + interfaz estática."""
import os
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from betfair import BetfairClient
from exchange import BetfairExchange, SimulatedExchange
from feeds import DemoFeed, OddsApiIoFeed
from service import Service, ServiceError
from store import Store

STATIC = Path(__file__).parent / "static"


def build_service(env=None):
    env = env if env is not None else os.environ
    store = Store(env.get("SUREBET_DB") or Path(__file__).parent / "datos" / "surebet.db")
    feed = OddsApiIoFeed(env["ODDS_API_KEY"]) if env.get("ODDS_API_KEY") else DemoFeed()
    creds = [env.get(k) for k in ("BETFAIR_APP_KEY", "BETFAIR_USERNAME", "BETFAIR_PASSWORD")]
    if env.get("SUREBET_LIVE") == "1" and all(creds):
        client = BetfairClient(*creds,
                               login_url=env.get("BETFAIR_LOGIN_URL"),
                               keepalive_url=env.get("BETFAIR_KEEPALIVE_URL"),
                               betting_url=env.get("BETFAIR_BETTING_URL"),
                               account_url=env.get("BETFAIR_ACCOUNT_URL"))
        exchange = BetfairExchange(client, float(env.get("BETFAIR_MIN_STAKE", "2")))
    else:
        exchange = SimulatedExchange(store)
        exchange.reason = ("Faltan claves de Betfair en .env" if not all(creds)
                           else "SUREBET_LIVE no está a 1")
    return Service(store, feed, exchange)


def create_app(service=None):
    svc = service or build_service()
    app = FastAPI(title="Surebet Scout", docs_url=None, redoc_url=None)
    # Solo accesible desde tu ordenador (protege contra DNS rebinding).
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.exception_handler(ServiceError)
    async def _service_error(_req: Request, exc: ServiceError):
        return JSONResponse({"error": str(exc)}, status_code=400)

    @app.middleware("http")
    async def _json_only_writes(request: Request, call_next):
        # Las escrituras exigen JSON: un formulario de otra web no puede dispararlas.
        if request.method in ("POST", "PUT", "DELETE") and \
                "application/json" not in request.headers.get("content-type", ""):
            return JSONResponse({"error": "Content-Type debe ser application/json"}, 415)
        return await call_next(request)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status")
    def status():
        st = svc.status()
        st["sim_reason"] = getattr(svc.exchange, "reason", "")
        return st

    @app.post("/api/exchange/check")
    def exchange_check(_: dict = Body(default={})):
        return svc.status(refresh_exchange=True)["exchange"]

    @app.get("/api/settings")
    def get_settings():
        return svc.settings()

    @app.put("/api/settings")
    def put_settings(patch: dict = Body(...)):
        return svc.update_settings(patch)

    @app.get("/api/catalog")
    def catalog():
        try:
            return {"sports": svc.feed.sports(), "bookmakers": svc.feed.bookmakers()}
        except Exception as exc:  # el catálogo es opcional para la interfaz
            raise HTTPException(502, f"No se pudo leer el catálogo: {exc}")

    @app.post("/api/scan")
    def do_scan(_: dict = Body(default={})):
        return {"opportunities": svc.scan(), "last_scan": svc.last_scan}

    @app.get("/api/opportunities")
    def opportunities():
        return {"opportunities": svc.opportunities(), "last_scan": svc.last_scan}

    @app.get("/api/operations")
    def operations():
        return svc.operations()

    @app.post("/api/operations")
    def create_op(body: dict = Body(...)):
        return svc.create_operation(body.get("opportunity_id"), body.get("budget"))

    @app.get("/api/operations/{op_id}")
    def get_op(op_id: int):
        return svc.operation(op_id)

    @app.post("/api/operations/{op_id}/cancel")
    def cancel(op_id: int, _: dict = Body(default={})):
        return svc.cancel(op_id)

    @app.post("/api/operations/{op_id}/settle")
    def settle(op_id: int, body: dict = Body(...)):
        return svc.settle(op_id, body.get("winner"))

    @app.post("/api/operations/{op_id}/legs/{leg_id}/manual")
    def manual(op_id: int, leg_id: int, body: dict = Body(...)):
        return svc.register_manual(op_id, leg_id, body.get("odds"), body.get("stake"),
                                   body.get("bookmaker"))

    @app.post("/api/operations/{op_id}/legs/{leg_id}/skip")
    def skip(op_id: int, leg_id: int, _: dict = Body(default={})):
        return svc.skip_leg(op_id, leg_id)

    @app.post("/api/operations/{op_id}/legs/{leg_id}/reopen")
    def reopen(op_id: int, leg_id: int, _: dict = Body(default={})):
        return svc.reopen_leg(op_id, leg_id)

    @app.post("/api/operations/{op_id}/legs/{leg_id}/mode")
    def mode(op_id: int, leg_id: int, body: dict = Body(...)):
        return svc.set_mode(op_id, leg_id, body.get("mode"))

    @app.post("/api/operations/{op_id}/legs/{leg_id}/prepare")
    def prepare(op_id: int, leg_id: int, _: dict = Body(default={})):
        return svc.prepare_auto(op_id, leg_id)

    @app.post("/api/operations/{op_id}/legs/{leg_id}/place")
    def place(op_id: int, leg_id: int, body: dict = Body(...)):
        return svc.place_auto(op_id, leg_id, body.get("confirm"), bool(body.get("accept_worse")))

    @app.get("/api/export.csv")
    def export():
        return Response(svc.export_csv().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=surebet_historial.csv"})

    return app
