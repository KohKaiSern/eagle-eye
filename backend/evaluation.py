"""Run the local extraction pipeline against a small labelled regression corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.extraction.date_extractor import extract_dates
from backend.extraction.party_extractor import extract_parties, normalize_party_name

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "evaluations" / "contracts.json"


def _prf(predicted: set[Any], expected: set[Any]) -> dict[str, float]:
    correct = len(predicted & expected)
    precision = correct / len(predicted) if predicted else float(not expected)
    recall = correct / len(expected) if expected else float(not predicted)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def evaluate(corpus_path: Path = DEFAULT_CORPUS) -> dict[str, Any]:
    """Evaluate party names/types and normalized dates with exact matching."""

    cases = json.loads(corpus_path.read_text(encoding="utf-8"))
    predicted_parties: set[tuple[str, str, str]] = set()
    expected_parties: set[tuple[str, str, str]] = set()
    predicted_dates: set[tuple[str, str, str]] = set()
    expected_dates: set[tuple[str, str, str]] = set()
    case_results: list[dict[str, Any]] = []

    for case in cases:
        case_id = str(case["id"])
        text = str(case["text"])
        parties = extract_parties(text, 1.0)
        dates = extract_dates(
            {"source": f"{case_id}.txt", "text": text, "confidence": 1.0}
        )["dates"]

        actual_party_keys = {
            (
                normalize_party_name(item["extracted_name"]),
                item["entity_type"],
                case_id,
            )
            for item in parties
        }
        expected_party_keys = {
            (
                normalize_party_name(item["name"]),
                item["entity_type"],
                case_id,
            )
            for item in case["expected_parties"]
        }
        actual_date_keys = {
            (item["date"], item["event_desc"], case_id) for item in dates
        }
        expected_date_keys = {
            (item["date"], item["event_desc"], case_id)
            for item in case["expected_dates"]
        }
        predicted_parties.update(actual_party_keys)
        expected_parties.update(expected_party_keys)
        predicted_dates.update(actual_date_keys)
        expected_dates.update(expected_date_keys)
        case_results.append(
            {
                "id": case_id,
                "parties": parties,
                "dates": dates,
                "party_exact_match": actual_party_keys == expected_party_keys,
                "date_exact_match": actual_date_keys == expected_date_keys,
            }
        )

    return {
        "cases": case_results,
        "metrics": {
            "parties": _prf(predicted_parties, expected_parties),
            "dates": _prf(predicted_dates, expected_dates),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.corpus), indent=2))


if __name__ == "__main__":
    main()
