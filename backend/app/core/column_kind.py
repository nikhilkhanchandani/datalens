"""Shared column-kind inference.

Both the profiler and the statistics engine need to classify a column as
numeric/categorical/boolean/datetime before computing type-appropriate
statistics. Centralizing the (slightly subtle) datetime-detection heuristic
here means every caller agrees on what counts as a date column, and the
heuristic only has to be reasoned about — and tested — in one place.
"""

from __future__ import annotations

import re
from typing import Literal

import pandas as pd

ColumnKind = Literal["numeric", "categorical", "boolean", "datetime"]

_DATETIME_PARSE_SUCCESS_THRESHOLD = 0.9
# Cheap pre-filter before attempting a real parse: require a date-like
# separator so plain numeric strings (zip codes, IDs) aren't misclassified.
_DATE_LIKE_PATTERN = re.compile(r"^\d{1,4}[-/]\d{1,2}[-/]\d{1,4}")


def infer_column_kind(series: pd.Series) -> ColumnKind:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if _looks_like_boolean(series):
        return "boolean"
    if _looks_like_datetime(series):
        return "datetime"
    return "categorical"


def _looks_like_boolean(series: pd.Series) -> bool:
    """Detect a True/False column that has missing values.

    `pd.read_csv` parses "True"/"False" tokens as real Python `bool`
    objects, but as soon as *any* value in that column is missing, Pandas
    can no longer use the plain `bool` dtype (it has no room for NaN) and
    falls back to `object` — so `is_bool_dtype` alone misses this very
    common case. Checking that every non-null value is actually a `bool`
    instance (not just a string that happens to say "true") catches it
    without risking a false match on ordinary text.
    """
    if not pd.api.types.is_object_dtype(series):
        return False
    non_null = series.dropna()
    if non_null.empty:
        return False
    return bool(non_null.map(lambda value: isinstance(value, bool)).all())


def _looks_like_datetime(series: pd.Series) -> bool:
    """Heuristic detection of date-like text columns.

    `pd.read_csv` never parses dates by default, so a "hire_date" column
    arrives as plain object/string data. We only attempt the (relatively
    expensive, and occasionally wrong) `pd.to_datetime` parse after a cheap
    regex pre-filter, so an all-numeric ID column is never misread as dates.
    """
    if not pd.api.types.is_object_dtype(series):
        return False

    non_null = series.dropna().astype(str)
    if non_null.empty:
        return False

    sample = non_null.head(50)
    if sample.str.match(_DATE_LIKE_PATTERN).mean() < _DATETIME_PARSE_SUCCESS_THRESHOLD:
        return False

    parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
    return parsed.notna().mean() >= _DATETIME_PARSE_SUCCESS_THRESHOLD
