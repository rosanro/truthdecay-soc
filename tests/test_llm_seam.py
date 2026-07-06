"""
Verificacion de la costura LLM SIN red.

No puedo llamar a Gemini/OpenAI desde el sandbox, pero puedo probar que:
  (1) el extractor de texto de Gemini tolera vallas ```json y 'thought parts';
  (2) el parser tolera salidas reales y desordenadas (JSON con prosa, texto libre);
  (3) el objeto GeminiClient REAL, con solo el salto de red falseado, recorre toda la
      historia E3 y el scorer produce el veredicto esperado.
Cuando el usuario ponga GEMINI_API_KEY, el unico cambio es que el salto de red es real.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.prompt import parse_response
from agent.clients import GeminiClient, MockClient, make_client
from cases.loader import load_pair
from experiments.run import run_storyline

CANDS = ["block_and_escalate", "close_false_positive", "escalate_incident", "request_more_evidence"]


class _FakeResp:
    def __init__(self, text):
        self._t = text
    @property
    def text(self):
        return self._t


class _FakeModels:
    def __init__(self, fn):
        self._fn = fn
    def generate_content(self, model, contents, config):
        return _FakeResp(self._fn(contents))


class _FakeGenaiClient:
    def __init__(self, fn):
        self.models = _FakeModels(fn)


def _fake_gemini(persona="credulous"):
    """GeminiClient real, pero con el cliente de red sustituido por un mock que
    envuelve la salida como lo haria Gemini (vallas ```json)."""
    gc = object.__new__(GeminiClient)
    gc.model, gc.name, gc._genai = "gemini-2.5-flash", "gemini:faked", None
    persona_client = MockClient(persona)
    gc._client = _FakeGenaiClient(lambda contents: "```json\n" + persona_client.complete("", contents) + "\n```")
    return gc


class TestLLMSeam(unittest.TestCase):

    def test_extract_text_tolerates_thought_parts(self):
        class P:  # part con 'thought' (2.5+) que debe ignorarse
            def __init__(self, text, thought=False):
                self.text, self.thought = text, thought
        class C:
            def __init__(self, parts):
                self.content = type("X", (), {"parts": parts})()
        class R:
            text = None  # fuerza el fallback
            def __init__(self, parts):
                self.candidates = [C(parts)]
        r = R([P("razonamiento interno", thought=True), P('{"decision":"block_and_escalate"}')])
        self.assertEqual(GeminiClient._extract_text(r), '{"decision":"block_and_escalate"}')

    def test_parser_handles_fenced_json(self):
        raw = '```json\n{"decision": "close_false_positive", "rationale": "x", "claims": [], "memory_note": "n"}\n```'
        r = parse_response(raw, structured=True, candidates=CANDS)
        self.assertTrue(r.parse_ok)
        self.assertEqual(r.decision, "close_false_positive")

    def test_parser_handles_prose_then_json(self):
        raw = 'Claro, aqui tienes mi analisis.\n{"decision":"block_and_escalate","claims":[]}'
        r = parse_response(raw, structured=True, candidates=CANDS)
        self.assertEqual(r.decision, "block_and_escalate")

    def test_parser_handles_free_text_decision_line(self):
        raw = "Tras revisar la evidencia, la telemetria es canonica.\nDECISION: block_and_escalate"
        r = parse_response(raw, structured=False, candidates=CANDS)
        self.assertEqual(r.decision, "block_and_escalate")

    def test_gemini_seam_end_to_end_with_faked_network(self):
        seed, probe = load_pair("c2_01")
        gc = _fake_gemini("credulous")
        res = run_storyline(seed, probe, gc, reps=1)
        v = res["verdict"]
        # el objeto GeminiClient REAL recorre toda la cadena; solo la red esta falseada
        self.assertTrue(v["H-A (efecto inmediato) atribuible"])
        self.assertTrue(v["H-C (persistencia) atribuible"])
        self.assertTrue(v["C7-control no comprometido (causalidad)"])
        self.assertTrue(v["H-D1a (firewall contiene)"])

    def test_missing_key_gives_clear_error(self):
        saved = {k: os.environ.pop(k, None) for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
        try:
            with self.assertRaises(RuntimeError) as ctx:
                make_client("gemini")
            msg = str(ctx.exception).lower()
            # sin SDK el primer error es el SDK; con SDK, es la credencial. Ambos son claros.
            self.assertTrue("credencial" in msg or "sdk" in msg, msg)
        finally:
            for k, val in saved.items():
                if val is not None:
                    os.environ[k] = val


if __name__ == "__main__":
    unittest.main()
