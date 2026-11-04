"""Unexpected server errors use the same JSON shape as expected ones.

The internal exception text must not reach the client. It belongs in the
server log.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient


def test_unexpected_error_returns_json_without_internal_details(monkeypatch) -> None:
    from app.main import app
    from app.services import comparison

    def broken(*_args, **_kwargs):
        raise RuntimeError("secret internal detail /var/lib/db")

    monkeypatch.setattr(comparison, "build_comparison", broken)
    client = TestClient(app, raise_server_exceptions=False)
    upload = client.post(
        "/api/datasets/upload",
        files={"file": ("a.csv", io.BytesIO(b"x,y\n1,2\n"), "text/csv")},
    ).json()

    response = client.get(f"/api/datasets/{upload['id']}/comparison")

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "InternalServerError"
    assert "secret internal detail" not in response.text


def test_expected_errors_keep_their_specific_names() -> None:
    from app.main import app

    response = TestClient(app).get("/api/datasets/does-not-exist/export")

    assert response.status_code == 404
    assert response.json()["error"] == "DatasetNotFoundError"
