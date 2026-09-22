"""Read embedded PDF text, falling back to local OCR for textless pages."""

from contextlib import ExitStack, closing
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

from pypdf import PdfReader
from pypdfium2 import PdfDocument

from backend.extraction.readers.png_reader import read_image


class PDFResult(TypedDict):
    """The text and confidence returned by the PDF reader."""

    text: str
    confidence: float


def read_pdf(filepath: str) -> PDFResult:
    """Extract pages in order, OCRing pages without embedded text.

    Confidence is the character-weighted mean of non-empty page results.
    Embedded text has confidence 1.0; scanned text uses the OCR confidence.
    """

    pages: list[str] = []
    weighted_confidence = 0.0
    character_count = 0
    with ExitStack() as resources:
        reader = PdfReader(filepath)
        resources.callback(reader.close)
        rendered_document = None
        for index, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            confidence = 1.0
            if not text:
                if rendered_document is None:
                    rendered_document = resources.enter_context(PdfDocument(filepath))
                    directory = resources.enter_context(TemporaryDirectory())
                image_path = Path(directory) / "page.png"
                with closing(rendered_document[index]) as rendered_page:
                    with closing(rendered_page.render(scale=300 / 72)) as bitmap:
                        with bitmap.to_pil() as image:
                            image.save(image_path)
                result = read_image(str(image_path))
                text = result["text"].strip()
                confidence = result["confidence"]
            if text:
                pages.append(text)
                character_count += len(text)
                weighted_confidence += confidence * len(text)

    text = "\n\n".join(pages)
    return {
        "text": text,
        "confidence": weighted_confidence / character_count if character_count else 0.0,
    }
