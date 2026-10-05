#!/usr/bin/env python3
"""Herramientas de línea de comandos de la agencia.

  python cli.py chat clinica-lumiere                 # prueba la recepcionista IA en la terminal
  python cli.py reactivar clinica-lumiere ejemplos/contactos_ejemplo.csv --campana "otoño"
  python cli.py auditar ejemplos/prospecto_ejemplo.txt --ticket 1500 --leads 80
  python cli.py propuesta notas.txt --negocio "Clínica X" --leads 80 --ticket 1500
  python cli.py roi --leads 60 --ticket 300
  python cli.py seguimiento clinica-lumiere
  python cli.py resena clinica-lumiere --autor Ana --estrellas 2 --texto "Me hicieron esperar 40 minutos"
"""
import argparse
import json
import uuid
from pathlib import Path

SALIDAS = Path("salidas")


def main() -> None:
    p = argparse.ArgumentParser(description="Agencia IA · herramientas internas")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("chat", help="Conversar con la recepcionista IA de un cliente")
    c.add_argument("cliente")

    r = sub.add_parser("reactivar", help="Generar campaña de reactivación desde un CSV")
    r.add_argument("cliente"); r.add_argument("csv"); r.add_argument("--campana", default="reactivacion")

    a = sub.add_parser("auditar", help="Auditoría + secuencia de prospección para un negocio")
    a.add_argument("fichero"); a.add_argument("--ticket", type=float, default=300); a.add_argument("--leads", type=int, default=60)

    pr = sub.add_parser("propuesta", help="Propuesta comercial a partir de notas de la llamada")
    pr.add_argument("notas"); pr.add_argument("--negocio", required=True)
    pr.add_argument("--leads", type=int, required=True); pr.add_argument("--ticket", type=float, required=True)
    pr.add_argument("--plan", default="crecimiento")

    ro = sub.add_parser("roi", help="Calcular el ROI para un prospecto")
    ro.add_argument("--leads", type=int, required=True); ro.add_argument("--ticket", type=float, required=True)
    ro.add_argument("--plan", default="crecimiento")

    s = sub.add_parser("seguimiento", help="Mensajes de seguimiento que tocan hoy")
    s.add_argument("cliente")

    re_ = sub.add_parser("resena", help="Responder una reseña")
    re_.add_argument("cliente"); re_.add_argument("--autor", required=True)
    re_.add_argument("--estrellas", type=int, required=True); re_.add_argument("--texto", required=True)

    args = p.parse_args()

    if args.cmd == "roi":
        from app.roi import calcular_roi
        print(json.dumps(calcular_roi(args.leads, args.ticket, args.plan), indent=2, ensure_ascii=False))

    elif args.cmd == "chat":
        from app.agents import recepcionista
        conv = uuid.uuid4().hex
        print("Escribe tus mensajes (Ctrl+C para salir)\n")
        try:
            while True:
                r = recepcionista.responder(args.cliente, conv, input("Tú: "), canal="terminal")
                print(f"IA: {r['respuesta']}" + ("  [ESCALADO A HUMANO]" if r["escalada"] else "") + "\n")
        except (KeyboardInterrupt, EOFError):
            print()

    elif args.cmd == "reactivar":
        from app.agents import reactivacion
        msgs = reactivacion.generar(args.cliente, reactivacion.leer_contactos(args.csv), args.campana)
        destino = SALIDAS / f"reactivacion_{args.cliente}_{args.campana}.csv"
        reactivacion.exportar_csv(msgs, destino)
        for m in msgs:
            print(f"[{m.prioridad}] {m.contacto} ({m.canal}): {m.mensaje}\n")
        print(f"→ {len(msgs)} mensajes guardados en {destino}")

    elif args.cmd == "auditar":
        from app.agents import prospector
        res = prospector.auditar(Path(args.fichero).read_text(encoding="utf-8"), args.ticket, args.leads)
        destino = SALIDAS / f"auditoria_{Path(args.fichero).stem}.json"
        SALIDAS.mkdir(exist_ok=True)
        destino.write_text(res.model_dump_json(indent=2), encoding="utf-8")
        print(res.model_dump_json(indent=2))
        print(f"→ guardado en {destino}")

    elif args.cmd == "propuesta":
        from app.agents import propuesta
        md = propuesta.generar(Path(args.notas).read_text(encoding="utf-8"), args.negocio, args.leads, args.ticket, args.plan)
        SALIDAS.mkdir(exist_ok=True)
        destino = SALIDAS / f"propuesta_{args.negocio.lower().replace(' ', '_')}.md"
        destino.write_text(md, encoding="utf-8")
        print(md)
        print(f"\n→ guardado en {destino}")

    elif args.cmd == "seguimiento":
        from app.agents import seguimiento
        for m in seguimiento.pendientes(args.cliente):
            print(f"Lead {m['lead_id']} · {m['telefono']} · día {m['dia']}\n  {m['mensaje']}\n")

    elif args.cmd == "resena":
        from app.agents import resenas
        print(resenas.responder(args.cliente, args.autor, args.estrellas, args.texto).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
