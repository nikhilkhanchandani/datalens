"""API and data-integrity tests for the cleaning workflow.

These exercise the full path (upload -> clean -> re-analyse) and check the
safety guarantees: the original upload is never modified, failed steps leave
the working copy untouched, and analysis always reflects the current version.
"""

from __future__ import annotations

import hashlib
import io

import pandas as pd
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.exceptions import TransformationWriteError

MESSY_CSV = (
    "id,name,salary,city,active\n"
    "1,Alice,100,NYC,True\n"
    "2,Bob,,  LA ,False\n"
    "3,Cara,300,   ,True\n"
    "3,Cara,300,   ,True\n"
    "4,Dan,,SF,\n"
    "5,Eve,500,NYC,True\n"
)


def _upload(client, content: str = MESSY_CSV, filename: str = "messy.csv") -> dict:
    response = client.post(
        "/api/datasets/upload",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _clean(client, dataset_id: str, body: dict):
    return client.post(f"/api/datasets/{dataset_id}/clean", json=body)


def _original_path(dataset_id: str):
    return get_settings().upload_dir / f"{dataset_id}.csv"


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- original vs working copy ---------------------------------------------


def test_original_upload_is_never_modified_by_cleaning(client) -> None:
    dataset = _upload(client)
    original = _original_path(dataset["id"])
    digest_before = _sha256(original)

    assert _clean(client, dataset["id"], {"operation": "remove_duplicates"}).status_code == 200
    assert _clean(
        client,
        dataset["id"],
        {"operation": "fill_missing", "column": "salary", "strategy": "median"},
    ).status_code == 200

    assert _sha256(original) == digest_before


def test_working_copy_reflects_transformations(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]
    assert dataset["working_version"] == 0
    assert dataset["row_count"] == 6

    response = _clean(client, dataset_id, {"operation": "remove_duplicates"})

    assert response.status_code == 200
    body = response.json()
    assert body["working_version"] == 1
    assert body["rows_before"] == 6
    assert body["rows_after"] == 5
    refreshed = client.get(f"/api/datasets/{dataset_id}").json()
    assert refreshed["working_version"] == 1
    assert refreshed["row_count"] == 5


def test_failed_transformation_leaves_working_copy_unchanged(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]
    assert _clean(client, dataset_id, {"operation": "remove_duplicates"}).status_code == 200
    profile_before = client.get(f"/api/datasets/{dataset_id}/profile").json()

    response = _clean(
        client,
        dataset_id,
        {"operation": "convert_type", "column": "name", "target": "numeric"},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "InvalidConversionError"
    assert client.get(f"/api/datasets/{dataset_id}").json()["working_version"] == 1
    assert client.get(f"/api/datasets/{dataset_id}/profile").json() == profile_before


def test_write_failure_leaves_dataset_unchanged_and_no_partial_file(client, monkeypatch) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]
    upload_dir = get_settings().upload_dir

    def failing_to_csv(self, *args, **kwargs):
        # Simulate the disk filling up after the first bytes are written.
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_csv", failing_to_csv)
    response = _clean(client, dataset_id, {"operation": "remove_duplicates"})
    monkeypatch.undo()

    assert response.status_code == 500
    assert response.json()["error"] == "TransformationWriteError"
    assert client.get(f"/api/datasets/{dataset_id}").json()["working_version"] == 0
    leftovers = [p.name for p in upload_dir.iterdir() if ".tmp" in p.name or ".v1." in p.name]
    assert leftovers == []


def test_database_failure_removes_new_version_and_keeps_pointer(client, monkeypatch) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]
    upload_dir = get_settings().upload_dir

    from app.db.session import _get_session_factory
    from app.models.dataset import Dataset
    from app.schemas.cleaning import RemoveDuplicatesRequest
    from app.services import transformations

    def failing_record(*args, **kwargs):
        raise SQLAlchemyError("database locked")

    monkeypatch.setattr(transformations, "Transformation", failing_record)
    session = _get_session_factory()()
    try:
        dataset_row = session.get(Dataset, dataset_id)
        with pytest.raises(TransformationWriteError):
            transformations.apply_cleaning(
                dataset_row, RemoveDuplicatesRequest(operation="remove_duplicates"), session
            )
    finally:
        session.close()

    assert client.get(f"/api/datasets/{dataset_id}").json()["working_version"] == 0
    assert not (upload_dir / f"{dataset_id}.v1.csv").exists()


def test_deleting_dataset_removes_working_copies(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]
    assert _clean(client, dataset_id, {"operation": "remove_duplicates"}).status_code == 200
    working = get_settings().upload_dir / f"{dataset_id}.v1.csv"
    assert working.exists()

    assert client.delete(f"/api/datasets/{dataset_id}").status_code == 204

    assert not working.exists()


# --- analysis follows the working copy ------------------------------------


