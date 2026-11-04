"""Unit tests for chart-data preparation (`services/visualizations.py`)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import (
    ColumnNotFoundError,
    IncompatibleColumnTypeError,
    InsufficientDataError,
    InvalidParameterError,
)
from app.services import visualizations as viz


# --- histogram -------------------------------------------------------------


def test_histogram_counts_sum_to_usable_observations() -> None:
    df = pd.DataFrame({"v": [1.0, 2.0, 2.5, 3.0, 9.0, None, np.inf]})

    hist = viz.histogram(df, "v", bins=None)

    assert sum(b.count for b in hist.bins) == hist.total_observations == 5
    assert hist.missing_count == 1
    assert hist.infinite_count == 1


def test_histogram_bin_edges_are_contiguous_and_span_the_data() -> None:
    df = pd.DataFrame({"v": [0.0, 10.0, 20.0, 30.0]})

    hist = viz.histogram(df, "v", bins=4)

    assert len(hist.bins) == 4
    assert hist.bins[0].start == pytest.approx(0.0)
    assert hist.bins[-1].end == pytest.approx(30.0)
    for left, right in zip(hist.bins, hist.bins[1:]):
        assert left.end == pytest.approx(right.start)


def test_histogram_fixed_bin_count_is_respected() -> None:
    df = pd.DataFrame({"v": list(range(100))})

    hist = viz.histogram(df, "v", bins=7)

    assert len(hist.bins) == 7
    assert "7" in hist.bin_strategy


def test_histogram_known_counts() -> None:
    # Edges for 2 bins over [0, 10] are [0, 5, 10]; 5.0 falls in the second bin.
    df = pd.DataFrame({"v": [0.0, 1.0, 4.9, 5.0, 10.0]})

    hist = viz.histogram(df, "v", bins=2)

    assert [b.count for b in hist.bins] == [3, 2]


def test_histogram_constant_column_is_flagged_and_counted() -> None:
    df = pd.DataFrame({"v": [4.0, 4.0, 4.0, 4.0]})

    hist = viz.histogram(df, "v", bins=None)

    assert hist.is_constant is True
    assert sum(b.count for b in hist.bins) == 4


def test_histogram_default_bins_are_capped() -> None:
    df = pd.DataFrame({"v": np.random.default_rng(3).normal(size=50_000)})

    hist = viz.histogram(df, "v", bins=None)

    assert len(hist.bins) <= viz.MAX_HISTOGRAM_BINS


def test_histogram_rejects_out_of_range_bin_count() -> None:
    df = pd.DataFrame({"v": [1.0, 2.0]})

    with pytest.raises(InvalidParameterError):
        viz.histogram(df, "v", bins=0)
    with pytest.raises(InvalidParameterError):
        viz.histogram(df, "v", bins=viz.MAX_HISTOGRAM_BINS + 1)


def test_histogram_without_usable_values_raises() -> None:
    df = pd.DataFrame({"v": pd.array([None, None], dtype="float64")})

    with pytest.raises(InsufficientDataError):
        viz.histogram(df, "v", bins=None)


# --- categorical frequencies -----------------------------------------------


def test_categorical_counts_and_percentages() -> None:
    df = pd.DataFrame({"city": ["NYC", "NYC", "LA", "LA", "LA", "SF", None]})

    freq = viz.categorical_frequencies(df, "city", top_n=10)

    by_value = {item.value: item for item in freq.items}
    assert by_value["LA"].count == 3
    assert by_value["LA"].percentage == pytest.approx(3 / 6 * 100)
    assert freq.total_count == 6
    assert freq.missing_count == 1
    assert freq.truncated is False


def test_categories_are_sorted_by_count_then_alphabetically() -> None:
    df = pd.DataFrame({"c": ["b", "a", "b", "a", "c"]})

    freq = viz.categorical_frequencies(df, "c", top_n=10)

    assert [item.value for item in freq.items] == ["a", "b", "c"]


def test_top_n_groups_remainder_as_other() -> None:
    df = pd.DataFrame({"c": ["a"] * 5 + ["b"] * 3 + ["c"] * 2 + ["d"] * 1})

    freq = viz.categorical_frequencies(df, "c", top_n=2)

    assert [item.value for item in freq.items] == ["a", "b", "Other"]
    other = freq.items[-1]
    assert other.is_other is True
    assert other.count == 3  # c + d
    assert freq.truncated is True
    assert sum(item.count for item in freq.items) == freq.total_count


def test_high_cardinality_column_returns_only_top_n_plus_other() -> None:
    df = pd.DataFrame({"id_like": [f"value-{i}" for i in range(5000)]})

    freq = viz.categorical_frequencies(df, "id_like", top_n=20)

    assert len(freq.items) == 21
    assert freq.unique_count == 5000
    assert freq.items[-1].value == "Other"
    assert sum(item.count for item in freq.items) == 5000


def test_top_n_out_of_range_is_rejected() -> None:
    df = pd.DataFrame({"c": ["a", "b"]})

    with pytest.raises(InvalidParameterError):
        viz.categorical_frequencies(df, "c", top_n=0)
    with pytest.raises(InvalidParameterError):
        viz.categorical_frequencies(df, "c", top_n=viz.MAX_CATEGORY_TOP_N + 1)


# --- scatter ---------------------------------------------------------------


def test_scatter_returns_all_points_when_under_limit() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 4.0, 6.0]})

    data = viz.scatter(df, "x", "y")

    assert data.sampled is False
    assert data.returned_points == data.total_points == 3
    assert data.pearson_r == pytest.approx(1.0)


def test_scatter_sample_is_bounded_and_flagged() -> None:
    n = viz.MAX_SCATTER_POINTS * 3
    df = pd.DataFrame({"x": np.arange(n, dtype=float), "y": np.arange(n, dtype=float) * 2})

    data = viz.scatter(df, "x", "y")

    assert data.sampled is True
    assert data.returned_points == viz.MAX_SCATTER_POINTS
    assert data.total_points == n


def test_scatter_sampling_is_deterministic() -> None:
    n = viz.MAX_SCATTER_POINTS * 2
    df = pd.DataFrame({"x": np.arange(n, dtype=float), "y": np.sin(np.arange(n, dtype=float))})

    first = viz.scatter(df, "x", "y")
    second = viz.scatter(df, "x", "y")

    assert first.points == second.points


def test_scatter_correlation_uses_all_rows_not_only_sample() -> None:
    n = viz.MAX_SCATTER_POINTS * 2
    df = pd.DataFrame({"x": np.arange(n, dtype=float), "y": np.arange(n, dtype=float) * 3})

    data = viz.scatter(df, "x", "y")

    assert data.pearson_r == pytest.approx(1.0)


def test_scatter_drops_rows_with_missing_or_infinite_values() -> None:
    df = pd.DataFrame(
        {
            "x": [1.0, 2.0, None, 4.0, np.inf],
            "y": [1.0, None, 3.0, 4.0, 5.0],
        }
    )

    data = viz.scatter(df, "x", "y")

    assert data.total_points == 2  # only rows 0 and 3 are usable on both axes


def test_scatter_rejects_same_column_on_both_axes() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})

    with pytest.raises(InvalidParameterError):
        viz.scatter(df, "x", "x")


def test_scatter_rejects_non_numeric_axis() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "city": ["a", "b", "c"]})

    with pytest.raises(IncompatibleColumnTypeError):
        viz.scatter(df, "x", "city")


def test_scatter_payload_is_standards_compliant_json() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, np.inf, 4.0], "y": [2.0, 4.0, 6.0, np.nan]})

    data = viz.scatter(df, "x", "y")

    text = data.model_dump_json()
    json.loads(text)
    assert "NaN" not in text and "Infinity" not in text


# --- distribution summary --------------------------------------------------


def test_distribution_summary_quartiles() -> None:
    # Known values: 1..9. Median 5, Q1 3, Q3 7 (linear interpolation).
    df = pd.DataFrame({"v": list(range(1, 10))})

    summary = viz.distribution_summary(df, "v")

    assert summary.minimum == 1.0
    assert summary.q1 == pytest.approx(3.0)
    assert summary.median == pytest.approx(5.0)
    assert summary.q3 == pytest.approx(7.0)
    assert summary.maximum == 9.0
    assert summary.iqr == pytest.approx(4.0)


def test_distribution_summary_ignores_missing_and_infinite() -> None:
    df = pd.DataFrame({"v": [1.0, 2.0, 3.0, None, np.inf]})

    summary = viz.distribution_summary(df, "v")

    assert summary.count == 3
    assert summary.missing_count == 1


def test_distribution_summary_rejects_categorical_column() -> None:
    df = pd.DataFrame({"city": ["a", "b", "c"]})

    with pytest.raises(IncompatibleColumnTypeError):
        viz.distribution_summary(df, "city")


# --- datetime trend --------------------------------------------------------


def test_datetime_trend_aggregates_per_period() -> None:
    df = pd.DataFrame(
        {
            "when": ["2023-01-05", "2023-01-20", "2023-02-10", "2023-03-01"],
            "salary": [100.0, 200.0, 300.0, 500.0],
        }
    )

    trend = viz.datetime_trend(df, "when", "salary")

    # A 55-day span fits within MAX_TREND_POINTS at daily grain.
    assert trend.granularity == "day"
    assert trend.total_observations == 4
    assert [p.period_start[:10] for p in trend.points] == [
        "2023-01-05",
        "2023-01-20",
        "2023-02-10",
        "2023-03-01",
    ]
    assert [p.mean for p in trend.points] == [100.0, 200.0, 300.0, 500.0]


def test_datetime_trend_groups_same_period_and_averages() -> None:
    df = pd.DataFrame(
        {
            "when": ["2023-01-05", "2023-01-05", "2023-01-06"],
            "v": [10.0, 30.0, 50.0],
        }
    )

    trend = viz.datetime_trend(df, "when", "v")

    assert len(trend.points) == 2
    assert trend.points[0].mean == pytest.approx(20.0)
    assert trend.points[0].count == 2
    assert trend.points[0].minimum == 10.0
    assert trend.points[0].maximum == 30.0


def test_datetime_trend_point_count_stays_bounded_for_long_spans() -> None:
    dates = pd.date_range("1990-01-01", "2024-12-31", freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({"when": dates, "v": np.arange(len(dates), dtype=float)})

    trend = viz.datetime_trend(df, "when", "v")

    assert len(trend.points) <= viz.MAX_TREND_POINTS


def test_datetime_trend_requires_a_datetime_column() -> None:
    df = pd.DataFrame({"city": ["a", "b"], "v": [1.0, 2.0]})

    with pytest.raises(IncompatibleColumnTypeError):
        viz.datetime_trend(df, "city", "v")


def test_datetime_trend_without_overlapping_values_raises() -> None:
    # Dates exist only where values are missing, and vice versa: no shared rows.
    df = pd.DataFrame({"when": ["2023-01-01", None], "v": [None, 5.0]})

    with pytest.raises(InsufficientDataError):
        viz.datetime_trend(df, "when", "v")


# --- validation across visualizations --------------------------------------


def test_nonexistent_column_is_rejected() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0]})

    with pytest.raises(ColumnNotFoundError):
        viz.histogram(df, "missing", bins=None)


def test_incompatible_column_type_is_rejected_for_histogram() -> None:
    df = pd.DataFrame({"city": ["a", "b"]})

    with pytest.raises(IncompatibleColumnTypeError):
        viz.histogram(df, "city", bins=None)


def test_categorical_chart_rejects_numeric_column() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0, 3.0]})

    with pytest.raises(IncompatibleColumnTypeError):
        viz.categorical_frequencies(df, "x")
