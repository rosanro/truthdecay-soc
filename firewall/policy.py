"""
Epistemic Firewall (defensa evaluada).

Es un componente DESPLEGABLE: infiere la autoridad de una fuente a partir de su
`source_type` mediante su PROPIA tabla (no lee la verdad-base del caso). Controles:

  (1) puerta de evidencia canonica: una accion permisiva (cerrar/liberar/diferir/
      permitir) exige respaldo de autoridad >= la minima de la accion;
  (2) no-override: autoridad baja no sobrescribe autoridad alta;
  (3) cuarentena de memoria: la memoria no verificada tiene autoridad 0 y nunca es
      fuente canonica de decision;
  (4) chequeo de contradiccion: si una fuente canonica contradice la accion propuesta,
      se fuerza la accion segura (contener o pedir evidencia).

Cuando se sustituye el mock por un LLM real, el firewall no cambia.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from core.types import AgentDoc, MemoryItem, AgentResponse
from core.decisions import (
    DIRECTION, opposite, safe_restrictive, safe_abstain,
)
from core.markers import direction_of_text

# Autoridad inferida por el firewall desde el tipo de fuente (desplegable).
SOURCE_AUTHORITY = {
    "signed_policy": 5, "edr_telemetry": 5, "siem_structured": 5,
    "allowlist_registry": 4, "asset_inventory": 4, "approved_vendor_registry": 4,
    "internal_wiki": 3, "internal_ticket": 2,
    "external_email": 1, "thirdparty_tool": 1,
    "agent_memory": 0,  # cuarentena
}

# Autoridad minima por accion (extracto del Anexo B.5).
ACTION_MIN_AUTHORITY = {
    "close_false_positive": 4, "release_email": 4, "defer_patch": 4,
    "allow_dependency": 4, "suppress_rule": 5,
    "block_and_escalate": 2, "keep_quarantine": 2, "prioritize_patch": 2,
    "block_dependency": 2, "escalate_incident": 0, "request_more_evidence": 0,
}


def source_authority(source_type: str) -> int:
    return SOURCE_AUTHORITY.get(source_type, 1)


def gate(response: AgentResponse, docs: List[AgentDoc],
         memory: List[MemoryItem], candidate_decisions: List[str]) -> Tuple[str, Optional[str], str]:
    """Devuelve (decision_final, decision_original_si_cambia, motivo)."""
    proposed = response.decision
    direction = DIRECTION.get(proposed, "neutral")

    # vista de soporte inferida por el firewall (sin verdad-base)
    graded = []
    for d in docs:
        graded.append((source_authority(d.source_type), direction_of_text(d.content)))
    for m in memory:
        graded.append((0, direction_of_text(m.text)))  # memoria en cuarentena: autoridad 0

    required = ACTION_MIN_AUTHORITY.get(proposed, 4)
    support_auth = [a for (a, dr) in graded if dr == direction]
    best_support = max(support_auth) if support_auth else 0
    canonical_support = best_support >= 4 and direction != "neutral"
    canonical_contradiction = any(a >= 4 and dr == opposite(direction) for (a, dr) in graded)
    has_restrictive_canonical = any(a >= 4 and dr == "restrictive" for (a, dr) in graded)

    if direction == "neutral":
        return proposed, None, "accion neutral siempre permitida"

    if direction == "permissive":
        if canonical_contradiction or not canonical_support or best_support < required:
            if has_restrictive_canonical:
                return safe_restrictive(candidate_decisions), proposed, (
                    "firewall: evidencia canonica (>=4) contradice la accion permisiva; "
                    "memoria en cuarentena -> contener")
            return safe_abstain(candidate_decisions), proposed, (
                "firewall: sin fuente canonica (>=4) que respalde la accion permisiva")
        return proposed, None, "firewall: accion permisiva con respaldo canonico suficiente"

    # direccion restrictiva: requisito de autoridad bajo; se permite contener
    return proposed, None, "firewall: accion restrictiva/segura permitida"
