"""Flask API and application-level persistence tests."""

from datetime import date
from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock, patch

from postgres_test_utils import create_test_engine, drop_test_schema
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.datastructures import FileStorage

from backend.app import (
    calendar_feed,
    create_app,
    delete_contract,
    list_conflicts,
    list_contracts,
    reset_contract_data,
    search_contracts,
    upload_contracts,
)
from backend.persistence.database import (
    Contract,
    ContractClause,
    ContractConflict,
    ContractDate,
    ContractPartyMention,
    ContractText,
    Party,
    UploadBatch,
)


class UploadContractsTests(TestCase):
    def setUp(self) -> None:
        self.engine, self.schema = create_test_engine()
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self.app = create_app(
            {
                "TESTING": True,
                "INITIALIZE_DATABASE": False,
                "SESSION_FACTORY": self.session_factory,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        drop_test_schema(self.engine, self.schema)

    def test_health_route_checks_database(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "database": "ok"})

    def test_searches_complete_contract_text_with_fuzzy_matching(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            contract = Contract(
                batch=UploadBatch(selection_name="leases"),
                source="lease.txt",
                relative_path="leases/lease.txt",
                file_type="txt",
                confidence=1.0,
                status="complete",
                text_record=ContractText(
                    text=(
                        "LEASE AGREEMENT\n"
                        "Either party may terminate with thirty days' notice."
                    ),
                    confidence=1.0,
                    character_count=69,
                    content_sha256="a" * 64,
                ),
            )
            session.add(contract)
            session.commit()

            result = search_contracts(
                session=session,
                q="terminte notice",
                limit=20,
            )

            self.assertEqual(result["query"], "terminte notice")
            self.assertEqual(result["matches"][0]["source"], "lease.txt")
            self.assertIn("terminate", result["matches"][0]["snippet"])

    def test_deletes_contract_and_contract_specific_records(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            contract = Contract(
                batch=UploadBatch(selection_name="folder"),
                source="agreement.txt",
                relative_path="folder/agreement.txt",
                file_type="txt",
                confidence=1.0,
                status="complete",
                text_record=ContractText(
                    text="Agreement text",
                    confidence=1.0,
                    character_count=14,
                    content_sha256="a" * 64,
                ),
                dates=[
                    ContractDate(
                        order_index=0,
                        event_date=date(2027, 6, 15),
                        event_desc="Payment due date",
                        confidence=0.82,
                        provenance="explicit",
                        evidence="Payment is due on 15 June 2027.",
                        start_offset=18,
                        end_offset=30,
                    )
                ],
                parties=[
                    ContractPartyMention(
                        order_index=0,
                        raw_text="Alpha Pte. Ltd.",
                        extracted_name="Alpha Pte. Ltd.",
                        normalized_name="alpha pte ltd",
                        entity_type="organization",
                        extraction_confidence=0.9,
                        resolution_confidence=1.0,
                        party=Party(
                            canonical_name="Alpha Pte. Ltd.",
                            normalized_name="alpha pte ltd",
                            entity_type="organization",
                        ),
                    )
                ],
            )
            session.add(contract)
            session.commit()
            contract_id = contract.id

            deleted = delete_contract(contract_id=contract_id, session=session)

            self.assertTrue(deleted)
            self.assertIsNone(session.get(Contract, contract_id))
            self.assertEqual(session.scalars(select(ContractText)).all(), [])
            self.assertEqual(session.scalars(select(ContractDate)).all(), [])
            self.assertEqual(session.scalars(select(Party)).all(), [])
            self.assertEqual(session.scalars(select(UploadBatch)).all(), [])

    def test_resets_all_contract_data_and_reports_deleted_records(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            contract = Contract(
                batch=UploadBatch(selection_name="folder"),
                source="agreement.txt",
                relative_path="folder/agreement.txt",
                file_type="txt",
                confidence=1.0,
                status="complete",
                parties=[
                    ContractPartyMention(
                        order_index=0,
                        raw_text="Alpha Pte. Ltd.",
                        extracted_name="Alpha Pte. Ltd.",
                        normalized_name="alpha pte ltd",
                        entity_type="organization",
                        extraction_confidence=0.9,
                        resolution_confidence=1.0,
                        party=Party(
                            canonical_name="Alpha Pte. Ltd.",
                            normalized_name="alpha pte ltd",
                            entity_type="organization",
                        ),
                    )
                ],
            )
            session.add(contract)
            session.commit()

            counts = reset_contract_data(session)

            self.assertEqual(
                counts,
                {"upload_batches": 1, "contracts": 1, "parties": 1},
            )
            self.assertEqual(session.scalars(select(Contract)).all(), [])
            self.assertEqual(session.scalars(select(Party)).all(), [])
            self.assertEqual(session.scalars(select(UploadBatch)).all(), [])

    def test_lists_conflicts_and_marks_both_contracts(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            left_clause = ContractClause(
                order_index=0,
                category="Payment Terms",
                text="Payment is due within 30 days.",
                confidence=0.9,
            )
            right_clause = ContractClause(
                order_index=0,
                category="Payment Terms",
                text="Payment is due within 60 days.",
                confidence=0.85,
            )
            contracts = [
                Contract(
                    batch=UploadBatch(selection_name=f"batch-{index}"),
                    source=f"agreement-{index}.txt",
                    relative_path=f"agreement-{index}.txt",
                    file_type="txt",
                    confidence=1.0,
                    status="complete",
                    clauses=[clause],
                )
                for index, clause in enumerate((left_clause, right_clause))
            ]
            session.add_all(contracts)
            session.flush()
            session.add(
                ContractConflict(
                    clause_a=left_clause,
                    clause_b=right_clause,
                    confidence=0.78,
                    model_confidence=0.91,
                    model_id="test-model",
                )
            )
            session.commit()

            contract_result = list_contracts(session)
            conflict_result = list_conflicts(session)

            self.assertTrue(
                all(
                    contract["has_conflicts"]
                    for contract in contract_result["contracts"]
                )
            )
            self.assertEqual(len(conflict_result["conflicts"]), 1)
            conflict = conflict_result["conflicts"][0]
            self.assertEqual(conflict["scope"], "shared_party")
            self.assertEqual(
                {clause["text"] for clause in conflict["clauses"]},
                {left_clause.text, right_clause.text},
            )

    def test_deleting_contract_preserves_parties_used_by_other_contracts(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            party = Party(
                canonical_name="Alpha Pte. Ltd.",
                normalized_name="alpha pte ltd",
                entity_type="organization",
            )
            batch = UploadBatch(selection_name="Selected contracts")
            contracts = [
                Contract(
                    batch=batch,
                    source=f"agreement-{index}.txt",
                    relative_path=f"agreement-{index}.txt",
                    file_type="txt",
                    confidence=1.0,
                    status="complete",
                    parties=[
                        ContractPartyMention(
                            order_index=0,
                            raw_text="Alpha Pte. Ltd.",
                            extracted_name="Alpha Pte. Ltd.",
                            normalized_name="alpha pte ltd",
                            entity_type="organization",
                            extraction_confidence=0.9,
                            resolution_confidence=1.0,
                            party=party,
                        )
                    ],
                )
                for index in range(2)
            ]
            session.add_all(contracts)
            session.commit()
            deleted_id = contracts[0].id
            retained_id = contracts[1].id
            party_id = party.id

            deleted = delete_contract(contract_id=deleted_id, session=session)

            self.assertTrue(deleted)
            self.assertIsNone(session.get(Contract, deleted_id))
            self.assertIsNotNone(session.get(Contract, retained_id))
            self.assertIsNotNone(session.get(Party, party_id))
            self.assertEqual(len(session.scalars(select(UploadBatch)).all()), 1)

    @patch("backend.app.process_contract")
    def test_persists_text_and_resolved_party_rows(self, process_contract) -> None:
        process_contract.return_value = {
            "source": "agreement.txt",
            "text": "Alpha Pte. Ltd. agrees to the terms.",
            "confidence": 1.0,
            "clauses": [
                {
                    "category": "Governing Law",
                    "text": "Singapore law applies.",
                    "confidence": 0.9,
                }
            ],
            "parties": [
                {
                    "raw_text": "Alpha Pte. Ltd.",
                    "extracted_name": "Alpha Pte. Ltd.",
                    "normalized_name": "alpha pte ltd",
                    "entity_type": "organization",
                    "confidence": 0.85,
                    "start_offset": 0,
                    "end_offset": 15,
                }
            ],
            "dates": [],
        }
        upload = FileStorage(stream=BytesIO(b"source"), filename="agreement.txt")

        with Session(self.engine, expire_on_commit=False) as session:
            result = upload_contracts(
                files=[upload],
                paths=["contracts/agreement.txt"],
                session=session,
            )

            contract = session.scalar(select(Contract))
            text_record = session.scalar(select(ContractText))
            party = session.scalar(select(Party))

            self.assertEqual(
                result["contracts"][0]["parties"][0]["text"],
                "Alpha Pte. Ltd.",
            )
            self.assertEqual(contract.relative_path, "contracts/agreement.txt")
            self.assertEqual(text_record.text, process_contract.return_value["text"])
            self.assertEqual(
                text_record.character_count,
                len(process_contract.return_value["text"]),
            )
            self.assertEqual(len(text_record.content_sha256), 64)
            self.assertEqual(party.canonical_name, "Alpha Pte. Ltd.")
            self.assertEqual(contract.parties[0].party_id, party.id)
            self.assertNotIn("role", result["contracts"][0]["parties"][0])

    @patch("backend.app.process_contract")
    def test_upload_route_accepts_multipart_contracts(self, process_contract) -> None:
        process_contract.return_value = {
            "source": "agreement.txt",
            "text": "Agreement text",
            "confidence": 0.0,
            "clauses": [],
            "parties": [],
            "dates": [],
        }

        response = self.client.post(
            "/api/contracts/upload",
            data={
                "files": (BytesIO(b"Agreement text"), "agreement.txt"),
                "paths": "agreement.txt",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["contracts"][0]["source"], "agreement.txt")
        process_contract.assert_called_once()

    @patch("backend.app.process_contract")
    def test_accepts_multiple_individual_files_without_folder_paths(
        self,
        process_contract,
    ) -> None:
        process_contract.return_value = {
            "source": "contract.txt",
            "text": "Contract text",
            "confidence": 1.0,
            "clauses": [],
            "parties": [],
            "dates": [],
        }
        uploads = [
            FileStorage(stream=BytesIO(b"first"), filename="first.txt"),
            FileStorage(stream=BytesIO(b"second"), filename="second.txt"),
        ]

        with Session(self.engine, expire_on_commit=False) as session:
            result = upload_contracts(files=uploads, paths=None, session=session)

            contracts = session.scalars(
                select(Contract).order_by(Contract.source)
            ).all()
            self.assertEqual(
                [item.source for item in contracts], ["first.txt", "second.txt"]
            )
            self.assertEqual(
                [item.relative_path for item in contracts],
                ["first.txt", "second.txt"],
            )
            self.assertEqual(len(result["contracts"]), 2)
            self.assertEqual(
                session.scalar(select(UploadBatch)).selection_name,
                "Selected contracts",
            )

    def test_calendar_feed_is_built_from_contract_date_rows(self) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            contract = Contract(
                batch=UploadBatch(selection_name="folder"),
                source="services.pdf",
                relative_path="folder/services.pdf",
                file_type="pdf",
                confidence=1.0,
                status="complete",
                dates=[
                    ContractDate(
                        order_index=0,
                        event_date=date(2027, 6, 15),
                        event_desc="Payment due date",
                        confidence=0.82,
                        provenance="explicit",
                        evidence="Payment is due on 15 June 2027.",
                        start_offset=18,
                        end_offset=30,
                    )
                ],
            )
            session.add(contract)
            session.commit()

            content = calendar_feed(session=session)

            self.assertIn("DTSTART;VALUE=DATE:20270615", content)
            self.assertIn("SUMMARY:Payment due date — services.pdf", content)
            self.assertIn("X-EAGLEEYE-SOURCE:services.pdf", content)
            self.assertIn(
                "X-EAGLEEYE-EVIDENCE:Payment is due on 15 June 2027.", content
            )

        response = self.client.get("/api/calendar.ics?download=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/calendar")
        self.assertIn("attachment;", response.headers["Content-Disposition"])

    @patch(
        "backend.app.process_contract",
        side_effect=RuntimeError("model unavailable"),
    )
    def test_processing_failure_is_isolated_and_persisted(
        self,
        process_contract,
    ) -> None:
        upload = FileStorage(stream=BytesIO(b"source"), filename="broken.txt")

        with Session(self.engine, expire_on_commit=False) as session:
            with self.assertLogs("backend.app", level="ERROR") as logs:
                result = upload_contracts(
                    files=[upload],
                    paths=["contracts/broken.txt"],
                    session=session,
                )

            contracts = session.scalars(select(Contract)).all()
            self.assertEqual(len(contracts), 1)
            self.assertEqual(contracts[0].status, "failed")
            self.assertEqual(contracts[0].error, "RuntimeError: model unavailable")
            self.assertIsNone(contracts[0].text_record)
            self.assertEqual(result["contracts"][0]["status"], "failed")
            self.assertIn("Contract processing failed: broken.txt", logs.output[0])
            process_contract.assert_called_once()

    @patch("backend.app.process_contract")
    def test_upload_read_failure_is_isolated_and_persisted(
        self,
        process_contract,
    ) -> None:
        failing_file = Mock()
        failing_file.read.side_effect = OSError("read failed")
        upload = FileStorage(stream=failing_file, filename="unreadable.pdf")

        with Session(self.engine, expire_on_commit=False) as session:
            with self.assertLogs("backend.app", level="ERROR"):
                result = upload_contracts(
                    files=[upload],
                    paths=["contracts/unreadable.pdf"],
                    session=session,
                )

            contract = session.scalar(select(Contract))
            self.assertEqual(contract.status, "failed")
            self.assertEqual(contract.error, "OSError: read failed")
            self.assertEqual(result["contracts"][0]["status"], "failed")
            process_contract.assert_not_called()

    @patch("backend.app.process_contract")
    def test_duplicate_relative_paths_are_rejected_before_processing(
        self,
        process_contract,
    ) -> None:
        process_contract.return_value = {
            "source": "agreement.txt",
            "text": "Agreement",
            "confidence": 1.0,
            "clauses": [],
            "parties": [],
            "dates": [],
        }
        uploads = [
            FileStorage(stream=BytesIO(b"one"), filename="agreement.txt"),
            FileStorage(stream=BytesIO(b"two"), filename="agreement.txt"),
        ]

        with Session(self.engine, expire_on_commit=False) as session:
            result = upload_contracts(
                files=uploads,
                paths=["folder/agreement.txt", "folder/agreement.txt"],
                session=session,
            )

            self.assertEqual(len(result["contracts"]), 1)
            self.assertEqual(
                result["rejected"],
                [{"source": "agreement.txt", "reason": "Duplicate relative path"}],
            )
            process_contract.assert_called_once()

    @patch("backend.app.process_contract")
    def test_rejected_only_upload_does_not_create_empty_batch(
        self,
        process_contract,
    ) -> None:
        upload = FileStorage(stream=BytesIO(b"source"), filename="notes.csv")

        with Session(self.engine, expire_on_commit=False) as session:
            result = upload_contracts(files=[upload], paths=None, session=session)

            self.assertEqual(result["contracts"], [])
            self.assertEqual(
                result["rejected"],
                [{"source": "notes.csv", "reason": "Unsupported file type"}],
            )
            self.assertEqual(session.scalars(select(UploadBatch)).all(), [])
            process_contract.assert_not_called()
