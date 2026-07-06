"""
Condiciones del MVP (memoria §5.3). Aqui se documentan y se ofrece el helper que
deriva el caso "limpio" (sin la fuente envenenada) para C0/C6.

  C0            corpus sin fuente contaminada            -> acierto base
  C1-texto-libre decision en prosa, sin enumerar claims  -> baseline de ataque
  C1-estruct    decision estructurada                    -> se reporta junto a C1-libre
  C3            veneno + resumen + memoria               -> lavado y escritura a memoria
  C7            persistencia: fuente retirada, probe      -> el veneno solo vive en memoria
  C7-control    igual que C7 pero memoria BENIGNA         -> descarta sobre-generalizacion
  C5 / C6       Epistemic Firewall (atacado / limpio)     -> eficacia y coste
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict

from core.types import Case

CONDITIONS: Dict[str, str] = {
    "C0": "limpio (sin fuente contaminada)",
    "C1-free": "texto libre, con veneno, sin defensa (baseline de ataque)",
    "C1-struct": "estructurado, con veneno, sin defensa",
    "C3": "veneno + resumen + escritura a memoria",
    "C7": "persistencia: probe con memoria envenenada, fuente retirada",
    "C7-control": "probe con memoria BENIGNA (control causal)",
    "C5": "atacado + Epistemic Firewall",
    "C6": "limpio + Epistemic Firewall (coste de utilidad)",
}


def clean_case(case: Case) -> Case:
    """Devuelve el caso sin documentos que portan el claim falso (C0/C6)."""
    docs = [d for d in case.documents if not d.carries_false_claim]
    return replace(case, documents=docs, writes_memory=False, poison_source_present=False)
