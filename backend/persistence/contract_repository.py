"""Translate extraction results into normalized persistence models."""

import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from backend.extraction.contract_processor import ProcessedContract
from backend.persistence.database import (
    Contract,
    ContractClause,
    ContractDate,
    ContractText,
    UploadBatch,
)
from backend.persistence.party_resolution import resolve_party_mentions


def create_processed_contract(
    session: Session,
    batch: UploadBatch,
    *,
    source: str,
    relative_path: str,
    file_type: str,
    result: ProcessedContract,
) -> Contract:
    """Create a complete normalized contract graph in the current transaction."""

    text = result["text"]
    contract = Contract(
        batch=batch,
        source=source,
        relative_path=relative_path,
        file_type=file_type,
        confidence=result["confidence"],
        status="complete",
        text_record=ContractText(
            text=text,
            confidence=result["confidence"],
            character_count=len(text),
            content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        ),
        clauses=[
            ContractClause(
                order_index=order_index,
                category=clause["category"],
                text=clause["text"],
                confidence=clause["confidence"],
            )
            for order_index, clause in enumerate(result["clauses"])
        ],
        dates=[
            ContractDate(
                order_index=order_index,
                event_date=datetime.strptime(item["date"], "%d/%m/%Y").date(),
                event_desc=item["event_desc"],
                confidence=item["confidence"],
                provenance=item["provenance"],
                evidence=item["evidence"],
                start_offset=item["start_offset"],
                end_offset=item["end_offset"],
            )
            for order_index, item in enumerate(result["dates"])
        ],
    )
    session.add(contract)
    resolve_party_mentions(session, contract, result["parties"])
    return contract


def create_failed_contract(
    session: Session,
    batch: UploadBatch,
    *,
    source: str,
    relative_path: str,
    file_type: str,
    error: Exception,
) -> Contract:
    """Create an auditable failure record without exposing a traceback."""

    contract = Contract(
        batch=batch,
        source=source,
        relative_path=relative_path,
        file_type=file_type,
        confidence=0.0,
        status="failed",
        error=f"{type(error).__name__}: {error}",
    )
    session.add(contract)
    return contract
