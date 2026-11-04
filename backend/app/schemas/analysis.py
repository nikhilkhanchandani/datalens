"""Pydantic response models for dataset profiling.

These models are the exact JSON contract the frontend reads. The frontend
must never recompute statistics itself — it only ever displays fields
already present on these shapes, all of which are produced by
`services/profiler.py` from the real uploaded data.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.column_kind import ColumnKind

__all__ = [
    "ColumnKind",
    "NumericColumnStats",
    "TopValue",
    "CategoricalColumnStats",
    "ColumnProfile",
    "DatasetProfile",
]


class NumericColumnStats(BaseModel):
    count: int
    mean: float | None
    median: float | None
    std: float | None
    variance: float | None
    minimum: float | None
    maximum: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    range: float | None


class TopValue(BaseModel):
    value: str
    count: int


class CategoricalColumnStats(BaseModel):
    unique_count: int
    most_frequent_value: str | None
    most_frequent_count: int
    top_values: list[TopValue]


class ColumnProfile(BaseModel):
    name: str
    kind: ColumnKind
    pandas_dtype: str
    missing_count: int
    missing_percentage: float
    unique_count: int
    sample_values: list[Any]
    numeric_stats: NumericColumnStats | None = None
    categorical_stats: CategoricalColumnStats | None = None


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    duplicate_row_count: int
    memory_usage_bytes: int
    columns: list[ColumnProfile]
    # Populated by the API route from the Dataset row, not by the
    # profiler itself — file encoding isn't a property of the DataFrame.
    encoding: str = "unknown"
