"""
Capa de cliente LLM: agnostica de proveedor.

  - MockClient(persona)      : DETERMINISTA, sin red. Dos personas:
        * "credulous": adopta cualquier afirmacion permisiva de CUALQUIER fuente
                       (incl. memoria) -> modela un agente sin tipado epistemico.
        * "skeptical": solo confia en tipos de fuente canonicos; ignora la
                       reasegurancia no canonica.
     El mock NO lee la verdad-base del caso: solo el contenido del prompt (lo mismo
     que veria el LLM). Sirve de FIXTURE para los tests golden y para validar la
     tuberia; las TASAS reales de compromiso las mide el LLM real (E1-E3/E6).
  - GeminiClient             : google-genai, salida estructurada (response_schema).
  - OpenAICompatibleClient   : OpenAI SDK con base_url (OpenAI, vLLM, Ollama, ...).

Todos exponen `complete(system, user) -> str`; la cadena vuelve por el MISMO parser.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import List, Optional, Protocol, Tuple

from core.decisions import DIRECTION
from core.markers import direction_of_text, PERMISSIVE_MARKERS

CANONICAL_SOURCE_TYPES = {
    "edr_telemetry", "signed_policy", "siem_structured",
    "allowlist_registry", "asset_inventory", "approved_vendor_registry",
}

_BLOCK_RE = re.compile(
    r"\[source:\s*([^\|]+?)\s*\|\s*id:\s*([^\]]+?)\s*\]\n(.*?)(?=\n\n\[source:|\n\n===|\Z)",
    re.DOTALL,
)


class LLMClient(Protocol):
    name: str
    def complete(self, system: str, user: str) -> str: ...


# ---------------------------------------------------------------- mock

def _parse_blocks(user: str) -> List[Tuple[str, str, str]]:
    """Devuelve [(source_type, doc_id, content)] tal como aparecen en el prompt."""
    out = []
    for m in _BLOCK_RE.finditer(user):
        out.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    return out


def _parse_actions(user: str) -> List[str]:
    m = re.search(r"ACTIONS:\s*(.+)", user)
    if not m:
        return []
    return [a.strip() for a in m.group(1).split("|")]


def _is_structured(user: str) -> bool:
    return "Responde SOLO con JSON" in user


def _pick(candidates: List[str], direction: str) -> Optional[str]:
    for c in candidates:
        if DIRECTION.get(c) == direction:
            return c
    return None


def _first_marker_sentence(content: str) -> str:
    for sent in re.split(r"(?<=[.!?])\s+", content):
        low = sent.lower()
        if any(mk in low for mk in PERMISSIVE_MARKERS):
            return sent.strip()
    return content.strip().split(".")[0]


class MockClient:
    """Fixture determinista. NO estima la tasa del LLM real; ejercita el harness."""

    def __init__(self, persona: str = "credulous"):
        assert persona in ("credulous", "skeptical")
        self.persona = persona
        self.name = f"mock:{persona}"

    def complete(self, system: str, user: str) -> str:
        blocks = _parse_blocks(user)
        candidates = _parse_actions(user)
        structured = _is_structured(user)

        graded = [(st, did, content, direction_of_text(content)) for (st, did, content) in blocks]
        permissive = [b for b in graded if b[3] == "permissive"]
        restrictive = [b for b in graded if b[3] == "restrictive"]
        canon_restrictive = [b for b in restrictive if b[0] in CANONICAL_SOURCE_TYPES]
        canon_permissive = [b for b in permissive if b[0] in CANONICAL_SOURCE_TYPES]

        decision = None
        adopted = None  # (source_type, id, content)

        if self.persona == "credulous":
            if permissive:
                decision = _pick(candidates, "permissive")
                adopted = permissive[0][:3]
            elif restrictive:
                decision = _pick(candidates, "restrictive")
                adopted = restrictive[0][:3]
        else:  # skeptical: solo confia en fuentes canonicas
            if canon_restrictive and not canon_permissive:
                decision = _pick(candidates, "restrictive")
                adopted = canon_restrictive[0][:3]
            elif canon_permissive:
                decision = _pick(candidates, "permissive")
                adopted = canon_permissive[0][:3]
            elif restrictive:
                decision = _pick(candidates, "restrictive")
                adopted = restrictive[0][:3]

        if decision is None:
            decision = "request_more_evidence" if "request_more_evidence" in candidates else (candidates[0] if candidates else "request_more_evidence")

        # nota de memoria = frase adoptada SIN puntero a fuente (lavado)
        memory_note = ""
        claims = []
        if adopted is not None:
            st, did, content = adopted
            memory_note = _first_marker_sentence(content) if DIRECTION.get(decision) == "permissive" else content.split(".")[0].strip()
            # credulo infla la autoridad auto-declarada (fuente PRE)
            claimed_auth = 5 if self.persona == "credulous" else (5 if st in CANONICAL_SOURCE_TYPES else 2)
            claims = [{"text": content[:160], "source_id": did, "authority": claimed_auth, "supports": True}]

        if structured:
            payload = {
                "decision": decision,
                "rationale": f"[{self.name}] adopta {adopted[1] if adopted else 'nada'}",
                "claims": claims,
                "memory_note": memory_note,
            }
            return json.dumps(payload, ensure_ascii=False)
        else:
            src = adopted[1] if adopted else "n/a"
            return (f"[{self.name}] Baso la decision en {src}. "
                    f"{memory_note}\nDECISION: {decision}")


def _wants_json(user: str) -> bool:
    return "Responde SOLO con JSON" in user


def _call_with_retries(fn, attempts: int = 3, base: float = 0.8):
    """Reintenta ante fallos transitorios (red, 429, 5xx) con backoff exponencial."""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 (queremos capturar cualquier fallo de servicio)
            last = e
            if i < attempts - 1:
                time.sleep(base * (2 ** i))
    raise last


# Esquema JSON del contrato del agente (para structured output de Gemini/OpenAI).
AGENT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string"},
        "rationale": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_id": {"type": "string"},
                    "authority": {"type": "integer"},
                    "supports": {"type": "boolean"},
                },
                "required": ["text"],
            },
        },
        "memory_note": {"type": "string"},
    },
    "required": ["decision"],
}


# ---------------------------------------------------------------- Gemini

class GeminiClient:
    """Cliente Gemini (SDK unificado `google-genai`).

    Instalacion:  pip install -e ".[gemini]"   (o  pip install google-genai)
    Credencial:   export GEMINI_API_KEY=...     (o GOOGLE_API_KEY)
    Modelo por defecto: gemini-2.5-flash (estable). Para otros, consulta la lista
    vigente en ai.google.dev/gemini-api/docs/models y usa gemini:MODELO.
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        try:
            from google import genai  # import diferido
        except ImportError as e:
            raise RuntimeError(
                "Falta el SDK. Instala:  pip install -e \".[gemini]\"") from e
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError(
                "Falta la credencial. Exporta GEMINI_API_KEY (o GOOGLE_API_KEY).")
        self._genai = genai
        self._client = genai.Client(api_key=key)
        self.model = model
        self.name = f"gemini:{model}"
        self.last_metadata = None

    @staticmethod
    def _extract_text(resp) -> str:
        try:
            t = resp.text
            if t:
                return t
        except Exception:
            pass
        # fallback: concatenar partes de texto, saltando 'thought parts' de 2.5+
        out = []
        for cand in getattr(resp, "candidates", []) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", []) or []:
                if getattr(part, "thought", False):
                    continue
                txt = getattr(part, "text", None)
                if txt:
                    out.append(txt)
        return "".join(out)

    def _metadata(self, resp, latency_ms):
        um = getattr(resp, "usage_metadata", None)
        g = lambda a: getattr(um, a, None) if um else None
        return {
            "model": self.model,
            "latency_ms": round(latency_ms, 1),
            "prompt_token_count": g("prompt_token_count"),
            "candidates_token_count": g("candidates_token_count"),
            "total_token_count": g("total_token_count"),
            "finish_reason": (getattr(resp.candidates[0], "finish_reason", None)
                              if getattr(resp, "candidates", None) else None),
        }

    def _once(self, system, user, want_json, use_schema):
        cfg = dict(system_instruction=system, temperature=0.0)
        if want_json:
            cfg["response_mime_type"] = "application/json"
            if use_schema:
                cfg["response_schema"] = AGENT_RESPONSE_SCHEMA
        t0 = time.time()
        resp = self._client.models.generate_content(
            model=self.model, contents=user, config=self._build_config(cfg))
        self.last_metadata = self._metadata(resp, (time.time() - t0) * 1000)
        return self._extract_text(resp)

    def complete(self, system: str, user: str) -> str:
        want_json = _wants_json(user)
        use_schema = want_json
        while True:
            try:
                return _call_with_retries(lambda: self._once(system, user, want_json, use_schema))
            except Exception:
                if use_schema:            # el modelo/SDK rechazo el schema: reintenta sin el
                    use_schema = False
                    continue
                raise

    @staticmethod
    def _build_config(cfg):
        """Envuelve la config en GenerateContentConfig si el SDK esta presente; si no
        (p. ej. en tests con la red falseada y sin google-genai), devuelve el dict tal
        cual: el objeto de red real ignora el tipo concreto en ese escenario."""
        try:
            from google.genai import types
            return types.GenerateContentConfig(**cfg)
        except ModuleNotFoundError:
            return cfg


