"""Detect possible contradictions between pairs of extracted contract clauses."""

from functools import lru_cache
from math import sqrt
from typing import Any, TypedDict

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from backend.config import MODEL_CACHE

MODEL_ID = "epequeno/legal-entailment-deberta-v3-large"
MODEL_REVISION = "55a0247781a720bd3f3d0f34f5b7c52834416bfe"
MODEL_REFERENCE = f"{MODEL_ID}@{MODEL_REVISION}"
MAX_SEQUENCE_LENGTH = 512
BATCH_SIZE = 8
MIN_MODEL_CONFIDENCE = 0.75


class ConflictClause(TypedDict):
    """The persisted identity and verbatim content of one extracted clause."""

    id: str
    contract_id: str
    text: str
    confidence: float


class ClausePair(TypedDict):
    """Two clauses eligible for contradiction analysis."""

    clause_a: ConflictClause
    clause_b: ConflictClause
    party_confidence: float


class ConflictPrediction(TypedDict):
    """A possible contradiction grounded in two source clauses."""

    clause_a_id: str
    clause_b_id: str
    confidence: float
    model_confidence: float


@lru_cache(maxsize=1)
def _get_conflict_components() -> tuple[Any, Any]:
    """Download the legal NLI checkpoint if needed and load it locally once."""

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        cache_dir=MODEL_CACHE,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        cache_dir=MODEL_CACHE,
    )
    model.eval()
    return tokenizer, model


def _contradiction_index(model: Any) -> int:
    for index, label in model.config.id2label.items():
        if "contradict" in str(label).lower():
            return int(index)
    raise RuntimeError(f"{MODEL_REFERENCE} does not expose a contradiction label")


def _score_batch(pairs: list[ClausePair]) -> list[float]:
    tokenizer, model = _get_conflict_components()
    premises: list[str] = []
    hypotheses: list[str] = []
    for pair in pairs:
        left = pair["clause_a"]["text"]
        right = pair["clause_b"]["text"]
        premises.extend((left, right))
        hypotheses.extend((right, left))

    encoded = tokenizer(
        premises,
        hypotheses,
        padding=True,
        truncation=True,
        max_length=MAX_SEQUENCE_LENGTH,
        return_tensors="pt",
    )
    with torch.inference_mode():
        probabilities = torch.softmax(model(**encoded).logits, dim=-1)

    contradiction_index = _contradiction_index(model)
    scores: list[float] = []
    for pair_index in range(len(pairs)):
        forward = float(probabilities[pair_index * 2, contradiction_index])
        reverse = float(probabilities[pair_index * 2 + 1, contradiction_index])
        scores.append(sqrt(forward * reverse))
    return scores


def extract_conflicts(pairs: list[ClausePair]) -> list[ConflictPrediction]:
    """Return high-confidence, bidirectionally scored clause contradictions.

    The model treats its two inputs asymmetrically, so each pair is evaluated in
    both directions. The reported confidence also incorporates the confidence of
    both upstream CUAD clause extractions.
    """

    predictions: list[ConflictPrediction] = []
    for start in range(0, len(pairs), BATCH_SIZE):
        batch = pairs[start : start + BATCH_SIZE]
        for pair, model_confidence in zip(batch, _score_batch(batch), strict=True):
            if model_confidence < MIN_MODEL_CONFIDENCE:
                continue
            clause_confidence = sqrt(
                pair["clause_a"]["confidence"] * pair["clause_b"]["confidence"]
            )
            party_confidence = pair.get("party_confidence", 1.0)
            predictions.append(
                {
                    "clause_a_id": pair["clause_a"]["id"],
                    "clause_b_id": pair["clause_b"]["id"],
                    "confidence": float(
                        model_confidence * clause_confidence * party_confidence
                    ),
                    "model_confidence": model_confidence,
                }
            )
    return predictions
