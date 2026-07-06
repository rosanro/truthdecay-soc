"""
Espacio de acciones del agente SOC (sandbox: solo se escriben a un ledger local).

Cada decision tiene una *direccion*:
  - "restrictive": actuar sobre la amenaza (contener, priorizar, bloquear).
  - "permissive" : ceder / rebajar (cerrar, liberar, diferir, permitir).
  - "neutral"    : abstenerse (pedir mas evidencia).

La direccion es la que usa el mock (persona del agente) y el firewall para razonar
sobre el contenido; NUNCA se usa la verdad-base del caso para producir la decision.
"""

BLOCK_AND_ESCALATE = "block_and_escalate"
CLOSE_FALSE_POSITIVE = "close_false_positive"
KEEP_QUARANTINE = "keep_quarantine"
RELEASE_EMAIL = "release_email"
PRIORITIZE_PATCH = "prioritize_patch"
DEFER_PATCH = "defer_patch"
BLOCK_DEPENDENCY = "block_dependency"
ALLOW_DEPENDENCY = "allow_dependency"
ESCALATE_INCIDENT = "escalate_incident"
REQUEST_MORE_EVIDENCE = "request_more_evidence"
SUPPRESS_RULE = "suppress_rule"

ALL_DECISIONS = {
    BLOCK_AND_ESCALATE, CLOSE_FALSE_POSITIVE, KEEP_QUARANTINE, RELEASE_EMAIL,
    PRIORITIZE_PATCH, DEFER_PATCH, BLOCK_DEPENDENCY, ALLOW_DEPENDENCY,
    ESCALATE_INCIDENT, REQUEST_MORE_EVIDENCE, SUPPRESS_RULE,
}

# Decisiones "seguras / de abstencion": no resuelven, pero no son el objetivo del
# adversario. Relevantes para H-D2 (una defensa que solo se abstiene es inutil).
ABSTAINING = {REQUEST_MORE_EVIDENCE, ESCALATE_INCIDENT}

DIRECTION = {
    BLOCK_AND_ESCALATE: "restrictive",
    KEEP_QUARANTINE: "restrictive",
    PRIORITIZE_PATCH: "restrictive",
    BLOCK_DEPENDENCY: "restrictive",
    ESCALATE_INCIDENT: "restrictive",
    CLOSE_FALSE_POSITIVE: "permissive",
    RELEASE_EMAIL: "permissive",
    DEFER_PATCH: "permissive",
    ALLOW_DEPENDENCY: "permissive",
    SUPPRESS_RULE: "permissive",
    REQUEST_MORE_EVIDENCE: "neutral",
}

# Accion segura por defecto cuando la evidencia canonica no respalda una accion
# permisiva (la usa el firewall). Si hay amenaza restrictiva canonica -> contener.
# Seleccion de accion segura DEPENDIENTE de la familia (del espacio de candidatos),
# en vez de una constante cableada a un caso.
def safe_restrictive(candidates) -> str:
    """Accion restrictiva concreta de contencion; si no hay, escala; si no, pide evidencia."""
    for c in candidates:
        if DIRECTION.get(c) == "restrictive" and c != ESCALATE_INCIDENT:
            return c
    if ESCALATE_INCIDENT in candidates:
        return ESCALATE_INCIDENT
    return REQUEST_MORE_EVIDENCE


def safe_abstain(candidates) -> str:
    if REQUEST_MORE_EVIDENCE in candidates:
        return REQUEST_MORE_EVIDENCE
    if ESCALATE_INCIDENT in candidates:
        return ESCALATE_INCIDENT
    return safe_restrictive(candidates)


def direction_of(decision: str) -> str:
    return DIRECTION.get(decision, "neutral")


def opposite(direction: str) -> str:
    if direction == "restrictive":
        return "permissive"
    if direction == "permissive":
        return "restrictive"
    return "neutral"
