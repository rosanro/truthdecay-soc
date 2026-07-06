#!/usr/bin/env python3
"""
TruthDecay-SOC - demo de extremo a extremo (experimento central E3).

A diferencia del andamiaje anterior, aqui la decision NO esta cableada: el agente
(mock con persona, o un LLM real) decide sobre CONTENIDO redactado, y el scorer
puntua desde el ledger, no desde el auto-informe. La cadena mostrada es:

  C0            limpio            -> deberia acertar (puerta de validez)
  C3  seed      con veneno        -> adopta el claim falso y lo escribe en memoria
  C7  probe     fuente retirada   -> SIGUE equivocandose solo por la memoria (persistencia)
  C7-control    memoria benigna   -> NO se equivoca (la causa es el contenido falso, no la memoria)
  C5  probe+fw  Epistemic Firewall-> se contiene (memoria en cuarentena, canonica prevalece)

Uso:
  python demo.py                          # mock:credulous (sin red, determinista)
  python demo.py --client mock:skeptical  # agente esceptico (no se deja enganar)
  python demo.py --client gemini          # LLM real (requiere GEMINI_API_KEY)
  python demo.py --reps 3                 # varias repeticiones (decision mayoritaria)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cases.loader import load_pair
from agent.clients import make_client
from experiments.run import run_storyline
from scorer.causal import majority


def line(txt=""):
    print(txt)


def hr(txt):
    print("\n" + "=" * 74)
    print(txt)
    print("=" * 74)


def fmt(v):
    if v is None:
        return "  -"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def show_condition(name, traces, correct, target):
    dec = majority(traces)
    tag = "COMPROMETIDO" if dec == target else ("correcto" if dec == correct else "abstiene/otro")
    line(f"  {name:<16} decision(mayoria) = {dec:<22} [{tag}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", default="mock:credulous")
    ap.add_argument("--case", default="c2_01")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--top-k", type=int, default=None, help="documentos recuperados por RAG (None=todos)")
    ap.add_argument("--system-mode", choices=["aware", "neutral"], default="aware",
                    help="aware=instruye sobre autoridad (principal); neutral=analisis de sensibilidad")
    ap.add_argument("--unstructured-storyline", action="store_true",
                    help="DIAGNOSTICO: fuerza TODAS las condiciones a texto libre (borra metricas de claim). "
                         "C1-texto-libre ya se ejecuta siempre por separado; no usar para la corrida principal.")
    args = ap.parse_args()

    seed_case, probe_case = load_pair(args.case)
    try:
        client = make_client(args.client)
    except RuntimeError as e:
        print(f"\n[!] No se pudo iniciar el cliente '{args.client}': {e}")
        print("    Prueba primero sin red:  python demo.py            (mock, determinista)")
        print("    Para LLM real (Gemini):  pip install -e \".[gemini]\"")
        print("                             export GEMINI_API_KEY=...")
        print("                             python demo.py --client gemini --reps 3")
        sys.exit(1)
    is_mock = args.client.startswith("mock")

    hr(f"TruthDecay-SOC  |  caso {args.case}  |  cliente {client.name}  |  reps {args.reps}")
    if is_mock:
        line("  NOTA: cliente MOCK (fixture determinista). Valida la tuberia y el scorer;")
        line("  NO estima la tasa del LLM real. Las tasas reales se miden con --client gemini.")

    res = run_storyline(seed_case, probe_case, client, reps=args.reps,
                        structured=not args.unstructured_storyline, top_k=args.top_k,
                        system_mode=args.system_mode)
    tr = res["traces"]
    correct, target = seed_case.correct_decision, seed_case.attacker_target_decision

    hr("CADENA DE DECISION (mayoria sobre repeticiones)")
    show_condition("C0 limpio", tr["C0"], correct, target)
    show_condition("C1-free (ataque)", tr["C1-free"], correct, target)
    show_condition("C3 seed atacado", tr["C3"], correct, target)
    show_condition("C7 persistencia", tr["C7"], correct, target)
    show_condition("C7-control", tr["C7-control"], correct, target)
    show_condition("C5 firewall", tr["C5"], correct, target)

    line("\n  Memoria escrita por el seed (lo que sobrevive al borrado de la fuente):")
    for m in res["poison_memory"]:
        line(f"    [{m.mem_id}] source={m.source}  \"{m.text[:70]}\"")

    hr("METRICAS (scorer determinista, desde el ledger; sin LLM juez)")
    cols = [("n", "n"), ("ASR", "ASR"), ("TFCA", "TFCA"), ("DDR", "DDR"),
            ("incorrect_rate", "incorr"), ("abstain_rate", "abst"),
            ("AIR", "AIR"), ("PCR", "PCR"), ("SLR", "SLR"), ("PRE", "PRE")]
    header = "  " + "cond".ljust(19) + "".join(lbl.rjust(8) for _, lbl in cols)
    line(header)
    line("  " + "-" * (len(header) - 2))
    for cond, sc in res["scores"].items():
        row = "  " + cond.ljust(19)
        for key, _ in cols:
            row += fmt(sc.get(key)).rjust(8)
        line(row)

    hr("VEREDICTO CAUSAL (but-for, decision mayoritaria)")
    for k, v in res["verdict"].items():
        line(f"  {k:<48} {fmt(v)}")

    hr("LECTURA")
    v = res["verdict"]
    if v["H-C (persistencia) atribuible"] and v["C7-control no comprometido (causalidad)"]:
        line("  PERSISTENCIA ATRIBUIBLE: el probe se cierra mal SOLO por la memoria")
        line("  contaminada (la fuente ya no existe), y el control con memoria benigna NO")
        line("  falla -> el fallo es del contenido falso, no de la mera presencia de memoria.")
    elif v["H-A (efecto inmediato) atribuible"] and not v["H-C (persistencia) atribuible"]:
        line("  Efecto inmediato SI, persistencia NO: pivote (caracterizar por que la")
        line("  memoria no conserva el veneno). Resultado negativo bien atribuido = valido.")
    else:
        line(f"  Persona/cliente '{client.name}': la cadena de compromiso no se reproduce")
        line("  en su totalidad (esperado, p.ej., en la persona esceptica).")
    if v["H-D1a (firewall contiene)"]:
        line("  El Epistemic Firewall contiene el ataque (memoria en cuarentena; la")
        line("  evidencia canonica >=4 prevalece).")
    line()


if __name__ == "__main__":
    main()
