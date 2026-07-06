#!/usr/bin/env python3
"""
dashboard/render_static.py — dashboard estatico (HTML autocontenido, sin dependencias).

Muestra la cadena que promete la memoria: fuente -> claim -> memoria -> accion, con la
correccion del Epistemic Firewall, para al menos un caso de persistencia.

Uso:
  python dashboard/render_static.py --pair c2_01 --out demo_c2_01.html
  python dashboard/render_static.py --pair p1_01 --client mock:credulous
"""
import argparse
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cases.loader import load_pair
from agent.clients import make_client
from experiments.run import run_storyline
from scorer.causal import majority

CSS = """
:root{--bg:#0f1420;--card:#1a2233;--ink:#e8edf6;--mut:#93a1b8;--line:#2b364c;
--bad:#ef5f6b;--good:#38c793;--warn:#e0a13b;--accent:#5b8def}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:940px;margin:0 auto;padding:32px 22px 60px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;letter-spacing:.04em;text-transform:uppercase;
color:var(--mut);margin:34px 0 14px;font-weight:600}
.sub{color:var(--mut);margin:0 0 8px}
.chain{display:flex;flex-wrap:wrap;gap:10px}
.step{flex:1;min-width:150px;background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:14px}
.step .k{font-size:12px;color:var(--mut);margin-bottom:6px}
.step .d{font-weight:600;font-size:14px}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;margin-top:8px}
.b-bad{background:rgba(239,95,107,.15);color:var(--bad)}
.b-good{background:rgba(56,199,147,.15);color:var(--good)}
.b-warn{background:rgba(224,161,59,.15);color:var(--warn)}
.flow{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 18px}
.node{padding:12px 0;border-bottom:1px dashed var(--line)}
.node:last-child{border-bottom:0}
.node .t{font-size:12px;color:var(--mut)}
.node .v{font-weight:600}
.arrow{color:var(--accent);font-weight:700;padding:2px 0 2px 6px}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;color:#c7d3ea}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
th,td{text-align:right;padding:7px 8px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{color:var(--mut);font-weight:600}
.v0{color:var(--mut)}.v1{color:var(--bad);font-weight:700}
.foot{color:var(--mut);font-size:12px;margin-top:26px}
.tag{display:inline-block;background:rgba(91,141,239,.14);color:var(--accent);
padding:2px 8px;border-radius:6px;font-size:12px;margin-left:6px}
"""


def badge(dec, correct, target):
    if dec == target:
        return '<span class="badge b-bad">COMPROMETIDO</span>'
    if dec == correct:
        return '<span class="badge b-good">correcto</span>'
    return '<span class="badge b-warn">abstiene / otro</span>'


def esc(s):
    return html.escape(str(s))


