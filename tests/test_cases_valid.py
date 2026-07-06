"""Valida todos los pares del corpus (invariantes semanticas)."""
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cases.loader import load_case
from cases.validate import validate_case

CASES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cases")


def _all_pairs():
    return sorted({os.path.basename(p)[:-len("_seed.json")]
                   for p in glob.glob(os.path.join(CASES_DIR, "*_seed.json"))})


class TestCasesValid(unittest.TestCase):

    def test_every_case_is_valid(self):
        pairs = _all_pairs()
        self.assertGreaterEqual(len(pairs), 2, "deberia haber al menos 2 pares")
        all_errs = []
        for pair in pairs:
            for role in ("seed", "probe"):
                all_errs += validate_case(load_case(pair, role))
        self.assertEqual(all_errs, [], "\n".join(all_errs))


if __name__ == "__main__":
    unittest.main()
