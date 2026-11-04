"""Dataset profiling: turns an arbitrary DataFrame into structured,
JSON-serializable statistics.

This is the core "real analysis" of the project — nothing here is
hardcoded or dataset-specific; every number comes from calling Pandas/NumPy
on whatever DataFrame was parsed from the user's CSV, so it must behave
sensibly on datasets this code has never seen.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.column_kind import infer_column_kind
from app.core.sanitize import to_json_safe
from app.schemas.analysis import (
    CategoricalColumnStats,
    ColumnProfile,
    DatasetProfile,
    NumericColumnStats,
    TopValue,
)

_MAX_SAMPLE_VALUES = 5
_MAX_TOP_VALUES = 10


def profile_dataset(df: pd.DataFrame) -> DatasetProfile:
    """Profile every column of `df` and summarize the dataset as a whole."""
    columns = [_profile_column(df[column_name]) for column_name in df.columns]

    return DatasetProfile(
        row_count=len(df),
        column_count=len(df.columns),
        duplicate_row_count=int(df.duplicated().sum()),
        memory_usage_bytes=int(df.memory_usage(deep=True).sum()),
        columns=columns,
    )


def _profile_column(series: pd.Series) -> ColumnProfile:
    kind = infer_column_kind(series)
    row_count = len(series)
    missing_count = int(series.isna().sum())
    missing_percentage = (
        round((missing_count / row_count) * 100, 2) if row_count else 0.0
    )

    return ColumnProfile(
        name=str(series.name),
        kind=kind,
        pandas_dtype=str(series.dtype),
        missing_count=missing_count,
        missing_percentage=missing_percentage,
        unique_count=int(series.nunique(dropna=True)),
        sample_values=_sample_values(series),
        numeric_stats=_numeric_stats(series) if kind == "numeric" else None,
        categorical_stats=(
            _categorical_stats(series) if kind in ("categorical", "boolean") else None
        ),
    )


def _numeric_stats(series: pd.Series) -> NumericColumnStats:
    numeric = pd.to_numeric(series, errors="coerce")
    # Infinite values would serialize to invalid JSON (`Infinity`) and break
    # the frontend's `response.json()`; excluding them from statistics here
    # is a deliberate simplification — flagging *that* a column contains
    # infinities is the Data Quality engine's job (Phase 3), not the profiler's.
    numeric = numeric.replace([np.inf, -np.inf], np.nan).dropna()

    if numeric.empty:
        return NumericColumnStats(
            count=0,
            mean=None,
            median=None,
            std=None,
            variance=None,
            minimum=None,
            maximum=None,
            p25=None,
            p50=None,
            p75=None,
            range=None,
        )

    minimum = float(numeric.min())
    maximum = float(numeric.max())
    has_spread = numeric.count() > 1

    return NumericColumnStats(
        count=int(numeric.count()),
        mean=float(numeric.mean()),
        median=float(numeric.median()),
        std=float(numeric.std()) if has_spread else 0.0,
        variance=float(numeric.var()) if has_spread else 0.0,
        minimum=minimum,
        maximum=maximum,
        p25=float(numeric.quantile(0.25)),
        p50=float(numeric.quantile(0.5)),
        p75=float(numeric.quantile(0.75)),
        range=maximum - minimum,
    )


def _categorical_stats(series: pd.Series) -> CategoricalColumnStats:
    value_counts = series.dropna().astype(str).value_counts()

    if value_counts.empty:
        return CategoricalColumnStats(
            unique_count=0,
            most_frequent_value=None,
            most_frequent_count=0,
            top_values=[],
        )

    top = value_counts.head(_MAX_TOP_VALUES)
    return CategoricalColumnStats(
        unique_count=int(series.dropna().nunique()),
        most_frequent_value=str(top.index[0]),
        most_frequent_count=int(top.iloc[0]),
        top_values=[TopValue(value=str(v), count=int(c)) for v, c in top.items()],
    )


def _sample_values(series: pd.Series) -> list[Any]:
    non_null = series.dropna().unique()[:_MAX_SAMPLE_VALUES]
    return [to_json_safe(value) for value in non_null]
