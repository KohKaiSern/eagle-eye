"""Tests for model-based party extraction and conservative normalization."""

from unittest import TestCase
from unittest.mock import Mock, patch

from backend.extraction.party_extractor import (
    _classify_entity_type,
    extract_parties,
    normalize_party_name,
)


class PartyExtractorTests(TestCase):
    def test_normalizes_names_without_dropping_the_legal_suffix(self) -> None:
        self.assertEqual(
            normalize_party_name("  ACME & Sons Pte. Ltd. "),
            "acme and sons pte ltd",
        )

    @patch(
        "backend.extraction.party_extractor._classify_entity_type",
        side_effect=[("organization", 0.96), ("organization", 0.95)],
    )
    @patch("backend.extraction.party_extractor.extract_legal_entities")
    def test_extracts_parties_from_whole_document_when_cuad_misses(
        self,
        extract_entities: Mock,
        classify_entity_type: Mock,
    ) -> None:
        text = "LEASE AGREEMENT\n\nLandlord: ABC Properties\nTenant: XYZ Corp"
        abc_start = text.index("ABC Properties")
        xyz_start = text.index("XYZ Corp")
        extract_entities.return_value = [
            {
                "text": "ABC Properties",
                "label": "Parties",
                "score": 0.91,
                "start": abc_start,
                "end": abc_start + len("ABC Properties"),
            },
            {
                "text": "XYZ Corp",
                "label": "Parties",
                "score": 0.88,
                "start": xyz_start,
                "end": xyz_start + len("XYZ Corp"),
            },
        ]
        result = extract_parties(text, 1.0)

        self.assertEqual(
            [item["extracted_name"] for item in result],
            ["ABC Properties", "XYZ Corp"],
        )
        self.assertTrue(all(item["entity_type"] == "organization" for item in result))
        self.assertEqual(result[0]["start_offset"], abc_start)
        extract_entities.assert_called_once_with(
            text,
            ["Parties"],
            threshold=0.5,
        )

    @patch("backend.extraction.party_extractor._get_party_classifier")
    @patch("backend.extraction.party_extractor.extract_legal_entities")
    def test_uses_contractner_entity_type_span_before_nli_fallback(
        self,
        extract_entities: Mock,
        get_classifier: Mock,
    ) -> None:
        extract_entities.return_value = [
            {
                "text": "Dana Lim",
                "label": "Person",
                "score": 0.99,
                "start": 0,
                "end": len("Dana Lim"),
            },
        ]

        result = _classify_entity_type("Tenant: Dana Lim", "Dana Lim")

        self.assertEqual(result, ("person", 0.99))
        get_classifier.assert_not_called()

    @patch(
        "backend.extraction.party_extractor._classify_entity_type",
        return_value=("organization", 0.8),
    )
    @patch("backend.extraction.party_extractor.extract_legal_entities")
    def test_combines_text_entity_and_type_confidence(
        self, extract_entities: Mock, classify_entity_type: Mock
    ) -> None:
        text = "Alpha Pte. Ltd."
        extract_entities.return_value = [
            {
                "text": text,
                "label": "Parties",
                "score": 0.6,
                "start": 0,
                "end": len(text),
            }
        ]
        result = extract_parties(text, 0.9)[0]

        self.assertAlmostEqual(result["confidence"], 0.9 * 0.6 * 0.8)

    @patch(
        "backend.extraction.party_extractor.extract_legal_entities",
        return_value=[],
    )
    def test_returns_empty_when_contractner_finds_no_parties(
        self,
        extract_entities: Mock,
    ) -> None:
        result = extract_parties("Alpha Pte. Ltd. and Beta Limited")

        self.assertEqual(result, [])
        extract_entities.assert_called_once()
