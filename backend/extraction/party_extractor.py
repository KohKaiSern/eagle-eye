"""Extract and normalize contracting parties from the complete contract."""

import re
import unicodedata
from functools import lru_cache
from typing import Any, TypedDict

from gliner import GLiNER

from backend.config import MODEL_CACHE
from backend.extraction.model_registry import get_zero_shot_classifier

PARTY_ENTITY_THRESHOLD = 0.5
ENTITY_TYPE_THRESHOLD = 0.1
PARTY_LABEL = "Parties"
TYPE_LABELS = {"Organization": "organization", "Person": "person"}
MODEL_ID = "agilelab-org/Contractner"
WINDOW_CHARACTERS = 1_000
WINDOW_OVERLAP = 180

SUFFIX_REPLACEMENTS = (
    (re.compile(r"\bprivate\s+limited\b"), "pte ltd"),
    (re.compile(r"\bpte\s+ltd\b"), "pte ltd"),
    (re.compile(r"\blimited\b"), "ltd"),
    (re.compile(r"\bincorporated\b"), "inc"),
    (re.compile(r"\bcorporation\b"), "corp"),
)

ENTITY_TYPE_LABELS = {
    "an organization, company, government body, or other legal entity": "organization",
    "an individual person": "person",
}


class LegalEntity(TypedDict):
    text: str
    label: str
    score: float
    start: int
    end: int


class PartyMention(TypedDict):
    raw_text: str
    extracted_name: str
    normalized_name: str
    entity_type: str
    confidence: float
    start_offset: int | None
    end_offset: int | None


def _get_party_classifier() -> Any:
    """Return the shared local contextual classifier."""

    return get_zero_shot_classifier()


@lru_cache(maxsize=1)
def _get_contract_ner() -> Any:
    """Load ContractNER locally, downloading weights only on first use."""

    model = GLiNER.from_pretrained(MODEL_ID, cache_dir=MODEL_CACHE)
    model.eval()
    return model


def _windows(text: str) -> list[tuple[int, str]]:
    """Split long text into overlapping, source-offset-preserving windows."""

    if len(text) <= WINDOW_CHARACTERS:
        return [(0, text)]

    windows: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        tentative_end = min(len(text), start + WINDOW_CHARACTERS)
        end = tentative_end
        if tentative_end < len(text):
            boundary = max(
                text.rfind("\n", start + WINDOW_CHARACTERS // 2, tentative_end),
                text.rfind(" ", start + WINDOW_CHARACTERS // 2, tentative_end),
            )
            if boundary > start:
                end = boundary
        windows.append((start, text[start:end]))
        if end >= len(text):
            break
        start = end - WINDOW_OVERLAP
    return windows


def _overlap(left: LegalEntity, right: LegalEntity) -> float:
    intersection = max(
        0,
        min(left["end"], right["end"]) - max(left["start"], right["start"]),
    )
    shorter = min(left["end"] - left["start"], right["end"] - right["start"])
    return intersection / shorter if shorter else 0.0


def extract_legal_entities(
    text: str,
    labels: list[str],
    *,
    threshold: float,
) -> list[LegalEntity]:
    """Return grounded ContractNER spans with complete-text offsets."""

    if not text.strip():
        return []

    candidates: list[LegalEntity] = []
    for window_start, window in _windows(text):
        for entity in _get_contract_ner().predict_entities(
            window,
            labels,
            threshold=threshold,
        ):
            start = window_start + int(entity["start"])
            end = window_start + int(entity["end"])
            if start < 0 or end <= start or end > len(text):
                continue
            candidates.append(
                {
                    "text": text[start:end],
                    "label": str(entity["label"]),
                    "score": float(entity["score"]),
                    "start": start,
                    "end": end,
                }
            )

    kept: list[LegalEntity] = []
    for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
        if not any(
            candidate["label"] == existing["label"]
            and _overlap(candidate, existing) >= 0.8
            for existing in kept
        ):
            kept.append(candidate)
    return sorted(kept, key=lambda item: (item["start"], item["end"]))


def normalize_party_name(name: str) -> str:
    """Return a conservative comparison key without altering the source name."""

    normalized = unicodedata.normalize("NFKC", name).casefold()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for pattern, replacement in SUFFIX_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _context_for(text: str, start: int, end: int) -> str:
    """Return a compact source context around one grounded party span."""

    context_start = max(0, text.rfind("\n", 0, start))
    if context_start:
        previous_line = text.rfind("\n", 0, context_start)
        context_start = 0 if previous_line < 0 else previous_line + 1
    context_end = text.find("\n", end)
    context_end = len(text) if context_end < 0 else context_end
    next_line = text.find("\n", context_end + 1)
    if next_line >= 0:
        context_end = next_line
    return text[context_start:context_end][:1_200]


def _classify_entity_type(context: str, name: str) -> tuple[str, float]:
    type_entities = extract_legal_entities(
        name,
        list(TYPE_LABELS),
        threshold=ENTITY_TYPE_THRESHOLD,
    )
    if type_entities:
        best = max(type_entities, key=lambda item: item["score"])
        if best["start"] == 0 and best["end"] == len(name):
            return TYPE_LABELS[best["label"]], float(best["score"])

    result = _get_party_classifier()(
        f"Candidate party: {name}\nContract context: {context}",
        candidate_labels=list(ENTITY_TYPE_LABELS),
        hypothesis_template="In this contract, the candidate party is {}.",
        multi_label=False,
    )
    label = str(result["labels"][0])
    return ENTITY_TYPE_LABELS[label], float(result["scores"][0])


def extract_parties(
    text: str,
    text_confidence: float = 1.0,
) -> list[PartyMention]:
    """Extract whole-document parties with ContractNER."""

    if not text.strip():
        return []

    mentions: dict[str, PartyMention] = {}
    entities = extract_legal_entities(
        text,
        [PARTY_LABEL],
        threshold=PARTY_ENTITY_THRESHOLD,
    )

    for entity in entities:
        start = entity["start"]
        end = entity["end"]
        raw_name = text[start:end]
        extracted_name = raw_name.strip(" \t\r\n,;:()[]{}\"'“”‘’")
        normalized_name = normalize_party_name(extracted_name)
        if len(normalized_name) < 2:
            continue

        context = _context_for(text, start, end)
        entity_type, type_confidence = _classify_entity_type(
            context,
            extracted_name,
        )
        contract_ner_confidence = float(entity["score"])
        confidence = text_confidence * contract_ner_confidence * type_confidence

        mention: PartyMention = {
            "raw_text": raw_name,
            "extracted_name": extracted_name,
            "normalized_name": normalized_name,
            "entity_type": entity_type,
            "confidence": min(1.0, max(0.0, float(confidence))),
            "start_offset": start,
            "end_offset": end,
        }

        existing = mentions.get(normalized_name)
        if existing is None or mention["confidence"] > existing["confidence"]:
            mentions[normalized_name] = mention

    return sorted(
        mentions.values(),
        key=lambda mention: mention["start_offset"] or 0,
    )
