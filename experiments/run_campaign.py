#!/usr/bin/env python3
"""
Runner de campanas de acumulacion multi-incidente (variante temporal, fase 2 - experimental).

Corre la ablacion completa (vacia, cada incidente aislado, prefijos acumulados,
memoria-correcta, firewall) y estima si el compromiso crece por acumulacion.

Uso:
  python -m experiments.run_campaign
  python -m experiments.run_campaign --client gemini:gemini-2.5-flash-lite --reps 5 --system-mode neutral --out results/t1_neutral
"""
import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent.clients import make_client
from experiments.accumulation import load_campaign, run_campaign, validate_campaign


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", default="cases/campaigns/t1_01.json")
    ap.add_argument("--client", default="mock:credulous")
    ap.add_argument("--reps", type=int, default=1, help="repeticiones de campana completa")
    ap.add_argument("--system-mode", choices=["aware", "neutral"], default="aware")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    camp = load_campaign(args.campaign)
    verr = validate_campaign(camp)
    if verr:
        print("CAMPANA INVALIDA:")
        for e in verr:
            print("   -", e)
        sys.exit(1)

    client = make_client(args.client)
    res = run_campaign(camp, client, reps=args.reps, system_mode=args.system_mode)
    v = res["verdict"]
    if client.name.startswith("mock:"):
        note = res["note"]
    else:
        note = ("Variante experimental de memoria temporal (fase 2). Cliente LLM real: "
                "interpretar como existencia/atribucion por caso tras revisar puertas de validez, "
                "no como estimacion poblacional de tasa.")

    print(f"\n=== Campana {camp['campaign_id']} ({camp['family']}) - experimental (fase 2) ===")
    print(f"    cliente {client.name} - modo {args.system_mode} - reps(campana) {args.reps}\n")
    print("    Ablacion - ASR del probe (fraccion que cierra el ataque) por memoria previa:")
    for cond, a in v["ASR por condicion"].items():
        bar = "#" * int(round(a * 20))
        print(f"      {cond:26} {a:>5}  {bar}")
    print()
    print(f"    curva de prefijos                : {v['curva de prefijos (a1, a1+a2, ...)']}")
    print(f"    max ASR de un incidente aislado  : {v['max ASR de un incidente aislado']}")
    print(f"    ASR con acumulacion completa     : {v['ASR con acumulacion completa']}")
    print(f"    control (memoria correcta) limpio: {v['control (memoria correcta) no comprometido']}")
    print(f"    firewall contiene                : {v['firewall contiene']}")
    print(f"    concordancia agente-ledger inc.  : {v['concordancia agente-ledger en incidentes (cerro los benignos)']}")
    print(f"    evidencia de acumulacion         : {v['evidencia de acumulacion (pleno > cualquier aislado, curva no decrece)']}")
    print(f"\n    {note}")

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        tag = client.name.replace(":", "_").replace("/", "_")
        with open(os.path.join(args.out, f"traces_{tag}.jsonl"), "w", encoding="utf-8") as fh:
            for cond, traces in res["traces"].items():
                for t in traces:
                    fh.write(json.dumps(t.as_dict(), ensure_ascii=False, default=str) + "\n")
        manifest = {
            "campaign_id": camp["campaign_id"], "family": camp["family"],
            "client": client.name, "system_mode": args.system_mode, "reps_campaign": args.reps,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
            "n_incidents": len(camp["incidents"]), "verdict": v,
            "note": note,
        }
        with open(os.path.join(args.out, f"manifest_{tag}.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        print(f"    trazas + manifiesto -> {args.out}")


if __name__ == "__main__":
    main()
