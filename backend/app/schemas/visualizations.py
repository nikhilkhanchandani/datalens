"""Pydantic response models for chart-ready visualization data.

Each model carries only what its chart needs, plus the metadata a user needs
to interpret it (observation counts, whether data was sampled or aggregated).
The frontend renders these shapes and never recomputes them.
"""

from __future__ import annotations

from pydantic import BaseModel


class HistogramBin(BaseModel):
    start: float
    end: float
    count: int


class HistogramData(BaseModel):
    column: str
    bins: list[HistogramBin]
    bin_strategy: str
    total_observations: int
    missing_count: int
    infinite_count: int
    is_constant: bool


class FrequencyItem(BaseModel):
    value: str
    count: int
    percentage: float
    is_other: bool


class CategoricalFrequencies(BaseModel):
    column: str
    total_count: int
    missing_count: int
    unique_count: int
    top_n: int
    truncated: bool
    items: list[FrequencyItem]


class ScatterPoint(BaseModel):
    x: float
    y: float


class ScatterData(BaseModel):
    x_column: str
    y_column: str
    total_points: int
    returned_points: int
    sampled: bool
    max_points: int
    pearson_r: float | None
    points: list[ScatterPoint]


class DistributionSummary(BaseModel):
    column: str
    count: int
    missing_count: int
    minimum: float
    q1: float
    median: float
    q3: float
    maximum: float
    iqr: float


class TrendPoint(BaseModel):
    period_start: str
    mean: float
    minimum: float
    maximum: float
    count: int


class DatetimeTrend(BaseModel):
    datetime_column: str
    value_column: str
    granularity: str
    total_observations: int
    points: list[TrendPoint]
