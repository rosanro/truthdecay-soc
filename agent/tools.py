"""
Herramientas SOC simuladas (sandbox). La decision del agente se "ejecuta" como una
accion registrada en un ledger local; nunca toca sistemas reales. Hace literal la
frase de la memoria: "acciones de seguridad ejecutadas en sandbox".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# Efecto declarado de cada accion (para el registro y el dashboard).
ACTION_EFFECT = {
    "block_and_escalate": "host aislado y ticket Tier-2 abierto (sandbox)",
    "close_false_positive": "alerta cerrada como falso positivo (sandbox)",
    "keep_quarantine": "correo retenido en cuarentena (sandbox)",
    "release_email": "correo liberado al buzon (sandbox)",
    "prioritize_patch": "parche priorizado en 48h (sandbox)",
    "defer_patch": "parche diferido (sandbox)",
    "block_dependency": "dependencia bloqueada en el registro (sandbox)",
    "allow_dependency": "dependencia permitida (sandbox)",
    "escalate_incident": "incidente escalado a analista humano (sandbox)",
    "request_more_evidence": "solicitada mas evidencia; sin accion (sandbox)",
    "suppress_rule": "regla de deteccion suprimida (sandbox)",
}


@dataclass
class ActionEvent:
    decision: str
    pair_id: str
    role: str
    condition: str
    effect: str
    ts: str
    reverted_by_firewall: bool = False


def execute_action(decision: str, pair_id: str, role: str, condition: str,
                   reverted_by_firewall: bool = False) -> ActionEvent:
    """Registra (no ejecuta de verdad) la accion elegida en el sandbox."""
    return ActionEvent(
        decision=decision,
        pair_id=pair_id,
        role=role,
        condition=condition,
        effect=ACTION_EFFECT.get(decision, f"accion desconocida: {decision} (sandbox)"),
        ts=datetime.now(timezone.utc).isoformat(),
        reverted_by_firewall=reverted_by_firewall,
    )
