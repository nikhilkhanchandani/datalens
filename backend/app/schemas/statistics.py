"""Pydantic response models for the descriptive statistics engine."""

from __future__ import annotations

from pydantic import BaseModel

from app.core.column_kind import ColumnKind


class NumericStatistics(BaseModel):
    count: int
    missing_count: int
    mean: float | None
    median: float | None
    std: float | None
    variance: float | None
    minimum: float | None
    maximum: float | None
    range: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    iqr: float | None


class CategoricalTopValue(BaseModel):
    value: str
    count: int


class CategoricalStatistics(BaseModel):
    count: int
    missing_count: int
    unique_count: int
    most_frequent_value: str | None
    most_frequent_count: int
    top_values: list[CategoricalTopValue]


class BooleanStatistics(BaseModel):
    count: int
    missing_count: int
    true_count: int
    false_count: int
    true_percentage: float | None


class DatetimeStatistics(BaseModel):
    valid_count: int
    missing_count: int
    earliest: str | None
    latest: str | None
    range_days: float | None


class ColumnStatistics(BaseModel):
    name: str
    kind: ColumnKind
    numeric: NumericStatistics | None = None
    categorical: CategoricalStatistics | None = None
    boolean: BooleanStatistics | None = None
    datetime: DatetimeStatistics | None = None


class DatasetStatistics(BaseModel):
    row_count: int
    columns: list[ColumnStatistics]
