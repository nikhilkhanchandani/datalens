"""Pydantic response models for data-quality analysis.

Mirrors the shape documented in `PROJECT_SPEC.md`: a 0-100 score with a
breakdown that mathematically explains it, plus a flat list of individual
issues a user can act on.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

IssueSeverity = Literal["low", "medium", "high"]

IssueType = Literal[
    "missing_values",
    "blank_strings",
    "duplicate_rows",
    "constant_column",
    "mostly_empty_column",
    "infinite_values",
    "mixed_types",
    "high_cardinality_column",
    "possible_identifier_column",
]


class QualityIssue(BaseModel):
    type: IssueType
    # None for dataset-wide issues (e.g. duplicate rows) that don't belong
    # to a single column.
    column: str | None = None
    severity: IssueSeverity
    affected_rows: int
    percentage: float
    message: str
    suggested_action: str


class ScoreBreakdownEntry(BaseModel):
    category: str
    penalty: int
    reason: str


class QualityReport(BaseModel):
    score: int
    breakdown: list[ScoreBreakdownEntry]
    issues: list[QualityIssue]
