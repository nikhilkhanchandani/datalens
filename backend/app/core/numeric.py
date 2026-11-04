"""Shared numeric and datetime value extraction.

Every analysis that works on a column (statistics, histograms, scatter plots,
correlations, trends) needs the same cleaned view of it: coerced to numbers,
with infinities and missing values removed. Centralizing that here keeps the
definition of "a usable observation" identical across every service.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def clean_numeric_series(series: pd.Series) -> pd.Series:
    """Coerce a column to floats, keeping its index, with unusable values as NaN.

    Non-numeric text becomes NaN, and +/-inf is treated as unusable (it would
    break JSON and make means/variances meaningless). Keeping the original
    index lets callers pair two columns row by row.
    """
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.replace([np.inf, -np.inf], np.nan)


def numeric_values(series: pd.Series) -> pd.Series:
    """Return the usable numeric observations of a column, without missing values.

    Its length is the number of usable observations.
    """
    return clean_numeric_series(series).dropna()


def parse_datetime_values(series: pd.Series) -> pd.Series:
    """Return the successfully parsed timestamps of a column, without missing values.

    `pd.read_csv` never parses dates, so text date columns are parsed here.
    Values that cannot be parsed are dropped rather than guessed at.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.dropna()
    return pd.to_datetime(
        series.dropna().astype(str), errors="coerce", format="mixed"
    ).dropna()
