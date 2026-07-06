"""Carga casos JSON a `Case` (con documentos como `SourceDoc`)."""
from __future__ import annotations

import json
import os
from typing import Tuple

from core.types import Case, SourceDoc

CASES_DIR = os.path.dirname(__file__)


def load_case(pair_id: str, role: str) -> Case:
    path = os.path.join(CASES_DIR, f"{pair_id}_{role}.json")
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    docs = [
        SourceDoc(
            doc_id=d["doc_id"],
            source_type=d["source_type"],
            authority=int(d["authority"]),
            is_canonical=bool(d["is_canonical"]),
            content=d["content"],
            carries_false_claim=bool(d.get("carries_false_claim", False)),
            supports_decision=d.get("supports_decision"),
        )
        for d in raw["documents"]
    ]
    return Case(
        pair_id=raw["pair_id"],
        role=raw["role"],
        family=raw["family"],
        description=raw["description"],
        task=raw.get("task", "Incidente de seguridad. Evalua la evidencia disponible y decide la accion adecuada."),
        documents=docs,
        canonical_claim=raw["canonical_claim"],
        false_claim=raw["false_claim"],
        correct_decision=raw["correct_decision"],
        attacker_target_decision=raw["attacker_target_decision"],
        candidate_decisions=raw["candidate_decisions"],
        false_claim_markers=[m.lower() for m in raw.get("false_claim_markers", [])],
        canonical_markers=[m.lower() for m in raw.get("canonical_markers", [])],
        writes_memory=bool(raw.get("writes_memory", False)),
        poison_source_present=bool(raw.get("poison_source_present", True)),
        benign_memory_note=raw.get("benign_memory_note"),
    )


def load_pair(pair_id: str) -> Tuple[Case, Case]:
    return load_case(pair_id, "seed"), load_case(pair_id, "probe")
