"""Smoke test del pipeline run_grid: genera CSV + manifiesto y agrega con IC."""
import csv
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run_grid


class TestRunGrid(unittest.TestCase):

    def test_grid_produces_results_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            rp, sp, mp, causal = run_grid.run("mock:credulous",
                                              ["c2_01", "p1_01"], reps=1, outdir=d,
                                              save_traces=True, dashboards=True)
            for path in (rp, sp, mp):
                self.assertTrue(os.path.exists(path))

            # results: una fila por (par, condicion), con columnas de metrica y validez
            with open(rp, encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertGreater(len(rows), 0)
            for col in ("ASR", "CLR", "parse_ok_rate", "poison_retrieved_rate"):
                self.assertIn(col, rows[0])

            # summary: agregado con IC bootstrap
            with open(sp, encoding="utf-8") as fh:
                srows = list(csv.DictReader(fh))
            self.assertTrue(any(r["condition"] == "C3(seed,atacado)" and r["metric"] == "ASR"
                                for r in srows))

            # manifiesto de reproducibilidad
            with open(mp, encoding="utf-8") as fh:
                man = json.load(fh)
            for k in ("client", "timestamp_utc", "python", "sdk_versions", "reps",
                      "n_pairs", "system_mode"):
                self.assertIn(k, man)

            # trazas forenses JSONL: raw prompt + hash + parse_ok por llamada
            tp = os.path.join(d, "traces_mock_credulous.jsonl")
            self.assertTrue(os.path.exists(tp))
            with open(tp, encoding="utf-8") as fh:
                first = json.loads(fh.readline())
            for k in ("prompt", "prompt_sha256", "decision", "system_mode", "action_event"):
                self.assertIn(k, first)
            self.assertIn("parse_ok", first["response"])

            # dashboards por par
            self.assertTrue(os.path.exists(os.path.join(d, "dashboard_c2_01.html")))

            # agregado causal: persistencia reproducida en todos los pares
            self.assertAlmostEqual(causal["H-C (persistencia) atribuible"]["frac"], 1.0)


if __name__ == "__main__":
    unittest.main()
