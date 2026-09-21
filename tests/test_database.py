"""Tests for normalized contract persistence models."""

from datetime import UTC, date, datetime
from unittest import TestCase
from uuid import UUID

from postgres_test_utils import create_test_engine, drop_test_schema
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.persistence.database import (
    Base,
    Contract,
    ContractClause,
    ContractDate,
    ContractPartyMention,
    ContractText,
    Party,
)


class DatabaseModelTests(TestCase):
    def test_schema_contains_normalized_extraction_tables(self) -> None:
        self.assertEqual(
            set(Base.metadata.tables),
            {
                "upload_batches",
                "contracts",
                "contract_texts",
                "contract_clauses",
                "contract_conflicts",
                "parties",
                "party_aliases",
                "contract_party_mentions",
                "contract_dates",
            },
        )

    def test_contract_serializes_related_rows_to_api_shape(self) -> None:
        contract = Contract(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            batch_id=UUID("00000000-0000-0000-0000-000000000002"),
            source="agreement.pdf",
            relative_path="contracts/agreement.pdf",
            file_type="pdf",
            confidence=0.95,
            status="complete",
            created_at=datetime(2026, 3, 4, 8, 30, tzinfo=UTC),
            text_record=ContractText(
                text="Complete agreement text.",
                confidence=0.95,
                character_count=24,
                content_sha256="a" * 64,
            ),
            clauses=[
                ContractClause(
                    order_index=0,
                    category="Governing Law",
                    text="This Agreement is governed by Singapore law.",
                    confidence=0.81,
                )
            ],
            parties=[
                ContractPartyMention(
                    party_id=UUID("00000000-0000-0000-0000-000000000003"),
                    order_index=0,
                    raw_text="Alpha Pte. Ltd.",
                    extracted_name="Alpha Pte. Ltd.",
                    normalized_name="alpha pte ltd",
                    entity_type="organization",
                    extraction_confidence=0.84,
                    resolution_confidence=0.98,
                    party=Party(
                        id=UUID("00000000-0000-0000-0000-000000000003"),
                        canonical_name="Alpha Pte. Ltd.",
                        normalized_name="alpha pte ltd",
                        entity_type="organization",
                        verification_status="unverified",
                    ),
                )
            ],
            dates=[
                ContractDate(
                    order_index=0,
                    event_date=date(2026, 3, 4),
                    event_desc="Contract effective or commencement date",
                    confidence=0.87,
                    provenance="explicit",
                    evidence="04/03/2026",
                    start_offset=10,
                    end_offset=20,
                )
            ],
        )

        result = contract.as_dict(include_text=True)

        self.assertEqual(result["source"], "agreement.pdf")
        self.assertAlmostEqual(result["confidence"], 0.84)
        self.assertEqual(result["dates"][0]["date"], "04/03/2026")
        self.assertEqual(result["dates"][0]["provenance"], "explicit")
        self.assertEqual(result["clauses"][0]["category"], "Governing Law")
        self.assertEqual(
            result["parties"][0]["text"],
            "Alpha Pte. Ltd.",
        )
        self.assertEqual(result["parties"][0]["canonical_name"], "Alpha Pte. Ltd.")
        self.assertEqual(result["text"]["content"], "Complete agreement text.")
        self.assertEqual(result["text"]["sha256"], "a" * 64)
        self.assertEqual(result["created_at"], "2026-03-04T08:30:00+00:00")

    def test_contract_list_shape_excludes_large_text_content(self) -> None:
        contract = Contract(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            batch_id=UUID("00000000-0000-0000-0000-000000000002"),
            source="agreement.txt",
            relative_path="agreement.txt",
            file_type="txt",
            confidence=1.0,
            status="complete",
            clauses=[],
            parties=[],
            dates=[],
            text_record=ContractText(
                text="Large text",
                confidence=1.0,
                character_count=10,
                content_sha256="b" * 64,
            ),
        )

        self.assertNotIn("text", contract.as_dict())

    def test_database_rejects_confidence_outside_unit_interval(self) -> None:
        engine, schema = create_test_engine()
        try:
            with Session(engine) as session:
                contract = Contract(
                    batch_id=UUID("00000000-0000-0000-0000-000000000002"),
                    source="invalid.txt",
                    relative_path="invalid.txt",
                    file_type="txt",
                    confidence=1.5,
                    status="complete",
                )
                session.add(contract)
                with self.assertRaises(IntegrityError):
                    session.flush()
        finally:
            drop_test_schema(engine, schema)
