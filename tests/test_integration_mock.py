"""Test de integracion de la historia E3 con el mock (fija el comportamiento end-to-end)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cases.loader import load_pair
from agent.clients import make_client
from experiments.run import run_storyline


class TestStoryline(unittest.TestCase):

    def test_credulous_reproduces_full_chain(self):
        for pair in ("c2_01", "p1_01"):
            seed, probe = load_pair(pair)
            res = run_storyline(seed, probe, make_client("mock:credulous"), reps=1)
            v = res["verdict"]
            self.assertEqual(v["clean_baseline_band"], "ok", pair)
            self.assertTrue(v["H-A (efecto inmediato) atribuible"], pair)
            self.assertTrue(v["H-B (lavado a memoria) exitoso"], pair)
            self.assertTrue(v["H-C (persistencia) atribuible"], pair)
            self.assertTrue(v["C7-control no comprometido (causalidad)"], pair)
            self.assertEqual(v["PPR (par)"], 1.0, pair)
            self.assertTrue(v["H-D1a (firewall contiene)"], pair)
            self.assertAlmostEqual(v["H-D2 (coste utilidad limpia seed+probe, incorrect_rate)"], 0.0, msg=pair)

    def test_skeptical_is_not_fooled(self):
        seed, probe = load_pair("c2_01")
        res = run_storyline(seed, probe, make_client("mock:skeptical"), reps=1)
        v = res["verdict"]
        # el agente esceptico nunca adopta el veneno: no hay lavado ni persistencia,
        # y PPR queda indefinido (denominador vacio), no 0 -> se distingue
        # "no persistio" de "nunca se contamino".
        self.assertFalse(v["H-B (lavado a memoria) exitoso"])
        self.assertIsNone(v["PPR (par)"])
        self.assertFalse(v["H-C (persistencia) atribuible"])


if __name__ == "__main__":
    unittest.main()
