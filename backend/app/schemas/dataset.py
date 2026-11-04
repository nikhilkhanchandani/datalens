"""Pydantic response models for dataset metadata (not analysis results)."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator


class DatasetResponse(BaseModel):
    """Public shape of a `Dataset` ORM row. Never exposes `stored_filename`
    — the on-disk name is an internal implementation detail."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    upload_timestamp: datetime
    # row_count and column_count describe the current working dataset, which
    # changes when cleaning is applied. file_size_bytes is the original upload.
    row_count: int
    column_count: int
    file_size_bytes: int
    encoding: str
    # 0 = analysis runs on the original upload; N = working copy version N.
    working_version: int

    @field_validator("upload_timestamp")
    @classmethod
    def _label_as_utc(cls, value: datetime) -> datetime:
        # SQLite returns naive datetimes. They were written in UTC, so label
        # them; otherwise browsers parse the ISO string as local time.
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
