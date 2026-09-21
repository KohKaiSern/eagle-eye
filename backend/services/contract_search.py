"""Rank fuzzy, source-offset-preserving matches in stored contract text."""

import re
from collections.abc import Iterable, Iterator
from difflib import SequenceMatcher
from statistics import fmean
from typing import TypedDict

MAX_PASSAGE_CHARACTERS = 360
PASSAGE_OVERLAP_CHARACTERS = 80
MATCHES_PER_CONTRACT = 3
MIN_MATCH_SCORE = 0.58

WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
LINE_PATTERN = re.compile(r"[^\r\n]+")


class SearchDocument(TypedDict):
    contract_id: str
    source: str
    relative_path: str
    text: str


class SearchMatch(TypedDict):
    contract_id: str
    source: str
    relative_path: str
    snippet: str
    score: float
    line_number: int
    start_offset: int
    end_offset: int


class _Passage(TypedDict):
    text: str
    start: int
    end: int


def _passages(text: str) -> Iterator[_Passage]:
    """Yield readable line windows while retaining offsets into the source."""

    for line_match in LINE_PATTERN.finditer(text):
        line = line_match.group(0)
        leading = len(line) - len(line.lstrip())
        trailing = len(line.rstrip())
        line = line[leading:trailing]
        line_start = line_match.start() + leading

        window_start = 0
        while window_start < len(line):
            window_end = min(len(line), window_start + MAX_PASSAGE_CHARACTERS)
            if window_end < len(line):
                boundary = line.rfind(
                    " ",
                    window_start + MAX_PASSAGE_CHARACTERS // 2,
                    window_end,
                )
                if boundary > window_start:
                    window_end = boundary

            snippet = line[window_start:window_end].strip()
            if snippet:
                snippet_start = line.find(snippet, window_start, window_end)
                start = line_start + snippet_start
                yield {
                    "text": snippet,
                    "start": start,
                    "end": start + len(snippet),
                }

            if window_end >= len(line):
                break
            window_start = window_end - PASSAGE_OVERLAP_CHARACTERS


def _normalized_words(value: str) -> list[str]:
    return [match.group(0).casefold() for match in WORD_PATTERN.finditer(value)]


def _word_similarity(query_word: str, candidate_word: str) -> float:
    if query_word == candidate_word:
        return 1.0
    if len(query_word) <= 3 or len(candidate_word) <= 3:
        return 0.0
    return SequenceMatcher(None, query_word, candidate_word).ratio()


def _match_score(query: str, passage: str) -> float:
    query_words = _normalized_words(query)
    passage_words = _normalized_words(passage)
    if not query_words or not passage_words:
        return 0.0

    normalized_query = " ".join(query_words)
    normalized_passage = " ".join(passage_words)
    if normalized_query in normalized_passage:
        return 1.0

    token_score = fmean(
        max(_word_similarity(query_word, word) for word in passage_words)
        for query_word in query_words
    )
    query_word_count = len(query_words)
    phrase_score = max(
        SequenceMatcher(
            None,
            normalized_query,
            " ".join(passage_words[start : start + query_word_count + 3]),
        ).ratio()
        for start in range(len(passage_words))
    )
    return min(1.0, 0.6 * token_score + 0.4 * phrase_score)


def _overlap(left: SearchMatch, right: SearchMatch) -> float:
    intersection = max(
        0,
        min(left["end_offset"], right["end_offset"])
        - max(left["start_offset"], right["start_offset"]),
    )
    shorter = min(
        left["end_offset"] - left["start_offset"],
        right["end_offset"] - right["start_offset"],
    )
    return intersection / shorter if shorter else 0.0


def search_contract_texts(
    documents: Iterable[SearchDocument],
    query: str,
    *,
    limit: int,
) -> list[SearchMatch]:
    """Return the strongest fuzzy passage matches across complete contracts."""

    matches: list[SearchMatch] = []
    for document in documents:
        document_matches: list[SearchMatch] = []
        for passage in _passages(document["text"]):
            score = _match_score(query, passage["text"])
            if score < MIN_MATCH_SCORE:
                continue
            document_matches.append(
                {
                    "contract_id": document["contract_id"],
                    "source": document["source"],
                    "relative_path": document["relative_path"],
                    "snippet": passage["text"],
                    "score": score,
                    "line_number": document["text"].count("\n", 0, passage["start"])
                    + 1,
                    "start_offset": passage["start"],
                    "end_offset": passage["end"],
                }
            )

        kept: list[SearchMatch] = []
        for match in sorted(
            document_matches,
            key=lambda item: (-item["score"], item["start_offset"]),
        ):
            if not any(_overlap(match, existing) >= 0.6 for existing in kept):
                kept.append(match)
            if len(kept) == MATCHES_PER_CONTRACT:
                break
        matches.extend(kept)

    return sorted(
        matches,
        key=lambda item: (-item["score"], item["source"], item["start_offset"]),
    )[:limit]
