"""Tests for the PNG/JPEG OCR reader's output contract."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.extraction.readers.png_reader import read_image


class ReadImageTests(TestCase):
    def test_returns_text_and_weighted_confidence(self) -> None:
        ocr_output = SimpleNamespace(
            txts=("Agreement", "Payment is due on Friday."),
            scores=(0.9, 0.6),
        )

        with patch(
            "backend.extraction.readers.png_reader._get_ocr_engine",
            return_value=Mock(return_value=ocr_output),
        ):
            result = read_image("contract.png")

        expected_confidence = (0.9 * 9 + 0.6 * 25) / 34
        self.assertEqual(
            result,
            {
                "text": "Agreement\nPayment is due on Friday.",
                "confidence": expected_confidence,
            },
        )

    def test_returns_zero_confidence_when_no_text_is_found(self) -> None:
        ocr_output = SimpleNamespace(txts=None, scores=None)

        with patch(
            "backend.extraction.readers.png_reader._get_ocr_engine",
            return_value=Mock(return_value=ocr_output),
        ):
            result = read_image("blank.jpg")

        self.assertEqual(result, {"text": "", "confidence": 0.0})
