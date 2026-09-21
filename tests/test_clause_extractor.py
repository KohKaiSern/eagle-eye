"""Tests for CUAD clause extraction and confidence propagation."""

from unittest import TestCase
from unittest.mock import Mock, patch

from backend.extraction.clause_extractor import CUAD_CATEGORIES, extract_clauses


class ExtractClausesTests(TestCase):
    def test_excludes_categories_owned_by_dedicated_extractors(self) -> None:
        categories = {category for category, _ in CUAD_CATEGORIES}

        self.assertEqual(len(categories), 39)
        self.assertNotIn("Parties", categories)
        self.assertNotIn("Expiration Date", categories)

    @patch("backend.extraction.clause_extractor._answer_question")
    def test_extracts_verbatim_clause_and_combines_confidence(
        self, answer_question: Mock
    ) -> None:
        text = (
            "Introduction.\n"
            "This Agreement shall be governed by the laws of Singapore.\n"
            "Signatures follow."
        )
        clause = "This Agreement shall be governed by the laws of Singapore."
        start = text.index(clause)

        def answers(question: str, _: str):
            if '"Governing Law"' in question:
                return [
                    {
                        "answer": clause,
                        "score": 0.8,
                        "start": start,
                        "end": start + len(clause),
                    },
                    {"answer": "", "score": 0.2, "start": 0, "end": 0},
                ]
            return [{"answer": "", "score": 0.9, "start": 0, "end": 0}]

        answer_question.side_effect = answers

        result = extract_clauses(
            {"text": text, "confidence": 0.9, "source": "contract.pdf"}
        )

        self.assertEqual(
            result["clauses"],
            [
                {
                    "category": "Governing Law",
                    "text": clause,
                    "confidence": 0.9 * 0.8,
                }
            ],
        )
        self.assertAlmostEqual(result["confidence"], 0.9 * 0.8)
        self.assertEqual(result["source"], "contract.pdf")
        self.assertEqual(answer_question.call_count, len(CUAD_CATEGORIES))

    @patch("backend.extraction.clause_extractor._answer_question")
    def test_rejects_answer_when_no_answer_is_more_likely(
        self, answer_question: Mock
    ) -> None:
        answer_question.return_value = [
            {"answer": "possible clause", "score": 0.4, "start": 0, "end": 15},
            {"answer": "", "score": 0.6, "start": 0, "end": 0},
        ]

        result = extract_clauses(
            {
                "text": "possible clause",
                "confidence": 1.0,
                "source": "contract.txt",
            }
        )

        self.assertEqual(
            result,
            {"clauses": [], "confidence": 0.0, "source": "contract.txt"},
        )

    @patch("backend.extraction.clause_extractor._answer_question")
    def test_deduplicates_overlapping_answers_in_the_same_category(
        self, answer_question: Mock
    ) -> None:
        text = "The liability cap is $100. The remaining terms apply."

        def answers(question: str, _: str):
            if '"Cap on Liability"' in question:
                return [
                    {
                        "answer": "The liability cap is $100.",
                        "score": 0.9,
                        "start": 0,
                        "end": 26,
                    },
                    {
                        "answer": "liability cap is $100.",
                        "score": 0.7,
                        "start": 4,
                        "end": 26,
                    },
                ]
            return [{"answer": "", "score": 0.9, "start": 0, "end": 0}]

        answer_question.side_effect = answers

        result = extract_clauses(
            {"text": text, "confidence": 1.0, "source": "terms.docx"}
        )

        self.assertEqual(
            result["clauses"],
            [
                {
                    "category": "Cap on Liability",
                    "text": text[:26],
                    "confidence": 0.9,
                }
            ],
        )
        self.assertAlmostEqual(result["confidence"], 0.9)

    @patch("backend.extraction.clause_extractor._answer_question")
    def test_returns_no_clauses_for_empty_text(self, answer_question: Mock) -> None:
        result = extract_clauses(
            {"text": " \n", "confidence": 1.0, "source": "empty.txt"}
        )

        self.assertEqual(
            result,
            {"clauses": [], "confidence": 0.0, "source": "empty.txt"},
        )
        answer_question.assert_not_called()
