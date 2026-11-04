"""Unit tests for the data quality engine (`services/quality.py`)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.quality import analyze_quality


def _issue_types(report) -> set[str]:
    return {issue.type for issue in report.issues}


def test_clean_dataset_scores_100_with_no_issues() -> None:
    df = pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Cara", "Dave"],
            "age": [30, 25, 40, 35],
            "active": [True, False, True, True],
        }
    )

    report = analyze_quality(df)

    assert report.score == 100
    assert report.breakdown == []
    assert report.issues == []


def test_missing_values_are_detected_and_penalized() -> None:
    df = pd.DataFrame({"value": [1, None, 3, None, 5]})

    report = analyze_quality(df)

    assert "missing_values" in _issue_types(report)
    issue = next(i for i in report.issues if i.type == "missing_values")
    assert issue.column == "value"
    assert issue.affected_rows == 2
    assert issue.percentage == 40.0
    assert report.score < 100
    assert any(b.category == "missing_values" for b in report.breakdown)


def test_blank_strings_are_detected() -> None:
    df = pd.DataFrame({"city": ["NYC", "  ", "LA", "", "LA"]})

    report = analyze_quality(df)

    issue = next(i for i in report.issues if i.type == "blank_strings")
    assert issue.column == "city"
    assert issue.affected_rows == 2


def test_duplicate_rows_are_detected_as_dataset_level_issue() -> None:
    df = pd.DataFrame({"a": [1, 1, 2, 3], "b": ["x", "x", "y", "z"]})

    report = analyze_quality(df)

    issue = next(i for i in report.issues if i.type == "duplicate_rows")
    assert issue.column is None
    assert issue.affected_rows == 1


def test_constant_column_is_detected() -> None:
    df = pd.DataFrame({"a": [1, 2, 3, 4], "flag": ["yes", "yes", "yes", "yes"]})

    report = analyze_quality(df)

    issue = next(i for i in report.issues if i.type == "constant_column")
    assert issue.column == "flag"
    assert issue.affected_rows == 4


def test_mostly_empty_column_is_detected() -> None:
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6],
            "sparse": [None, None, None, None, 1, None],
        }
    )

    report = analyze_quality(df)

    issue = next(i for i in report.issues if i.type == "mostly_empty_column")
    assert issue.column == "sparse"
    assert issue.severity == "high"


def test_infinite_values_are_detected() -> None:
    df = pd.DataFrame({"ratio": [1.0, 2.0, np.inf, -np.inf, 5.0]})

    report = analyze_quality(df)

    issue = next(i for i in report.issues if i.type == "infinite_values")
    assert issue.column == "ratio"
    assert issue.affected_rows == 2


def test_mixed_type_column_is_detected() -> None:
    df = pd.DataFrame({"value": ["10", "20", "unknown", "30", "40"]})

    report = analyze_quality(df)

    issue = next(i for i in report.issues if i.type == "mixed_types")
    assert issue.column == "value"
    assert issue.affected_rows == 1


def test_mixed_type_ignores_single_typo_in_large_column() -> None:
    values = [str(n) for n in range(500)] + ["oops"]
    df = pd.DataFrame({"value": values})

    report = analyze_quality(df)

    assert "mixed_types" not in _issue_types(report)


def test_high_cardinality_column_is_detected_but_not_penalized() -> None:
    df = pd.DataFrame({"freetext": [f"note {i}" for i in range(60)]})
    # Make it not *perfectly* unique so it's high-cardinality, not an identifier.
    df.loc[1, "freetext"] = df.loc[0, "freetext"]

    report = analyze_quality(df)

    issue = next(i for i in report.issues if i.type == "high_cardinality_column")
    assert issue.column == "freetext"
    assert issue.severity == "low"
    assert not any(b.category == "cardinality" for b in report.breakdown)


def test_possible_identifier_column_is_detected_but_not_penalized() -> None:
    df = pd.DataFrame(
        {
            "order_id": [f"ORD-{i}" for i in range(60)],
            "amount": [10.0 + i for i in range(60)],
        }
    )

    report = analyze_quality(df)

    issue = next(i for i in report.issues if i.type == "possible_identifier_column")
    assert issue.column == "order_id"
    assert issue.affected_rows == 60
    # A continuous float column being 100% unique is normal, not flagged.
    assert "amount" not in {i.column for i in report.issues if i.type == "possible_identifier_column"}


def test_small_dataset_does_not_flag_coincidentally_unique_columns() -> None:
    # With only 10 rows, an ordinary numeric column can be 100% unique by
    # pure chance — that's not meaningful evidence of being an identifier.
    df = pd.DataFrame(
        {
            "employee_id": range(1, 11),
            "age": [28, 34, 45, 29, 41, 38, 31, 26, 52, 36],
        }
    )

    report = analyze_quality(df)

    assert "possible_identifier_column" not in _issue_types(report)
    assert "high_cardinality_column" not in _issue_types(report)


def test_continuous_float_column_is_not_flagged_as_identifier() -> None:
    rng = np.random.default_rng(42)
    df = pd.DataFrame({"temperature": rng.normal(70, 5, size=50)})

    report = analyze_quality(df)

    assert "possible_identifier_column" not in _issue_types(report)
    assert "high_cardinality_column" not in _issue_types(report)


def test_score_breakdown_sums_to_exactly_100_minus_score() -> None:
    df = pd.DataFrame(
        {
            "a": [1, None, None, 4, 5, 1, 1],
            "b": ["x", "x", "x", "x", "x", "x", "x"],
            "c": [1.0, 2.0, np.inf, 4.0, 5.0, 6.0, 7.0],
        }
    )
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)

    report = analyze_quality(df)

    assert sum(entry.penalty for entry in report.breakdown) == 100 - report.score


def test_score_never_drops_below_zero_for_a_very_bad_dataset() -> None:
    row_count = 50
    df = pd.DataFrame(
        {
            "a": [None] * (row_count - 1) + [1],
            "b": ["x"] * row_count,
            "c": [np.inf] * row_count,
            "d": [" "] * row_count,
        }
    )
    df = pd.concat([df] * 3, ignore_index=True)  # pile on duplicates too

    report = analyze_quality(df)

    assert 0 <= report.score <= 100


def test_score_never_exceeds_100_for_empty_dataframe() -> None:
    df = pd.DataFrame()

    report = analyze_quality(df)

    assert report.score == 100
    assert report.issues == []


def test_quality_analysis_does_not_modify_the_dataframe() -> None:
    df = pd.DataFrame({"a": [1, None, 3], "b": ["x", "x", "y"]})
    original = df.copy(deep=True)

    analyze_quality(df)

    pd.testing.assert_frame_equal(df, original)
