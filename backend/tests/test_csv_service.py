"""Unit tests for upload validation, safe storage, and CSV parsing."""

from __future__ import annotations

import io

import pytest
from fastapi import UploadFile

from app.core.exceptions import (
    CSVParsingError,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
)
from app.services import csv_service


def _upload_file(content: bytes, filename: str = "data.csv") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


def test_validate_filename_rejects_non_csv_extension() -> None:
    with pytest.raises(InvalidFileTypeError):
        csv_service.validate_filename("data.txt")


def test_validate_filename_rejects_missing_filename() -> None:
    with pytest.raises(InvalidFileTypeError):
        csv_service.validate_filename(None)


def test_validate_filename_accepts_csv_extension() -> None:
    csv_service.validate_filename("data.csv")


async def test_save_upload_rejects_empty_file() -> None:
    upload = _upload_file(b"")

    with pytest.raises(EmptyFileError):
        await csv_service.save_upload(upload)


async def test_save_upload_enforces_size_limit(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("DATALENS_MAX_UPLOAD_SIZE_MB", "0")
    get_settings.cache_clear()

    upload = _upload_file(b"a,b\n1,2\n")

    with pytest.raises(FileTooLargeError):
        await csv_service.save_upload(upload)


async def test_save_upload_stores_file_under_generated_id() -> None:
    content = b"a,b\n1,2\n"
    upload = _upload_file(content)

    saved = await csv_service.save_upload(upload)

    assert saved.path.exists()
    assert saved.path.name == f"{saved.dataset_id}.csv"
    assert saved.size_bytes == len(content)


def test_read_dataframe_raises_on_malformed_csv(tmp_path) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("a,b,c\n1,2\n3,4,5,6\n")

    with pytest.raises(CSVParsingError):
        csv_service.read_dataframe(bad_csv)


def test_malformed_csv_error_explains_row_and_field_counts(tmp_path) -> None:
    # Row 3 ("3,4,5,6") has one extra value beyond the 3-column header,
    # e.g. from an unescaped comma inside a field.
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("a,b,c\n1,2\n3,4,5,6\n")

    with pytest.raises(CSVParsingError) as exc_info:
        csv_service.read_dataframe(bad_csv)

    message = str(exc_info.value)
    assert "Row 3" in message
    assert "3 columns" in message
    assert "4 values" in message
    assert "comma, quote, or line break" in message
    # The raw Pandas "C error: ..." text should not leak through verbatim.
    assert "C error" not in message


def test_read_dataframe_raises_on_header_only_empty_file(tmp_path) -> None:
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("")

    with pytest.raises(CSVParsingError):
        csv_service.read_dataframe(empty_csv)


def test_read_dataframe_parses_valid_csv(tmp_path) -> None:
    good_csv = tmp_path / "good.csv"
    good_csv.write_text("a,b\n1,2\n3,4\n")

    df = csv_service.read_dataframe(good_csv)

    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2
