"""Tests for combining contract extraction outputs."""

from unittest import TestCase
from unittest.mock import patch

from backend.extraction.contract_processor import process_contract


class ProcessContractTests(TestCase):
    @patch("backend.extraction.contract_processor.extract_parties")
    @patch("backend.extraction.contract_processor.extract_dates")
    @patch("backend.extraction.contract_processor.extract_clauses")
    @patch("backend.extraction.contract_processor.format_text")
    def test_combines_clause_date_and_party_results(
        self, format_text, extract_clauses, extract_dates, extract_parties
    ) -> None:
        format_text.return_value = {
            "text": "Agreement text",
            "confidence": 0.9,
            "source": "temporary.pdf",
        }
        extract_clauses.return_value = {
            "source": "contract.pdf",
            "confidence": 0.72,
            "clauses": [
                {
                    "category": "Document Name",
                    "text": "Agreement",
                    "confidence": 0.8,
                },
                {
                    "category": "Governing Law",
                    "text": "The laws of Singapore apply.",
                    "confidence": 0.7,
                },
            ],
        }
        extract_dates.return_value = {
            "source": "contract.pdf",
            "confidence": 0.75,
            "dates": [
                {
                    "date": "04/03/2026",
                    "event_desc": "Contract effective or commencement date",
                    "confidence": 0.75,
                }
            ],
        }
        extract_parties.return_value = [
            {
                "raw_text": "Acme Pte. Ltd.",
                "extracted_name": "Acme Pte. Ltd.",
                "normalized_name": "acme pte ltd",
                "entity_type": "organization",
                "confidence": 0.8,
                "start_offset": 0,
                "end_offset": 14,
            }
        ]

        result = process_contract("/tmp/random.pdf", "contract.pdf")

        self.assertEqual(result["source"], "contract.pdf")
        self.assertAlmostEqual(result["confidence"], 0.7625)
        self.assertEqual(result["text"], "Agreement text")
        self.assertEqual(result["parties"], extract_parties.return_value)
        self.assertEqual(len(result["clauses"]), 2)
        self.assertEqual(len(result["dates"]), 1)
        self.assertEqual(extract_clauses.call_args.args[0]["source"], "contract.pdf")
        self.assertEqual(extract_dates.call_args.args[0]["source"], "contract.pdf")
        extract_parties.assert_called_once_with(
            "Agreement text",
            0.9,
        )

    @patch("backend.extraction.contract_processor.extract_parties", return_value=[])
    @patch("backend.extraction.contract_processor.extract_dates")
    @patch("backend.extraction.contract_processor.extract_clauses")
    @patch("backend.extraction.contract_processor.format_text")
    def test_uses_zero_when_no_intelligence_is_extracted(
        self,
        format_text,
        extract_clauses,
        extract_dates,
        extract_parties,
    ) -> None:
        format_text.return_value = {
            "text": "Readable text without extracted intelligence",
            "confidence": 1.0,
            "source": "temporary.txt",
        }
        extract_clauses.return_value = {
            "source": "contract.txt",
            "confidence": 0.0,
            "clauses": [],
        }
        extract_dates.return_value = {
            "source": "contract.txt",
            "confidence": 0.0,
            "dates": [],
        }

        result = process_contract("/tmp/random.txt", "contract.txt")

        self.assertEqual(result["confidence"], 0.0)
        extract_parties.assert_called_once()
