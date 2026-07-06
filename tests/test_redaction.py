"""El agente NUNCA ve la verdad-base. Este test hace de esa promesa algo ejecutable."""
import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SourceDoc
from cases.loader import load_case


class TestRedaction(unittest.TestCase):
    def setUp(self):
        self.doc = SourceDoc(
            doc_id="d1", source_type="external_email", authority=1, is_canonical=False,
            content="telemetria aprobada", carries_false_claim=True,
            supports_decision="permissive",
        )

    def test_agent_view_has_no_ground_truth_fields(self):
        av = self.doc.redact()
        for forbidden in ("authority", "is_canonical", "carries_false_claim", "supports_decision"):
            self.assertFalse(hasattr(av, forbidden),
                             f"la vista del agente NO debe exponer {forbidden}")
        self.assertEqual(av.doc_id, "d1")
        self.assertEqual(av.source_type, "external_email")
        self.assertEqual(av.content, "telemetria aprobada")

    def test_agent_view_is_immutable(self):
        av = self.doc.redact()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            av.content = "otra cosa"  # type: ignore

    def test_case_agent_view_redacts_all_docs(self):
        case = load_case("c2_01", "seed")
        views = case.agent_view()
        self.assertEqual(len(views), len(case.documents))
        for v in views:
            self.assertFalse(hasattr(v, "authority"))
            self.assertFalse(hasattr(v, "carries_false_claim"))


if __name__ == "__main__":
    unittest.main()
