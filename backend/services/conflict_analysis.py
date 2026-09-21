"""Build and persist eligible clause-pair contradiction analysis."""

from itertools import combinations, product
from math import sqrt
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.extraction.conflict_extractor import (
    MODEL_REFERENCE,
    ClausePair,
    ConflictClause,
    extract_conflicts,
)
from backend.persistence.database import (
    Contract,
    ContractClause,
    ContractConflict,
    ContractPartyMention,
)


def _normalized_clause_text(text: str) -> str:
    return " ".join(text.split()).casefold()


def _logical_clauses(contract: Contract) -> list[ContractClause]:
    """Collapse duplicate CUAD categories over the same verbatim clause span."""

    clauses: dict[str, ContractClause] = {}
    for clause in contract.clauses:
        key = _normalized_clause_text(clause.text)
        if not key:
            continue
        current = clauses.get(key)
        if current is None or clause.confidence > current.confidence:
            clauses[key] = clause
    return list(clauses.values())


def _party_resolution(contract: Contract) -> dict[UUID, float]:
    resolution: dict[UUID, float] = {}
    for mention in contract.parties:
        if mention.party_id:
            resolution[mention.party_id] = max(
                resolution.get(mention.party_id, 0.0),
                mention.resolution_confidence,
            )
    return resolution


def _clause_pair(
    left: ContractClause,
    right: ContractClause,
    party_confidence: float = 1.0,
) -> ClausePair:
    if str(left.id) > str(right.id):
        left, right = right, left
    left_contract_id = left.contract_id or left.contract.id
    right_contract_id = right.contract_id or right.contract.id
    clause_a: ConflictClause = {
        "id": str(left.id),
        "contract_id": str(left_contract_id),
        "text": left.text,
        "confidence": left.confidence,
    }
    clause_b: ConflictClause = {
        "id": str(right.id),
        "contract_id": str(right_contract_id),
        "text": right.text,
        "confidence": right.confidence,
    }
    return {
        "clause_a": clause_a,
        "clause_b": clause_b,
        "party_confidence": party_confidence,
    }


def build_conflict_candidates(
    contracts: list[Contract],
    changed_contract_ids: set[UUID] | None = None,
) -> list[ClausePair]:
    """Create intra-contract and shared-party cross-contract clause pairs."""

    candidates: dict[tuple[str, str], ClausePair] = {}
    logical_clauses = {
        contract.id: _logical_clauses(contract) for contract in contracts
    }

    for contract in contracts:
        if changed_contract_ids is not None and contract.id not in changed_contract_ids:
            continue
        for left, right in combinations(logical_clauses[contract.id], 2):
            pair = _clause_pair(left, right)
            key = (pair["clause_a"]["id"], pair["clause_b"]["id"])
            candidates[key] = pair

    for left_contract, right_contract in combinations(contracts, 2):
        if changed_contract_ids is not None and not (
            left_contract.id in changed_contract_ids
            or right_contract.id in changed_contract_ids
        ):
            continue
        left_parties = _party_resolution(left_contract)
        right_parties = _party_resolution(right_contract)
        shared_party_ids = left_parties.keys() & right_parties.keys()
        if not shared_party_ids:
            continue
        party_confidence = max(
            sqrt(left_parties[party_id] * right_parties[party_id])
            for party_id in shared_party_ids
        )
        for left, right in product(
            logical_clauses[left_contract.id],
            logical_clauses[right_contract.id],
        ):
            pair = _clause_pair(left, right, party_confidence)
            key = (pair["clause_a"]["id"], pair["clause_b"]["id"])
            candidates[key] = pair

    return list(candidates.values())


def analyze_contract_conflicts(
    session: Session,
    changed_contract_ids: set[UUID] | None = None,
) -> list[ContractConflict]:
    """Analyze eligible pairs and persist newly identified conflicts."""

    contracts = session.scalars(
        select(Contract)
        .where(Contract.status == "complete")
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.parties),
        )
    ).all()
    candidates = build_conflict_candidates(contracts, changed_contract_ids)
    existing_pairs = set(
        session.execute(
            select(ContractConflict.clause_a_id, ContractConflict.clause_b_id)
        ).all()
    )
    candidates = [
        pair
        for pair in candidates
        if (
            UUID(pair["clause_a"]["id"]),
            UUID(pair["clause_b"]["id"]),
        )
        not in existing_pairs
    ]

    conflicts = [
        ContractConflict(
            clause_a_id=UUID(prediction["clause_a_id"]),
            clause_b_id=UUID(prediction["clause_b_id"]),
            confidence=prediction["confidence"],
            model_confidence=prediction["model_confidence"],
            model_id=MODEL_REFERENCE,
        )
        for prediction in extract_conflicts(candidates)
    ]
    session.add_all(conflicts)
    session.flush()
    return conflicts


def list_conflicts(session: Session) -> list[ContractConflict]:
    """Load all possible conflicts with their clauses, contracts, and parties."""

    return session.scalars(
        select(ContractConflict)
        .options(
            selectinload(ContractConflict.clause_a)
            .selectinload(ContractClause.contract)
            .selectinload(Contract.parties)
            .selectinload(ContractPartyMention.party),
            selectinload(ContractConflict.clause_b)
            .selectinload(ContractClause.contract)
            .selectinload(Contract.parties)
            .selectinload(ContractPartyMention.party),
            selectinload(ContractConflict.clause_a)
            .selectinload(ContractClause.contract)
            .selectinload(Contract.clauses),
            selectinload(ContractConflict.clause_b)
            .selectinload(ContractClause.contract)
            .selectinload(Contract.clauses),
        )
        .order_by(
            ContractConflict.confidence.desc(), ContractConflict.created_at.desc()
        )
    ).all()
