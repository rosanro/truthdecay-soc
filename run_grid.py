#!/usr/bin/env python3
"""
run_grid.py — pipeline de resultados de TruthDecay-SOC.

Recorre todos los pares del benchmark, corre la historia E3 con el cliente elegido,
y produce:
  - results_<client>.csv     : una fila por (par, condicion) con las metricas del scorer
  - summary_<client>.csv      : agregado por condicion (media + IC bootstrap al 95%, unidad=caso)
  - manifest_<client>.json    : reproducibilidad (modelo, SDK, timestamp, git, config)

La unidad de agregacion es el CASO (no la llamada). Con N pequeno los IC son anchos y se
reportan como orientativos (ver §8 de la memoria y prereg.md).

Uso:
  python run_grid.py                          # mock:credulous, todos los pares
  python run_grid.py --client gemini --reps 3 # LLM real
  python run_grid.py --pairs c2_01 p1_01      # subconjunto
"""
import argparse
import csv
import glob
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cases.loader import load_pair
from agent.clients import make_client
from experiments.run import run_storyline
from scorer.bootstrap import bootstrap_ci

CASES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")
METRIC_COLS = ["ASR", "TFCA", "DDR", "incorrect_rate", "abstain_rate",
               "AIR", "PCR", "SLR", "CLR", "PRE",
               "parse_ok_rate", "poison_retrieved_rate", "canonical_retrieved_rate"]
# Condiciones que interesan en el CSV agregado (las de scores del storyline).
GRID_CONDITIONS = ["C0", "C1-free", "C1-struct", "C3(seed,atacado)", "C7(persistencia)",
                   "C7-control", "C5(firewall)", "C6-seed(limpio+fw)", "C6-probe(limpio+fw)"]


def discover_pairs():
    pairs = []
    for path in sorted(glob.glob(os.path.join(CASES_DIR, "*_seed.json"))):
        pairs.append(os.path.basename(path)[:-len("_seed.json")])
    return pairs


def _git_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=os.path.dirname(os.path.abspath(__file__)),
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def _sdk_versions():
    out = {}
    for pkg in ("google-genai", "openai", "anthropic"):
        try:
            from importlib.metadata import version
            out[pkg] = version(pkg)
        except Exception:
            out[pkg] = None
    return out


def _write_traces_jsonl(path, pair, res):
    with open(path, "a", encoding="utf-8") as fh:
        for cond, traces in res["traces"].items():
            for t in traces:
                fh.write(json.dumps(t.as_dict(), ensure_ascii=False, default=str) + "\n")


