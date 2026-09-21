"""Text reader for softcopy PDF contracts."""

from typing import TypedDict

from pypdf import PdfReader


class PDFResult(TypedDict):
    """The text and confidence returned by the PDF reader."""

    text: str
    confidence: float


def read_pdf(filepath: str) -> PDFResult:
    """Extract embedded text from a softcopy PDF contract.

    Text extracted directly from the PDF's text layer has confidence 1.0.
    A PDF with no extractable text has confidence 0.0.
    """

    reader = PdfReader(filepath)
    try:
        pages = tuple(
            text
            for page in reader.pages
            if (text := (page.extract_text() or "").strip())
        )
    finally:
        reader.close()

    text = "\n\n".join(pages)
    return {"text": text, "confidence": 1.0 if text else 0.0}
