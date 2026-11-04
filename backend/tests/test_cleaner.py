"""Unit tests for the pure cleaning transformations (`services/cleaner.py`)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import (
    ColumnNotFoundError,
    IncompatibleColumnTypeError,
    InsufficientDataError,
    InvalidConversionError,
    InvalidParameterError,
    NoOpTransformationError,
)
from app.schemas.cleaning import (
    ConvertTypeRequest,
    DropColumnsRequest,
    FillMissingRequest,
    NormalizeTextRequest,
    RemoveDuplicatesRequest,
    RenameColumnRequest,
)
from app.services.cleaner import apply_cleaning


def _fill(column: str, strategy: str, value=None) -> FillMissingRequest:
    return FillMissingRequest(operation="fill_missing", column=column, strategy=strategy, value=value)


# --- missing values --------------------------------------------------------


def test_numeric_mean_fill() -> None:
    df = pd.DataFrame({"salary": [10.0, None, 30.0, None, 50.0]})

    cleaned, result = apply_cleaning(df, _fill("salary", "mean"), next_version=1)

    assert cleaned["salary"].tolist() == [10.0, 30.0, 30.0, 30.0, 50.0]
    assert result.affected_rows == 2
    assert result.rows_before == result.rows_after == 5
    assert result.strategy == "mean"


def test_numeric_median_fill_differs_from_mean_for_skewed_data() -> None:
    df = pd.DataFrame({"salary": [10.0, 20.0, 30.0, 1000.0, None]})

    cleaned, _ = apply_cleaning(df, _fill("salary", "median"), next_version=1)

    assert cleaned["salary"].iloc[4] == 25.0  # median of [10, 20, 30, 1000]
    mean_cleaned, _ = apply_cleaning(df, _fill("salary", "mean"), next_version=1)
    assert mean_cleaned["salary"].iloc[4] == pytest.approx(265.0)


def test_numeric_custom_fill() -> None:
    df = pd.DataFrame({"score": [1.0, None, 3.0]})

    cleaned, result = apply_cleaning(df, _fill("score", "custom", 0), next_version=1)

    assert cleaned["score"].tolist() == [1.0, 0.0, 3.0]
    assert result.affected_rows == 1


def test_numeric_custom_fill_rejects_text() -> None:
    df = pd.DataFrame({"score": [1.0, None]})

    with pytest.raises(InvalidParameterError):
        apply_cleaning(df, _fill("score", "custom", "zero"), next_version=1)


def test_numeric_custom_fill_rejects_infinity() -> None:
    df = pd.DataFrame({"score": [1.0, None]})

    with pytest.raises(InvalidParameterError):
        apply_cleaning(df, _fill("score", "custom", float("inf")), next_version=1)


def test_categorical_mode_fill() -> None:
    df = pd.DataFrame({"city": ["NYC", "LA", "NYC", None]})

    cleaned, result = apply_cleaning(df, _fill("city", "mode"), next_version=1)

    assert cleaned["city"].tolist() == ["NYC", "LA", "NYC", "NYC"]
    assert result.affected_rows == 1


def test_mode_ties_resolve_deterministically() -> None:
    df = pd.DataFrame({"city": ["b", "a", None]})

    cleaned, _ = apply_cleaning(df, _fill("city", "mode"), next_version=1)

    assert cleaned["city"].iloc[2] == "a"


def test_categorical_custom_fill() -> None:
    df = pd.DataFrame({"city": ["NYC", None]})

    cleaned, _ = apply_cleaning(df, _fill("city", "custom", "Unknown"), next_version=1)

    assert cleaned["city"].tolist() == ["NYC", "Unknown"]


def test_categorical_custom_fill_rejects_empty_text() -> None:
    df = pd.DataFrame({"city": ["NYC", None]})

    with pytest.raises(InvalidParameterError):
        apply_cleaning(df, _fill("city", "custom", "   "), next_version=1)


def test_remove_rows_with_missing_value() -> None:
    df = pd.DataFrame({"a": [1.0, None, 3.0], "b": ["x", "y", "z"]})

    cleaned, result = apply_cleaning(df, _fill("a", "remove_rows"), next_version=1)

    assert cleaned["b"].tolist() == ["x", "z"]
    assert result.affected_rows == 1
    assert result.rows_before == 3
    assert result.rows_after == 2


def test_mean_is_rejected_for_categorical_column() -> None:
    df = pd.DataFrame({"city": ["NYC", None]})

    with pytest.raises(IncompatibleColumnTypeError) as exc_info:
        apply_cleaning(df, _fill("city", "mean"), next_version=1)

    assert "text" in exc_info.value.message.lower() or "categorical" in exc_info.value.message.lower()


def test_mode_is_rejected_for_numeric_column() -> None:
    df = pd.DataFrame({"age": [1.0, None]})

    with pytest.raises(IncompatibleColumnTypeError):
        apply_cleaning(df, _fill("age", "mode"), next_version=1)


def test_all_missing_numeric_column_cannot_take_a_mean() -> None:
    df = pd.DataFrame({"x": pd.array([None, None], dtype="float64")})

    with pytest.raises(InsufficientDataError):
        apply_cleaning(df, _fill("x", "mean"), next_version=1)


def test_all_missing_column_can_still_take_a_custom_value() -> None:
    df = pd.DataFrame({"x": pd.array([None, None], dtype="float64")})

    cleaned, result = apply_cleaning(df, _fill("x", "custom", 7), next_version=1)

    assert cleaned["x"].tolist() == [7.0, 7.0]
    assert result.affected_rows == 2


def test_fill_without_missing_values_is_a_noop() -> None:
    df = pd.DataFrame({"x": [1.0, 2.0]})

    with pytest.raises(NoOpTransformationError):
        apply_cleaning(df, _fill("x", "mean"), next_version=1)


def test_fill_on_unknown_column_is_rejected() -> None:
    df = pd.DataFrame({"x": [1.0, None]})

    with pytest.raises(ColumnNotFoundError):
        apply_cleaning(df, _fill("nope", "mean"), next_version=1)


def test_rejected_fill_does_not_change_input_frame() -> None:
    df = pd.DataFrame({"city": ["NYC", None]})
    before = df.copy(deep=True)

    with pytest.raises(IncompatibleColumnTypeError):
        apply_cleaning(df, _fill("city", "mean"), next_version=1)

    pd.testing.assert_frame_equal(df, before)


# --- duplicates ------------------------------------------------------------


def test_exact_duplicate_removal_keeps_first_occurrence() -> None:
    df = pd.DataFrame({"a": [1, 1, 2, 1], "b": ["x", "x", "y", "x"]})

    cleaned, result = apply_cleaning(
        df, RemoveDuplicatesRequest(operation="remove_duplicates"), next_version=1
    )

    assert len(cleaned) == 2
    assert result.affected_rows == 2
    assert result.rows_before == 4
    assert result.rows_after == 2
    assert list(cleaned.index) == [0, 1]


def test_duplicate_removal_without_duplicates_is_a_noop() -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})

    with pytest.raises(NoOpTransformationError):
        apply_cleaning(df, RemoveDuplicatesRequest(operation="remove_duplicates"), next_version=1)


def test_subset_duplicate_removal_compares_only_selected_columns() -> None:
    df = pd.DataFrame({"id": [1, 1, 2], "note": ["a", "b", "c"]})

    cleaned, result = apply_cleaning(
        df,
        RemoveDuplicatesRequest(operation="remove_duplicates", subset=["id"]),
        next_version=1,
    )

    assert cleaned["note"].tolist() == ["a", "c"]
    assert result.affected_rows == 1
    assert result.columns == ["id"]


def test_subset_with_unknown_column_is_rejected() -> None:
    df = pd.DataFrame({"id": [1, 1]})

    with pytest.raises(ColumnNotFoundError):
        apply_cleaning(
            df,
            RemoveDuplicatesRequest(operation="remove_duplicates", subset=["ghost"]),
            next_version=1,
        )


# --- text normalization ----------------------------------------------------


def test_trims_whitespace_in_text_column() -> None:
    df = pd.DataFrame({"city": ["  NYC ", "LA", "\tSF\n"]})

    cleaned, result = apply_cleaning(
        df,
        NormalizeTextRequest(operation="normalize_text", columns=["city"], blank_to_missing=False),
        next_version=1,
    )

    assert cleaned["city"].tolist() == ["NYC", "LA", "SF"]
    assert result.affected_rows == 2


def test_whitespace_only_values_become_missing() -> None:
    df = pd.DataFrame({"city": ["NYC", "   ", None, "LA"]})

    cleaned, result = apply_cleaning(
        df,
        NormalizeTextRequest(operation="normalize_text", columns=["city"], trim=False),
        next_version=1,
    )

    assert cleaned["city"].isna().tolist() == [False, True, True, False]
    assert result.affected_rows == 1


def test_trim_and_blank_normalization_combine() -> None:
    df = pd.DataFrame({"city": [" NYC ", "   ", "LA"]})

    cleaned, result = apply_cleaning(
        df,
        NormalizeTextRequest(operation="normalize_text", columns=["city"]),
        next_version=1,
    )

    assert cleaned["city"].iloc[0] == "NYC"
    assert pd.isna(cleaned["city"].iloc[1])
    assert result.affected_rows == 2


def test_text_normalization_leaves_numeric_columns_untouched() -> None:
    df = pd.DataFrame({"amount": [1.0, 2.0], "city": [" NYC", "LA"]})

    with pytest.raises(IncompatibleColumnTypeError):
        apply_cleaning(
            df,
            NormalizeTextRequest(operation="normalize_text", columns=["amount"]),
            next_version=1,
        )


def test_text_normalization_without_changes_is_a_noop() -> None:
    df = pd.DataFrame({"city": ["NYC", "LA"]})

    with pytest.raises(NoOpTransformationError):
        apply_cleaning(
            df,
            NormalizeTextRequest(operation="normalize_text", columns=["city"]),
            next_version=1,
        )


def test_text_normalization_needs_at_least_one_option() -> None:
    df = pd.DataFrame({"city": [" NYC"]})

    with pytest.raises(InvalidParameterError):
        apply_cleaning(
            df,
            NormalizeTextRequest(
                operation="normalize_text", columns=["city"], trim=False, blank_to_missing=False
            ),
            next_version=1,
        )


# --- drop / rename ---------------------------------------------------------


def test_drop_valid_column() -> None:
    df = pd.DataFrame({"keep": [1, 2], "drop_me": ["a", "b"]})

    cleaned, result = apply_cleaning(
        df, DropColumnsRequest(operation="drop_columns", columns=["drop_me"]), next_version=1
    )

    assert list(cleaned.columns) == ["keep"]
    assert result.columns == ["drop_me"]
    assert result.affected_rows == 2


def test_drop_nonexistent_column_is_rejected() -> None:
    df = pd.DataFrame({"keep": [1]})

    with pytest.raises(ColumnNotFoundError):
        apply_cleaning(
            df, DropColumnsRequest(operation="drop_columns", columns=["ghost"]), next_version=1
        )


def test_dropping_every_column_is_rejected() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})

    with pytest.raises(InvalidParameterError):
        apply_cleaning(
            df, DropColumnsRequest(operation="drop_columns", columns=["a", "b"]), next_version=1
        )


def test_rename_valid_column_preserves_data() -> None:
    df = pd.DataFrame({"old": [1, 2, 3]})

    cleaned, result = apply_cleaning(
        df,
        RenameColumnRequest(operation="rename_column", column="old", new_name="annual_salary"),
        next_version=1,
    )

    assert list(cleaned.columns) == ["annual_salary"]
    assert cleaned["annual_salary"].tolist() == [1, 2, 3]
    assert result.affected_rows == 0
    assert result.columns == ["old", "annual_salary"]


def test_rename_collision_is_rejected() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})

    with pytest.raises(InvalidParameterError) as exc_info:
        apply_cleaning(
            df,
            RenameColumnRequest(operation="rename_column", column="a", new_name="b"),
            next_version=1,
        )

    assert "already exists" in exc_info.value.message


def test_rename_to_empty_name_is_rejected() -> None:
    df = pd.DataFrame({"a": [1]})

    with pytest.raises(InvalidParameterError):
        apply_cleaning(
            df,
            RenameColumnRequest(operation="rename_column", column="a", new_name="   "),
            next_version=1,
        )


def test_rename_to_same_name_is_a_noop() -> None:
    df = pd.DataFrame({"a": [1]})

    with pytest.raises(NoOpTransformationError):
        apply_cleaning(
            df,
            RenameColumnRequest(operation="rename_column", column="a", new_name="a"),
            next_version=1,
        )


def test_rename_nonexistent_column_is_rejected() -> None:
    df = pd.DataFrame({"a": [1]})

    with pytest.raises(ColumnNotFoundError):
        apply_cleaning(
            df,
            RenameColumnRequest(operation="rename_column", column="ghost", new_name="b"),
            next_version=1,
        )


# --- type conversion -------------------------------------------------------


def test_valid_string_to_numeric_conversion() -> None:
    df = pd.DataFrame({"amount": ["10", "20.5", None]})

    cleaned, result = apply_cleaning(
        df,
        ConvertTypeRequest(operation="convert_type", column="amount", target="numeric"),
        next_version=1,
    )

    assert cleaned["amount"].iloc[0] == 10.0
    assert cleaned["amount"].iloc[1] == 20.5
    assert pd.isna(cleaned["amount"].iloc[2])
    assert result.affected_rows == 2


def test_invalid_string_to_numeric_fails_and_reports_count() -> None:
    df = pd.DataFrame({"amount": ["10", "unknown", "N/A ", "20"]})

    with pytest.raises(InvalidConversionError) as exc_info:
        apply_cleaning(
            df,
            ConvertTypeRequest(operation="convert_type", column="amount", target="numeric"),
            next_version=1,
        )

    assert "2 of 4" in exc_info.value.message
    assert "Nothing was changed" in exc_info.value.message


def test_numeric_string_with_thousands_separator_is_not_silently_converted() -> None:
    df = pd.DataFrame({"amount": ["1,000", "2"]})

    with pytest.raises(InvalidConversionError):
        apply_cleaning(
            df,
            ConvertTypeRequest(operation="convert_type", column="amount", target="numeric"),
            next_version=1,
        )


def test_valid_string_to_datetime_conversion() -> None:
    df = pd.DataFrame({"hired": ["January 15, 2022", "March 1, 2022", None]})

    cleaned, result = apply_cleaning(
        df,
        ConvertTypeRequest(operation="convert_type", column="hired", target="datetime"),
        next_version=1,
    )

    assert cleaned["hired"].iloc[0] == "2022-01-15"
    assert cleaned["hired"].iloc[1] == "2022-03-01"
    assert result.affected_rows == 2


def test_invalid_datetime_conversion_fails() -> None:
    df = pd.DataFrame({"hired": ["2022-01-01", "not a date", "2022-02-02"]})

    with pytest.raises(InvalidConversionError) as exc_info:
        apply_cleaning(
            df,
            ConvertTypeRequest(operation="convert_type", column="hired", target="datetime"),
            next_version=1,
        )

    assert "1 of 3" in exc_info.value.message


def test_numeric_to_string_conversion() -> None:
    df = pd.DataFrame({"code": [101, 202, None]})

    cleaned, result = apply_cleaning(
        df,
        ConvertTypeRequest(operation="convert_type", column="code", target="string"),
        next_version=1,
    )

    assert cleaned["code"].iloc[0] == "101"
    assert pd.isna(cleaned["code"].iloc[2])
    assert result.affected_rows == 2


def test_boolean_conversion_from_yes_no_and_one_zero() -> None:
    df = pd.DataFrame({"active": ["yes", "No", "1", None]})

    cleaned, result = apply_cleaning(
        df,
        ConvertTypeRequest(operation="convert_type", column="active", target="boolean"),
        next_version=1,
    )

    assert cleaned["active"].iloc[0] is True
    assert cleaned["active"].iloc[1] is False
    assert cleaned["active"].iloc[2] is True
    assert pd.isna(cleaned["active"].iloc[3])
    assert result.affected_rows == 3


def test_boolean_conversion_rejects_unrecognized_values() -> None:
    df = pd.DataFrame({"active": ["maybe", "yes"]})

    with pytest.raises(InvalidConversionError):
        apply_cleaning(
            df,
            ConvertTypeRequest(operation="convert_type", column="active", target="boolean"),
            next_version=1,
        )


def test_converting_to_the_same_kind_is_a_noop() -> None:
    df = pd.DataFrame({"amount": [1.0, 2.0]})

    with pytest.raises(NoOpTransformationError):
        apply_cleaning(
            df,
            ConvertTypeRequest(operation="convert_type", column="amount", target="numeric"),
            next_version=1,
        )


def test_failed_conversion_leaves_source_frame_unchanged() -> None:
    df = pd.DataFrame({"amount": ["10", "bad"]})
    before = df.copy(deep=True)

    with pytest.raises(InvalidConversionError):
        apply_cleaning(
            df,
            ConvertTypeRequest(operation="convert_type", column="amount", target="numeric"),
            next_version=1,
        )

    pd.testing.assert_frame_equal(df, before)


def test_numpy_nan_is_not_mistaken_for_text() -> None:
    df = pd.DataFrame({"amount": [np.nan, "3"]})

    cleaned, _ = apply_cleaning(
        df,
        ConvertTypeRequest(operation="convert_type", column="amount", target="numeric"),
        next_version=1,
    )

    assert cleaned["amount"].iloc[1] == 3.0
