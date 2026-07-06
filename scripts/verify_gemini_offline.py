#!/usr/bin/env python3
"""
Verificacion OFFLINE de la costura Gemini (sin red, sin API key real).

Corre el GeminiClient REAL por TODA la tuberia (construccion de config con los tipos
reales del SDK, parser, memoria, firewall, scorer y export forense) y sustituye
UNICAMENTE el transporte HTTP por un stub que devuelve respuestas con la FORMA de una
respuesta Gemini (.text, .usage_metadata, .candidates[0].finish_reason).

El 'juicio' tras el stub es el mock determinista (fixture del repo), NO una simulacion
del modelo real: esto prueba la INTEGRACION, no estima tasas. Sirve para comprobar, antes
de gastar en una corrida real, que el camino Gemini funciona de extremo a extremo.

Uso:  python scripts/verify_gemini_offline.py
Requiere el SDK:  pip install -e ".[gemini]"
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("GEMINI_API_KEY", "dummy-offline")  # no se usa: transporte stubbeado

try:
    import google.genai as genai_mod
except ModuleNotFoundError:
    sys.exit("Falta el SDK. Instala:  pip install -e \".[gemini]\"")

from agent.clients import MockClient
import run_grid


class _Usage:
    def __init__(self, p, c):
        self.prompt_token_count = p
        self.candidates_token_count = c
        self.total_token_count = p + c


class _Cand:
    def __init__(self):
        self.finish_reason = "STOP"
        self.content = None


class _Resp:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = _Usage(420, 55)
        self.candidates = [_Cand()]


class _Models:
    def generate_content(self, model, contents, config):
        # config es un types.GenerateContentConfig REAL construido por nuestro cliente
        assert config.system_instruction, "system_instruction perdido en la config real"
        assert config.response_schema is not None, "response_schema perdido en la config real"
        return _Resp(MockClient("credulous").complete(config.system_instruction, contents))


class _FakeClient:
    def __init__(self, *a, **k):
        self.models = _Models()


def main():
    genai_mod.Client = _FakeClient  # inyecta el stub donde GeminiClient hace genai.Client(...)
    outdir = os.path.join(ROOT, "results", "gemini_offline_check")
    rp, sp, mp, causal = run_grid.run(
        "gemini:gemini-2.5-flash-lite", ["c2_01", "s1_01"], reps=2,
        outdir=outdir, save_traces=True, dashboards=True)
    print("OK: el GeminiClient real recorrio toda la tuberia (solo se stubbeo el HTTP).")
    print("   client   : gemini:gemini-2.5-flash-lite")
    print("   causal H-C:", causal["H-C (persistencia) atribuible"]["frac"], "(mock; fixture, no empirico)")
    print("   artefactos:", outdir)


if __name__ == "__main__":
    main()
