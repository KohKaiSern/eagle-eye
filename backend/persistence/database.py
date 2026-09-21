"""PostgreSQL persistence for processed contracts."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from statistics import fmean
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from backend.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UploadBatch(Base):
    """A file or folder selection submitted to Eagle Eye for processing."""

    __tablename__ = "upload_batches"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    selection_name: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    contracts: Mapped[list[Contract]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class Contract(Base):
    """One uploaded contract file and its processing state."""

    __tablename__ = "contracts"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_contracts_confidence",
        ),
        CheckConstraint(
            "status IN ('complete', 'failed')",
            name="ck_contracts_status",
        ),
        UniqueConstraint(
            "batch_id",
            "relative_path",
            name="uq_contracts_batch_relative_path",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(512), index=True)
    relative_path: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="complete", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    batch: Mapped[UploadBatch] = relationship(back_populates="contracts")
    clauses: Mapped[list[ContractClause]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractClause.order_index",
    )
    text_record: Mapped[ContractText | None] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        uselist=False,
    )
    parties: Mapped[list[ContractPartyMention]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractPartyMention.order_index",
    )
    dates: Mapped[list[ContractDate]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractDate.order_index",
    )

    def as_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        extracted_confidences = [
            *(clause.confidence for clause in self.clauses),
            *(party.extraction_confidence for party in self.parties),
            *(contract_date.confidence for contract_date in self.dates),
        ]
        result = {
            "id": str(self.id),
            "batch_id": str(self.batch_id),
            "source": self.source,
            "relative_path": self.relative_path,
            "file_type": self.file_type,
            "confidence": (
                float(fmean(extracted_confidences))
                if extracted_confidences
                else self.confidence
            ),
            "clauses": [clause.as_dict() for clause in self.clauses],
            "parties": [party.as_dict() for party in self.parties],
            "dates": [contract_date.as_dict() for contract_date in self.dates],
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_text:
            result["text"] = self.text_record.as_dict() if self.text_record else None
        return result


class ContractText(Base):
    """The exact text produced by the formatter for one contract."""

    __tablename__ = "contract_texts"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_contract_texts_confidence",
        ),
        CheckConstraint(
            "character_count >= 0",
            name="ck_contract_texts_character_count",
        ),
    )

    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    character_count: Mapped[int] = mapped_column(Integer)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    contract: Mapped[Contract] = relationship(back_populates="text_record")

    def as_dict(self) -> dict[str, Any]:
        return {
            "content": self.text,
            "confidence": self.confidence,
            "character_count": self.character_count,
            "sha256": self.content_sha256,
        }


class ContractClause(Base):
    """One CUAD clause extracted from a contract."""

    __tablename__ = "contract_clauses"
    __table_args__ = (
        CheckConstraint("order_index >= 0", name="ck_contract_clauses_order"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_contract_clauses_confidence",
        ),
        UniqueConstraint(
            "contract_id",
            "order_index",
            name="uq_contract_clauses_contract_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)

    contract: Mapped[Contract] = relationship(back_populates="clauses")
    conflicts_as_a: Mapped[list[ContractConflict]] = relationship(
        back_populates="clause_a",
        foreign_keys="ContractConflict.clause_a_id",
        passive_deletes=True,
    )
    conflicts_as_b: Mapped[list[ContractConflict]] = relationship(
        back_populates="clause_b",
        foreign_keys="ContractConflict.clause_b_id",
        passive_deletes=True,
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "category": self.category,
            "text": self.text,
            "confidence": self.confidence,
        }


class ContractConflict(Base):
    """A model-identified possible contradiction between two exact clauses."""

    __tablename__ = "contract_conflicts"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_contract_conflicts_confidence",
        ),
        CheckConstraint(
            "model_confidence >= 0 AND model_confidence <= 1",
            name="ck_contract_conflicts_model_confidence",
        ),
        CheckConstraint(
            "clause_a_id <> clause_b_id",
            name="ck_contract_conflicts_distinct_clauses",
        ),
        UniqueConstraint(
            "clause_a_id",
            "clause_b_id",
            name="uq_contract_conflicts_clause_pair",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    clause_a_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_clauses.id", ondelete="CASCADE"),
        index=True,
    )
    clause_b_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_clauses.id", ondelete="CASCADE"),
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float)
    model_confidence: Mapped[float] = mapped_column(Float)
    model_id: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    clause_a: Mapped[ContractClause] = relationship(
        back_populates="conflicts_as_a",
        foreign_keys=[clause_a_id],
    )
    clause_b: Mapped[ContractClause] = relationship(
        back_populates="conflicts_as_b",
        foreign_keys=[clause_b_id],
    )

    @staticmethod
    def _clause_dict(clause: ContractClause) -> dict[str, Any]:
        normalized_text = " ".join(clause.text.split()).casefold()
        categories = [
            {
                "name": item.category,
                "confidence": item.confidence,
            }
            for item in clause.contract.clauses
            if " ".join(item.text.split()).casefold() == normalized_text
        ]
        return {
            "id": str(clause.id),
            "contract_id": str(clause.contract_id),
            "source": clause.contract.source,
            "relative_path": clause.contract.relative_path,
            "text": clause.text,
            "confidence": clause.confidence,
            "categories": categories,
        }

    def as_dict(self) -> dict[str, Any]:
        left_contract = self.clause_a.contract
        right_contract = self.clause_b.contract
        left_parties = {
            mention.party_id: mention.party.canonical_name
            for mention in left_contract.parties
            if mention.party_id and mention.party
        }
        right_party_ids = {
            mention.party_id for mention in right_contract.parties if mention.party_id
        }
        shared_parties = [
            name
            for party_id, name in left_parties.items()
            if party_id in right_party_ids
        ]
        return {
            "id": str(self.id),
            "confidence": self.confidence,
            "model_confidence": self.model_confidence,
            "scope": (
                "within_contract"
                if self.clause_a.contract_id == self.clause_b.contract_id
                else "shared_party"
            ),
            "shared_parties": sorted(shared_parties),
            "clauses": [
                self._clause_dict(self.clause_a),
                self._clause_dict(self.clause_b),
            ],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Party(Base):
    """A canonical person or organization referenced by contracts."""

    __tablename__ = "parties"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('organization', 'person')",
            name="ck_parties_entity_type",
        ),
        CheckConstraint(
            "verification_status IN ('unverified', 'verified', 'rejected')",
            name="ck_parties_verification_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    canonical_name: Mapped[str] = mapped_column(String(512))
    normalized_name: Mapped[str] = mapped_column(String(512), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    verification_status: Mapped[str] = mapped_column(
        String(24),
        default="unverified",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    aliases: Mapped[list[PartyAlias]] = relationship(
        back_populates="party",
        cascade="all, delete-orphan",
    )
    mentions: Mapped[list[ContractPartyMention]] = relationship(
        back_populates="party",
    )


class PartyAlias(Base):
    """A source-observed name associated with a canonical party."""

    __tablename__ = "party_aliases"
    __table_args__ = (
        UniqueConstraint(
            "party_id",
            "normalized_alias",
            name="uq_party_aliases_party_normalized",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    party_id: Mapped[UUID] = mapped_column(
        ForeignKey("parties.id", ondelete="CASCADE"),
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(512))
    normalized_alias: Mapped[str] = mapped_column(String(512), index=True)
    source: Mapped[str] = mapped_column(String(32), default="contract")

    party: Mapped[Party] = relationship(back_populates="aliases")


class ContractPartyMention(Base):
    """A party name as it appears in a particular contract."""

    __tablename__ = "contract_party_mentions"
    __table_args__ = (
        CheckConstraint(
            "order_index >= 0",
            name="ck_contract_party_mentions_order",
        ),
        CheckConstraint(
            "entity_type IN ('organization', 'person')",
            name="ck_contract_party_mentions_entity_type",
        ),
        CheckConstraint(
            "extraction_confidence >= 0 AND extraction_confidence <= 1",
            name="ck_contract_party_mentions_extraction_confidence",
        ),
        CheckConstraint(
            "resolution_confidence >= 0 AND resolution_confidence <= 1",
            name="ck_contract_party_mentions_resolution_confidence",
        ),
        CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR "
            "(start_offset >= 0 AND end_offset > start_offset)",
            name="ck_contract_party_mentions_offsets",
        ),
        UniqueConstraint(
            "contract_id",
            "order_index",
            name="uq_contract_party_mentions_contract_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        index=True,
    )
    party_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("parties.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    extracted_name: Mapped[str] = mapped_column(String(512))
    normalized_name: Mapped[str] = mapped_column(String(512), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    extraction_confidence: Mapped[float] = mapped_column(Float)
    resolution_confidence: Mapped[float] = mapped_column(Float)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    contract: Mapped[Contract] = relationship(back_populates="parties")
    party: Mapped[Party | None] = relationship(back_populates="mentions")

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.extracted_name,
            "raw_text": self.raw_text,
            "normalized_name": self.normalized_name,
            "entity_type": self.entity_type,
            "confidence": self.extraction_confidence,
            "resolution_confidence": self.resolution_confidence,
            "party_id": str(self.party_id) if self.party_id else None,
            "canonical_name": self.party.canonical_name if self.party else None,
        }


class ContractDate(Base):
    """One normalized explicit or deterministically derived contract event."""

    __tablename__ = "contract_dates"
    __table_args__ = (
        CheckConstraint("order_index >= 0", name="ck_contract_dates_order"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_contract_dates_confidence",
        ),
        CheckConstraint(
            "provenance IN ('explicit', 'derived')",
            name="ck_contract_dates_provenance",
        ),
        CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR "
            "(start_offset >= 0 AND end_offset > start_offset)",
            name="ck_contract_dates_offsets",
        ),
        UniqueConstraint(
            "contract_id",
            "order_index",
            name="uq_contract_dates_contract_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer)
    event_date: Mapped[date] = mapped_column(Date, index=True)
    event_desc: Mapped[str] = mapped_column(String(256), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    provenance: Mapped[str] = mapped_column(String(16), default="explicit", index=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    contract: Mapped[Contract] = relationship(back_populates="dates")

    def as_dict(self) -> dict[str, Any]:
        return {
            "date": self.event_date.strftime("%d/%m/%Y"),
            "event_desc": self.event_desc,
            "confidence": self.confidence,
            "provenance": self.provenance,
            "evidence": self.evidence,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
        }


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def initialize_database() -> None:
    """Create the current prototype schema when the application starts."""

    Base.metadata.create_all(engine)
