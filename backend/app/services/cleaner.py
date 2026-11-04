"""Pure, explicit cleaning transformations.

Each function takes a DataFrame and a validated request, and returns a *new*
DataFrame plus a structured result. Nothing here touches the disk or the
database; `services/transformations.py` owns persistence. Keeping this layer
pure means every rule can be tested with a DataFrame and no files.

Every check runs before any data is produced. Validation failures raise a
`DataLensError` subclass and nothing is returned, so a rejected request can't
leave a half-cleaned frame behind.

Rules that depend on column type:

- Numeric columns: mean, median, custom number, remove rows.
- Text (categorical) and true/false columns: mode, custom text, remove rows.
- Datetime columns: custom date text, remove rows.
- Text cleanup applies to text columns only; other columns are refused.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from app.core.column_kind import ColumnKind, infer_column_kind
from app.core.exceptions import (
    ColumnNotFoundError,
    IncompatibleColumnTypeError,
    InsufficientDataError,
    InvalidConversionError,
    InvalidParameterError,
    NoOpTransformationError,
)
from app.core.numeric import clean_numeric_series
from app.schemas.cleaning import (
    CleaningRequest,
    ConvertTypeRequest,
    DropColumnsRequest,
    FillMissingRequest,
    NormalizeTextRequest,
    RemoveDuplicatesRequest,
    RenameColumnRequest,
    TransformationResult,
)

_FILL_STRATEGIES_BY_KIND: dict[ColumnKind, set[str]] = {
    "numeric": {"mean", "median", "custom", "remove_rows"},
    "categorical": {"mode", "custom", "remove_rows"},
    "boolean": {"mode", "custom", "remove_rows"},
    "datetime": {"custom", "remove_rows"},
}
_STRATEGY_NEEDS: dict[str, str] = {
    "mean": "numeric",
    "median": "numeric",
    "mode": "text or true/false",
    "custom": "a value of the right type",
    "remove_rows": "any",
}
_TARGET_KIND: dict[str, ColumnKind] = {
    "numeric": "numeric",
    "datetime": "datetime",
    "boolean": "boolean",
    "string": "categorical",
}
_TRUE_TOKENS = {"true", "yes", "y", "t", "1", "1.0"}
_FALSE_TOKENS = {"false", "no", "n", "f", "0", "0.0"}
_EXAMPLES_SHOWN = 3


def apply_cleaning(
    df: pd.DataFrame, request: CleaningRequest, next_version: int
) -> tuple[pd.DataFrame, TransformationResult]:
    """Apply one validated request and describe what changed."""
    if isinstance(request, FillMissingRequest):
        return _fill_missing(df, request, next_version)
    if isinstance(request, RemoveDuplicatesRequest):
        return _remove_duplicates(df, request, next_version)
    if isinstance(request, NormalizeTextRequest):
        return _normalize_text(df, request, next_version)
    if isinstance(request, DropColumnsRequest):
        return _drop_columns(df, request, next_version)
    if isinstance(request, RenameColumnRequest):
        return _rename_column(df, request, next_version)
    if isinstance(request, ConvertTypeRequest):
        return _convert_type(df, request, next_version)
    raise InvalidParameterError(f"Unsupported operation: {request.operation}.")


def _require_column(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        raise ColumnNotFoundError(f"Column '{name}' does not exist in this dataset.")
    return df[name]


def _result(
    df_before: pd.DataFrame,
    *,
    operation: str,
    next_version: int,
    affected_rows: int,
    rows_after: int,
    summary: str,
    column: str | None = None,
    strategy: str | None = None,
    columns: list[str] | None = None,
) -> TransformationResult:
    return TransformationResult(
        operation=operation,
        column=column,
        strategy=strategy,
        columns=columns or [],
        affected_rows=affected_rows,
        rows_before=len(df_before),
        rows_after=rows_after,
        summary=summary,
        working_version=next_version,
    )


# --- missing values --------------------------------------------------------


def _fill_missing(
    df: pd.DataFrame, req: FillMissingRequest, next_version: int
) -> tuple[pd.DataFrame, TransformationResult]:
    series = _require_column(df, req.column)
    kind = infer_column_kind(series)
    allowed = _FILL_STRATEGIES_BY_KIND[kind]
    if req.strategy not in allowed:
        raise IncompatibleColumnTypeError(
            f"'{req.column}' is {kind} data, so the '{req.strategy}' strategy doesn't apply. "
            f"Use one of: {', '.join(sorted(allowed))}."
        )

    missing = series.isna()
    missing_count = int(missing.sum())
    if missing_count == 0:
        raise NoOpTransformationError(f"'{req.column}' has no missing values; nothing to fill.")

    if req.strategy == "remove_rows":
        cleaned = df.loc[~missing].reset_index(drop=True)
        return cleaned, _result(
            df,
            operation="fill_missing",
            column=req.column,
            strategy="remove_rows",
            next_version=next_version,
            affected_rows=missing_count,
            rows_after=len(cleaned),
            summary=f"Removed {missing_count} row(s) where '{req.column}' was missing.",
        )

    fill_value = _fill_value(series, kind, req)
    cleaned = df.copy()
    cleaned[req.column] = series.fillna(fill_value)
    return cleaned, _result(
        df,
        operation="fill_missing",
        column=req.column,
        strategy=req.strategy,
        next_version=next_version,
        affected_rows=missing_count,
        rows_after=len(cleaned),
        summary=(
            f"Filled {missing_count} missing value(s) in '{req.column}' "
            f"using {req.strategy} ({_describe_value(fill_value)})."
        ),
    )


def _fill_value(series: pd.Series, kind: ColumnKind, req: FillMissingRequest) -> Any:
    if req.strategy in ("mean", "median"):
        usable = clean_numeric_series(series).dropna()
        if usable.empty:
            raise InsufficientDataError(
                f"'{req.column}' has no usable numeric values to compute a {req.strategy} from. "
                "Use a custom value instead."
            )
        return float(usable.mean() if req.strategy == "mean" else usable.median())

    if req.strategy == "mode":
        observed = series.dropna()
        if observed.empty:
            raise InsufficientDataError(
                f"'{req.column}' has no non-missing values to take a mode from. "
                "Use a custom value instead."
            )
        # Ties resolve to the alphabetically/numerically smallest value, so
        # the same data always produces the same fill.
        return observed.mode().sort_values().iloc[0]

    return _custom_fill_value(req.column, kind, req.value)


def _custom_fill_value(column: str, kind: ColumnKind, value: Any) -> Any:
    if value is None:
        raise InvalidParameterError("A custom fill needs a value.")

    if kind == "numeric":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidParameterError(
                f"'{column}' is numeric, so the custom fill must be a number, not text."
            )
        if not math.isfinite(float(value)):
            raise InvalidParameterError("The custom fill must be a finite number.")
        return float(value)

    if kind == "boolean":
        if not isinstance(value, bool):
            raise InvalidParameterError(
                f"'{column}' is true/false data, so the custom fill must be true or false."
            )
        return value

    if kind == "datetime":
        if not isinstance(value, str) or pd.isna(pd.to_datetime(value, errors="coerce")):
            raise InvalidParameterError(
                f"'{column}' holds dates, so the custom fill must be a date such as 2024-01-31."
            )
        return value

    # categorical
    if not isinstance(value, str) or not value.strip():
        raise InvalidParameterError(
            f"'{column}' is text, so the custom fill must be a non-empty string."
        )
    return value


def _describe_value(value: Any) -> str:
    if isinstance(value, float):
        return f"value {value:g}"
    return f"value '{value}'" if isinstance(value, str) else f"value {value}"


# --- duplicates ------------------------------------------------------------


def _remove_duplicates(
    df: pd.DataFrame, req: RemoveDuplicatesRequest, next_version: int
) -> tuple[pd.DataFrame, TransformationResult]:
    subset = list(dict.fromkeys(req.subset)) if req.subset else None
    for name in subset or []:
        _require_column(df, name)

    duplicate = df.duplicated(subset=subset, keep="first")
    duplicate_count = int(duplicate.sum())
    if duplicate_count == 0:
        scope = f" across {', '.join(subset)}" if subset else ""
        raise NoOpTransformationError(f"No duplicate rows found{scope}; nothing to remove.")

    cleaned = df.loc[~duplicate].reset_index(drop=True)
    scope = f" (compared on {', '.join(subset)})" if subset else ""
    return cleaned, _result(
        df,
        operation="remove_duplicates",
        next_version=next_version,
        affected_rows=duplicate_count,
        rows_after=len(cleaned),
        columns=subset or [],
        summary=f"Removed {duplicate_count} duplicate row(s){scope}; kept the first occurrence.",
    )


# --- text normalization ----------------------------------------------------


def _normalize_text(
    df: pd.DataFrame, req: NormalizeTextRequest, next_version: int
) -> tuple[pd.DataFrame, TransformationResult]:
    if not (req.trim or req.blank_to_missing):
        raise InvalidParameterError("Enable at least one of trim or blank-to-missing.")

    columns = list(dict.fromkeys(req.columns))
    for name in columns:
        series = _require_column(df, name)
        kind = infer_column_kind(series)
        if kind != "categorical":
            raise IncompatibleColumnTypeError(
                f"'{name}' is {kind} data; text cleanup only applies to text columns."
            )

    cleaned = df.copy()
    changed_rows = np.zeros(len(df), dtype=bool)
    for name in columns:
        before = cleaned[name]
        after = before.map(lambda v: _clean_text(v, req.trim, req.blank_to_missing))
        changed = np.array([not _same(a, b) for a, b in zip(before, after)], dtype=bool)
        changed_rows |= changed
        cleaned[name] = after

    affected = int(changed_rows.sum())
    if affected == 0:
        raise NoOpTransformationError("Those columns have no extra whitespace or blank cells to clean.")

    actions = []
    if req.trim:
        actions.append("trimmed surrounding whitespace")
    if req.blank_to_missing:
        actions.append("turned blank cells into missing values")
    return cleaned, _result(
        df,
        operation="normalize_text",
        next_version=next_version,
        affected_rows=affected,
        rows_after=len(cleaned),
        columns=columns,
        summary=f"In {', '.join(columns)}: {' and '.join(actions)} ({affected} row(s) changed).",
    )


def _clean_text(value: Any, trim: bool, blank_to_missing: bool) -> Any:
    if not isinstance(value, str):
        return value
    if blank_to_missing and value.strip() == "":
        return None
    return value.strip() if trim else value


def _same(a: Any, b: Any) -> bool:
    if pd.isna(a) and pd.isna(b):
        return True
    return a == b


# --- drop / rename ---------------------------------------------------------


def _drop_columns(
    df: pd.DataFrame, req: DropColumnsRequest, next_version: int
) -> tuple[pd.DataFrame, TransformationResult]:
    columns = list(dict.fromkeys(req.columns))
    for name in columns:
        _require_column(df, name)
    if len(columns) >= len(df.columns):
        raise InvalidParameterError("At least one column must remain after dropping.")

    cleaned = df.drop(columns=columns)
    return cleaned, _result(
        df,
        operation="drop_columns",
        next_version=next_version,
        affected_rows=len(df),
        rows_after=len(cleaned),
        columns=columns,
        summary=f"Dropped column(s): {', '.join(columns)}.",
    )


def _rename_column(
    df: pd.DataFrame, req: RenameColumnRequest, next_version: int
) -> tuple[pd.DataFrame, TransformationResult]:
    _require_column(df, req.column)
    new_name = req.new_name.strip()
    if not new_name:
        raise InvalidParameterError("The new column name can't be empty.")
    if "\n" in new_name or "\r" in new_name:
        raise InvalidParameterError("Column names can't contain line breaks.")
    if new_name == req.column:
        raise NoOpTransformationError(f"The column is already named '{new_name}'.")
    if new_name in df.columns:
        raise InvalidParameterError(f"A column named '{new_name}' already exists.")

    cleaned = df.rename(columns={req.column: new_name})
    return cleaned, _result(
        df,
        operation="rename_column",
        column=req.column,
        next_version=next_version,
        affected_rows=0,
        rows_after=len(cleaned),
        columns=[req.column, new_name],
        summary=f"Renamed '{req.column}' to '{new_name}'. No data changed.",
    )


# --- type conversion -------------------------------------------------------


def _convert_type(
    df: pd.DataFrame, req: ConvertTypeRequest, next_version: int
) -> tuple[pd.DataFrame, TransformationResult]:
    series = _require_column(df, req.column)
    kind = infer_column_kind(series)
    if kind == _TARGET_KIND[req.target]:
        raise NoOpTransformationError(f"'{req.column}' is already {req.target} data.")

    non_null = series.dropna()
    if non_null.empty:
        raise InsufficientDataError(f"'{req.column}' has no values to convert.")

    cleaned = df.copy()
    if req.target == "numeric":
        _to_numeric_strict(req.column, non_null)
        cleaned[req.column] = pd.to_numeric(series, errors="coerce")
    elif req.target == "datetime":
        cleaned[req.column] = _to_datetime_text(req.column, series, non_null)
    elif req.target == "boolean":
        cleaned[req.column] = _to_boolean(req.column, series, non_null)
    else:  # string
        cleaned[req.column] = series.astype(object)
        cleaned.loc[non_null.index, req.column] = non_null.map(_as_text)

    return cleaned, _result(
        df,
        operation="convert_type",
        column=req.column,
        strategy=req.target,
        next_version=next_version,
        affected_rows=len(non_null),
        rows_after=len(cleaned),
        summary=f"Converted '{req.column}' from {kind} to {req.target} ({len(non_null)} value(s)).",
    )


def _as_text(value: Any) -> str:
    # Pandas stores a column with a missing value as float, so 101 arrives as 101.0.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _examples(values: pd.Series) -> str:
    shown = [repr(str(v)) for v in values.head(_EXAMPLES_SHOWN)]
    return ", ".join(shown)


def _to_numeric_strict(column: str, non_null: pd.Series) -> pd.Series:
    coerced = pd.to_numeric(non_null, errors="coerce")
    failed = coerced.isna() | np.isinf(coerced.fillna(0.0))
    if failed.any():
        bad = non_null[failed]
        raise InvalidConversionError(
            f"{len(bad)} of {len(non_null)} values in '{column}' can't be read as numbers "
            f"(for example {_examples(bad)}). Nothing was changed."
        )
    return coerced


def _to_datetime_text(column: str, series: pd.Series, non_null: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(non_null.astype(str), errors="coerce", format="mixed")
    failed = parsed.isna()
    if failed.any():
        bad = non_null[failed]
        raise InvalidConversionError(
            f"{len(bad)} of {len(non_null)} values in '{column}' aren't recognizable dates "
            f"(for example {_examples(bad)}). Nothing was changed."
        )
    all_midnight = bool((parsed == parsed.dt.normalize()).all())
    fmt = "%Y-%m-%d" if all_midnight else "%Y-%m-%d %H:%M:%S"
    out = series.astype(object)
    out.loc[non_null.index] = parsed.dt.strftime(fmt)
    return out


def _to_boolean(column: str, series: pd.Series, non_null: pd.Series) -> pd.Series:
    tokens = non_null.map(lambda v: str(v).strip().lower())
    recognized = tokens.isin(_TRUE_TOKENS | _FALSE_TOKENS)
    if not recognized.all():
        bad = non_null[~recognized]
        raise InvalidConversionError(
            f"{len(bad)} of {len(non_null)} values in '{column}' aren't true/false values "
            f"(for example {_examples(bad)}). Use true/false, yes/no, or 1/0. Nothing was changed."
        )
    out = series.astype(object)
    out.loc[non_null.index] = tokens.isin(_TRUE_TOKENS).astype(bool).to_numpy()
    return out
