"""Tests for canonical party resolution."""

from unittest import TestCase

from postgres_test_utils import create_test_engine, drop_test_schema
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.persistence.database import Contract, Party, PartyAlias, UploadBatch
from backend.persistence.party_resolution import resolve_party_mentions


def mention(name: str, normalized: str) -> dict:
    return {
        "raw_text": name,
        "extracted_name": name,
        "normalized_name": normalized,
        "entity_type": "organization",
        "confidence": 0.8,
        "start_offset": 0,
        "end_offset": len(name),
    }


class PartyResolutionTests(TestCase):
    def setUp(self) -> None:
        self.engine, self.schema = create_test_engine()

    def tearDown(self) -> None:
        drop_test_schema(self.engine, self.schema)

    def test_reuses_a_unique_exact_alias(self) -> None:
        with Session(self.engine) as session:
            party = Party(
                canonical_name="Acme Pte. Ltd.",
                normalized_name="acme pte ltd",
                entity_type="organization",
                verification_status="unverified",
                aliases=[
                    PartyAlias(
                        alias="ACME PTE LTD",
                        normalized_alias="acme pte ltd",
                        source="contract",
                    )
                ],
            )
            contract = Contract(
                batch=UploadBatch(selection_name="folder"),
                source="contract.txt",
                relative_path="folder/contract.txt",
                file_type="txt",
                confidence=1.0,
                status="complete",
            )
            session.add_all([party, contract])
            session.flush()

            resolve_party_mentions(
                session,
                contract,
                [mention("Acme Pte. Ltd.", "acme pte ltd")],
            )
            session.flush()

            parties = session.scalars(select(Party)).all()
            self.assertEqual(len(parties), 1)
            self.assertEqual(contract.parties[0].party_id, party.id)
            self.assertEqual(contract.parties[0].resolution_confidence, 0.98)

    def test_ambiguous_alias_is_not_automatically_merged(self) -> None:
        with Session(self.engine) as session:
            for canonical_name in ("Acme Singapore", "Acme Australia"):
                session.add(
                    Party(
                        canonical_name=canonical_name,
                        normalized_name="acme",
                        entity_type="organization",
                        verification_status="unverified",
                        aliases=[
                            PartyAlias(
                                alias="Acme",
                                normalized_alias="acme",
                                source="contract",
                            )
                        ],
                    )
                )
            contract = Contract(
                batch=UploadBatch(selection_name="folder"),
                source="contract.txt",
                relative_path="folder/contract.txt",
                file_type="txt",
                confidence=1.0,
                status="complete",
            )
            session.add(contract)
            session.flush()

            resolve_party_mentions(session, contract, [mention("Acme", "acme")])
            session.flush()

            self.assertEqual(len(session.scalars(select(Party)).all()), 2)
            self.assertIsNone(contract.parties[0].party_id)
            self.assertEqual(contract.parties[0].resolution_confidence, 0.0)
