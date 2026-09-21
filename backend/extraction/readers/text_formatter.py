"""Dispatch contract files to the appropriate text reader."""

import logging
from pathlib import Path
from typing import TypedDict

from backend.extraction.readers.docx_reader import read_docx
from backend.extraction.readers.pdf_reader import read_pdf
from backend.extraction.readers.png_reader import read_image

logger = logging.getLogger(__name__)


class TextResult(TypedDict):
    """The common output returned by all supported text readers."""

    text: str
    confidence: float
    source: str


def format_text(filepath: str) -> TextResult | None:
    """Extract text from a supported contract file.

    Unsupported files are logged and ignored by returning ``None``.
    """

    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        reader_result = {
            "text": path.read_text(encoding="utf-8"),
            "confidence": 1.0,
        }
    elif suffix == ".docx":
        reader_result = read_docx(filepath)
    elif suffix == ".pdf":
        reader_result = read_pdf(filepath)
    elif suffix in {".png", ".jpg", ".jpeg"}:
        reader_result = read_image(filepath)
    else:
        logger.warning("Unsupported file ignored: %s", filepath)
        return None

    return {
        "text": reader_result["text"],
        "confidence": reader_result["confidence"],
        "source": path.name,
    }