def test_profile_reflects_transformed_dataset(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]

    assert _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "salary", "strategy": "median"},
    ).status_code == 200

    profile = client.get(f"/api/datasets/{dataset_id}/profile").json()
    salary = next(c for c in profile["columns"] if c["name"] == "salary")
    assert salary["missing_count"] == 0
    assert profile["encoding"] == "UTF-8 (cleaned working copy)"


def test_quality_reflects_transformed_dataset(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]
    before = client.get(f"/api/datasets/{dataset_id}/quality").json()
    assert any(i["type"] == "duplicate_rows" for i in before["issues"])

    assert _clean(client, dataset_id, {"operation": "remove_duplicates"}).status_code == 200

    after = client.get(f"/api/datasets/{dataset_id}/quality").json()
    assert not any(i["type"] == "duplicate_rows" for i in after["issues"])


def test_statistics_reflects_transformed_dataset(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]

    assert _clean(client, dataset_id, {"operation": "remove_duplicates"}).status_code == 200

    stats = client.get(f"/api/datasets/{dataset_id}/statistics").json()
    assert stats["row_count"] == 5


def test_explore_endpoints_reflect_transformed_dataset(client) -> None:
    dataset = _upload(client)
    dataset_id = dataset["id"]

    assert _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "salary", "strategy": "mean"},
    ).status_code == 200

    histogram = client.get(
        f"/api/datasets/{dataset_id}/visualizations/histogram?column=salary"
    ).json()
    assert histogram["missing_count"] == 0
    assert histogram["total_observations"] == 6

    categorical = client.get(
        f"/api/datasets/{dataset_id}/visualizations/categorical?column=city"
    )
    assert categorical.status_code == 200
    assert categorical.json()["total_count"] == 6

    correlations = client.get(f"/api/datasets/{dataset_id}/correlations")
    assert correlations.status_code == 200


# --- cleaning operations through the API ----------------------------------


def test_fill_missing_median_returns_structured_result(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "salary", "strategy": "median"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "fill_missing"
    assert body["column"] == "salary"
    assert body["strategy"] == "median"
    assert body["affected_rows"] == 2
    assert body["rows_before"] == body["rows_after"] == 6
    assert body["working_version"] == 1
    assert body["summary"]


def test_noop_request_returns_409_and_writes_nothing(client) -> None:
    dataset_id = _upload(client, "a,b\n1,x\n2,y\n")["id"]

    response = _clean(client, dataset_id, {"operation": "remove_duplicates"})

    assert response.status_code == 409
    assert response.json()["error"] == "NoOpTransformationError"
    assert client.get(f"/api/datasets/{dataset_id}").json()["working_version"] == 0


def test_incompatible_strategy_is_rejected(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "name", "strategy": "mean"},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "IncompatibleColumnTypeError"


def test_custom_numeric_fill_with_text_is_rejected(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "salary", "strategy": "custom", "value": "zero"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "InvalidParameterError"


def test_rename_collision_returns_400(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(
        client,
        dataset_id,
        {"operation": "rename_column", "column": "name", "new_name": "city"},
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["message"]


def test_drop_column_via_api(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(client, dataset_id, {"operation": "drop_columns", "columns": ["active"]})

    assert response.status_code == 200
    profile = client.get(f"/api/datasets/{dataset_id}/profile").json()
    assert "active" not in [c["name"] for c in profile["columns"]]


def test_trim_and_blank_normalization_via_api(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(
        client,
        dataset_id,
        {"operation": "normalize_text", "columns": ["city"]},
    )

    assert response.status_code == 200
    assert response.json()["affected_rows"] == 3


def test_type_conversion_via_api(client) -> None:
    dataset_id = _upload(client, "amount,label\n10,a\n20,b\n30,c\n")["id"]

    response = _clean(
        client,
        dataset_id,
        {"operation": "convert_type", "column": "label", "target": "numeric"},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "InvalidConversionError"


# --- request validation and errors ----------------------------------------


def test_unknown_dataset_returns_404(client) -> None:
    response = _clean(client, "missing", {"operation": "remove_duplicates"})

    assert response.status_code == 404
    assert response.json()["error"] == "DatasetNotFoundError"


def test_unknown_operation_is_a_useful_validation_error(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(client, dataset_id, {"operation": "delete_everything"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "InvalidRequestError"
    assert "operation" in body["message"]


def test_unknown_field_is_rejected(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(
        client,
        dataset_id,
        {"operation": "remove_duplicates", "keep": "last"},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "InvalidRequestError"


def test_missing_required_field_is_rejected(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(client, dataset_id, {"operation": "fill_missing", "column": "salary"})

    assert response.status_code == 422
    assert "strategy" in response.json()["message"]


def test_invalid_strategy_value_is_rejected(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(
        client,
        dataset_id,
        {"operation": "fill_missing", "column": "salary", "strategy": "guess"},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "InvalidRequestError"


def test_empty_column_list_is_rejected(client) -> None:
    dataset_id = _upload(client)["id"]

    response = _clean(client, dataset_id, {"operation": "drop_columns", "columns": []})

    assert response.status_code == 422
