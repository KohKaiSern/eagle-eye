"""Tests for the contract text-reader dispatcher."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.extraction.readers.text_formatter import format_text


class FormatTextTests(TestCase):
    def test_reads_txt_directly_with_full_confidence(self) -> None:
        with TemporaryDirectory() as directory:
            filepath = Path(directory) / "contract.TXT"
            filepath.write_text("Payment is due Friday.\n", encoding="utf-8")

            result = format_text(str(filepath))

        self.assertEqual(
            result,
            {
                "text": "Payment is due Friday.\n",
                "confidence": 1.0,
                "source": "contract.TXT",
            },
        )

    @patch("backend.extraction.readers.text_formatter.read_docx")
    def test_dispatches_docx(self, read_docx) -> None:
        read_docx.return_value = {"text": "DOCX", "confidence": 1.0}

        result = format_text("contract.DOCX")

        read_docx.assert_called_once_with("contract.DOCX")
        self.assertEqual(
            result,
            {"text": "DOCX", "confidence": 1.0, "source": "contract.DOCX"},
        )

    @patch("backend.extraction.readers.text_formatter.read_pdf")
    def test_dispatches_pdf(self, read_pdf) -> None:
        read_pdf.return_value = {"text": "PDF", "confidence": 1.0}

        result = format_text("contract.pdf")

        read_pdf.assert_called_once_with("contract.pdf")
        self.assertEqual(
            result,
            {"text": "PDF", "confidence": 1.0, "source": "contract.pdf"},
        )

    @patch("backend.extraction.readers.text_formatter.read_image")
    def test_dispatches_supported_image_extensions(self, read_image) -> None:
        read_image.return_value = {"text": "IMAGE", "confidence": 0.9}

        for filepath in ("contract.png", "contract.JPG", "contract.jpeg"):
            with self.subTest(filepath=filepath):
                self.assertEqual(
                    format_text(filepath),
                    {
                        "text": "IMAGE",
                        "confidence": 0.9,
                        "source": filepath,
                    },
                )

        self.assertEqual(read_image.call_count, 3)

    def test_logs_and_ignores_unsupported_files(self) -> None:
        with self.assertLogs(
            "backend.extraction.readers.text_formatter",
            level="WARNING",
        ) as logs:
            result = format_text("contract.rtf")

        self.assertIsNone(result)
        self.assertIn("Unsupported file ignored: contract.rtf", logs.output[0])
