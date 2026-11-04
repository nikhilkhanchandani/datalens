"""Unit tests for the Pandas-based profiling engine.

These test `profile_dataset` directly against hand-built DataFrames (no
HTTP, no disk) so failures point straight at the statistics logic.
"""

from __future__ import annotations

import math

import pandas as pd

from app.services.profiler import profile_dataset


def test_profile_counts_rows_and_columns() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})

    profile = profile_dataset(df)

    assert profile.row_count == 3
    assert profile.column_count == 2
    assert profile.duplicate_row_count == 0


def test_profile_detects_duplicate_rows() -> None:
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})

    profile = profile_dataset(df)

    assert profile.duplicate_row_count == 1


def test_numeric_column_statistics() -> None:
    df = pd.DataFrame({"value": [10, 20, 30, 40, 50]})

    column = profile_dataset(df).columns[0]

    assert column.kind == "numeric"
    assert column.numeric_stats is not None
    assert column.numeric_stats.mean == 30
    assert column.numeric_stats.minimum == 10
    assert column.numeric_stats.maximum == 50
    assert column.numeric_stats.range == 40
    assert column.numeric_stats.p50 == 30


def test_categorical_column_statistics() -> None:
    df = pd.DataFrame({"city": ["NYC", "NYC", "LA", "LA", "LA"]})

    column = profile_dataset(df).columns[0]

    assert column.kind == "categorical"
    assert column.categorical_stats is not None
    assert column.categorical_stats.most_frequent_value == "LA"
    assert column.categorical_stats.most_frequent_count == 3
    assert column.categorical_stats.unique_count == 2


def test_missing_values_are_counted() -> None:
    df = pd.DataFrame({"value": [1, None, 3, None]})

    column = profile_dataset(df).columns[0]

    assert column.missing_count == 2
    assert column.missing_percentage == 50.0


def test_boolean_column_is_detected() -> None:
    df = pd.DataFrame({"flag": [True, False, True]})

    column = profile_dataset(df).columns[0]

    assert column.kind == "boolean"


def test_boolean_column_with_missing_values_is_still_detected() -> None:
    # A real CSV upload with a gap in a True/False column parses as
    # `object` dtype (real Python bool objects + NaN), not plain `bool`.
    import io

    df = pd.read_csv(io.StringIO("flag,name\nTrue,a\nFalse,b\n,c\n"))

    column = profile_dataset(df).columns[0]

    assert column.kind == "boolean"


def test_datetime_like_strings_are_detected() -> None:
    df = pd.DataFrame({"hire_date": ["2022-01-15", "2022-03-01", "2021-11-30"]})

    column = profile_dataset(df).columns[0]

    assert column.kind == "datetime"


def test_plain_numeric_strings_are_not_misdetected_as_datetime() -> None:
    df = pd.DataFrame({"zip_code": ["10001", "90210", "60614"]})

    column = profile_dataset(df).columns[0]

    assert column.kind == "categorical"


def test_non_numeric_text_column_is_categorical_with_no_missing() -> None:
    df = pd.DataFrame({"value": ["10", "20", "unknown", "30"]})

    column = profile_dataset(df).columns[0]

    assert column.kind == "categorical"
    assert column.missing_count == 0


def test_infinite_values_are_excluded_from_numeric_stats() -> None:
    df = pd.DataFrame({"value": [1.0, 2.0, float("inf")]})

    column = profile_dataset(df).columns[0]

    assert column.numeric_stats is not None
    assert math.isfinite(column.numeric_stats.maximum)


def test_all_missing_numeric_column_does_not_crash() -> None:
    df = pd.DataFrame({"value": pd.array([None, None, None], dtype="float64")})

    column = profile_dataset(df).columns[0]

    assert column.numeric_stats is not None
    assert column.numeric_stats.count == 0
    assert column.numeric_stats.mean is None


def test_memory_usage_is_positive() -> None:
    df = pd.DataFrame({"a": range(100), "b": [str(i) for i in range(100)]})

    profile = profile_dataset(df)

    assert profile.memory_usage_bytes > 0
