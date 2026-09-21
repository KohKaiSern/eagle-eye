"""Flask server for the local Eagle Eye application."""

import logging
import shutil
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID, uuid4

import click
from flask import (
    Flask,
    Response,
    abort,
    current_app,
    jsonify,
    request,
    send_from_directory,
)
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload
from werkzeug.datastructures import FileStorage

from backend.config import (
    CONTRACT_LIST_DEFAULT_LIMIT,
    CONTRACT_LIST_MAX_LIMIT,
    FRONTEND_DIST,
)
from backend.extraction.contract_processor import (
    SUPPORTED_EXTENSIONS,
    process_contract,
)
from backend.persistence.contract_repository import (
    create_failed_contract,
    create_processed_contract,
)
from backend.persistence.database import (
    Contract,
    ContractClause,
    ContractConflict,
    ContractDate,
    ContractPartyMention,
    ContractText,
    Party,
    SessionLocal,
    UploadBatch,
    initialize_database,
)
from backend.services.calendar_export import CalendarEvent, build_calendar
from backend.services.conflict_analysis import (
    analyze_contract_conflicts,
)
from backend.services.conflict_analysis import (
    list_conflicts as load_conflicts,
)
from backend.services.contract_search import SearchDocument, search_contract_texts

logger = logging.getLogger(__name__)


def _safe_upload_names(filename: str, relative_path: str | None) -> tuple[str, str]:
    normalized_filename = filename.replace("\\", "/")
    source = PurePosixPath(normalized_filename).name
    candidate = (relative_path or source).replace("\\", "/")
    safe_parts = [
        part
        for part in PurePosixPath(candidate).parts
        if part not in {"", ".", "..", "/"}
    ]
    return source, "/".join(safe_parts) or source


def health(session: Session) -> dict[str, str]:
    session.execute(select(1))
    return {"status": "ok", "database": "ok"}


def _conflict_contract_ids(session: Session) -> set[UUID]:
    clause_ids = {
        clause_id
        for row in session.execute(
            select(ContractConflict.clause_a_id, ContractConflict.clause_b_id)
        )
        for clause_id in row
    }
    if not clause_ids:
        return set()
    return set(
        session.scalars(
            select(ContractClause.contract_id).where(ContractClause.id.in_(clause_ids))
        ).all()
    )


