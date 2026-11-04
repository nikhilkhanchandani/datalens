"""Correlation analysis between numeric columns.

Measures how strongly pairs of numeric columns move together, using Pandas'
built-in `DataFrame.corr`, which implements both coefficients:

- Pearson: the correlation of the raw values — it measures *linear* association.
- Spearman: Pearson's correlation of the *ranks* of the values — it measures
  any consistent monotonic association and is less sensitive to outliers and
  skew.

Missing values are handled by pairwise deletion: each pair of columns is
compared using only the rows where both have usable values.

A correlation describes how two columns vary together. It does not show that
one causes the other, and this module never claims otherwise.
"""

from __future__ import annotations

import pandas as pd

from app.core.column_kind import infer_column_kind
from app.core.exceptions import InsufficientDataError, InvalidParameterError
from app.core.numeric import clean_numeric_series, numeric_values
from app.core.sanitize import safe_coefficient
from app.schemas.correlations import (
    CorrelationMethod,
    CorrelationReport,
    ExcludedColumn,
    StrongPair,
)

SUPPORTED_METHODS: tuple[str, ...] = ("pearson", "spearman")
STRONG_THRESHOLD = 0.7
DISCLAIMER = (
    "Correlation measures how columns vary together. It does not establish that "
    "one column causes another."
)


def analyze_correlations(df: pd.DataFrame, method: str) -> CorrelationReport:
    if method not in SUPPORTED_METHODS:
        raise InvalidParameterError(
            f"Unsupported correlation method '{method}'. Use one of: "
            f"{', '.join(SUPPORTED_METHODS)}."
        )

    usable, excluded = _select_usable_columns(df)
    if len(usable) < 2:
        raise InsufficientDataError(
            "Correlation needs at least two numeric columns with variation; "
            f"this dataset has {len(usable)}."
        )

    frame = pd.DataFrame({name: clean_numeric_series(df[name]) for name in usable})
    raw_matrix = frame.corr(method=method, min_periods=2)

    matrix = [
        [safe_coefficient(raw_matrix.loc[row, col]) for col in usable] for row in usable
    ]

    return CorrelationReport(
        method=_as_method(method),
        columns=usable,
        matrix=matrix,
        excluded_columns=excluded,
        strong_pairs=_strong_pairs(usable, matrix),
        strong_threshold=STRONG_THRESHOLD,
        disclaimer=DISCLAIMER,
    )


def _select_usable_columns(df: pd.DataFrame) -> tuple[list[str], list[ExcludedColumn]]:
    usable: list[str] = []
    excluded: list[ExcludedColumn] = []

    for name in df.columns:
        series = df[name]
        column = str(name)
        if infer_column_kind(series) != "numeric":
            continue

        values = numeric_values(series)
        if len(values) < 2:
            excluded.append(
                ExcludedColumn(name=column, reason="fewer than two usable values")
            )
        elif values.nunique() == 1:
            excluded.append(
                ExcludedColumn(
                    name=column,
                    reason="constant column: correlation is undefined without variation",
                )
            )
        else:
            usable.append(column)

    return usable, excluded


def _strong_pairs(columns: list[str], matrix: list[list[float | None]]) -> list[StrongPair]:
    pairs: list[StrongPair] = []
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            r = matrix[i][j]
            if r is None or abs(r) < STRONG_THRESHOLD:
                continue
            pairs.append(
                StrongPair(
                    x=columns[i],
                    y=columns[j],
                    r=r,
                    direction="positive" if r > 0 else "negative",
                )
            )
    return sorted(pairs, key=lambda pair: abs(pair.r), reverse=True)


def _as_method(method: str) -> CorrelationMethod:
    return "pearson" if method == "pearson" else "spearman"
