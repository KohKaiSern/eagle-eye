"""Tests for explicit contract date extraction and event classification."""

from unittest import TestCase
from unittest.mock import Mock, patch

from backend.extraction.date_extractor import extract_dates


class ExtractDatesTests(TestCase):
    def setUp(self) -> None:
        self.entity_patcher = patch(
            "backend.extraction.date_extractor.extract_legal_entities",
            return_value=[],
        )
        self.entity_patcher.start()

    def tearDown(self) -> None:
        self.entity_patcher.stop()

    @patch("backend.extraction.date_extractor._classify_event")
    def test_parses_numeric_dates_in_singapore_dmy_order(
        self, classify_event: Mock
    ) -> None:
        classify_event.return_value = ("Payment due date", 0.8)

        result = extract_dates(
            {
                "text": "The payment is due on 04/03/2026.",
                "confidence": 0.9,
                "source": "agreement.pdf",
            }
        )

        self.assertEqual(result["source"], "agreement.pdf")
        self.assertEqual(
            result["dates"],
            [
                {
                    "date": "04/03/2026",
                    "event_desc": "Payment due date",
                    "confidence": 0.9 * 0.8,
                    "provenance": "explicit",
                    "evidence": "04/03/2026",
                    "start_offset": 22,
                    "end_offset": 32,
                }
            ],
        )
        self.assertAlmostEqual(result["confidence"], 0.9 * 0.8)

    @patch("backend.extraction.date_extractor._classify_event")
    def test_normalizes_textual_and_iso_dates(self, classify_event: Mock) -> None:
        classify_event.side_effect = [
            ("Contract effective or commencement date", 0.9),
            ("Contract expiration or end date", 0.7),
            ("Contract renewal date", 0.8),
        ]

        result = extract_dates(
            {
                "text": (
                    "The term begins on March 4, 2026, ends on 5th April 2027, "
                    "and renews on 2028-05-06."
                ),
                "confidence": 1.0,
                "source": "term.txt",
            }
        )

        self.assertEqual(
            [item["date"] for item in result["dates"]],
            ["04/03/2026", "05/04/2027", "06/05/2028"],
        )
        self.assertAlmostEqual(result["confidence"], 0.8)

    @patch("backend.extraction.date_extractor._classify_event")
    def test_ignores_relative_incomplete_and_invalid_dates(
        self, classify_event: Mock
    ) -> None:
        result = extract_dates(
            {
                "text": (
                    "Pay within 30 days after delivery. Renew every March. "
                    "The invalid date is 31/02/2027."
                ),
                "confidence": 1.0,
                "source": "terms.docx",
            }
        )

        self.assertEqual(
            result,
            {"source": "terms.docx", "confidence": 0.0, "dates": []},
        )
        classify_event.assert_not_called()

    @patch("backend.extraction.date_extractor._classify_event")
    def test_excludes_dates_classified_as_irrelevant(
        self, classify_event: Mock
    ) -> None:
        classify_event.return_value = None

        result = extract_dates(
            {
                "text": "The background report was published on 01/02/2020.",
                "confidence": 1.0,
                "source": "history.txt",
            }
        )

        self.assertEqual(result["dates"], [])
        self.assertEqual(result["confidence"], 0.0)

    @patch("backend.extraction.date_extractor._classify_event")
    def test_returns_empty_result_for_empty_text(self, classify_event: Mock) -> None:
        result = extract_dates(
            {"text": " \n", "confidence": 1.0, "source": "empty.txt"}
        )

        self.assertEqual(
            result,
            {"source": "empty.txt", "confidence": 0.0, "dates": []},
        )
        classify_event.assert_not_called()

    @patch("backend.extraction.date_extractor._classify_event")
    @patch("backend.extraction.date_extractor._has_event_dependency")
    @patch(
        "backend.extraction.date_extractor._extract_term_duration",
        return_value=None,
    )
    @patch("backend.extraction.date_extractor.extract_legal_entities")
    def test_contractner_hint_avoids_duplicate_event_classification(
        self,
        extract_entities: Mock,
        extract_duration: Mock,
        has_dependency: Mock,
        classify_event: Mock,
    ) -> None:
        text = "The contract starts on 1 July 2026."
        start = text.index("1 July 2026")
        extract_entities.return_value = [
            {
                "text": "1 July 2026",
                "label": "EffectiveDate",
                "score": 0.91,
                "start": start,
                "end": start + len("1 July 2026"),
            }
        ]

        result = extract_dates({"text": text, "confidence": 1.0, "source": "term.txt"})

        self.assertEqual(
            result["dates"][0]["event_desc"], "Contract effective or commencement date"
        )
        classify_event.assert_not_called()
        has_dependency.assert_not_called()

    @patch("backend.extraction.date_extractor._classify_event")
    def test_deduplicates_repeated_date_events_using_best_confidence(
        self,
        classify_event: Mock,
    ) -> None:
        classify_event.side_effect = [
            ("Payment due date", 0.6),
            ("Payment due date", 0.9),
        ]

        result = extract_dates(
            {
                "text": (
                    "Payment is due on 04/03/2026.\n\n"
                    "The same payment date is 4 March 2026."
                ),
                "confidence": 0.8,
                "source": "invoice.txt",
            }
        )

        self.assertEqual(len(result["dates"]), 1)
        self.assertEqual(result["dates"][0]["date"], "04/03/2026")
        self.assertAlmostEqual(result["dates"][0]["confidence"], 0.8 * 0.9)

    @patch(
        "backend.extraction.date_extractor._has_event_dependency",
        return_value=False,
    )
    @patch("backend.extraction.date_extractor._extract_term_duration")
    @patch("backend.extraction.date_extractor._classify_event")
    def test_derives_inclusive_expiration_from_fixed_initial_term(
        self,
        classify_event: Mock,
        extract_duration: Mock,
        has_dependency: Mock,
    ) -> None:
        classify_event.return_value = (
            "Contract effective or commencement date",
            0.9,
        )
        extract_duration.return_value = ("3 years", 0.8)

        result = extract_dates(
            {
                "text": "Term: 3 years, starting July 1, 2026.",
                "confidence": 1.0,
                "source": "lease.txt",
            }
        )

        self.assertEqual(
            [(item["date"], item["provenance"]) for item in result["dates"]],
            [("01/07/2026", "explicit"), ("30/06/2029", "derived")],
        )
        derived = result["dates"][1]
        self.assertEqual(derived["event_desc"], "Contract expiration or end date")
        self.assertEqual(
            derived["evidence"],
            "Term: 3 years, starting July 1, 2026.",
        )

    @patch(
        "backend.extraction.date_extractor._has_event_dependency",
        return_value=True,
    )
    @patch("backend.extraction.date_extractor._extract_term_duration")
    @patch("backend.extraction.date_extractor._classify_event")
    def test_does_not_derive_event_dependent_date(
        self,
        classify_event: Mock,
        extract_duration: Mock,
        has_dependency: Mock,
    ) -> None:
        classify_event.return_value = (
            "Contract effective or commencement date",
            0.9,
        )
        extract_duration.return_value = ("30 days", 0.8)
        result = extract_dates(
            {
                "text": "Starts 1 July 2026 and ends 30 days after delivery.",
                "confidence": 1.0,
                "source": "services.txt",
            }
        )

        self.assertEqual(len(result["dates"]), 1)
        self.assertEqual(result["dates"][0]["date"], "01/07/2026")
        extract_duration.assert_called_once()
