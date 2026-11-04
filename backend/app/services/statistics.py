"""Descriptive statistics engine.

Computes the fuller, type-appropriate statistical summary shown on the
dashboard's dedicated Statistics page. Deliberately independent of
`profiler.py`: the profiler produces a lightweight per-column snapshot for
the Overview/Columns tabs (a handful of numbers, picked for a quick
glance), while this module computes a complete breakdown — including
boolean and datetime statistics the profiler does not attempt at all — for
a dedicated deep-dive page. The two tabs are allowed to show overlapping
numbers; that overlap is intentional, matching the dashboard design in
`PROJECT_SPEC.md`.
"""

from __future__ import annotations

import pandas as pd

from app.core.column_kind import infer_column_kind
from app.core.numeric import numeric_values, parse_datetime_values
from app.core.sanitize import safe_float
from app.schemas.statistics import (
    BooleanStatistics,
    CategoricalStatistics,
    CategoricalTopValue,
    ColumnStatistics,
    DatasetStatistics,
    DatetimeStatistics,
    NumericStatistics,
)

_MAX_TOP_VALUES = 10


def analyze_statistics(df: pd.DataFrame) -> DatasetStatistics:
    columns = [_column_statistics(df[name]) for name in df.columns]
    return DatasetStatistics(row_count=len(df), columns=columns)


def _column_statistics(series: pd.Series) -> ColumnStatistics:
    kind = infer_column_kind(series)
    return ColumnStatistics(
        name=str(series.name),
        kind=kind,
        numeric=_numeric_statistics(series) if kind == "numeric" else None,
        categorical=_categorical_statistics(series) if kind == "categorical" else None,
        boolean=_boolean_statistics(series) if kind == "boolean" else None,
        datetime=_datetime_statistics(series) if kind == "datetime" else None,
    )


def _numeric_statistics(series: pd.Series) -> NumericStatistics:
    missing_count = int(series.isna().sum())

    # *That* a column contains infinities is a data-quality concern flagged by
    # `services/quality.py`; here they're simply not usable observations.
    numeric = numeric_values(series)

    if numeric.empty:
        return NumericStatistics(
            count=0,
            missing_count=missing_count,
            mean=None,
            median=None,
            std=None,
            variance=None,
            minimum=None,
            maximum=None,
            range=None,
            p25=None,
            p50=None,
            p75=None,
            iqr=None,
        )

    minimum = safe_float(numeric.min())
    maximum = safe_float(numeric.max())
    p25 = safe_float(numeric.quantile(0.25))
    p75 = safe_float(numeric.quantile(0.75))
    has_spread = numeric.count() > 1

    return NumericStatistics(
        count=int(numeric.count()),
        missing_count=missing_count,
        mean=safe_float(numeric.mean()),
        median=safe_float(numeric.median()),
        std=safe_float(numeric.std()) if has_spread else 0.0,
        variance=safe_float(numeric.var()) if has_spread else 0.0,
        minimum=minimum,
        maximum=maximum,
        range=(maximum - minimum) if minimum is not None and maximum is not None else None,
        p25=p25,
        p50=safe_float(numeric.quantile(0.5)),
        p75=p75,
        iqr=(p75 - p25) if p25 is not None and p75 is not None else None,
    )


def _categorical_statistics(series: pd.Series) -> CategoricalStatistics:
    missing_count = int(series.isna().sum())
    non_null = series.dropna().astype(str)
    value_counts = non_null.value_counts()

    if value_counts.empty:
        return CategoricalStatistics(
            count=0,
            missing_count=missing_count,
            unique_count=0,
            most_frequent_value=None,
            most_frequent_count=0,
            top_values=[],
        )

    top = value_counts.head(_MAX_TOP_VALUES)
    return CategoricalStatistics(
        count=int(non_null.shape[0]),
        missing_count=missing_count,
        unique_count=int(non_null.nunique()),
        most_frequent_value=str(top.index[0]),
        most_frequent_count=int(top.iloc[0]),
        top_values=[CategoricalTopValue(value=str(v), count=int(c)) for v, c in top.items()],
    )


def _boolean_statistics(series: pd.Series) -> BooleanStatistics:
    missing_count = int(series.isna().sum())
    non_null = series.dropna()

    true_count = int(non_null.sum())  # True sums as 1, False as 0
    false_count = int(non_null.shape[0]) - true_count
    total = true_count + false_count
    true_percentage = round((true_count / total) * 100, 2) if total else None

    return BooleanStatistics(
        count=total,
        missing_count=missing_count,
        true_count=true_count,
        false_count=false_count,
        true_percentage=true_percentage,
    )


def _datetime_statistics(series: pd.Series) -> DatetimeStatistics:
    missing_count = int(series.isna().sum())

    parsed = parse_datetime_values(series)

    if parsed.empty:
        return DatetimeStatistics(
            valid_count=0,
            missing_count=missing_count,
            earliest=None,
            latest=None,
            range_days=None,
        )

    earliest = parsed.min()
    latest = parsed.max()
    range_days = (latest - earliest).total_seconds() / 86400

    return DatetimeStatistics(
        valid_count=int(parsed.shape[0]),
        missing_count=missing_count,
        earliest=earliest.isoformat(),
        latest=latest.isoformat(),
        range_days=round(range_days, 2),
    )
