"""Correlation and exploratory-visualization endpoints for a dataset.

One narrow endpoint per chart, rather than a single endpoint returning every
visualization: the browser requests only what the user is looking at, and each
response carries only the data that chart needs. Route handlers stay thin —
validation and calculation live in `services/correlations.py` and
`services/visualizations.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_dataset_or_404, load_dataframe
from app.db.session import get_db
from app.schemas.correlations import CorrelationReport
from app.schemas.visualizations import (
    CategoricalFrequencies,
    DatetimeTrend,
    DistributionSummary,
    HistogramData,
    ScatterData,
)
from app.services import correlations, visualizations

router = APIRouter(prefix="/datasets", tags=["analysis"])


@router.get("/{dataset_id}/correlations", response_model=CorrelationReport)
def get_correlations(
    dataset_id: str,
    method: str = Query("pearson", description="pearson or spearman"),
    db: Session = Depends(get_db),
) -> CorrelationReport:
    dataframe = load_dataframe(get_dataset_or_404(dataset_id, db))
    return correlations.analyze_correlations(dataframe, method)


@router.get("/{dataset_id}/visualizations/histogram", response_model=HistogramData)
def get_histogram(
    dataset_id: str,
    column: str,
    bins: int | None = Query(None, description="Optional fixed bin count (1-100)"),
    db: Session = Depends(get_db),
) -> HistogramData:
    dataframe = load_dataframe(get_dataset_or_404(dataset_id, db))
    return visualizations.histogram(dataframe, column, bins)


@router.get(
    "/{dataset_id}/visualizations/categorical", response_model=CategoricalFrequencies
)
def get_categorical_frequencies(
    dataset_id: str,
    column: str,
    top_n: int = Query(
        visualizations.DEFAULT_CATEGORY_TOP_N,
        description="Number of categories to return before grouping the rest as Other (1-100)",
    ),
    db: Session = Depends(get_db),
) -> CategoricalFrequencies:
    dataframe = load_dataframe(get_dataset_or_404(dataset_id, db))
    return visualizations.categorical_frequencies(dataframe, column, top_n)


@router.get("/{dataset_id}/visualizations/scatter", response_model=ScatterData)
def get_scatter(
    dataset_id: str,
    x: str,
    y: str,
    db: Session = Depends(get_db),
) -> ScatterData:
    dataframe = load_dataframe(get_dataset_or_404(dataset_id, db))
    return visualizations.scatter(dataframe, x, y)


@router.get(
    "/{dataset_id}/visualizations/distribution", response_model=DistributionSummary
)
def get_distribution(
    dataset_id: str,
    column: str,
    db: Session = Depends(get_db),
) -> DistributionSummary:
    dataframe = load_dataframe(get_dataset_or_404(dataset_id, db))
    return visualizations.distribution_summary(dataframe, column)


@router.get("/{dataset_id}/visualizations/datetime-trend", response_model=DatetimeTrend)
def get_datetime_trend(
    dataset_id: str,
    datetime_column: str,
    value_column: str,
    db: Session = Depends(get_db),
) -> DatetimeTrend:
    dataframe = load_dataframe(get_dataset_or_404(dataset_id, db))
    return visualizations.datetime_trend(dataframe, datetime_column, value_column)
