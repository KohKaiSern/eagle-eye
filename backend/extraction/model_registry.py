"""Shared lazy loaders for local Hugging Face inference models."""

from functools import lru_cache
from typing import Any

from transformers import (
    AutoModelForQuestionAnswering,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    pipeline,
)

from backend.config import MODEL_CACHE

ZERO_SHOT_MODEL_ID = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"
TEMPORAL_QA_MODEL_ID = "deepset/tinyroberta-squad2"


@lru_cache(maxsize=1)
def get_zero_shot_classifier() -> Any:
    """Load the shared local NLI classifier once per application process."""

    tokenizer = AutoTokenizer.from_pretrained(
        ZERO_SHOT_MODEL_ID,
        cache_dir=MODEL_CACHE,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        ZERO_SHOT_MODEL_ID,
        cache_dir=MODEL_CACHE,
    )
    return pipeline(
        "zero-shot-classification",
        model=model,
        tokenizer=tokenizer,
        device="cpu",
    )


@lru_cache(maxsize=1)
def get_temporal_qa_components() -> tuple[Any, Any]:
    """Load the tokenizer/model pair used for grounded fixed-term QA."""

    tokenizer = AutoTokenizer.from_pretrained(
        TEMPORAL_QA_MODEL_ID,
        cache_dir=MODEL_CACHE,
    )
    model = AutoModelForQuestionAnswering.from_pretrained(
        TEMPORAL_QA_MODEL_ID,
        cache_dir=MODEL_CACHE,
    )
    model.eval()
    return tokenizer, model
