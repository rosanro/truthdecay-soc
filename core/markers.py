"""
Deteccion lexica de la *direccion* de un texto: restrictive / permissive / neutral.

Es un PROXY deliberadamente simple de un juicio semantico (en produccion seria un
modelo NLI o el propio LLM). Lo usan dos componentes DISTINTOS:

  - el mock del agente (persona bajo prueba), para decidir sobre contenido; y
  - el firewall (defensa), para inferir si una fuente respalda o contradice una accion.

Ninguno de los dos lee la verdad-base del caso (authority / is_canonical /
carries_false_claim). Cuando se sustituye el mock por un LLM real, el firewall sigue
usando esta capa; por eso vive fuera del agente.
"""
from __future__ import annotations

PERMISSIVE_MARKERS = [
    "aprobad", "approved", "whitelist", "allowlist ok", "puede ignorar", "pueden ignorar",
    "podeis ignorar", "ignorar las alertas", "ignore the alert", "ignore alerts",
    "safe to close", "puede cerrarse", "cerrar como falso", "false positive",
    "no aplica", "not applicable", "no procede", "benign", "benigno", "trusted telemetry",
    "telemetria aprobada", "release", "liberar", "diferir", "defer", "permitir dependencia",
]

RESTRICTIVE_MARKERS = [
    "bloquear", "block", "escalar", "escalate", "cuarentena", "quarantine",
    "priorizar", "prioritize", "beaconing", "coherente con c2", "c2", "no esta en la allowlist",
    "not in the allowlist", "malicious", "malicioso", "exploit", "vulnerable",
    "kev", "explotada activamente", "actively exploited", "contener", "contain",
    "phishing", "typosquatting", "recien registrado", "recently registered",
    "dominio no aprobado", "mantener en cuarentena",
]


def _hits(text: str, markers) -> int:
    t = (text or "").lower()
    return sum(1 for m in markers if m in t)


def direction_of_text(text: str) -> str:
    """restrictive / permissive / neutral segun el balance de marcadores."""
    p = _hits(text, PERMISSIVE_MARKERS)
    r = _hits(text, RESTRICTIVE_MARKERS)
    if p > r:
        return "permissive"
    if r > p:
        return "restrictive"
    return "neutral"


def contains_any(text: str, markers) -> bool:
    t = (text or "").lower()
    return any(m.lower() in t for m in (markers or []))
