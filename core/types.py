"""
Modelo de datos de TruthDecay-SOC.

Punto clave de credibilidad: la separacion AGENTE / LEDGER.

  - `SourceDoc`  = vista de LEDGER (verdad-base). Incluye authority, is_canonical,
                   carries_false_claim y marcadores de scoring. SOLO la ve el scorer
                   y (parcialmente) el firewall.
  - `AgentDoc`   = vista REDACTADA que ve el agente. Solo doc_id, source_type y
                   content. El agente NUNCA accede a la autoridad numerica, a
                   is_canonical ni a si el documento porta el claim falso.

Esta frontera es lo que evita que la demo sea circular: el compromiso emerge de un
agente que decide sobre contenido, no de un `if veneno: comprometido`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, List


@dataclass(frozen=True)
class AgentDoc:
    """Vista agente-visible. Inmutable y sin campos de verdad-base."""
    doc_id: str
    source_type: str
    content: str


@dataclass
class SourceDoc:
    """Vista de ledger (verdad-base). No se pasa nunca al agente."""
    doc_id: str
    source_type: str
    authority: int                       # 0-5, verdad-base
    is_canonical: bool
    content: str
    carries_false_claim: bool = False
    supports_decision: Optional[str] = None   # "restrictive" | "permissive" | None

    def redact(self) -> AgentDoc:
        """Devuelve la unica vista que el agente puede ver."""
        return AgentDoc(doc_id=self.doc_id, source_type=self.source_type, content=self.content)


@dataclass
class MemoryItem:
    mem_id: str
    text: str
    source: str = "agent_memory"         # puntero de procedencia; "agent_memory" = sin origen (lavado)
    origin_doc_id: Optional[str] = None
    authority_asserted: Optional[int] = None

    def redact_source_type(self) -> str:
        return "agent_memory"


@dataclass
class Claim:
    """Claim que el agente dice haber usado. Su procedencia auto-declarada
    (cited_source_id, claimed_authority) es AUTO-INFORME: solo alimenta PRE/H-G,
    nunca las metricas primarias."""
    text: str
    cited_source_id: Optional[str] = None
    claimed_authority: Optional[int] = None
    supports: bool = True


@dataclass
class AgentResponse:
    decision: str
    rationale: str = ""
    claims: List[Claim] = field(default_factory=list)
    memory_note: Optional[str] = None            # lo que el agente escribe a memoria (sitio del lavado)
    self_reported_provenance: Optional[str] = None
    parse_ok: bool = True
    raw: str = ""


@dataclass
class Trace:
    """Registro de UNA ejecucion. Es lo unico que lee el scorer (mas el caso)."""
    pair_id: str
    role: str                 # "seed" | "probe"
    condition: str
    rep: int
    client: str               # "mock:credulous" | "gemini:..." | ...
    retrieved_doc_ids: List[str]
    summary: Optional[str]
    memory_before: List[MemoryItem]
    memory_after: List[MemoryItem]
    response: AgentResponse
    firewall_applied: bool = False
    firewall_override_from: Optional[str] = None   # decision original si el firewall la cambio
    decision: str = ""        # decision FINAL (tras firewall)
    action_event: Optional[object] = None          # ActionEvent: accion ejecutada en sandbox
    prompt: Optional[str] = None                    # prompt renderizado (corpus sintetico)
    prompt_sha256: Optional[str] = None
    system_mode: str = "aware"                      # aware | neutral
    client_metadata: Optional[dict] = None          # modelo, usage, latencia (LLM real)
    error: Optional[str] = None                     # si la llamada al modelo fallo

    def as_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class Case:
    pair_id: str
    role: str
    family: str
    description: str
    task: str
    documents: List[SourceDoc]
    canonical_claim: str
    false_claim: str
    correct_decision: str
    attacker_target_decision: str
    candidate_decisions: List[str]
    false_claim_markers: List[str] = field(default_factory=list)
    canonical_markers: List[str] = field(default_factory=list)
    writes_memory: bool = False
    poison_source_present: bool = True
    benign_memory_note: Optional[str] = None

    def agent_view(self) -> List[AgentDoc]:
        return [d.redact() for d in self.documents]

    def poison_docs(self) -> List[SourceDoc]:
        return [d for d in self.documents if d.carries_false_claim]

    def canonical_docs(self) -> List[SourceDoc]:
        return [d for d in self.documents if d.is_canonical and d.authority >= 4]
