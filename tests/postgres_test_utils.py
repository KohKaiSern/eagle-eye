"""Isolated PostgreSQL schemas for persistence tests."""

from uuid import uuid4

from sqlalchemy import Engine, create_engine, text

from backend.config import DATABASE_URL
from backend.persistence.database import Base


def create_test_engine() -> tuple[Engine, str]:
    schema = f"eagle_eye_test_{uuid4().hex}"
    admin_engine = create_engine(DATABASE_URL)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    admin_engine.dispose()

    engine = create_engine(
        DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    Base.metadata.create_all(engine)
    return engine, schema


def drop_test_schema(engine: Engine, schema: str) -> None:
    engine.dispose()
    admin_engine = create_engine(DATABASE_URL)
    with admin_engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin_engine.dispose()
