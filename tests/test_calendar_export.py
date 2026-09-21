"""Tests for the database-backed iCalendar export."""

from datetime import UTC, date, datetime
from unittest import TestCase

from backend.services.calendar_export import build_calendar


class CalendarExportTests(TestCase):
    def test_builds_all_day_event_and_escapes_text(self) -> None:
        result = build_calendar(
            [
                {
                    "uid": "date-id",
                    "contract_id": "contract-id",
                    "date": date(2026, 3, 4),
                    "summary": "Payment, delivery; and review",
                    "source": "terms, final.txt",
                    "confidence": 0.876,
                    "provenance": "explicit",
                    "evidence": "Payment is due on 04/03/2026.",
                    "start_offset": 18,
                    "end_offset": 28,
                }
            ],
            generated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        )

        self.assertTrue(result.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertIn("DTSTAMP:20260102T030405Z\r\n", result)
        self.assertIn("DTSTART;VALUE=DATE:20260304\r\n", result)
        self.assertIn(
            "SUMMARY:Payment\\, delivery\\; and review — terms\\, final.txt\r\n",
            result,
        )
        self.assertIn(
            "X-EAGLEEYE-EVENT-DESC:Payment\\, delivery\\; and review\r\n",
            result,
        )
        self.assertIn("X-EAGLEEYE-CONTRACT-ID:contract-id\r\n", result)
        self.assertIn("X-EAGLEEYE-EVIDENCE:Payment is due on 04/03/2026.", result)
        self.assertIn("X-EAGLEEYE-START-OFFSET:18\r\n", result)
        self.assertIn("X-EAGLEEYE-END-OFFSET:28\r\n", result)
        self.assertIn("Contract: terms\\, final.txt\\nConfidence: 88%", result)
        self.assertTrue(result.endswith("END:VCALENDAR\r\n"))

    def test_folds_long_unicode_lines_to_75_octets(self) -> None:
        result = build_calendar(
            [
                {
                    "uid": "long-event",
                    "contract_id": "contract-id",
                    "date": date(2026, 12, 31),
                    "summary": "履行期限" * 30,
                    "source": "long-contract.txt",
                    "confidence": 1.0,
                }
            ],
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        self.assertTrue(
            all(len(line.encode("utf-8")) <= 75 for line in result.splitlines())
        )
        self.assertIn("\r\n ", result)