def build_html(seed, probe, res):
    correct, target = seed.correct_decision, seed.attacker_target_decision
    tr, scores, verdict = res["traces"], res["scores"], res["verdict"]
    poison_doc = next((d for d in seed.documents if d.carries_false_claim), None)
    mem = res["poison_memory"][0] if res["poison_memory"] else None

    steps_order = [("C0 limpio", "C0"), ("C1-free (ataque)", "C1-free"),
                   ("C3 seed (lavado)", "C3"), ("C7 persistencia", "C7"),
                   ("C7-control", "C7-control"), ("C5 firewall", "C5")]
    chain = ""
    for label, key in steps_order:
        dec = majority(tr[key])
        chain += (f'<div class="step"><div class="k">{esc(label)}</div>'
                  f'<div class="d mono">{esc(dec)}</div>{badge(dec, correct, target)}</div>')

    # flujo vertical fuente -> claim -> memoria -> probe -> accion -> firewall
    probe_dec = majority(tr["C7"])
    fw_dec = majority(tr["C5"])
    fw_from = next((t.firewall_override_from for t in tr["C5"] if t.firewall_override_from), None)
    flow = f"""
    <div class="node"><div class="t">FUENTE de baja autoridad (seed)</div>
      <div class="v mono">{esc(poison_doc.source_type if poison_doc else '?')} · autoridad {poison_doc.authority if poison_doc else '?'}</div>
      <div class="sub">{esc(poison_doc.content if poison_doc else '')}</div></div>
    <div class="arrow">&#8595; introduce claim falso</div>
    <div class="node"><div class="t">CLAIM FALSO</div>
      <div class="v">{esc(seed.false_claim)}</div></div>
    <div class="arrow">&#8595; se escribe en memoria (pierde procedencia)</div>
    <div class="node"><div class="t">MEMORIA del agente</div>
      <div class="v mono">{esc(mem.mem_id if mem else 'n/a')} · source={esc(mem.source if mem else 'n/a')}</div>
      <div class="sub">{esc(mem.text if mem else '')}</div></div>
    <div class="arrow">&#8595; recuperada en el PROBE (la fuente original ya no existe)</div>
    <div class="node"><div class="t">DECISION del agente (sin defensa)</div>
      <div class="v mono v1">{esc(probe_dec)}</div>
      <div class="sub">{'coincide con el objetivo del adversario' if probe_dec==target else 'no comprometida'}</div></div>
    <div class="arrow">&#8595; Epistemic Firewall (memoria en cuarentena, canonica prevalece)</div>
    <div class="node"><div class="t">DECISION corregida</div>
      <div class="v mono" style="color:var(--good)">{esc(fw_dec)}</div>
      <div class="sub">{('revierte '+esc(fw_from)) if fw_from else 'sin cambio'}</div></div>
    """

    # tabla de metricas
    cols = [("ASR", "ASR"), ("TFCA", "TFCA"), ("DDR", "DDR"), ("AIR", "AIR"),
            ("PCR", "PCR"), ("SLR", "SLR"), ("CLR", "CLR"), ("PRE", "PRE")]
    head = "<tr><th>condicion</th>" + "".join(f"<th>{c}</th>" for _, c in cols) + "</tr>"
    body = ""
    for label, key in [("C0", "C0"), ("C1-free", "C1-free"), ("C3(seed,atacado)", "C3(seed,atacado)"),
                       ("C7(persistencia)", "C7(persistencia)"), ("C7-control", "C7-control"),
                       ("C5(firewall)", "C5(firewall)"), ("C6-seed(limpio+fw)", "C6-seed(limpio+fw)"), ("C6-probe(limpio+fw)", "C6-probe(limpio+fw)")]:
        sc = scores.get(key, {})
        cells = ""
        for k, _ in cols:
            v = sc.get(k)
            if v is None:
                cells += '<td class="v0">-</td>'
            else:
                cls = "v1" if v >= 0.5 else "v0"
                cells += f'<td class="{cls}">{v:.2f}</td>'
        body += f"<tr><td>{esc(label)}</td>{cells}</tr>"

    ver = ""
    for k, v in verdict.items():
        ver += f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>"

    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TruthDecay-SOC · {esc(seed.pair_id)}</title><style>{CSS}</style></head><body><div class="wrap">
<h1>TruthDecay-SOC <span class="tag">{esc(seed.family)}</span></h1>
<p class="sub">Caso <b>{esc(seed.pair_id)}</b> — {esc(seed.description)}</p>
<h2>Cadena de decision</h2><div class="chain">{chain}</div>
<h2>Persistencia: fuente &#8594; claim &#8594; memoria &#8594; accion</h2><div class="flow">{flow}</div>
<h2>Metricas (scorer determinista, desde el ledger)</h2>
<table>{head}{body}</table>
<h2>Veredicto causal (but-for)</h2><table>{ver}</table>
<p class="foot">Generado con cliente mock (fixture de integracion). Las tasas 0/1 son por
construccion; la medicion empirica se obtiene con un LLM real (--client gemini).</p>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="c2_01")
    ap.add_argument("--client", default="mock:credulous")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    seed, probe = load_pair(args.pair)
    res = run_storyline(seed, probe, make_client(args.client), reps=args.reps)
    out = args.out or f"demo_{args.pair}.html"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build_html(seed, probe, res))
    print(f"dashboard escrito: {out}")


if __name__ == "__main__":
    main()
