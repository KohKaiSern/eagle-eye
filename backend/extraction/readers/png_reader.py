"""Local OCR reader for PNG and JPEG contract images."""

from functools import lru_cache
from typing import TypedDict

from rapidocr import RapidOCR


class OCRResult(TypedDict):
    """The text and aggregate confidence returned by the OCR reader."""

    text: str
    confidence: float


@lru_cache(maxsize=1)
def _get_ocr_engine() -> RapidOCR:
    """Create the local OCR engine once, on the first read."""

    return RapidOCR()


def read_image(filepath: str) -> OCRResult:
    """Extract text from a PNG or JPEG contract image.

    Confidence is returned on a 0.0-to-1.0 scale. It is calculated as a
    character-weighted mean of RapidOCR's confidence for each detected line.
    """

    result = _get_ocr_engine()(filepath)
    lines = result.txts or []
    scores = result.scores or []

    text = "\n".join(lines)
    weights = [max(len(line.strip()), 1) for line in lines]
    total_weight = sum(weights)
    confidence = (
        sum(score * weight for score, weight in zip(scores, weights, strict=False))
        / total_weight
        if total_weight
        else 0.0
    )

    return {"text": text, "confidence": float(confidence)}
