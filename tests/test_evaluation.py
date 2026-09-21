"""Tests for deterministic extraction evaluation metrics."""

from unittest import TestCase

from backend.evaluation import _prf


class EvaluationTests(TestCase):
    def test_computes_precision_recall_and_f1(self) -> None:
        metrics = _prf({"a", "b"}, {"b", "c"})

        self.assertEqual(metrics, {"precision": 0.5, "recall": 0.5, "f1": 0.5})
