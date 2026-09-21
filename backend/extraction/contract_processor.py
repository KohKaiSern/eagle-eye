"""Coordinate text, clause, party, and date extraction for one contract."""

from pathlib import Path
from statistics import fmean
from typing import TypedDict

from backend.extraction.clause_extractor import Clause, extract_clauses
from backend.extraction.date_extractor import ExtractedDate, extract_dates
from backend.extraction.party_extractor import PartyMention, extract_parties
from backend.extraction.readers.text_formatter import format_text

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt"}


class ProcessedContract(TypedDict):
    source: str
    text: str
    confidence: float
    clauses: list[Clause]
    parties: list[PartyMention]
    dates: list[ExtractedDate]


def process_contract(filepath: str, source: str) -> ProcessedContract:
    """Run every extractor and prepare the database payload for one file."""

    formatted = format_text(filepath)
    if formatted is None:
        raise ValueError(f"Unsupported contract type: {Path(source).suffix}")

    # The formatter sees a temporary server-side filename. Preserve the actual
    # uploaded basename throughout all downstream results instead.
    formatted["source"] = source
    clause_result = extract_clauses(formatted)
    date_result = extract_dates(formatted)
    parties = extract_parties(
        formatted["text"],
        formatted["confidence"],
    )
    extracted_confidences = [
        *(clause["confidence"] for clause in clause_result["clauses"]),
        *(party["confidence"] for party in parties),
        *(item["confidence"] for item in date_result["dates"]),
    ]

    return {
        "source": source,
        "text": formatted["text"],
        "confidence": (
            float(fmean(extracted_confidences)) if extracted_confidences else 0.0
        ),
        "clauses": clause_result["clauses"],
        "parties": parties,
        "dates": date_result["dates"],
    }
