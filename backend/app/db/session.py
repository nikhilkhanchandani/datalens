"""Database engine/session management.

The engine is built lazily from *current* settings rather than once at
import time. This is what lets tests point the whole app at a fresh
temporary SQLite file per test (via env vars + `get_settings.cache_clear()`)
without needing to re-import the application.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def _get_engine(database_url: str) -> Engine:
    # SQLite only allows a connection to be used from the thread that
    # created it by default; FastAPI may hand requests to different threads,
    # so this must be disabled for our use of a shared engine.
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    return create_engine(database_url, connect_args=connect_args)


def _get_session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    engine = _get_engine(settings.database_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    session = _get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables for the current settings' database.

    Safe to call repeatedly. `create_all` never alters existing tables, so the
    one column added after Phase 2 is added explicitly if an older database
    file lacks it. This project uses no migration tool; a production service
    would use Alembic.
    """
    import app.models.dataset  # noqa: F401  (registers the model on Base)
    import app.models.transformation  # noqa: F401  (registers the model on Base)
    from app.models.database import Base

    settings = get_settings()
    engine = _get_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(datasets)")}
        if "working_version" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE datasets ADD COLUMN working_version INTEGER NOT NULL DEFAULT 0"
            )
