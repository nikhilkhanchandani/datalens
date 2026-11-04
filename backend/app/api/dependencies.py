"""Helpers shared by every dataset-scoped route module.

Looking up a dataset by ID and loading its current CSV into a DataFrame is the
same for profiling, quality, statistics, visualization, and cleaning
endpoints, so it lives here rather than being copied into each router.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.core.exceptions import DatasetNotFoundError
from app.models.dataset import Dataset
from app.services import csv_service, transformations


def get_dataset_or_404(dataset_id: str, db: Session) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise DatasetNotFoundError(f"Dataset '{dataset_id}' was not found.")
    return dataset


def load_dataframe(dataset: Dataset) -> pd.DataFrame:
    """Load the dataset as analysis sees it: the current working copy if one exists."""
    return csv_service.read_dataframe(
        transformations.current_path(dataset),
        encoding=transformations.current_encoding(dataset),
    )
