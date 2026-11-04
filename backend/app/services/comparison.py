"""Original-vs-current comparison.

Dataset-state metrics come from reading the two real files and running the
existing profiler and quality engine on each, so the comparison can't drift
from the Profile and Data Quality tabs.

Operation totals come only from the recorded transformation history. Row-by-row
comparison of the two files is deliberately not used: duplicate removal and
row deletion shift positions, so "values modified" can't be computed reliably
that way, and it isn't reported.

Read-only: this module opens files for reading and never writes.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.core.exceptions import DatasetFileMissingError
from app.models.dataset import Dataset
from app.schemas.comparison import (
    ColumnRename,
    ComparisonResponse,
    DatasetMetrics,
    MetricChanges,
    OperationTotals,
)
from app.schemas.history import TransformationRecord
from app.services import csv_service, history, profiler, quality, transformations


def build_comparison(dataset: Dataset, db: Session) -> ComparisonResponse:
    original = _metrics(_read_version(dataset, 0))
    current = _metrics(_read_version(dataset, dataset.working_version))
    records = history.list_transformations(dataset.id, db)
    return ComparisonResponse(
        working_version=dataset.working_version,
        original=original,
        current=current,
        changes=_changes(original, current),
        operations=_operation_totals(records),
    )


def _read_version(dataset: Dataset, version: int) -> pd.DataFrame:
    path = transformations.version_path(dataset, version)
    if not path.exists():
        label = "original upload" if version == 0 else f"working version {version}"
        raise DatasetFileMissingError(f"The {label} for this dataset is missing from disk.")
    encoding = dataset.encoding_codec if version == 0 else transformations.WORKING_ENCODING
    return csv_service.read_dataframe(path, encoding=encoding)


def _metrics(dataframe: pd.DataFrame) -> DatasetMetrics:
    profile = profiler.profile_dataset(dataframe)
    return DatasetMetrics(
        row_count=profile.row_count,
        column_count=profile.column_count,
        missing_values=sum(column.missing_count for column in profile.columns),
        duplicate_rows=profile.duplicate_row_count,
        quality_score=quality.analyze_quality(dataframe).score,
    )


def _changes(original: DatasetMetrics, current: DatasetMetrics) -> MetricChanges:
    return MetricChanges(
        row_count=current.row_count - original.row_count,
        column_count=current.column_count - original.column_count,
        missing_values=current.missing_values - original.missing_values,
        duplicate_rows=current.duplicate_rows - original.duplicate_rows,
        quality_score=current.quality_score - original.quality_score,
    )


def _operation_totals(records: list[TransformationRecord]) -> OperationTotals:
    rows_removed = 0
    duplicate_rows_removed = 0
    values_filled = 0
    text_rows_changed = 0
    columns_dropped: list[str] = []
    columns_renamed: list[ColumnRename] = []

    for record in records:
        rows_removed += record.rows_before - record.rows_after
        if record.operation == "remove_duplicates":
            duplicate_rows_removed += record.affected_rows
        elif record.operation == "fill_missing" and record.parameters.get("strategy") != "remove_rows":
            values_filled += record.affected_rows
        elif record.operation == "normalize_text":
            text_rows_changed += record.affected_rows
        elif record.operation == "drop_columns":
            columns_dropped.extend(record.parameters.get("columns", []))
        elif record.operation == "rename_column":
            columns_renamed.append(
                ColumnRename(from_name=record.column or "", to_name=record.parameters["new_name"])
            )

    return OperationTotals(
        transformation_count=len(records),
        rows_removed=rows_removed,
        duplicate_rows_removed=duplicate_rows_removed,
        values_filled=values_filled,
        text_rows_changed=text_rows_changed,
        columns_dropped=columns_dropped,
        columns_renamed=columns_renamed,
    )
