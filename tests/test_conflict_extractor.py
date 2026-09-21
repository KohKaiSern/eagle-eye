"""Conflict candidate routing and legal NLI confidence tests."""

from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend.extraction.conflict_extractor import (
    MODEL_REVISION,
    _get_conflict_components,
    extract_conflicts,
)
from backend.persistence.database import (
    Contract,
    ContractClause,
    ContractPartyMention,
    Party,
)
from backend.services.conflict_analysis import build_conflict_candidates


def _clause(text: str, confidence: float = 1.0) -> ContractClause:
    return ContractClause(
        id=uuid4(),
        order_index=0,
        category="Test category",
        text=text,
        confidence=confidence,
    )


def _contract(*clauses: ContractClause, party: Party | None = None) -> Contract:
    contract = Contract(
        id=uuid4(),
        batch_id=uuid4(),
        source="agreement.txt",
        relative_path="agreement.txt",
        file_type="txt",
        confidence=1.0,
        status="complete",
        clauses=list(clauses),
    )
    if party:
        contract.parties = [
            ContractPartyMention(
                id=uuid4(),
                party_id=party.id,
                party=party,
                order_index=0,
                raw_text=party.canonical_name,
                extracted_name=party.canonical_name,
                normalized_name=party.normalized_name,
                entity_type=party.entity_type,
                extraction_confidence=1.0,
                resolution_confidence=1.0,
            )
        ]
    return contract


class ConflictExtractorTests(TestCase):
    @patch("backend.extraction.conflict_extractor.AutoModelForSequenceClassification")
    @patch("backend.extraction.conflict_extractor.AutoTokenizer")
    def test_loads_the_pinned_model_revision(
        self,
        tokenizer_class,
        model_class,
    ) -> None:
        _get_conflict_components.cache_clear()
        model_class.from_pretrained.return_value = MagicMock()

        _get_conflict_components()

        self.assertEqual(
            tokenizer_class.from_pretrained.call_args.kwargs["revision"],
            MODEL_REVISION,
        )
        self.assertEqual(
            model_class.from_pretrained.call_args.kwargs["revision"],
            MODEL_REVISION,
        )
        _get_conflict_components.cache_clear()

    @patch(
        "backend.extraction.conflict_extractor._score_batch",
        return_value=[0.9],
    )
    def test_combines_model_clause_and_party_confidences(self, _score_batch) -> None:
        left_id = str(uuid4())
        right_id = str(uuid4())
        predictions = extract_conflicts(
            [
                {
                    "clause_a": {
                        "id": left_id,
                        "contract_id": str(uuid4()),
                        "text": "Payment is due in 30 days.",
                        "confidence": 0.81,
                    },
                    "clause_b": {
                        "id": right_id,
                        "contract_id": str(uuid4()),
                        "text": "Payment is due in 60 days.",
                        "confidence": 1.0,
                    },
                    "party_confidence": 0.8,
                }
            ]
        )

        self.assertEqual(predictions[0]["clause_a_id"], left_id)
        self.assertAlmostEqual(predictions[0]["model_confidence"], 0.9)
        self.assertAlmostEqual(predictions[0]["confidence"], 0.648)

    @patch(
        "backend.extraction.conflict_extractor._score_batch",
        return_value=[0.74],
    )
    def test_excludes_predictions_below_model_threshold(self, _score_batch) -> None:
        predictions = extract_conflicts(
            [
                {
                    "clause_a": {
                        "id": str(uuid4()),
                        "contract_id": str(uuid4()),
                        "text": "First clause",
                        "confidence": 1.0,
                    },
                    "clause_b": {
                        "id": str(uuid4()),
                        "contract_id": str(uuid4()),
                        "text": "Second clause",
                        "confidence": 1.0,
                    },
                    "party_confidence": 1.0,
                }
            ]
        )

        self.assertEqual(predictions, [])

    def test_compares_clauses_within_the_same_contract(self) -> None:
        contract = _contract(_clause("First clause"), _clause("Second clause"))

        candidates = build_conflict_candidates([contract])

        self.assertEqual(len(candidates), 1)

    def test_compares_contracts_only_when_they_share_a_canonical_party(self) -> None:
        shared_party = Party(
            id=uuid4(),
            canonical_name="Alpha Pte. Ltd.",
            normalized_name="alpha pte ltd",
            entity_type="organization",
        )
        related = [
            _contract(_clause("First clause"), party=shared_party),
            _contract(_clause("Second clause"), party=shared_party),
        ]
        unrelated = _contract(_clause("Third clause"))

        candidates = build_conflict_candidates([*related, unrelated])

        self.assertEqual(len(candidates), 1)
        compared_contract_ids = {
            candidates[0]["clause_a"]["contract_id"],
            candidates[0]["clause_b"]["contract_id"],
        }
        self.assertEqual(compared_contract_ids, {str(item.id) for item in related})

    def test_collapses_duplicate_cuad_categories_for_the_same_text(self) -> None:
        duplicate_a = _clause("The same extracted clause.", 0.8)
        duplicate_b = _clause("The same extracted clause.", 0.9)
        other = _clause("A different clause.")
        contract = _contract(duplicate_a, duplicate_b, other)

        candidates = build_conflict_candidates([contract])

        self.assertEqual(len(candidates), 1)
        compared_ids = {
            candidates[0]["clause_a"]["id"],
            candidates[0]["clause_b"]["id"],
        }
        self.assertIn(str(duplicate_b.id), compared_ids)
        self.assertNotIn(str(duplicate_a.id), compared_ids)
