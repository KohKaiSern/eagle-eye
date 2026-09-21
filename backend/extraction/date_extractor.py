"""Extract explicit and deterministic fixed-term dates from contract text."""

import re
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from statistics import fmean
from string import punctuation
from typing import Any, TypedDict

import torch
from dateutil.relativedelta import relativedelta

from backend.extraction.model_registry import (
    get_temporal_qa_components,
    get_zero_shot_classifier,
)
from backend.extraction.party_extractor import LegalEntity, extract_legal_entities

MIN_EVENT_CONFIDENCE = 0.25
MIN_DURATION_CONFIDENCE = 0.2
MIN_DEPENDENCY_CONFIDENCE = 0.2
DERIVED_DATE_DISCOUNT = 0.9
MAX_CONTEXT_CHARACTERS = 1_200

IRRELEVANT_EVENT = "Incidental, historical, or reference date"
EVENT_DESCRIPTIONS = (
    "Contract signing or agreement date",
    "Contract effective or commencement date",
    "Contract expiration or end date",
    "Contract renewal date",
    "Payment due date",
    "Delivery or performance due date",
    "Termination date",
    "Notice deadline",
    "Reporting or filing deadline",
    "Warranty start or expiration date",
    "Contractual milestone date",
    "Other contractual deadline or event date",
    IRRELEVANT_EVENT,
)

DEPENDENCY_EVENT = "a future event or action whose occurrence controls the end date"
DEPENDENCY_TYPES = (
    DEPENDENCY_EVENT,
    "a fixed duration or calendar date",
)
CONTRACT_NER_DATE_LABELS = {
    "EffectiveDate": "Contract effective or commencement date",
    "TerminationDate": "Contract expiration or end date",
}

NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
SUPPORTED_DURATION_UNITS = {
    "year": "years",
    "years": "years",
    "month": "months",
    "months": "months",
    "week": "weeks",
    "weeks": "weeks",
    "day": "days",
    "days": "days",
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
MONTH_PATTERN = "|".join(MONTHS)

NUMERIC_DMY_PATTERN = re.compile(
    r"\b(?P<day>0?[1-9]|[12]\d|3[01])"
    r"(?P<separator>[/.-])"
    r"(?P<month>0?[1-9]|1[0-2])"
    r"(?P=separator)"
    r"(?P<year>(?:19|20)\d{2})\b"
)
ISO_PATTERN = re.compile(
    r"\b(?P<year>(?:19|20)\d{2})-"
    r"(?P<month>0?[1-9]|1[0-2])-"
    r"(?P<day>0?[1-9]|[12]\d|3[01])\b"
)
DAY_FIRST_TEXT_PATTERN = re.compile(
    rf"\b(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
    rf"(?:\s+day\s+of)?\s+(?P<month>{MONTH_PATTERN}),?\s+"
    r"(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
MONTH_FIRST_TEXT_PATTERN = re.compile(
    rf"\b(?P<month>{MONTH_PATTERN})\s+"
    r"(?P<day>0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?,?\s+"
    r"(?P<year>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)


class FormattedText(TypedDict):
    """Input produced by ``text_formatter.format_text``."""

    text: str
    confidence: float
    source: str


class ExtractedDate(TypedDict):
    """One normalized date and the contractual event it represents."""

    date: str
    event_desc: str
    confidence: float
    provenance: str
    evidence: str
    start_offset: int
    end_offset: int


class DateResult(TypedDict):
    """Date extraction result for one contract."""

    source: str
    confidence: float
    dates: list[ExtractedDate]


class _DateCandidate(TypedDict):
    raw: str
    normalized: str
    start: int
    end: int


def _get_event_classifier() -> Any:
    """Return the process-wide local classifier."""

    return get_zero_shot_classifier()


def _get_duration_qa() -> Any:
    """Return the process-wide grounded temporal QA components."""

    return get_temporal_qa_components()


def _normalized_date(day: int, month: int, year: int) -> str | None:
    """Validate and format a calendar date as Singapore-style DD/MM/YYYY."""

    try:
        parsed = date(year, month, day)
    except ValueError:
        return None
    return parsed.strftime("%d/%m/%Y")


def _matches(text: str) -> Iterator[tuple[re.Match[str], bool]]:
    """Yield supported full-date matches and whether their month is textual."""

    for pattern, textual_month in (
        (NUMERIC_DMY_PATTERN, False),
        (ISO_PATTERN, False),
        (DAY_FIRST_TEXT_PATTERN, True),
        (MONTH_FIRST_TEXT_PATTERN, True),
    ):
        for match in pattern.finditer(text):
            yield match, textual_month


def _find_explicit_dates(text: str) -> list[_DateCandidate]:
    """Find valid full dates without resolving relative date expressions."""

    candidates: dict[tuple[int, int], _DateCandidate] = {}
    for match, textual_month in _matches(text):
        day = int(match.group("day"))
        year = int(match.group("year"))
        month_text = match.group("month")
        month = MONTHS[month_text.lower()] if textual_month else int(month_text)
        normalized = _normalized_date(day, month, year)
        if normalized is None:
            continue

        candidates[(match.start(), match.end())] = {
            "raw": match.group(0),
            "normalized": normalized,
            "start": match.start(),
            "end": match.end(),
        }

    return sorted(candidates.values(), key=lambda item: item["start"])


def _context_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Return source offsets for the candidate's capped paragraph."""

    paragraph_start = text.rfind("\n\n", 0, start)
    paragraph_start = 0 if paragraph_start < 0 else paragraph_start + 2
    paragraph_end = text.find("\n\n", end)
    paragraph_end = len(text) if paragraph_end < 0 else paragraph_end

    if paragraph_end - paragraph_start <= MAX_CONTEXT_CHARACTERS:
        return paragraph_start, paragraph_end

    radius = MAX_CONTEXT_CHARACTERS // 2
    window_start = max(0, start - radius)
    window_end = min(len(text), end + radius)
    return window_start, window_end


def _context_for(text: str, start: int, end: int) -> str:
    context_start, context_end = _context_span(text, start, end)
    return text[context_start:context_end]


def _classify_event(context: str, date_text: str) -> tuple[str, float] | None:
    """Classify what an explicit date represents in its contract context."""

    result = _get_event_classifier()(
        f"Explicit date: {date_text}\nContract context: {context}",
        candidate_labels=list(EVENT_DESCRIPTIONS),
        hypothesis_template="In this contract, this date is the {}.",
        multi_label=False,
    )
    event_desc = str(result["labels"][0])
    confidence = float(result["scores"][0])

    if event_desc == IRRELEVANT_EVENT or confidence < MIN_EVENT_CONFIDENCE:
        return None
    return event_desc, confidence


def _answer_question(
    question: str,
    context: str,
    *,
    max_answer_tokens: int,
    validator: Callable[[str], bool] | None = None,
) -> tuple[str, float] | None:
    """Return the strongest grounded answer that beats the model's null answer."""

    tokenizer, model = _get_duration_qa()
    encoded = tokenizer(
        question,
        context,
        truncation="only_second",
        max_length=386,
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    offsets = encoded.pop("offset_mapping")[0]
    sequence_ids = encoded.sequence_ids(0)
    with torch.inference_mode():
        output = model(**encoded)

    valid_context = torch.tensor(
        [sequence_id == 1 for sequence_id in sequence_ids],
        dtype=torch.bool,
        device=output.start_logits.device,
    )
    cls_matches = (encoded["input_ids"][0] == tokenizer.cls_token_id).nonzero(
        as_tuple=False
    )
    cls_index = int(cls_matches[0].item()) if len(cls_matches) else 0
    valid_context[cls_index] = True
    start_logits = output.start_logits[0].masked_fill(~valid_context, float("-inf"))
    end_logits = output.end_logits[0].masked_fill(~valid_context, float("-inf"))
    start_probabilities = torch.softmax(start_logits, dim=0)
    end_probabilities = torch.softmax(end_logits, dim=0)
    null_score = float(start_probabilities[cls_index] * end_probabilities[cls_index])
    start_indexes = torch.topk(
        start_probabilities,
        min(20, start_probabilities.shape[0]),
    ).indices.tolist()
    end_indexes = torch.topk(
        end_probabilities,
        min(20, end_probabilities.shape[0]),
    ).indices.tolist()

    best: tuple[str, float] | None = None
    for start_index in start_indexes:
        for end_index in end_indexes:
            if sequence_ids[start_index] != 1 or sequence_ids[end_index] != 1:
                continue
            if end_index < start_index or end_index - start_index > max_answer_tokens:
                continue
            start = int(offsets[start_index, 0])
            end = int(offsets[end_index, 1])
            if end <= start:
                continue
            answer = context[start:end].strip()
            if validator is not None and not validator(answer):
                continue
            score = float(
                start_probabilities[start_index] * end_probabilities[end_index]
            )
            if best is None or score > best[1]:
                best = (answer, score)

    if best is None or best[1] <= null_score:
        return None

    return best


def _extract_term_duration(context: str, date_text: str) -> tuple[str, float] | None:
    """Extract a verbatim fixed-term duration associated with an explicit date."""

    answer = _answer_question(
        f"How long is the initial contract term that starts on {date_text}?",
        context,
        max_answer_tokens=12,
        validator=lambda value: _parse_duration(value) is not None,
    )
    if answer is None:
        return None
    answer_text, score = answer
    if not answer_text or score < MIN_DURATION_CONFIDENCE:
        return None
    return answer_text, score


def _has_event_dependency(context: str) -> bool:
    """Detect whether a future action, rather than elapsed time, controls expiry."""

    answer = _answer_question(
        "Which future event or action must happen before the contract term ends?",
        context,
        max_answer_tokens=16,
    )
    if answer is None or answer[1] < MIN_DEPENDENCY_CONFIDENCE:
        return False
    answer_text, _ = answer
    result = _get_event_classifier()(
        f"Extracted answer: {answer_text}\nContract context: {context}",
        candidate_labels=list(DEPENDENCY_TYPES),
        hypothesis_template="The extracted answer is {}.",
        multi_label=False,
    )
    label = str(result["labels"][0])
    classification_confidence = float(result["scores"][0])
    return label == DEPENDENCY_EVENT and classification_confidence >= 0.5


def _contract_ner_hint(
    candidate: _DateCandidate,
    hints: list[LegalEntity],
) -> tuple[str, float] | None:
    """Return a ContractNER event label when it covers the explicit date span."""

    for hint in sorted(hints, key=lambda item: item["score"], reverse=True):
        intersection = max(
            0,
            min(candidate["end"], hint["end"]) - max(candidate["start"], hint["start"]),
        )
        if intersection / (candidate["end"] - candidate["start"]) >= 0.8:
            return CONTRACT_NER_DATE_LABELS[hint["label"]], float(hint["score"])
    return None


def _parse_duration(value: str) -> dict[str, int] | None:
    """Parse a model-grounded duration span into calendar arithmetic inputs."""

    tokens = [token.strip(punctuation).casefold() for token in value.split()]
    duration = {"years": 0, "months": 0, "weeks": 0, "days": 0}
    found = False
    for index, token in enumerate(tokens[:-1]):
        try:
            amount = int(token)
        except ValueError:
            amount = NUMBER_WORDS.get(token, 0)
        unit = SUPPORTED_DURATION_UNITS.get(tokens[index + 1])
        if amount > 0 and unit:
            duration[unit] += amount
            found = True
    return duration if found else None


def _derived_expiration(
    anchor: _DateCandidate,
    explicit_date: ExtractedDate,
    text: str,
    text_confidence: float,
) -> ExtractedDate | None:
    context_start, context_end = _context_span(text, anchor["start"], anchor["end"])
    context = text[context_start:context_end]
    duration_answer = _extract_term_duration(context, anchor["raw"])
    if duration_answer is None:
        return None
    duration_text, duration_confidence = duration_answer
    if _has_event_dependency(context):
        return None
    duration = _parse_duration(duration_text)
    if duration is None:
        return None

    anchor_date = datetime.strptime(anchor["normalized"], "%d/%m/%Y").date()
    exclusive_boundary = anchor_date + relativedelta(**duration)
    inclusive_end = exclusive_boundary - timedelta(days=1)
    anchor_model_confidence = (
        explicit_date["confidence"] / text_confidence if text_confidence else 0.0
    )
    model_confidence = (anchor_model_confidence * duration_confidence) ** 0.5
    return {
        "date": inclusive_end.strftime("%d/%m/%Y"),
        "event_desc": "Contract expiration or end date",
        "confidence": float(
            min(1.0, text_confidence * model_confidence * DERIVED_DATE_DISCOUNT)
        ),
        "provenance": "derived",
        "evidence": context.strip(),
        "start_offset": context_start,
        "end_offset": context_end,
    }


def extract_dates(formatted_text: FormattedText) -> DateResult:
    """Extract explicit and deterministic fixed-term contract dates.

    Slash-separated numeric dates are always interpreted in Singapore DMY
    order. Dates dependent on a future action or uncertain event remain ignored.
    Fixed durations anchored to an explicit commencement date may produce an
    inclusive, clearly marked derived expiration date.
    """

    text = formatted_text["text"]
    extracted_by_event: dict[tuple[str, str], ExtractedDate] = {}
    explicit_anchors: list[tuple[_DateCandidate, ExtractedDate]] = []
    candidates = _find_explicit_dates(text)
    if not candidates:
        return {
            "source": formatted_text["source"],
            "confidence": 0.0,
            "dates": [],
        }
    date_hints = extract_legal_entities(
        text,
        list(CONTRACT_NER_DATE_LABELS),
        threshold=0.5,
    )

    for candidate in candidates:
        hint = _contract_ner_hint(candidate, date_hints)
        if hint is not None:
            event_desc, model_confidence = hint
        else:
            classification = _classify_event(
                _context_for(text, candidate["start"], candidate["end"]),
                candidate["raw"],
            )
            if classification is None:
                continue
            event_desc, model_confidence = classification
        combined_confidence = formatted_text["confidence"] * model_confidence
        key = (candidate["normalized"], event_desc)
        extracted_date: ExtractedDate = {
            "date": candidate["normalized"],
            "event_desc": event_desc,
            "confidence": float(combined_confidence),
            "provenance": "explicit",
            "evidence": candidate["raw"],
            "start_offset": candidate["start"],
            "end_offset": candidate["end"],
        }
        existing = extracted_by_event.get(key)
        if existing is None or extracted_date["confidence"] > existing["confidence"]:
            extracted_by_event[key] = extracted_date
        if event_desc == "Contract effective or commencement date":
            explicit_anchors.append((candidate, extracted_date))

    has_explicit_expiration = any(
        item["event_desc"] == "Contract expiration or end date"
        for item in extracted_by_event.values()
    )
    if not has_explicit_expiration:
        for anchor, explicit_date in explicit_anchors:
            derived = _derived_expiration(
                anchor,
                explicit_date,
                text,
                formatted_text["confidence"],
            )
            if derived is None:
                continue
            key = (derived["date"], derived["event_desc"])
            existing = extracted_by_event.get(key)
            if existing is None or derived["confidence"] > existing["confidence"]:
                extracted_by_event[key] = derived

    extracted = sorted(
        extracted_by_event.values(),
        key=lambda item: (
            datetime.strptime(item["date"], "%d/%m/%Y").date(),
            item["provenance"] == "derived",
        ),
    )

    return {
        "source": formatted_text["source"],
        "confidence": float(
            fmean(item["confidence"] for item in extracted) if extracted else 0.0
        ),
        "dates": extracted,
    }
