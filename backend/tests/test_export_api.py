"""Tests for GET /api/datasets/{id}/export and the export filename rules.

Export is read-only: it streams the working file as it is, creates no files,
and never touches the original upload.
"""

from __future__ import annotations

import hashlib
import io

import pandas as pd
import pytest

from app.core.config import get_settings
from app.services.exporter import export_filename

CSV = (
    "id,name,salary,city\n"
    "1,Alice,100,NYC\n"
    "2,Bob,,LA\n"
    "3,Cara,300,SF\n"
    "3,Cara,300,SF\n"
    "4,Dan,,SF\n"
)


def _upload(client, filename: str = "messy.csv", content: str = CSV) -> dict:
    response = client.post(
        "/api/datasets/upload",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _clean(client, dataset_id: str, body: dict) -> None:
    response = client.post(f"/api/datasets/{dataset_id}/clean", json=body)
    assert response.status_code == 200, response.text


def _export(client, dataset_id: str):
    return client.get(f"/api/datasets/{dataset_id}/export")


def _upload_dir_files() -> set[str]:
    return {path.name for path in get_settings().upload_dir.iterdir()}


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_untouched_dataset_exports_the_original(client) -> None:
    dataset = _upload(client)
    original = get_settings().upload_dir / f"{dataset['id']}.csv"

    response = _export(client, dataset["id"])

    assert response.status_code == 200
    assert response.content == original.read_bytes()
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="messy_original.csv"'


def test_transformed_dataset_exports_the_current_version(client) -> None:
    dataset = _upload(client)
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})
    _clean(
        client,
        dataset["id"],
        {"operation": "fill_missing", "column": "salary", "strategy": "median"},
    )
    working = get_settings().upload_dir / f"{dataset['id']}.v2.csv"

    response = _export(client, dataset["id"])

    assert response.status_code == 200
    assert response.content == working.read_bytes()
    assert response.headers["content-disposition"] == 'attachment; filename="messy_cleaned.csv"'
    exported = pd.read_csv(io.BytesIO(response.content))
    assert len(exported) == 4
    assert exported["salary"].isna().sum() == 0


def test_export_creates_no_files_and_changes_nothing(client) -> None:
    dataset = _upload(client)
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})
    files_before = _upload_dir_files()
    original = get_settings().upload_dir / f"{dataset['id']}.csv"
    digest = _sha256(original)

    _export(client, dataset["id"])
    _export(client, dataset["id"])

    assert _upload_dir_files() == files_before
    assert _sha256(original) == digest


def test_export_does_not_alter_the_working_copy_or_history(client) -> None:
    dataset = _upload(client)
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})

    _export(client, dataset["id"])

    refreshed = client.get(f"/api/datasets/{dataset['id']}").json()
    assert refreshed["working_version"] == 1
    assert refreshed["row_count"] == 4
    history = client.get(f"/api/datasets/{dataset['id']}/transformations").json()
    assert len(history) == 1


def test_missing_working_file_is_reported(client) -> None:
    dataset = _upload(client)
    _clean(client, dataset["id"], {"operation": "remove_duplicates"})
    (get_settings().upload_dir / f"{dataset['id']}.v1.csv").unlink()

    response = _export(client, dataset["id"])

    assert response.status_code == 500
    assert response.json()["error"] == "DatasetFileMissingError"


def test_unknown_dataset_returns_404(client) -> None:
    response = _export(client, "does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"] == "DatasetNotFoundError"


@pytest.mark.parametrize(
    ("original_filename", "working_version", "expected"),
    [
        ("sales data (final)!.csv", 1, "sales_data_final_cleaned.csv"),
        ("../../etc/passwd.csv", 0, "passwd_original.csv"),
        ("C:\\Users\\me\\report.csv", 2, "report_cleaned.csv"),
        ("!!!.csv", 0, "dataset_original.csv"),
        ("weird\"name;rm.csv", 1, "weird_name_rm_cleaned.csv"),
    ],
)
def test_export_filenames_are_safe(original_filename, working_version, expected) -> None:
    assert export_filename(original_filename, working_version) == expected


def test_export_filename_stem_is_length_limited() -> None:
    name = export_filename("a" * 300 + ".csv", 1)

    assert name == "a" * 100 + "_cleaned.csv"
