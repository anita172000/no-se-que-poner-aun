"""Captura cómo carga cada casa sus cuotas, para poder escribir su lector.

Ejecútalo en TU ordenador, desde España (desde fuera muchas casas bloquean):

    pip install playwright
    python -m playwright install chromium
    python herramientas/capturar_casas.py

Abre cada casa en un navegador, SIN iniciar sesión, espera a que carguen las
cuotas de fútbol y guarda las respuestas de datos (JSON) que recibe la página,
el HTML y una captura de pantalla. No guarda cookies, contraseñas ni cabeceras.
Al final crea un .zip: ese es el archivo que hay que pasar.

Opcional: python herramientas/capturar_casas.py codere luckia   (solo esas casas)
          --sin-ventana   (sin abrir ventana; algunas casas lo detectan peor)
"""
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

CASAS = {
    "codere": ["https://www.codere.es/apuestas-deportivas/futbol", "https://apuestas.codere.es/"],
    "bwin": ["https://sports.bwin.es/es/sports/f%C3%BAtbol-4"],
    "luckia": ["https://www.luckia.es/apuestas/futbol/"],
    "retabet": ["https://apuestas.retabet.es/deportes/futbol"],
    "sportium": ["https://www.sportium.es/apuestas/futbol"],
    "kirolbet": ["https://apuestas.kirolbet.es/esp/Sport/Futbol"],
    "winamax": ["https://www.winamax.es/apuestas-deportivas/sports/1"],
    "888sport": ["https://www.888sport.es/futbol/"],
    "pokerstars": ["https://www.pokerstars.es/sports/futbol/1/"],
    "betway": ["https://betway.es/es/sports/cat/soccer"],
    "marcaapuestas": ["https://www.marcaapuestas.es/es/apuestas-deportivas/futbol"],
    "betfair_sportsbook": ["https://www.betfair.es/sport/football"],
    "versus": ["https://www.versus.es/apuestas/sports/futbol"],
    "bet365": ["https://www.bet365.es/#/AS/B1/"],
}
MAX_BODY = 400_000       # bytes por respuesta
MAX_RESPONSES = 80       # por casa
WAIT_S = 15              # tiempo para que carguen las cuotas
SKIP = re.compile(r"\.(png|jpe?g|gif|svg|webp|woff2?|ttf|css|mp4|ico)(\?|$)|google|facebook|doubleclick|"
                  r"hotjar|analytics|onetrust|cookielaw|sentry|newrelic|tiktok|bing", re.I)


def capture(page, url, out_dir):
    found = []

    def on_response(resp):
        try:
            if len(found) >= MAX_RESPONSES or SKIP.search(resp.url):
                return
            ctype = resp.headers.get("content-type", "")
            if "json" not in ctype and "javascript" not in ctype and "text/plain" not in ctype:
                return
            if "javascript" in ctype and "odds" not in resp.url.lower() and "api" not in resp.url.lower():
                return
            body = resp.body()[:MAX_BODY].decode("utf-8", "replace")
            found.append({"url": resp.url, "status": resp.status, "method": resp.request.method,
                          "content_type": ctype, "post_data": (resp.request.post_data or "")[:2000],
                          "body": body})
        except Exception:  # respuestas cerradas, redirecciones...
            pass

    def on_ws(ws):
        entry = {"url": ws.url, "websocket": True, "frames": []}
        found.append(entry)

        def frame(payload):
            if len(entry["frames"]) < 60:
                text = payload if isinstance(payload, str) else payload.decode("utf-8", "replace")
                entry["frames"].append(text[:50_000])
        ws.on("framereceived", frame)
        ws.on("framesent", lambda p: frame(f">> {p if isinstance(p, str) else ''}"[:2000]))

    page.on("response", on_response)
    page.on("websocket", on_ws)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    except Exception as exc:
        found.append({"url": url, "error": str(exc)})
    for _ in range(WAIT_S):
        time.sleep(1)
        try:
            page.mouse.wheel(0, 600)
        except Exception:
            break
    try:
        (out_dir / "pagina.html").write_text(page.content()[:800_000], encoding="utf-8")
        page.screenshot(path=str(out_dir / "pantalla.png"), full_page=False)
    except Exception:
        pass
    page.remove_listener("response", on_response)
    page.remove_listener("websocket", on_ws)
    return found


def main():
    from playwright.sync_api import sync_playwright

    headless = "--sin-ventana" in sys.argv
    only = [a.lower() for a in sys.argv[1:] if not a.startswith("--")]
    casas = {k: v for k, v in CASAS.items() if not only or k in only}
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    root = Path(f"captura_casas_{stamp}")
    root.mkdir()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, executable_path=os.environ.get("CHROMIUM_PATH") or None)
        ctx = browser.new_context(locale="es-ES", timezone_id="Europe/Madrid",
                                  viewport={"width": 1366, "height": 900})
        for casa, urls in casas.items():
            print(f"· {casa}...", flush=True)
            out_dir = root / casa
            out_dir.mkdir()
            page = ctx.new_page()
            responses = []
            for url in urls:
                responses += capture(page, url, out_dir)
            page.close()
            (out_dir / "respuestas.json").write_text(json.dumps(responses, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
            ok = sum(1 for r in responses if r.get("status") == 200)
            print(f"  {ok} respuestas de datos guardadas")
        browser.close()
    zpath = Path(f"{root}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in root.rglob("*"):
            z.write(f, f.relative_to(root.parent))
    print(f"\nListo. Pasa este archivo: {zpath.resolve()}")


if __name__ == "__main__":
    main()