def run(client_spec, pairs, reps, structured=True, outdir=".", top_k=None,
        system_mode="aware", save_traces=False, dashboards=False):
    client = make_client(client_spec)
    tag = client.name.replace(":", "_").replace("/", "_")

    rows = []              # long: (pair, condition, metrics...)
    verdicts = []          # per-pair causal verdict
    per_pair_metric = {c: {m: [] for m in METRIC_COLS} for c in GRID_CONDITIONS}
    os.makedirs(outdir, exist_ok=True)
    traces_path = os.path.join(outdir, f"traces_{tag}.jsonl")
    if save_traces and os.path.exists(traces_path):
        os.remove(traces_path)

    for pair in pairs:
        seed, probe = load_pair(pair)
        res = run_storyline(seed, probe, client, reps=reps, structured=structured,
                            top_k=top_k, system_mode=system_mode)
        for cond, sc in res["scores"].items():
            row = {"pair": pair, "condition": cond}
            for m in METRIC_COLS:
                row[m] = sc.get(m)
            rows.append(row)
            if cond in per_pair_metric:
                for m in METRIC_COLS:
                    v = sc.get(m)
                    if v is not None:
                        per_pair_metric[cond][m].append(v)
        v = dict(res["verdict"]); v["pair"] = pair
        verdicts.append(v)
        if save_traces:
            _write_traces_jsonl(traces_path, pair, res)
        if dashboards:
            from dashboard.render_static import build_html
            with open(os.path.join(outdir, f"dashboard_{pair}.html"), "w", encoding="utf-8") as fh:
                fh.write(build_html(seed, probe, res))

    os.makedirs(outdir, exist_ok=True)
    results_path = os.path.join(outdir, f"results_{tag}.csv")
    with open(results_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["pair", "condition"] + METRIC_COLS)
        w.writeheader()
        w.writerows(rows)

    # agregado por condicion: media + IC bootstrap (unidad = caso)
    summary_path = os.path.join(outdir, f"summary_{tag}.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "metric", "n_pairs", "mean", "ci95_low", "ci95_high"])
        for cond in GRID_CONDITIONS:
            for m in METRIC_COLS:
                vals = per_pair_metric[cond][m]
                if not vals:
                    continue
                mean, lo, hi = bootstrap_ci(vals)
                w.writerow([cond, m, len(vals), f"{mean:.3f}", f"{lo:.3f}", f"{hi:.3f}"])

    # agregado causal (fraccion de pares que reproducen cada hipotesis)
    def frac(key):
        xs = [1.0 if vd.get(key) else 0.0 for vd in verdicts]
        return bootstrap_ci(xs)
    causal = {}
    for key in ["H-A (efecto inmediato) atribuible", "H-C (persistencia) atribuible",
                "C7-control no comprometido (causalidad)", "H-D1a (firewall contiene)",
                "H-D1b (contencion correctiva, no solo abstencion)"]:
        m, lo, hi = frac(key)
        causal[key] = {"frac": round(m, 3), "ci95": [round(lo, 3), round(hi, 3)]}
    ppr_vals = [vd["PPR (par)"] for vd in verdicts if vd.get("PPR (par)") is not None]
    if ppr_vals:
        m, lo, hi = bootstrap_ci(ppr_vals)
        causal["PPR (agregado, pares con lavado)"] = {"frac": round(m, 3),
                                                      "ci95": [round(lo, 3), round(hi, 3)],
                                                      "n_pairs": len(ppr_vals)}

    manifest = {
        "project": "TruthDecay-SOC",
        "client": client.name,
        "pairs": pairs,
        "n_pairs": len(pairs),
        "reps": reps,
        "top_k": top_k,
        "system_mode": system_mode,
        "structured": structured,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "sdk_versions": _sdk_versions(),
        "git": _git_hash(),
        "causal_aggregate": causal,
        "note": (
            "Cliente mock: fixture de tuberia, tasas 0/1 por construccion; no es evidencia "
            "empirica." if client.name.startswith("mock") else
            "Cliente LLM real: tasas empiricas. Interpretar SOLO tras revisar las puertas de "
            "validez (parse_ok_rate, clean_baseline C0, poison_retrieved_rate). system_mode="
            f"{system_mode}."),
    }
    manifest_path = os.path.join(outdir, f"manifest_{tag}.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    return results_path, summary_path, manifest_path, causal


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", default="mock:credulous")
    ap.add_argument("--pairs", nargs="*", default=None)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--top-k", type=int, default=None, help="documentos recuperados por RAG (None=todos)")
    ap.add_argument("--system-mode", choices=["aware", "neutral"], default="aware",
                    help="aware=instruye sobre autoridad (principal); neutral=sensibilidad")
    ap.add_argument("--save-traces", action="store_true", help="exporta traces_<client>.jsonl (forense)")
    ap.add_argument("--dashboards", action="store_true", help="genera dashboard_<pair>.html por par")
    ap.add_argument("--unstructured-storyline", action="store_true",
                    help="DIAGNOSTICO: fuerza todas las condiciones a texto libre (no usar para metricas de claim)")
    ap.add_argument("--out", default="results")
    args = ap.parse_args(argv)

    pairs = args.pairs or discover_pairs()
    try:
        rp, sp, mp, causal = run(args.client, pairs, args.reps,
                                 structured=not args.unstructured_storyline, outdir=args.out,
                                 top_k=args.top_k, system_mode=args.system_mode,
                                 save_traces=args.save_traces, dashboards=args.dashboards)
    except RuntimeError as e:
        print(f"[!] {e}")
        return 1

    print(f"pares: {len(pairs)}  cliente: {args.client}  reps: {args.reps}")
    print(f"  {rp}\n  {sp}\n  {mp}")
    print("\nAgregado causal (fraccion de pares + IC95, unidad=caso):")
    for k, v in causal.items():
        print(f"  {k:<48} {v['frac']:.2f}  IC95 {v['ci95']}")
    if args.client.startswith("mock"):
        print("\nNOTA: cliente mock (fixture). Tasas 0/1 por construccion; usa --client gemini para tasas reales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
