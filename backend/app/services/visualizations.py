"""Chart-data preparation for exploratory visualizations.

Every function here turns a DataFrame into the small, aggregated data one chart
needs, so the browser never receives a whole column. Each function validates
its inputs first (column exists, column kind is compatible, parameters are in
range) and raises a `DataLensError` subclass otherwise.

Documented limits (all deliberate, all bounded):

- Histogram: `np.histogram` bins, default edges from NumPy's "auto" rule
  (the smaller of Sturges and Freedman-Diaconis bin counts), capped at
  MAX_HISTOGRAM_BINS. Counts are returned, never raw values.
- Categorical: Top N categories by count (ties broken alphabetically so output
  is deterministic), with everything else summed into one "Other" bucket.
- Scatter: at most MAX_SCATTER_POINTS points, drawn by a seeded random sample,
  so refreshing the same chart returns the same points.
- Distribution: five-number summary (min, Q1, median, Q3, max) and IQR.
- Datetime trend: values averaged per calendar period, with the period chosen
  so the chart has at most MAX_TREND_POINTS points.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.core.column_kind import ColumnKind, infer_column_kind
from app.core.exceptions import (
    ColumnNotFoundError,
    IncompatibleColumnTypeError,
    InsufficientDataError,
    InvalidParameterError,
)
from app.core.numeric import clean_numeric_series, numeric_values, parse_datetime_values
from app.core.sanitize import safe_coefficient
from app.schemas.visualizations import (
    CategoricalFrequencies,
    DatetimeTrend,
    DistributionSummary,
    FrequencyItem,
    HistogramBin,
    HistogramData,
    ScatterData,
    ScatterPoint,
    TrendPoint,
)

MAX_HISTOGRAM_BINS = 100
MAX_CATEGORY_TOP_N = 100
DEFAULT_CATEGORY_TOP_N = 20
MAX_SCATTER_POINTS = 2000
SCATTER_SAMPLE_SEED = 42
MAX_TREND_POINTS = 120
OTHER_LABEL = "Other"


def histogram(df: pd.DataFrame, column: str, bins: int | None) -> HistogramData:
    series = _require_column(df, column, {"numeric"})
    if bins is not None and not 1 <= bins <= MAX_HISTOGRAM_BINS:
        raise InvalidParameterError(
            f"bins must be between 1 and {MAX_HISTOGRAM_BINS}; got {bins}."
        )

    values = numeric_values(series)
    if values.empty:
        raise InsufficientDataError(f"Column '{column}' has no usable numeric values.")

    if bins is None:
        edges = np.histogram_bin_edges(values, bins="auto")
        strategy = "auto (smaller of Sturges and Freedman-Diaconis counts)"
        if len(edges) - 1 > MAX_HISTOGRAM_BINS:
            edges = np.histogram_bin_edges(values, bins=MAX_HISTOGRAM_BINS)
            strategy = f"auto, capped at {MAX_HISTOGRAM_BINS} bins"
    else:
        edges = np.histogram_bin_edges(values, bins=bins)
        strategy = f"fixed at {bins} bins"

    counts, _ = np.histogram(values, bins=edges)

    return HistogramData(
        column=column,
        bins=[
            HistogramBin(start=float(edges[i]), end=float(edges[i + 1]), count=int(counts[i]))
            for i in range(len(counts))
        ],
        bin_strategy=strategy,
        total_observations=len(values),
        missing_count=int(series.isna().sum()),
        infinite_count=int(np.isinf(pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)).sum()),
        is_constant=bool(values.nunique() == 1),
    )


def categorical_frequencies(
    df: pd.DataFrame, column: str, top_n: int = DEFAULT_CATEGORY_TOP_N
) -> CategoricalFrequencies:
    series = _require_column(df, column, {"categorical", "boolean"})
    if not 1 <= top_n <= MAX_CATEGORY_TOP_N:
        raise InvalidParameterError(
            f"top_n must be between 1 and {MAX_CATEGORY_TOP_N}; got {top_n}."
        )

    non_null = series.dropna().astype(str)
    if non_null.empty:
        raise InsufficientDataError(f"Column '{column}' has no non-missing values.")

    counts = (
        non_null.value_counts()
        .rename_axis("value")
        .reset_index(name="count")
        .sort_values(["count", "value"], ascending=[False, True], kind="mergesort")
    )
    total = int(counts["count"].sum())

    head = counts.head(top_n)
    items = [
        FrequencyItem(
            value=str(value),
            count=int(count),
            percentage=round(int(count) / total * 100, 2),
            is_other=False,
        )
        for value, count in zip(head["value"], head["count"])
    ]

    rest = counts.iloc[top_n:]
    truncated = not rest.empty
    if truncated:
        other_count = int(rest["count"].sum())
        items.append(
            FrequencyItem(
                value=OTHER_LABEL,
                count=other_count,
                percentage=round(other_count / total * 100, 2),
                is_other=True,
            )
        )

    return CategoricalFrequencies(
        column=column,
        total_count=total,
        missing_count=int(series.isna().sum()),
        unique_count=len(counts),
        top_n=top_n,
        truncated=truncated,
        items=items,
    )


def scatter(df: pd.DataFrame, x_column: str, y_column: str) -> ScatterData:
    if x_column == y_column:
        raise InvalidParameterError("Choose two different columns for the X and Y axes.")

    x_series = _require_column(df, x_column, {"numeric"})
    y_series = _require_column(df, y_column, {"numeric"})

    pairs = pd.DataFrame(
        {"x": clean_numeric_series(x_series), "y": clean_numeric_series(y_series)}
    ).dropna()
    if len(pairs) < 2:
        raise InsufficientDataError(
            "The chosen columns need at least two rows where both have usable values."
        )

    total = len(pairs)
    pearson_r = safe_coefficient(pairs["x"].corr(pairs["y"]))

    # Sampling happens after the correlation, so the reported r always describes
    # every usable row, not just the drawn points.
    sampled_pairs = pairs
    if total > MAX_SCATTER_POINTS:
        sampled_pairs = pairs.sample(n=MAX_SCATTER_POINTS, random_state=SCATTER_SAMPLE_SEED)
        sampled_pairs = sampled_pairs.sort_index()

    return ScatterData(
        x_column=x_column,
        y_column=y_column,
        total_points=total,
        returned_points=len(sampled_pairs),
        sampled=total > MAX_SCATTER_POINTS,
        max_points=MAX_SCATTER_POINTS,
        pearson_r=pearson_r,
        points=[ScatterPoint(x=float(x), y=float(y)) for x, y in sampled_pairs.itertuples(index=False)],
    )


def distribution_summary(df: pd.DataFrame, column: str) -> DistributionSummary:
    series = _require_column(df, column, {"numeric"})
    values = numeric_values(series)
    if values.empty:
        raise InsufficientDataError(f"Column '{column}' has no usable numeric values.")

    minimum, q1, median, q3, maximum = (
        float(v) for v in values.quantile([0.0, 0.25, 0.5, 0.75, 1.0]).tolist()
    )
    return DistributionSummary(
        column=column,
        count=len(values),
        missing_count=int(series.isna().sum()),
        minimum=minimum,
        q1=q1,
        median=median,
        q3=q3,
        maximum=maximum,
        iqr=q3 - q1,
    )


def datetime_trend(df: pd.DataFrame, datetime_column: str, value_column: str) -> DatetimeTrend:
    if datetime_column == value_column:
        raise InvalidParameterError("Choose different columns for time and value.")

    time_series = _require_column(df, datetime_column, {"datetime"})
    value_series = _require_column(df, value_column, {"numeric"})

    times = parse_datetime_values(time_series).rename("time")
    values = clean_numeric_series(value_series).rename("value")
    joined = pd.concat([times, values], axis=1, join="inner").dropna()
    if joined.empty:
        raise InsufficientDataError(
            "No rows have both a parseable date and a usable numeric value."
        )

    granularity = _choose_granularity(joined["time"])
    periods = joined["time"].dt.to_period(granularity["pandas_code"])
    grouped = joined.groupby(periods)["value"].agg(["mean", "min", "max", "count"])

    return DatetimeTrend(
        datetime_column=datetime_column,
        value_column=value_column,
        granularity=granularity["label"],
        total_observations=len(joined),
        points=[
            TrendPoint(
                period_start=period.start_time.isoformat(),
                mean=float(row["mean"]),
                minimum=float(row["min"]),
                maximum=float(row["max"]),
                count=int(row["count"]),
            )
            for period, row in grouped.iterrows()
        ],
    )


_GRANULARITIES: tuple[tuple[str, str, float], ...] = (
    ("D", "day", 1.0),
    ("W", "week", 7.0),
    ("M", "month", 30.44),
    ("Q", "quarter", 91.31),
    ("Y", "year", 365.25),
)


def _choose_granularity(times: pd.Series) -> dict[str, str]:
    """Pick the finest calendar period that keeps the chart within MAX_TREND_POINTS."""
    span_days = (times.max() - times.min()).total_seconds() / 86400
    for code, label, period_days in _GRANULARITIES:
        estimated_points = math.floor(span_days / period_days) + 1
        if estimated_points <= MAX_TREND_POINTS:
            return {"pandas_code": code, "label": label}
    return {"pandas_code": "Y", "label": "year"}


def _require_column(df: pd.DataFrame, name: str, allowed_kinds: set[ColumnKind]) -> pd.Series:
    if name not in df.columns:
        raise ColumnNotFoundError(f"Column '{name}' does not exist in this dataset.")

    series = df[name]
    kind = infer_column_kind(series)
    if kind not in allowed_kinds:
        needed = " or ".join(sorted(allowed_kinds))
        raise IncompatibleColumnTypeError(
            f"Column '{name}' is {kind}; this chart needs {needed} data."
        )
    return series
