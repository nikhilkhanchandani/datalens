"""Data quality analysis.

Detects concrete, explainable problems in an arbitrary DataFrame and turns
them into a deterministic 0-100 quality score. This module never modifies
the data it's given — it only observes and reports; cleaning/transformation
is a separate, explicitly user-initiated step (a later phase).

== The scoring algorithm ==

The score starts at 100 and loses points per *category* of problem, not per
individual issue — a dataset with the same minor problem repeated across
many columns should not be punished more harshly than one with a single
instance of a serious problem. Each category:

1. Computes a `raw_penalty` proportional to how *prevalent* the problem is
   (e.g. the percentage of all cells that are missing), using a fixed,
   documented rate.
2. Clamps that `raw_penalty` to a per-category maximum, so one dominant
   problem can never overwhelm the whole score.

The final score is `100 - sum(category penalties)`, clamped to [0, 100].
Every category that contributed a nonzero penalty appears in the response's
`breakdown` list with its exact penalty and the reason for it, so the
`breakdown` always sums to exactly `100 - score` — the score is never a
black box.

High-cardinality/identifier-column detection is intentionally
informational only (zero penalty): a column where every value is unique
(e.g. an order ID) is normal and expected, not a quality defect.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.sanitize import to_json_safe
from app.schemas.quality import IssueSeverity, QualityIssue, QualityReport, ScoreBreakdownEntry

# --- category penalty rates & caps (the whole scoring algorithm lives here) ---

_MISSING_PENALTY_RATE = 1.0  # points lost per 1% of all cells missing
_MISSING_MAX_PENALTY = 25.0
_MISSING_SEVERITY_MEDIUM = 5.0  # % missing in a single column
_MISSING_SEVERITY_HIGH = 20.0

_BLANK_STRING_PENALTY_RATE = 1.0  # points lost per 1% of all cells blank
_BLANK_STRING_MAX_PENALTY = 10.0
_BLANK_SEVERITY_MEDIUM = 5.0
_BLANK_SEVERITY_HIGH = 20.0

_DUPLICATE_PENALTY_RATE = 1.5  # points lost per 1% of rows duplicated
_DUPLICATE_MAX_PENALTY = 15.0
_DUPLICATE_SEVERITY_MEDIUM = 2.0
_DUPLICATE_SEVERITY_HIGH = 10.0

_CONSTANT_COLUMN_PENALTY_PER_COLUMN = 2.0
_CONSTANT_COLUMN_MAX_PENALTY = 10.0

_MOSTLY_EMPTY_THRESHOLD_PCT = 50.0  # a column is "mostly empty" at >= 50% missing
_MOSTLY_EMPTY_PENALTY_PER_COLUMN = 3.0
_MOSTLY_EMPTY_MAX_PENALTY = 15.0

_INFINITE_PENALTY_PER_COLUMN = 5.0
_INFINITE_MAX_PENALTY = 10.0

_MIXED_TYPE_MIN_MINORITY_FRACTION = 0.02  # ignore a single stray typo in a huge column
_MIXED_TYPE_PENALTY_PER_COLUMN = 4.0
_MIXED_TYPE_MAX_PENALTY = 10.0
_MIXED_TYPE_SEVERITY_MEDIUM = 5.0
_MIXED_TYPE_SEVERITY_HIGH = 20.0

# Cardinality checks are informational (penalty is always 0 — see module docstring).
# The row-count floors matter more than they might look: with few rows, an
# ordinary column (e.g. "age") can easily be 100% unique by pure chance —
# that's a small-sample coincidence, not evidence of being an identifier.
# Demanding a reasonably sized sample before trusting "every value is
# unique" as a signal avoids flagging columns like that in small datasets.
_HIGH_CARDINALITY_MIN_ROWS = 50
_HIGH_CARDINALITY_UNIQUE_FRACTION = 0.5
_IDENTIFIER_MIN_ROWS = 50


@dataclass
class _CategoryResult:
    name: str
    issues: list[QualityIssue]
    # Always a whole number of points: each category rounds its own penalty
    # to the nearest point *before* it's stored, so the integer penalties in
    # `breakdown` always sum to exactly `100 - score` — no separate rounding
    # step at the end that could drift the displayed breakdown out of sync
    # with the final score.
    penalty: int
    reason: str | None


def analyze_quality(df: pd.DataFrame) -> QualityReport:
    """Run every quality check once and derive the score from the same results.

    Computing issues and the score from a single pass per category (rather
    than detecting issues in one place and re-deriving numbers for scoring
    in another) guarantees the breakdown can never drift out of sync with
    the issues list.
    """
    categories = [
        _analyze_missing_values(df),
        _analyze_blank_strings(df),
        _analyze_duplicate_rows(df),
        _analyze_constant_columns(df),
        _analyze_mostly_empty_columns(df),
        _analyze_infinite_values(df),
        _analyze_mixed_types(df),
        _analyze_cardinality(df),
    ]

    issues = [issue for category in categories for issue in category.issues]
    breakdown = [
        ScoreBreakdownEntry(
            category=category.name,
            penalty=category.penalty,
            reason=category.reason,
        )
        for category in categories
        if category.penalty > 0 and category.reason is not None
    ]

    total_penalty = sum(category.penalty for category in categories)
    score = max(0, min(100, 100 - total_penalty))

    return QualityReport(score=score, breakdown=breakdown, issues=issues)


def _severity_from_percentage(pct: float, *, medium: float, high: float) -> IssueSeverity:
    if pct >= high:
        return "high"
    if pct >= medium:
        return "medium"
    return "low"


def _analyze_missing_values(df: pd.DataFrame) -> _CategoryResult:
    row_count = len(df)
    issues: list[QualityIssue] = []

    for column in df.columns:
        missing = int(df[column].isna().sum())
        if missing == 0:
            continue
        pct = round((missing / row_count) * 100, 2) if row_count else 0.0
        issues.append(
            QualityIssue(
                type="missing_values",
                column=str(column),
                severity=_severity_from_percentage(
                    pct, medium=_MISSING_SEVERITY_MEDIUM, high=_MISSING_SEVERITY_HIGH
                ),
                affected_rows=missing,
                percentage=pct,
                message=f"{pct}% of '{column}' values are missing.",
                suggested_action=(
                    "Review missing values; consider imputing (mean/median/mode) "
                    "or removing affected rows."
                ),
            )
        )

    total_cells = df.size
    overall_pct = round((df.isna().sum().sum() / total_cells) * 100, 2) if total_cells else 0.0
    penalty = round(min(_MISSING_MAX_PENALTY, overall_pct * _MISSING_PENALTY_RATE))
    reason = f"{overall_pct}% of all dataset values are missing." if penalty > 0 else None
    return _CategoryResult("missing_values", issues, penalty, reason)


def _count_blank_strings(series: pd.Series) -> int:
    if not pd.api.types.is_object_dtype(series):
        return 0
    non_null = series.dropna()
    if non_null.empty:
        return 0
    is_blank = non_null.astype(str).str.strip().eq("")
    return int(is_blank.sum())


def _analyze_blank_strings(df: pd.DataFrame) -> _CategoryResult:
    row_count = len(df)
    issues: list[QualityIssue] = []
    total_blank = 0

    for column in df.columns:
        blank = _count_blank_strings(df[column])
        if blank == 0:
            continue
        total_blank += blank
        pct = round((blank / row_count) * 100, 2) if row_count else 0.0
        issues.append(
            QualityIssue(
                type="blank_strings",
                column=str(column),
                severity=_severity_from_percentage(
                    pct, medium=_BLANK_SEVERITY_MEDIUM, high=_BLANK_SEVERITY_HIGH
                ),
                affected_rows=blank,
                percentage=pct,
                message=f"{blank} value(s) in '{column}' are blank or whitespace-only.",
                suggested_action=(
                    "Treat blank/whitespace-only text as missing, then review or impute."
                ),
            )
        )

    total_cells = df.size
    overall_pct = round((total_blank / total_cells) * 100, 2) if total_cells else 0.0
    penalty = round(min(_BLANK_STRING_MAX_PENALTY, overall_pct * _BLANK_STRING_PENALTY_RATE))
    reason = (
        f"{overall_pct}% of all dataset values are blank/whitespace-only text."
        if penalty > 0
        else None
    )
    return _CategoryResult("blank_strings", issues, penalty, reason)


def _analyze_duplicate_rows(df: pd.DataFrame) -> _CategoryResult:
    row_count = len(df)
    duplicate_count = int(df.duplicated().sum())
    if duplicate_count == 0 or row_count == 0:
        return _CategoryResult("duplicates", [], 0, None)

    pct = round((duplicate_count / row_count) * 100, 2)
    issue = QualityIssue(
        type="duplicate_rows",
        column=None,
        severity=_severity_from_percentage(
            pct, medium=_DUPLICATE_SEVERITY_MEDIUM, high=_DUPLICATE_SEVERITY_HIGH
        ),
        affected_rows=duplicate_count,
        percentage=pct,
        message=f"{duplicate_count} row(s) ({pct}%) are exact duplicates of another row.",
        suggested_action="Review and remove duplicate rows if they are not intentional repeats.",
    )
    penalty = round(min(_DUPLICATE_MAX_PENALTY, pct * _DUPLICATE_PENALTY_RATE))
    return _CategoryResult("duplicates", [issue], penalty, f"{pct}% of rows are duplicates.")


def _analyze_constant_columns(df: pd.DataFrame) -> _CategoryResult:
    row_count = len(df)
    issues: list[QualityIssue] = []

    for column in df.columns:
        non_null = df[column].dropna()
        # A fully-empty column is reported by `_analyze_mostly_empty_columns`
        # instead — it has no "repeated value" to report here.
        if non_null.empty or non_null.nunique() != 1:
            continue

        value = to_json_safe(non_null.iloc[0])
        affected = int(non_null.shape[0])
        issues.append(
            QualityIssue(
                type="constant_column",
                column=str(column),
                severity="medium",
                affected_rows=affected,
                percentage=round((affected / row_count) * 100, 2) if row_count else 0.0,
                message=f"'{column}' contains only a single repeated value ({value!r}).",
                suggested_action=(
                    "Consider dropping this column — it carries no distinguishing information."
                ),
            )
        )

    penalty = round(
        min(_CONSTANT_COLUMN_MAX_PENALTY, len(issues) * _CONSTANT_COLUMN_PENALTY_PER_COLUMN)
    )
    reason = (
        f"{len(issues)} column(s) contain only a single repeated value." if issues else None
    )
    return _CategoryResult("constant_columns", issues, penalty, reason)


def _analyze_mostly_empty_columns(df: pd.DataFrame) -> _CategoryResult:
    row_count = len(df)
    issues: list[QualityIssue] = []

    for column in df.columns:
        missing = int(df[column].isna().sum())
        pct = round((missing / row_count) * 100, 2) if row_count else 0.0
        if pct < _MOSTLY_EMPTY_THRESHOLD_PCT:
            continue
        issues.append(
            QualityIssue(
                type="mostly_empty_column",
                column=str(column),
                severity="high",
                affected_rows=missing,
                percentage=pct,
                message=f"'{column}' is {pct}% empty.",
                suggested_action=(
                    "Consider dropping this column unless the sparsity itself is meaningful."
                ),
            )
        )

    penalty = round(
        min(_MOSTLY_EMPTY_MAX_PENALTY, len(issues) * _MOSTLY_EMPTY_PENALTY_PER_COLUMN)
    )
    reason = (
        f"{len(issues)} column(s) are at least {_MOSTLY_EMPTY_THRESHOLD_PCT:.0f}% empty."
        if issues
        else None
    )
    return _CategoryResult("mostly_empty_columns", issues, penalty, reason)


def _count_infinite(series: pd.Series) -> int:
    # Only a float column can physically hold +/-inf (NumPy integer dtypes
    # have no representation for it), so there's nothing to check otherwise.
    if not pd.api.types.is_float_dtype(series):
        return 0
    return int(np.isinf(series.to_numpy()).sum())


def _analyze_infinite_values(df: pd.DataFrame) -> _CategoryResult:
    row_count = len(df)
    issues: list[QualityIssue] = []

    for column in df.columns:
        count = _count_infinite(df[column])
        if count == 0:
            continue
        pct = round((count / row_count) * 100, 2) if row_count else 0.0
        issues.append(
            QualityIssue(
                type="infinite_values",
                column=str(column),
                severity="high",
                affected_rows=count,
                percentage=pct,
                message=f"'{column}' contains {count} infinite value(s).",
                suggested_action=(
                    "Infinite values usually indicate a division-by-zero or overflow bug "
                    "upstream; review the source data and likely treat them as missing."
                ),
            )
        )

    penalty = round(min(_INFINITE_MAX_PENALTY, len(issues) * _INFINITE_PENALTY_PER_COLUMN))
    reason = f"{len(issues)} column(s) contain infinite values." if issues else None
    return _CategoryResult("infinite_values", issues, penalty, reason)


def _analyze_mixed_types(df: pd.DataFrame) -> _CategoryResult:
    """Flag object columns that mix numeric-looking and text values.

    Only object-dtype columns are checked — Pandas already gives a column a
    single consistent dtype (int64/float64/bool/...) whenever every value
    parses the same way, so a *mix* can only survive as `object`.
    """
    row_count = len(df)
    issues: list[QualityIssue] = []

    for column in df.columns:
        series = df[column]
        if not pd.api.types.is_object_dtype(series):
            continue

        non_null = series.dropna()
        if non_null.empty:
            continue

        numeric_like = pd.to_numeric(non_null, errors="coerce").notna()
        numeric_count = int(numeric_like.sum())
        text_count = len(non_null) - numeric_count
        minority_count = min(numeric_count, text_count)
        if minority_count == 0:
            continue

        minority_fraction = minority_count / len(non_null)
        if minority_fraction < _MIXED_TYPE_MIN_MINORITY_FRACTION:
            continue

        pct = round((minority_count / row_count) * 100, 2) if row_count else 0.0
        issues.append(
            QualityIssue(
                type="mixed_types",
                column=str(column),
                severity=_severity_from_percentage(
                    minority_fraction * 100,
                    medium=_MIXED_TYPE_SEVERITY_MEDIUM,
                    high=_MIXED_TYPE_SEVERITY_HIGH,
                ),
                affected_rows=minority_count,
                percentage=pct,
                message=(
                    f"'{column}' mixes numeric-looking and text values "
                    f"({numeric_count} numeric-like vs {text_count} text value(s))."
                ),
                suggested_action=(
                    "Standardize this column to a single type, or split inconsistent "
                    "values into a separate column."
                ),
            )
        )

    penalty = round(
        min(_MIXED_TYPE_MAX_PENALTY, len(issues) * _MIXED_TYPE_PENALTY_PER_COLUMN)
    )
    reason = f"{len(issues)} column(s) mix numeric and text values." if issues else None
    return _CategoryResult("mixed_types", issues, penalty, reason)


def _analyze_cardinality(df: pd.DataFrame) -> _CategoryResult:
    """Flag likely identifier / high-cardinality columns. Informational only.

    Continuous (float) and datetime columns are excluded: measurements like
    "temperature" or timestamps are *expected* to be highly unique
    row-to-row, so checking them here would just be noise.
    """
    row_count = len(df)
    issues: list[QualityIssue] = []

    for column in df.columns:
        series = df[column]
        if (
            pd.api.types.is_float_dtype(series)
            or pd.api.types.is_bool_dtype(series)
            or pd.api.types.is_datetime64_any_dtype(series)
        ):
            continue

        non_null = series.dropna()
        if non_null.empty:
            continue
        unique_count = int(non_null.nunique())

        if row_count >= _IDENTIFIER_MIN_ROWS and unique_count == row_count:
            issues.append(
                QualityIssue(
                    type="possible_identifier_column",
                    column=str(column),
                    severity="low",
                    affected_rows=row_count,
                    percentage=100.0,
                    message=(
                        f"Every value in '{column}' is unique — it may be an identifier column."
                    ),
                    suggested_action=(
                        "Identifier columns are usually not meaningful for statistical "
                        "analysis; consider excluding them from correlation/ML steps."
                    ),
                )
            )
            continue  # same underlying signal as high-cardinality — don't double-report

        if row_count >= _HIGH_CARDINALITY_MIN_ROWS:
            fraction_unique = unique_count / row_count
            if fraction_unique >= _HIGH_CARDINALITY_UNIQUE_FRACTION:
                issues.append(
                    QualityIssue(
                        type="high_cardinality_column",
                        column=str(column),
                        severity="low",
                        affected_rows=unique_count,
                        percentage=round(fraction_unique * 100, 2),
                        message=(
                            f"'{column}' has {unique_count} distinct values across "
                            f"{row_count} rows ({fraction_unique:.0%} unique)."
                        ),
                        suggested_action=(
                            "High-cardinality categorical columns are often identifiers or "
                            "free text; consider whether they belong in grouped analysis."
                        ),
                    )
                )

    # Cardinality is a descriptive signal, not a defect — never penalized.
    return _CategoryResult("cardinality", issues, 0, None)
