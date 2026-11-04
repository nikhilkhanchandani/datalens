"""Pydantic response models for correlation analysis."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CorrelationMethod = Literal["pearson", "spearman"]


class ExcludedColumn(BaseModel):
    name: str
    reason: str


class StrongPair(BaseModel):
    x: str
    y: str
    r: float
    direction: Literal["positive", "negative"]


class CorrelationReport(BaseModel):
    method: CorrelationMethod
    columns: list[str]
    # Square matrix aligned with `columns`. `None` where a coefficient is
    # undefined (e.g. the two columns never have two rows in common).
    matrix: list[list[float | None]]
    excluded_columns: list[ExcludedColumn]
    strong_pairs: list[StrongPair]
    strong_threshold: float
    disclaimer: str
