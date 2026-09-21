"""Build an RFC 5545 iCalendar feed from normalized contract dates."""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import NotRequired, TypedDict


class CalendarEvent(TypedDict):
    uid: str
    contract_id: str
    date: date
    summary: str
    source: str
    confidence: float
    provenance: NotRequired[str]
    evidence: NotRequired[str | None]
    start_offset: NotRequired[int | None]
    end_offset: NotRequired[int | None]


def _escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _fold_line(line: str) -> list[str]:
    """Fold a content line without exceeding the RFC's 75-octet limit."""

    folded: list[str] = []
    current = ""
    for character in line:
        candidate = current + character
        if current and len(candidate.encode("utf-8")) > 75:
            folded.append(current)
            current = " " + character
        else:
            current = candidate
    folded.append(current)
    return folded


def build_calendar(
    events: Iterable[CalendarEvent],
    *,
    generated_at: datetime | None = None,
) -> str:
    """Return a standards-compatible calendar containing all-day events."""

    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    dtstamp = timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AITHENA//Eagle Eye//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Eagle Eye Contract Events",
    ]
    for event in events:
        confidence_percent = round(event["confidence"] * 100)
        provenance = event.get("provenance", "explicit")
        evidence = event.get("evidence")
        description = (
            f"Contract: {event['source']}\nConfidence: {confidence_percent}%"
            f"\nDate provenance: {provenance}"
        )
        if evidence:
            description += f"\nEvidence: {evidence}"

        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{_escape_text(event['uid'])}@eagle-eye.local",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;VALUE=DATE:{event['date'].strftime('%Y%m%d')}",
            "SUMMARY:" + _escape_text(f"{event['summary']} — {event['source']}"),
            "DESCRIPTION:" + _escape_text(description),
            f"X-EAGLEEYE-CONTRACT-ID:{_escape_text(event['contract_id'])}",
            f"X-EAGLEEYE-SOURCE:{_escape_text(event['source'])}",
            f"X-EAGLEEYE-EVENT-DESC:{_escape_text(event['summary'])}",
            f"X-EAGLEEYE-CONFIDENCE:{event['confidence']:.6f}",
            f"X-EAGLEEYE-PROVENANCE:{provenance}",
        ]
        if evidence:
            event_lines.append(f"X-EAGLEEYE-EVIDENCE:{_escape_text(evidence)}")
        if event.get("start_offset") is not None:
            event_lines.append(f"X-EAGLEEYE-START-OFFSET:{event['start_offset']}")
        if event.get("end_offset") is not None:
            event_lines.append(f"X-EAGLEEYE-END-OFFSET:{event['end_offset']}")
        event_lines.extend(["TRANSP:TRANSPARENT", "END:VEVENT"])
        lines.extend(event_lines)
    lines.append("END:VCALENDAR")

    return (
        "\r\n".join(folded_line for line in lines for folded_line in _fold_line(line))
        + "\r\n"
    )
