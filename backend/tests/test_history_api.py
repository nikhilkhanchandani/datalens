"""Tests for GET /api/datasets/{id}/transformations.

The history is read back from the `transformations` table, so these tests
apply real cleaning steps and then check that the history matches them exactly.
"""

from __future__ import annotations

import io
from datetime import datetime

from app.db.session import _get_session_factory
from app.models.transformation import Transformation

CSV = (
    "id,name,salary,city\n"
    "1,Alice,100,NYC\n"
    "2,Bob,,LA\n"
    "3,Cara,300,SF\n"
    "3,Cara,300,SF\n"
    "4,Dan,,SF\n"
)


def _upload(client, content: str = CSV) -> dict:
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("small.csv", io.BytesIO(content.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _clean(client, dataset_id: str, body: dict) -> None:
    response = client.post(f"/api/datasets/{dataset_id}/clean", json=body)
    assert response.status_code == 200, response.text


def _history(client, dataset_id: str) -> list[dict]:
    response = client.get(f"/api/datasets/{dataset_id}/transformations")
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_history_for_untouched_dataset(client) -> None:
    dataset = _upload(client)

    assert _history(client, dataset["id"]) == []


def test_single_transformation_fields(client) -> None:
    dataset = _upload(client)
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})

    [entry] = _history(client, dataset["id"])

    assert entry["operation"] == "remove_duplicates"
    assert entry["column"] is None
    assert entry["parameters"] == {"subset": None}
    assert entry["affected_rows"] == 1
    assert entry["rows_before"] == 5
    assert entry["rows_after"] == 4
    assert entry["resulting_version"] == 1
    assert entry["description"] == "Removed 1 duplicate row(s)"
    # Internal fields stay out of the response.
    assert "dataset_id" not in entry
    assert "version" not in entry


def test_multiple_transformations_are_chronological(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]
    _clean(client, dataset_id, {"operation": "remove_duplicates"})
    _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "salary", "strategy": "median"},
    )
    _clean(client, dataset_id, {"operation": "drop_columns", "columns": ["city"]})

    entries = _history(client, dataset_id)

    assert [entry["operation"] for entry in entries] == [
        "remove_duplicates",
        "fill_missing",
        "drop_columns",
    ]
    assert [entry["resulting_version"] for entry in entries] == [1, 2, 3]
    assert [entry["resulting_version"] for entry in entries] == sorted(
        entry["resulting_version"] for entry in entries
    )


def test_parameters_are_structured_not_raw_json_text(client) -> None:
    dataset = _upload(client)
    _clean(
        client,
        dataset["id"],
        {"operation": "fill_missing", "column": "salary", "strategy": "custom", "value": 0},
    )

    [entry] = _history(client, dataset["id"])

    assert entry["column"] == "salary"
    assert entry["parameters"] == {"column": "salary", "strategy": "custom", "value": 0.0}
    assert entry["description"] == 'Filled 2 missing value(s) in "salary" using custom (0.0)'


def test_descriptions_read_as_plain_sentences(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]
    _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "salary", "strategy": "median"},
    )
    _clean(
        client,
        dataset_id,
        {"operation": "rename_column", "column": "name", "new_name": "full_name"},
    )
    _clean(client, dataset_id, {"operation": "drop_columns", "columns": ["city"]})

    descriptions = [entry["description"] for entry in _history(client, dataset_id)]

    assert descriptions == [
        'Filled 2 missing value(s) in "salary" using median',
        'Renamed "name" to "full_name"',
        'Dropped column "city"',
    ]


def test_timestamps_are_utc_and_non_decreasing(client) -> None:
    dataset = _upload(client)
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})
    _clean(client, dataset["id"], {"operation": "drop_columns", "columns": ["city"]})

    timestamps = [
        datetime.fromisoformat(entry["timestamp"]) for entry in _history(client, dataset["id"])
    ]

    assert all(stamp.utcoffset() is not None for stamp in timestamps)
    assert all(stamp.utcoffset().total_seconds() == 0 for stamp in timestamps)
    assert timestamps == sorted(timestamps)


def test_history_only_lists_its_own_dataset(client) -> None:
    first = _upload(client)
    second = _upload(client)
    _clean(client, first["id"], {"operation": "remove_duplicates"})

    assert len(_history(client, first["id"])) == 1
    assert _history(client, second["id"]) == []


def test_unreadable_stored_parameters_are_reported(client) -> None:
    dataset = _upload(client)
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})
    with _get_session_factory()() as db:
        row = db.query(Transformation).filter(Transformation.dataset_id == dataset["id"]).one()
        row.parameters = "{not valid json"
        db.commit()

    response = client.get(f"/api/datasets/{dataset['id']}/transformations")

    assert response.status_code == 500
    assert response.json()["error"] == "CorruptHistoryError"


def test_unknown_dataset_returns_404(client) -> None:
    response = client.get("/api/datasets/does-not-exist/transformations")

    assert response.status_code == 404
    assert response.json()["error"] == "DatasetNotFoundError"
