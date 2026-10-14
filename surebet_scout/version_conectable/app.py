"""Arranca la web de Surebet Scout en http://127.0.0.1:8050 y abre el navegador."""
import os
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def load_env(path):
    """Lee KEY=VALOR de un .env local sin pisar variables ya definidas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    load_env(HERE / ".env")
    import uvicorn
    from web import create_app

    port = int(os.environ.get("SUREBET_PORT", "8050"))
    url = f"http://127.0.0.1:{port}"
    print(f"Surebet Scout en {url}  (Ctrl+C para salir)")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    # Solo 127.0.0.1: la web no es accesible desde otros equipos.
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
