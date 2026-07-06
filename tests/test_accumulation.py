"""Variante de acumulacion: maquinaria + disciplina de ledger.

Importante: el mock no puede demostrar acumulacion (credulous adopta cualquier memoria
permisiva). Estos tests verifican la maquinaria de ablacion y la disciplina agente/ledger,
no la hipotesis de acumulacion (eso requiere un LLM real). De hecho aseveramos que el mock
no produce evidencia de acumulacion, para no vender un falso positivo del fixture.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.clients import make_client
from experiments.accumulation import load_campaign, run_campaign, validate_campaign

CAMPS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "cases", "campaigns", "t1_01.json"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "cases", "campaigns", "t2_01.json"),
]
DEFAULT_CAMP = CAMPS[0]



class TestAccumulation(unittest.TestCase):

    def setUp(self):
        self.camp = load_campaign(DEFAULT_CAMP)

    def test_campaign_is_valid_by_ledger(self):
        for path in CAMPS:
            with self.subTest(path=path):
                self.assertEqual(validate_campaign(load_campaign(path)), [])

    def test_machinery_and_ledger_discipline(self):
        v = run_campaign(self.camp, make_client("mock:credulous"))["verdict"]
        self.assertTrue(v["campana valida (ledger)"])
        # el agente cierra los incidentes benignos (concordancia con el ledger)
        self.assertEqual(v["concordancia agente-ledger en incidentes (cerro los benignos)"], 1.0)
        # la ablacion produce TODAS las condiciones
        cond = v["ASR por condicion"]
        for c in ("vacia", "a1-sola", "a2-sola", "a3-sola",
                  "prefijo:a1", "prefijo:a1+a2", "prefijo:a1+a2+a3", "memoria-correcta", "firewall"):
            self.assertIn(c, cond)
        # but-for debil: sin memoria bloquea; con memoria acumulada cae
        self.assertEqual(cond["vacia"], 0.0)
        self.assertEqual(cond["prefijo:a1+a2+a3"], 1.0)
        # control con memoria correcta no se compromete; firewall contiene
        self.assertTrue(v["control (memoria correcta) no comprometido"])
        self.assertTrue(v["firewall contiene"])

    def test_mock_cannot_show_accumulation(self):
        # rigor: el mock adopta cualquier memoria permisiva, asi que un incidente aislado
        # ya cae igual que la acumulacion completa -> no hay evidencia de acumulacion.
        v = run_campaign(self.camp, make_client("mock:credulous"))["verdict"]
        self.assertEqual(v["max ASR de un incidente aislado"], v["ASR con acumulacion completa"])
        self.assertFalse(v["evidencia de acumulacion (pleno > cualquier aislado, curva no decrece)"])

    def test_skeptical_agent_resists(self):
        v = run_campaign(self.camp, make_client("mock:skeptical"))["verdict"]
        self.assertEqual(v["ASR con acumulacion completa"], 0.0)


if __name__ == "__main__":
    unittest.main()
