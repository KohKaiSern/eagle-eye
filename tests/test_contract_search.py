"""Tests for fuzzy search over locally stored contract text."""

from unittest import TestCase

from backend.services.contract_search import search_contract_texts


class ContractSearchTests(TestCase):
    def setUp(self) -> None:
        self.documents = [
            {
                "contract_id": "contract-1",
                "source": "lease.txt",
                "relative_path": "leases/lease.txt",
                "text": (
                    "LEASE AGREEMENT\n"
                    "Rent is due on the first day of every month.\n"
                    "Termination: Either party may end the lease with 30 days' notice."
                ),
            },
            {
                "contract_id": "contract-2",
                "source": "services.txt",
                "relative_path": "services/services.txt",
                "text": "The supplier must deliver the report by Friday.",
            },
        ]

    def test_exact_phrase_ranks_as_full_match_with_source_offsets(self) -> None:
        matches = search_contract_texts(self.documents, "rent is due", limit=10)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source"], "lease.txt")
        self.assertEqual(matches[0]["score"], 1.0)
        self.assertEqual(matches[0]["line_number"], 2)
        self.assertEqual(
            self.documents[0]["text"][
                matches[0]["start_offset"] : matches[0]["end_offset"]
            ],
            matches[0]["snippet"],
        )

    def test_tolerates_typographical_errors_and_separated_terms(self) -> None:
        matches = search_contract_texts(
            self.documents,
            "terminaton notce",
            limit=10,
        )

        self.assertEqual(matches[0]["source"], "lease.txt")
        self.assertIn("30 days' notice", matches[0]["snippet"])
        self.assertGreater(matches[0]["score"], 0.58)

    def test_omits_unrelated_passages(self) -> None:
        matches = search_contract_texts(
            self.documents,
            "banana tractor",
            limit=10,
        )

        self.assertEqual(matches, [])

    def test_applies_global_result_limit(self) -> None:
        matches = search_contract_texts(self.documents, "the", limit=1)

        self.assertEqual(len(matches), 1)
