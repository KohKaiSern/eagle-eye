"""Resolve extracted party mentions to canonical database entities."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.extraction.party_extractor import PartyMention
from backend.persistence.database import (
    Contract,
    ContractPartyMention,
    Party,
    PartyAlias,
)


def _party_for_unique_alias(
    session: Session,
    normalized_name: str,
    entity_type: str,
) -> tuple[Party | None, bool]:
    candidates = session.scalars(
        select(Party)
        .join(PartyAlias)
        .where(
            PartyAlias.normalized_alias == normalized_name,
            Party.entity_type == entity_type,
        )
        .limit(2)
    ).all()
    if len(candidates) == 1:
        return candidates[0], False
    return None, len(candidates) > 1


def _ensure_alias(party: Party, alias: str, normalized_alias: str) -> None:
    if not any(item.normalized_alias == normalized_alias for item in party.aliases):
        party.aliases.append(
            PartyAlias(
                alias=alias,
                normalized_alias=normalized_alias,
                source="contract",
            )
        )


def resolve_party_mentions(
    session: Session,
    contract: Contract,
    mentions: Iterable[PartyMention],
) -> None:
    """Attach mentions to unique normalized aliases, creating parties as needed."""

    for order_index, mention in enumerate(mentions):
        party, ambiguous_alias = _party_for_unique_alias(
            session,
            mention["normalized_name"],
            mention["entity_type"],
        )
        resolution_confidence = 0.98 if party else 0.0

        if party is None and not ambiguous_alias:
            party = Party(
                canonical_name=mention["extracted_name"],
                normalized_name=mention["normalized_name"],
                entity_type=mention["entity_type"],
                verification_status="unverified",
            )
            party.aliases.append(
                PartyAlias(
                    alias=mention["extracted_name"],
                    normalized_alias=mention["normalized_name"],
                    source="contract",
                )
            )
            session.add(party)
            resolution_confidence = 0.75
        elif party is not None:
            _ensure_alias(
                party,
                mention["extracted_name"],
                mention["normalized_name"],
            )

        contract.parties.append(
            ContractPartyMention(
                party=party,
                order_index=order_index,
                raw_text=mention["raw_text"],
                extracted_name=mention["extracted_name"],
                normalized_name=mention["normalized_name"],
                entity_type=mention["entity_type"],
                extraction_confidence=mention["confidence"],
                resolution_confidence=resolution_confidence,
                start_offset=mention["start_offset"],
                end_offset=mention["end_offset"],
            )
        )
