"""Response model for the original-vs-current comparison.

The response has two kinds of numbers, kept apart on purpose:

- `original` and `current` are dataset-state metrics, computed from the two
  files by the same helpers the dashboard uses.
- `operations` are totals taken from the recorded transformation history. They
  describe what the user did, not what the data looks like now.
"""

from __future__ import annotations

from pydantic import BaseModel


class DatasetMetrics(BaseModel):
    row_count: int
    column_count: int
    missing_values: int
    duplicate_rows: int
    quality_score: int


class MetricChanges(BaseModel):
    """Current minus original, for each dataset-state metric."""

    row_count: int
    column_count: int
    missing_values: int
    duplicate_rows: int
    quality_score: int


class ColumnRename(BaseModel):
    from_name: str
    to_name: str


class OperationTotals(BaseModel):
    transformation_count: int
    rows_removed: int
    duplicate_rows_removed: int
    values_filled: int
    text_rows_changed: int
    columns_dropped: list[str]
    columns_renamed: list[ColumnRename]


class ComparisonResponse(BaseModel):
    working_version: int
    original: DatasetMetrics
    current: DatasetMetrics
    changes: MetricChanges
    operations: OperationTotals
