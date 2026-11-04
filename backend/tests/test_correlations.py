"""Unit tests for the correlation service (`services/correlations.py`)."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import InsufficientDataError, InvalidParameterError
from app.services.correlations import analyze_correlations


def _cell(report, row: str, col: str) -> float | None:
    return report.matrix[report.columns.index(row)][report.columns.index(col)]


def test_perfect_positive_pearson_correlation() -> None:
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 4, 6, 8, 10]})

    report = analyze_correlations(df, "pearson")

    assert _cell(report, "x", "y") == pytest.approx(1.0)
    assert _cell(report, "x", "x") == pytest.approx(1.0)


def test_negative_pearson_correlation() -> None:
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [10, 8, 6, 4, 2]})

    report = analyze_correlations(df, "pearson")

    assert _cell(report, "x", "y") == pytest.approx(-1.0)


def test_pearson_matches_hand_computed_value() -> None:
    # mean x = 3, mean y = 4.6. Sum of cross-products = 16.0, Sxx = 10,
    # Syy = 29.2, so r = 16 / sqrt(10 * 29.2).
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [2, 3, 4, 5, 9]})

    report = analyze_correlations(df, "pearson")

    assert _cell(report, "x", "y") == pytest.approx(16 / math.sqrt(10 * 29.2), abs=1e-6)


def test_spearman_is_one_for_monotonic_but_nonlinear_relationship() -> None:
    # y = x**3 is perfectly monotonic (Spearman = 1) but not linear (Pearson < 1).
    x = [1, 2, 3, 4, 5, 6]
    df = pd.DataFrame({"x": x, "y": [v**3 for v in x]})

    spearman = analyze_correlations(df, "spearman")
    pearson = analyze_correlations(df, "pearson")

    assert _cell(spearman, "x", "y") == pytest.approx(1.0)
    assert _cell(pearson, "x", "y") < 1.0


def test_missing_values_use_pairwise_complete_rows() -> None:
    df = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, 4.0, None],
            "y": [2.0, 4.0, None, 8.0, 10.0],
        }
    )

    report = analyze_correlations(df, "pearson")

    # Only rows 0, 1, 3 have both values; on those, y = 2x exactly.
    assert _cell(report, "x", "y") == pytest.approx(1.0)


def test_infinite_values_are_treated_as_unusable() -> None:
    df = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, 4.0, 5.0],
            "y": [2.0, 4.0, 6.0, np.inf, 10.0],
        }
    )

    report = analyze_correlations(df, "pearson")

    assert _cell(report, "x", "y") == pytest.approx(1.0)


def test_constant_column_is_excluded_with_reason() -> None:
    df = pd.DataFrame(
        {
            "x": [1, 2, 3, 4],
            "y": [2, 4, 6, 8],
            "flat": [7, 7, 7, 7],
        }
    )

    report = analyze_correlations(df, "pearson")

    assert "flat" not in report.columns
    excluded = {e.name: e.reason for e in report.excluded_columns}
    assert "constant" in excluded["flat"]


def test_insufficient_numeric_columns_raises_clear_error() -> None:
    df = pd.DataFrame({"x": [1, 2, 3], "label": ["a", "b", "c"]})

    with pytest.raises(InsufficientDataError) as exc_info:
        analyze_correlations(df, "pearson")

    assert "at least two numeric columns" in exc_info.value.message


def test_no_numeric_columns_raises_clear_error() -> None:
    df = pd.DataFrame({"city": ["NYC", "LA"], "state": ["NY", "CA"]})

    with pytest.raises(InsufficientDataError):
        analyze_correlations(df, "spearman")


def test_unknown_method_is_rejected() -> None:
    df = pd.DataFrame({"x": [1, 2, 3], "y": [1, 2, 4]})

    with pytest.raises(InvalidParameterError):
        analyze_correlations(df, "kendall")


def test_strong_pairs_are_listed_with_direction() -> None:
    df = pd.DataFrame(
        {
            "x": [1, 2, 3, 4, 5, 6],
            "y_up": [2, 4, 6, 8, 10, 12],
            "y_down": [6, 5, 4, 3, 2, 1],
        }
    )

    report = analyze_correlations(df, "pearson")

    directions = {(p.x, p.y): p.direction for p in report.strong_pairs}
    assert directions[("x", "y_up")] == "positive"
    assert directions[("x", "y_down")] == "negative"


def test_correlation_response_is_standards_compliant_json() -> None:
    df = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0, np.nan],
            "y": [2.0, np.inf, 6.0, 8.0],
            "z": [9.0, 7.0, 5.0, 3.0],
        }
    )

    report = analyze_correlations(df, "pearson")
    text = report.model_dump_json()

    json.loads(text)  # strict parse
    assert "NaN" not in text
    assert "Infinity" not in text


def test_coefficients_are_bounded_between_minus_one_and_one() -> None:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({f"c{i}": rng.normal(size=50) for i in range(4)})

    report = analyze_correlations(df, "pearson")

    for row in report.matrix:
        for value in row:
            assert value is not None
            assert -1.0 - 1e-9 <= value <= 1.0 + 1e-9


def test_correlation_matrix_is_symmetric() -> None:
    rng = np.random.default_rng(1)
    df = pd.DataFrame({f"c{i}": rng.normal(size=30) for i in range(3)})

    report = analyze_correlations(df, "spearman")

    for i in range(len(report.columns)):
        for j in range(len(report.columns)):
            assert math.isclose(report.matrix[i][j], report.matrix[j][i], abs_tol=1e-9)
