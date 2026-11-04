"""Tests for GET /api/datasets/{id}/comparison.

The expected numbers are worked out by hand from the small CSV below, not read
back from the code under test. Dataset-state metrics are also checked against
the quality engine, so the comparison can't drift from the rest of the app.
"""

from __future__ import annotations

import hashlib
import io

import pandas as pd

from app.core.config import get_settings
from app.services import quality

# Original: 5 rows, 4 columns, 2 missing salaries, 1 duplicate row (Cara twice).
SMALL_CSV = (
    "id,name,salary,city\n"
    "1,Alice,100,NYC\n"
    "2,Bob,,LA\n"
    "3,Cara,300,SF\n"
    "3,Cara,300,SF\n"
    "4,Dan,,SF\n"
)


def _upload(client, content: str = SMALL_CSV, filename: str = "small.csv") -> dict:
    response = client.post(
        "/api/datasets/upload",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _clean(client, dataset_id: str, body: dict):
    response = client.post(f"/api/datasets/{dataset_id}/clean", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _comparison(client, dataset_id: str) -> dict:
    response = client.get(f"/api/datasets/{dataset_id}/comparison")
    assert response.status_code == 200, response.text
    return response.json()


def _original_path(dataset_id: str):
    return get_settings().upload_dir / f"{dataset_id}.csv"


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_untouched_dataset_compares_equal(client) -> None:
    dataset = _upload(client)

    body = _comparison(client, dataset["id"])

    assert body["working_version"] == 0
    assert body["original"] == body["current"]
    assert body["changes"] == {
        "row_count": 0,
        "column_count": 0,
        "missing_values": 0,
        "duplicate_rows": 0,
        "quality_score": 0,
    }
    assert body["operations"] == {
        "transformation_count": 0,
        "rows_removed": 0,
        "duplicate_rows_removed": 0,
        "values_filled": 0,
        "text_rows_changed": 0,
        "columns_dropped": [],
        "columns_renamed": [],
    }


def test_original_metrics_match_hand_counts(client) -> None:
    dataset = _upload(client)

    original = _comparison(client, dataset["id"])["original"]

    assert original["row_count"] == 5
    assert original["column_count"] == 4
    assert original["missing_values"] == 2
    assert original["duplicate_rows"] == 1


def test_quality_scores_come_from_the_quality_engine(client) -> None:
    dataset = _upload(client)
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})

    body = _comparison(client, dataset["id"])

    original_frame = pd.read_csv(io.StringIO(SMALL_CSV))
    assert body["original"]["quality_score"] == quality.analyze_quality(original_frame).score
    current_path = get_settings().upload_dir / f"{dataset['id']}.v1.csv"
    current_frame = pd.read_csv(current_path)
    assert body["current"]["quality_score"] == quality.analyze_quality(current_frame).score
    # Duplicates and missing values were both penalised before, and only missing
    # values remain now, so the score should go up.
    assert body["changes"]["quality_score"] > 0


def test_multiple_transformations_give_hand_computed_deltas(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]

    _clean(client, dataset_id, {"operation": "remove_duplicates"})
    # Remaining salaries are 100, missing, 300, missing; the median is 200.
    _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "salary", "strategy": "median"},
    )
    _clean(client, dataset_id, {"operation": "drop_columns", "columns": ["city"]})
    _clean(
        client,
        dataset_id,
        {"operation": "rename_column", "column": "name", "new_name": "full_name"},
    )

    body = _comparison(client, dataset_id)

    assert body["working_version"] == 4
    assert body["current"]["row_count"] == 4
    assert body["current"]["column_count"] == 3
    assert body["current"]["missing_values"] == 0
    assert body["current"]["duplicate_rows"] == 0

    assert body["changes"]["row_count"] == -1
    assert body["changes"]["column_count"] == -1
    assert body["changes"]["missing_values"] == -2
    assert body["changes"]["duplicate_rows"] == -1

    operations = body["operations"]
    assert operations["transformation_count"] == 4
    assert operations["rows_removed"] == 1
    assert operations["duplicate_rows_removed"] == 1
    assert operations["values_filled"] == 2
    assert operations["text_rows_changed"] == 0
    assert operations["columns_dropped"] == ["city"]
    assert operations["columns_renamed"] == [{"from_name": "name", "to_name": "full_name"}]


def test_text_cleanup_counts_changed_rows(client) -> None:
    dataset = _upload(client, content="id,city\n1,  LA \n2,   \n3,SF\n")

    _clean(
        client,
        dataset["id"],
        {"operation": "normalize_text", "columns": ["city"]},
    )

    body = _comparison(client, dataset["id"])
    # "  LA " is trimmed and "   " becomes missing: two rows changed. "SF" is untouched.
    assert body["operations"]["text_rows_changed"] == 2
    assert body["operations"]["rows_removed"] == 0
    assert body["changes"]["missing_values"] == 1


def test_comparison_leaves_the_original_file_unchanged(client) -> None:
    dataset = _upload(client)
    original = _original_path(dataset["id"])
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})
    digest = _sha256(original)

    _comparison(client, dataset["id"])

    assert _sha256(original) == digest


def test_missing_original_file_is_reported(client) -> None:
    dataset = _upload(client)
    _original_path(dataset["id"]).unlink()

    response = client.get(f"/api/datasets/{dataset['id']}/comparison")

    assert response.status_code == 500
    assert response.json()["error"] == "DatasetFileMissingError"


def test_unknown_dataset_returns_404(client) -> None:
    response = client.get("/api/datasets/does-not-exist/comparison")

    assert response.status_code == 404
    assert response.json()["error"] == "DatasetNotFoundError"