def list_contracts(
    session: Session,
    limit: int = CONTRACT_LIST_DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    contracts = session.scalars(
        select(Contract)
        .options(
            selectinload(Contract.clauses),
            selectinload(Contract.parties).selectinload(ContractPartyMention.party),
            selectinload(Contract.dates),
        )
        .order_by(Contract.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    conflict_contract_ids = _conflict_contract_ids(session)
    return {
        "contracts": [
            {
                **contract.as_dict(),
                "has_conflicts": contract.id in conflict_contract_ids,
            }
            for contract in contracts
        ]
    }


def list_conflicts(session: Session) -> dict[str, Any]:
    return {"conflicts": [conflict.as_dict() for conflict in load_conflicts(session)]}


def search_contracts(session: Session, q: str, limit: int = 20) -> dict[str, Any]:
    rows = session.execute(
        select(
            Contract.id,
            Contract.source,
            Contract.relative_path,
            ContractText.text,
        )
        .join(ContractText)
        .where(Contract.status == "complete")
    ).all()
    documents: list[SearchDocument] = [
        {
            "contract_id": str(contract_id),
            "source": source,
            "relative_path": relative_path,
            "text": text,
        }
        for contract_id, source, relative_path, text in rows
    ]
    return {"query": q, "matches": search_contract_texts(documents, q, limit=limit)}


def calendar_feed(session: Session) -> str:
    dates = session.scalars(
        select(ContractDate)
        .join(Contract)
        .options(selectinload(ContractDate.contract))
        .where(Contract.status == "complete")
        .order_by(ContractDate.event_date, ContractDate.order_index)
    ).all()
    events: list[CalendarEvent] = [
        {
            "uid": str(contract_date.id),
            "contract_id": str(contract_date.contract_id),
            "date": contract_date.event_date,
            "summary": contract_date.event_desc,
            "source": contract_date.contract.source,
            "confidence": contract_date.confidence,
            "provenance": contract_date.provenance,
            "evidence": contract_date.evidence,
            "start_offset": contract_date.start_offset,
            "end_offset": contract_date.end_offset,
        }
        for contract_date in dates
    ]
    return build_calendar(events)


def get_contract(session: Session, contract_id: UUID) -> dict[str, Any] | None:
    contract = session.scalar(
        select(Contract)
        .where(Contract.id == contract_id)
        .options(
            selectinload(Contract.text_record),
            selectinload(Contract.clauses),
            selectinload(Contract.parties).selectinload(ContractPartyMention.party),
            selectinload(Contract.dates),
        )
    )
    if contract is None:
        return None
    return {
        **contract.as_dict(include_text=True),
        "has_conflicts": contract.id in _conflict_contract_ids(session),
    }


def delete_contract(session: Session, contract_id: UUID) -> bool:
    contract = session.get(Contract, contract_id)
    if contract is None:
        return False
    batch = contract.batch
    party_ids = set(
        session.scalars(
            select(ContractPartyMention.party_id).where(
                ContractPartyMention.contract_id == contract_id,
                ContractPartyMention.party_id.is_not(None),
            )
        ).all()
    )
    remaining_contract = session.scalar(
        select(Contract.id)
        .where(Contract.batch_id == batch.id, Contract.id != contract_id)
        .limit(1)
    )
    session.delete(contract if remaining_contract is not None else batch)
    session.flush()
    for party_id in party_ids:
        still_referenced = session.scalar(
            select(ContractPartyMention.id)
            .where(ContractPartyMention.party_id == party_id)
            .limit(1)
        )
        if still_referenced is None and (party := session.get(Party, party_id)):
            session.delete(party)
    session.commit()
    return True


def reset_contract_data(session: Session) -> dict[str, int]:
    """Delete all uploaded and extracted contract data."""

    counts = {
        "upload_batches": session.scalar(select(func.count()).select_from(UploadBatch))
        or 0,
        "contracts": session.scalar(select(func.count()).select_from(Contract)) or 0,
        "parties": session.scalar(select(func.count()).select_from(Party)) or 0,
    }
    session.execute(delete(UploadBatch))
    session.execute(delete(Party))
    session.commit()
    return counts


def upload_contracts(
    session: Session,
    files: list[FileStorage],
    paths: list[str] | None = None,
) -> dict[str, Any]:
    stored_contracts: list[Contract] = []
    rejected: list[dict[str, str]] = []
    relative_paths = paths or []
    seen_relative_paths: set[str] = set()
    accepted: list[tuple[FileStorage, str, str, str]] = []

    for index, upload in enumerate(files):
        source, relative_path = _safe_upload_names(
            upload.filename or f"contract-{index}",
            relative_paths[index] if index < len(relative_paths) else None,
        )
        suffix = Path(source).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            rejected.append({"source": source, "reason": "Unsupported file type"})
            continue
        if relative_path in seen_relative_paths:
            rejected.append({"source": source, "reason": "Duplicate relative path"})
            continue
        seen_relative_paths.add(relative_path)
        accepted.append((upload, source, relative_path, suffix))

    if not accepted:
        return {"contracts": [], "rejected": rejected}

    first_relative_path = accepted[0][2]
    selection_name = (
        first_relative_path.split("/", 1)[0]
        if "/" in first_relative_path
        else "Selected contracts"
    )
    batch = UploadBatch(selection_name=selection_name)
    session.add(batch)
    session.flush()

    with TemporaryDirectory(prefix="eagle-eye-") as directory:
        temporary_directory = Path(directory)
        for upload, source, relative_path, suffix in accepted:
            temporary_path = temporary_directory / f"{uuid4().hex}{suffix}"
            try:
                with temporary_path.open("wb") as destination:
                    shutil.copyfileobj(upload.stream, destination)
                with session.begin_nested():
                    result = process_contract(str(temporary_path), source)
                    contract = create_processed_contract(
                        session,
                        batch,
                        source=source,
                        relative_path=relative_path,
                        file_type=suffix.removeprefix("."),
                        result=result,
                    )
            except Exception as error:
                logger.exception("Contract processing failed: %s", source)
                contract = create_failed_contract(
                    session,
                    batch,
                    source=source,
                    relative_path=relative_path,
                    file_type=suffix.removeprefix("."),
                    error=error,
                )
            session.commit()
            session.refresh(contract)
            stored_contracts.append(contract)

    conflict_analysis_error: str | None = None
    try:
        analyze_contract_conflicts(
            session,
            {
                contract.id
                for contract in stored_contracts
                if contract.status == "complete"
            },
        )
        session.commit()
    except Exception as error:
        session.rollback()
        conflict_analysis_error = f"{type(error).__name__}: {error}"
        logger.exception("Conflict analysis failed after upload")

    conflict_contract_ids = _conflict_contract_ids(session)
    result: dict[str, Any] = {
        "contracts": [
            {
                **contract.as_dict(),
                "has_conflicts": contract.id in conflict_contract_ids,
            }
            for contract in stored_contracts
        ],
        "rejected": rejected,
    }
    if conflict_analysis_error:
        result["conflict_analysis_error"] = conflict_analysis_error
    return result


def _query_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except ValueError:
        abort(400, description=f"{name} must be an integer")
    if not minimum <= value <= maximum:
        abort(400, description=f"{name} must be between {minimum} and {maximum}")
    return value


def create_app(config: dict[str, Any] | None = None) -> Flask:
    """Create a Flask application with injectable persistence dependencies."""

    flask_app = Flask(__name__, static_folder=None)
    flask_app.config.from_mapping(
        SESSION_FACTORY=SessionLocal,
        INITIALIZE_DATABASE=True,
        FRONTEND_DIST=FRONTEND_DIST,
    )
    if config:
        flask_app.config.update(config)
    schema_ready = False

    @flask_app.before_request
    def ensure_schema() -> None:
        nonlocal schema_ready
        if flask_app.config["INITIALIZE_DATABASE"] and not schema_ready:
            initialize_database()
            schema_ready = True

    def session() -> Session:
        return current_app.config["SESSION_FACTORY"]()

    @flask_app.cli.command("reset-database")
    @click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
    def reset_database_command(yes: bool) -> None:
        """Delete every uploaded contract and all extracted data."""

        if not yes and not click.confirm(
            "Delete every Eagle Eye upload, contract, and extracted record?"
        ):
            click.echo("Database reset cancelled.")
            return
        with session() as database_session:
            counts = reset_contract_data(database_session)
        click.echo(
            "Database reset complete: "
            f"deleted {counts['contracts']} contract(s) from "
            f"{counts['upload_batches']} upload batch(es) and "
            f"{counts['parties']} canonical party record(s)."
        )
        click.echo("Reload any open Eagle Eye browser tabs to refresh the UI.")

    @flask_app.errorhandler(400)
    @flask_app.errorhandler(404)
    @flask_app.errorhandler(503)
    def json_error(error: Any) -> tuple[Response, int]:
        return jsonify({"detail": error.description}), error.code

    @flask_app.get("/api/health")
    def health_route() -> Response:
        with session() as database_session:
            return jsonify(health(database_session))

    @flask_app.get("/api/contracts")
    def list_contracts_route() -> Response:
        limit = _query_int(
            "limit", CONTRACT_LIST_DEFAULT_LIMIT, 1, CONTRACT_LIST_MAX_LIMIT
        )
        offset = _query_int("offset", 0, 0, 2**31 - 1)
        with session() as database_session:
            return jsonify(list_contracts(database_session, limit, offset))

    @flask_app.get("/api/contracts/search")
    def search_contracts_route() -> Response:
        query = request.args.get("q", "").strip()
        if not 2 <= len(query) <= 200:
            abort(400, description="q must contain between 2 and 200 characters")
        limit = _query_int("limit", 20, 1, 50)
        with session() as database_session:
            return jsonify(search_contracts(database_session, query, limit))

    @flask_app.get("/api/conflicts")
    def list_conflicts_route() -> Response:
        with session() as database_session:
            return jsonify(list_conflicts(database_session))

    @flask_app.get("/api/calendar.ics")
    def calendar_route() -> Response:
        with session() as database_session:
            content = calendar_feed(database_session)
        disposition = (
            "attachment" if request.args.get("download") == "true" else "inline"
        )
        return Response(
            content,
            mimetype="text/calendar",
            headers={
                "Content-Disposition": (
                    f'{disposition}; filename="eagle-eye-contract-calendar.ics"'
                ),
                "Cache-Control": "no-store",
            },
        )

    @flask_app.get("/api/contracts/<uuid:contract_id>")
    def get_contract_route(contract_id: UUID) -> Response:
        with session() as database_session:
            contract = get_contract(database_session, contract_id)
        if contract is None:
            abort(404, description="Contract not found")
        return jsonify(contract)

    @flask_app.delete("/api/contracts/<uuid:contract_id>")
    def delete_contract_route(contract_id: UUID) -> tuple[str, int]:
        with session() as database_session:
            deleted = delete_contract(database_session, contract_id)
        if not deleted:
            abort(404, description="Contract not found")
        return "", 204

    @flask_app.post("/api/contracts/upload")
    def upload_contracts_route() -> Response:
        files = request.files.getlist("files")
        if not files:
            abort(400, description="At least one contract file is required")
        with session() as database_session:
            result = upload_contracts(
                database_session,
                files,
                request.form.getlist("paths"),
            )
        return jsonify(result)

    def frontend_file(filename: str) -> Response:
        directory = Path(current_app.config["FRONTEND_DIST"])
        if not (directory / filename).is_file():
            abort(503, description="Frontend build not found. Run npm run build.")
        return send_from_directory(directory, filename)

    @flask_app.get("/assets/<path:filename>")
    def frontend_asset(filename: str) -> Response:
        return frontend_file(f"assets/{filename}")

    @flask_app.get("/")
    @flask_app.get("/contracts/<uuid:contract_id>/text")
    def frontend(contract_id: UUID | None = None) -> Response:
        return frontend_file("index.html")

    return flask_app


app = create_app()
