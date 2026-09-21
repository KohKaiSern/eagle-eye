"""Tests for the softcopy PDF reader's output contract."""

from unittest import TestCase
from unittest.mock import Mock, patch

from backend.extraction.readers.pdf_reader import read_pdf


class ReadPDFTests(TestCase):
    @patch("backend.extraction.readers.pdf_reader.PdfReader")
    def test_returns_pages_in_order_with_full_confidence(
        self, pdf_reader: Mock
    ) -> None:
        reader = pdf_reader.return_value
        reader.pages = [
            Mock(extract_text=Mock(return_value="Service Agreement\n")),
            Mock(extract_text=Mock(return_value="Payment is due Friday.\n")),
        ]

        result = read_pdf("contract.pdf")

        pdf_reader.assert_called_once_with("contract.pdf")
        self.assertEqual(
            result,
            {
                "text": "Service Agreement\n\nPayment is due Friday.",
                "confidence": 1.0,
            },
        )
        reader.close.assert_called_once_with()

    @patch("backend.extraction.readers.pdf_reader.PdfReader")
    def test_ignores_empty_pages_and_returns_zero_for_no_text(
        self, pdf_reader: Mock
    ) -> None:
        reader = pdf_reader.return_value
        reader.pages = [
            Mock(extract_text=Mock(return_value=None)),
            Mock(extract_text=Mock(return_value="  \n")),
        ]

        result = read_pdf("blank.pdf")

        self.assertEqual(result, {"text": "", "confidence": 0.0})
        reader.close.assert_called_once_with()