# ---------------------------------------------------------------- OpenAI-compatible

class OpenAICompatibleClient:
    """OpenAI SDK con base_url configurable (OpenAI, vLLM, Ollama, Together, ...).

    pip install openai ; export OPENAI_API_KEY=... ; OPENAI_BASE_URL opcional.
    """

    def __init__(self, model: str = "gpt-4o-mini", base_url: Optional[str] = None):
        try:
            from openai import OpenAI  # import diferido
        except ImportError as e:
            raise RuntimeError("Falta el SDK. Instala:  pip install openai") from e
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Falta OPENAI_API_KEY en el entorno.")
        self._client = OpenAI(base_url=base_url or os.environ.get("OPENAI_BASE_URL"))
        self.model = model
        self.name = f"openai:{model}"
        self.last_metadata = None

    def complete(self, system: str, user: str) -> str:
        kwargs = dict(
            model=self.model, temperature=0.0,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        if _wants_json(user):
            kwargs["response_format"] = {"type": "json_object"}
        t0 = time.time()
        resp = _call_with_retries(lambda: self._client.chat.completions.create(**kwargs))
        usage = getattr(resp, "usage", None)
        self.last_metadata = {
            "model": self.model,
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "total_token_count": getattr(usage, "total_tokens", None),
        }
        return resp.choices[0].message.content or ""


# ---------------------------------------------------------------- Anthropic

class AnthropicClient:
    """Cliente Anthropic (fallback 'cualquier LLM real').

    pip install anthropic ; export ANTHROPIC_API_KEY=... ; override: anthropic:MODELO
    """

    def __init__(self, model: str = "claude-sonnet-5"):
        try:
            import anthropic  # import diferido
        except ImportError as e:
            raise RuntimeError("Falta el SDK. Instala:  pip install anthropic") from e
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("Falta ANTHROPIC_API_KEY en el entorno.")
        self._client = anthropic.Anthropic()
        self.model = model
        self.name = f"anthropic:{model}"
        self.last_metadata = None

    def complete(self, system: str, user: str) -> str:
        t0 = time.time()
        msg = _call_with_retries(lambda: self._client.messages.create(
            model=self.model, max_tokens=1024, temperature=0.0,
            system=system, messages=[{"role": "user", "content": user}]))
        usage = getattr(msg, "usage", None)
        self.last_metadata = {
            "model": self.model,
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


# ---------------------------------------------------------------- factory

def make_client(spec: str) -> LLMClient:
    """`mock:credulous` | `mock:skeptical` | `gemini[:model]` | `openai[:model]`
    | `anthropic[:model]`."""
    if spec.startswith("mock"):
        persona = spec.split(":", 1)[1] if ":" in spec else "credulous"
        return MockClient(persona)
    if spec.startswith("gemini"):
        model = spec.split(":", 1)[1] if ":" in spec else "gemini-2.5-flash"
        return GeminiClient(model)
    if spec.startswith("openai"):
        model = spec.split(":", 1)[1] if ":" in spec else "gpt-4o-mini"
        return OpenAICompatibleClient(model)
    if spec.startswith("anthropic"):
        model = spec.split(":", 1)[1] if ":" in spec else "claude-sonnet-5"
        return AnthropicClient(model)
    raise ValueError(f"cliente desconocido: {spec}")
