"""Unit tests for the descriptive statistics engine (`services/statistics.py`)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.statistics import analyze_statistics


def _column(stats, name):
    return next(c for c in stats.columns if c.name == name)


def test_numeric_statistics_against_known_values() -> None:
    # Known values: 10, 20, 30, 40, 50 -> mean 30, median 30, population
    # range [10, 50]; Pandas uses sample (ddof=1) std/var by default.
    df = pd.DataFrame({"value": [10, 20, 30, 40, 50]})

    stats = analyze_statistics(df)
    numeric = _column(stats, "value").numeric

    assert numeric.count == 5
    assert numeric.missing_count == 0
    assert numeric.mean == 30.0
    assert numeric.median == 30.0
    assert numeric.minimum == 10.0
    assert numeric.maximum == 50.0
    assert numeric.range == 40.0
    assert numeric.p25 == 20.0
    assert numeric.p50 == 30.0
    assert numeric.p75 == 40.0
    assert numeric.iqr == 20.0
    assert round(numeric.std, 4) == round(float(np.std([10, 20, 30, 40, 50], ddof=1)), 4)


def test_numeric_statistics_counts_missing_values() -> None:
    df = pd.DataFrame({"value": [1, None, 3, None]})

    numeric = _column(analyze_statistics(df), "value").numeric

    assert numeric.count == 2
    assert numeric.missing_count == 2


def test_numeric_statistics_excludes_infinite_values() -> None:
    df = pd.DataFrame({"value": [1.0, 2.0, np.inf, -np.inf, 5.0]})

    numeric = _column(analyze_statistics(df), "value").numeric

    assert numeric.count == 3
    assert numeric.maximum == 5.0
    assert numeric.minimum == 1.0


def test_numeric_statistics_single_value_has_zero_spread() -> None:
    df = pd.DataFrame({"value": [42.0]})

    numeric = _column(analyze_statistics(df), "value").numeric

    assert numeric.std == 0.0
    assert numeric.variance == 0.0


def test_numeric_statistics_all_missing_returns_none_fields() -> None:
    df = pd.DataFrame({"value": pd.array([None, None], dtype="float64")})

    numeric = _column(analyze_statistics(df), "value").numeric

    assert numeric.count == 0
    assert numeric.mean is None
    assert numeric.range is None
    assert numeric.iqr is None


def test_categorical_statistics_against_known_values() -> None:
    df = pd.DataFrame({"city": ["NYC", "NYC", "LA", "LA", "LA", None]})

    categorical = _column(analyze_statistics(df), "city").categorical

    assert categorical.count == 5
    assert categorical.missing_count == 1
    assert categorical.unique_count == 2
    assert categorical.most_frequent_value == "LA"
    assert categorical.most_frequent_count == 3
    assert {tv.value for tv in categorical.top_values} == {"NYC", "LA"}


def test_boolean_statistics_against_known_values() -> None:
    # A plain Python list mixing bool and None becomes `object` dtype in
    # Pandas (bool has no room for NaN) — the nullable "boolean" extension
    # dtype is what actually represents a boolean column with missing
    # values, so that's what a real upload with gaps would look like.
    df = pd.DataFrame({"active": pd.array([True, False, True, True, None], dtype="boolean")})

    boolean = _column(analyze_statistics(df), "active").boolean

    assert boolean.count == 4
    assert boolean.missing_count == 1
    assert boolean.true_count == 3
    assert boolean.false_count == 1
    assert boolean.true_percentage == 75.0


def test_boolean_statistics_from_real_csv_with_missing_values() -> None:
    # Reproduces exactly what `pd.read_csv` produces for a True/False column
    # with a gap: an `object`-dtype Series of real Python `bool` objects
    # plus NaN (not the nullable "boolean" extension dtype) — the case the
    # `_looks_like_boolean` heuristic in `core/column_kind.py` exists for.
    import io

    df = pd.read_csv(io.StringIO("flag,name\nTrue,a\nFalse,b\n,c\nTrue,d\n"))
    assert df["flag"].dtype == object  # sanity-check the premise

    stats = _column(analyze_statistics(df), "flag")

    assert stats.kind == "boolean"
    assert stats.boolean.count == 3
    assert stats.boolean.missing_count == 1
    assert stats.boolean.true_count == 2
    assert stats.boolean.false_count == 1


def test_datetime_statistics_against_known_values() -> None:
    df = pd.DataFrame({"hire_date": ["2022-01-01", "2022-01-11", None, "2022-01-06"]})

    stats = _column(analyze_statistics(df), "hire_date")

    assert stats.kind == "datetime"
    dt = stats.datetime
    assert dt.valid_count == 3
    assert dt.missing_count == 1
    assert dt.earliest == "2022-01-01T00:00:00"
    assert dt.latest == "2022-01-11T00:00:00"
    assert dt.range_days == 10.0


def test_all_null_object_column_is_categorical_not_datetime() -> None:
    # An all-null object column has no values to pattern-match against, so
    # it's classified as categorical rather than (incorrectly) datetime.
    df = pd.DataFrame({"maybe_date": pd.array([None, None], dtype="object")})

    stats = analyze_statistics(df)

    assert _column(stats, "maybe_date").kind == "categorical"


def test_row_count_matches_dataframe_length() -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})

    stats = analyze_statistics(df)

    assert stats.row_count == 3


def test_statistics_does_not_modify_the_dataframe() -> None:
    df = pd.DataFrame({"a": [1, None, 3], "b": ["x", "y", "z"]})
    original = df.copy(deep=True)

    analyze_statistics(df)

    pd.testing.assert_frame_equal(df, original)
