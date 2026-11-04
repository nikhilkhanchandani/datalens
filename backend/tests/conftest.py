"""Shared pytest fixtures.

Every test gets its own temporary upload directory and SQLite database
(via env var overrides + clearing `get_settings`'s cache), so tests never
touch the real `backend/data/` directory and can't leak state into each
other.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DATALENS_UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv(
        "DATALENS_DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    )

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.db.session import init_db

    init_db()

    yield

    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)
