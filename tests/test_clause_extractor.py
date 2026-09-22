"""Tests for CUAD clause extraction and confidence propagation."""

from unittest import TestCase
from unittest.mock import Mock, patch
from types import SimpleNamespace

import torch

from backend.extraction.clause_extractor import (
    CUAD_CATEGORIES, MAX_SEQUENCE_LENGTH, WINDOW_BATCH_SIZE,
    _answer_question, _question_windows, extract_clauses,
)


class CharacterTokenizer:
    cls_token_id = 0
    sep_token_id = 2
    pad_token_id = 1

    def __call__(self, text, **kwargs):
        assert kwargs["truncation"] is False
        assert kwargs["padding"] is False
        assert kwargs["add_special_tokens"] is False
        return {
            "input_ids": [ord(char) + 10 for char in text],
            "offset_mapping": [(i, i + 1) for i in range(len(text))],
        }


class QuestionWindowTests(TestCase):
    def test_windows_cover_all_tokens_with_overlap_and_original_offsets(self):
        text = "x" * 2200
        windows = list(_question_windows(CharacterTokenizer(), "Question", text))
        covered = set()
        previous_end = None
        for ids, sequence_ids, offsets in windows:
            self.assertLessEqual(len(ids), MAX_SEQUENCE_LENGTH)
            spans = [span for seq, span in zip(sequence_ids, offsets) if seq == 1]
            covered.update(a for a, _ in spans)
            if previous_end is not None:
                self.assertEqual(previous_end - spans[0][0], 256)
            previous_end = spans[-1][1]
        self.assertEqual(covered, set(range(len(text))))
        self.assertEqual(previous_end, len(text))

    def test_long_question_reduces_overlap_without_gaps(self):
        windows = list(_question_windows(CharacterTokenizer(), "q" * 500, "x" * 20))
        covered = {a for _, seqs, offsets in windows
                   for seq, (a, _) in zip(seqs, offsets) if seq == 1}
        self.assertEqual(covered, set(range(20)))
        self.assertTrue(all(len(ids) <= 512 for ids, _, _ in windows))

    @patch("backend.extraction.clause_extractor._get_clause_components")
    def test_extracts_beginning_boundary_and_end_spans_in_bounded_batches(self, components):
        tokenizer = CharacterTokenizer()
        batches = []

        def predict(input_ids, attention_mask):
            batches.append(len(input_ids))
            starts = torch.full(input_ids.shape, -20.0)
            ends = torch.full(input_ids.shape, -20.0)
            for i, row in enumerate(input_ids):
                opening = (row == ord("[") + 10).nonzero().flatten().tolist()
                closing = (row == ord("]") + 10).nonzero().flatten().tolist()
                pairs = [(a, b) for a in opening for b in closing if a < b]
                a, b = pairs[0] if pairs else (0, 0)
                starts[i, a] = ends[i, b] = 20.0
            return SimpleNamespace(start_logits=starts, end_logits=ends)

        components.return_value = tokenizer, predict
        text = "[Beginning]".ljust(500, "x") + "[Boundary clause]"
        text = text.ljust(1800, "x") + "[Final clause]"
        answers = _answer_question("Q", text)
        retained = [a for a in answers if a["score"] >= 0.1 and a["answer"]]
        self.assertEqual({a["answer"] for a in retained},
                         {"[Beginning]", "[Boundary clause]", "[Final clause]"})
        for answer in retained:
            self.assertEqual(answer["answer"], text[answer["start"]:answer["end"]])
        self.assertEqual(len(retained), 3)
        self.assertGreater(len(batches), 1)
        self.assertLessEqual(max(batches), WINDOW_BATCH_SIZE)


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
