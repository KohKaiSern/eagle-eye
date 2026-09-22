"""Tests for embedded-text and scanned PDF extraction."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from PIL import Image
from pypdf import PdfWriter

from backend.extraction.readers.pdf_reader import read_pdf


class ReadPDFTests(TestCase):
    @patch("backend.extraction.readers.pdf_reader.PdfDocument")
    @patch("backend.extraction.readers.pdf_reader.PdfReader")
    def test_returns_pages_in_order_with_full_confidence(
        self, pdf_reader: Mock, pdf_document: Mock
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
        pdf_document.assert_not_called()

    @patch("backend.extraction.readers.pdf_reader.read_image")
    def test_ignores_empty_pages_and_returns_zero_for_no_text(
        self, read_image: Mock
    ) -> None:
        read_image.return_value = {"text": "", "confidence": 0.0}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "blank.pdf"
            with PdfWriter() as writer:
                writer.add_blank_page(width=72, height=72)
                writer.write(path)
            result = read_pdf(str(path))

        self.assertEqual(result, {"text": "", "confidence": 0.0})

    @patch("backend.extraction.readers.pdf_reader.read_image")
    def test_scanned_pages_are_rendered_in_order_and_cleaned_up(self, ocr: Mock) -> None:
        paths = []

        def recognize(path):
            paths.append(Path(path))
            with Image.open(path) as image:
                self.assertEqual(image.size, (300, 300))
                color = image.getpixel((150, 150))
            if color[0] > color[2]:
                return {"text": "First", "confidence": 0.8}
            return {"text": "Second page", "confidence": 0.6}

        ocr.side_effect = recognize
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scan.pdf"
            with Image.new("RGB", (72, 72), "red") as first:
                with Image.new("RGB", (72, 72), "blue") as second:
                    first.save(path, "PDF", save_all=True, append_images=[second])
            result = read_pdf(str(path))
        self.assertEqual(result["text"], "First\n\nSecond page")
        self.assertAlmostEqual(result["confidence"], (5 * 0.8 + 11 * 0.6) / 16)
        self.assertEqual(ocr.call_count, 2)
        self.assertTrue(all(not path.exists() for path in paths))

    @patch("backend.extraction.readers.pdf_reader.read_image")
    @patch("backend.extraction.readers.pdf_reader.PdfReader")
    def test_mixed_pages_combine_text_and_ocr(self, pdf_reader: Mock, ocr: Mock) -> None:
        reader = pdf_reader.return_value
        reader.pages = [Mock(extract_text=Mock(return_value="Text")),
                        Mock(extract_text=Mock(return_value=None))]
        ocr.return_value = {"text": "Scan", "confidence": 0.8}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "mixed.pdf"
            with PdfWriter() as writer:
                for _ in range(2):
                    writer.add_blank_page(width=72, height=72)
                writer.write(path)
            result = read_pdf(str(path))
        self.assertEqual(result["text"], "Text\n\nScan")
        self.assertAlmostEqual(result["confidence"], 0.9)
        ocr.assert_called_once()
        reader.close.assert_called_once_with()

    @patch("backend.extraction.readers.pdf_reader.read_image")
    def test_temporary_image_removed_when_ocr_fails(self, ocr: Mock) -> None:
        paths = []

        def fail(path):
            paths.append(Path(path))
            raise RuntimeError("OCR failed")

        ocr.side_effect = fail
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scan.pdf"
            with PdfWriter() as writer:
                writer.add_blank_page(width=72, height=72)
                writer.write(path)
            with self.assertRaisesRegex(RuntimeError, "OCR failed"):
                read_pdf(str(path))
        self.assertEqual(len(paths), 1)
        self.assertFalse(paths[0].exists())
