"""Working-copy versioning and safe persistence for cleaning operations.

Storage layout for one dataset with id `ID`:

    ID.csv        version 0: the original upload. Never written again.
    ID.v1.csv     working copy after the first successful cleaning step.
    ID.v2.csv     ... and so on.

The `datasets.working_version` column is a pointer to the current version.
Every analysis route reads whichever file the pointer names, so no analysis
result can be served from an older version.

Applying one cleaning step:

1. Under a process-wide lock, read the current version and compute the new
   DataFrame with `services/cleaner.py`. Validation errors stop here, before
   any file is touched.
2. Write the new version to a temporary file in the same directory, then
   `os.replace` it to `ID.v{N}.csv`. Readers see either the complete old file
   or the complete new file, never a partial one.
3. In one database transaction, record the transformation and move the pointer
   to version N.
4. Only after the commit, delete the previous working version (the original
   is never deleted).

If step 2 or 3 fails, the pointer still names the last good version, the
temporary or new file is removed, and the caller gets a
`TransformationWriteError`. The dataset is unchanged.

This is a deliberately small pointer-swap design, not version control. Each
version is a full copy, and there is no undo; both are sensible for
portfolio-sized CSVs, and both are noted as limitations.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import TransformationWriteError
from app.models.dataset import Dataset
from app.models.transformation import Transformation
from app.schemas.cleaning import CleaningRequest, TransformationResult
from app.services import cleaner, csv_service

WORKING_ENCODING = "utf-8"

_LOCK = threading.Lock()
_logger = logging.getLogger(__name__)


def version_path(dataset: Dataset, version: int) -> Path:
    settings = get_settings()
    if version == 0:
        return settings.upload_dir / dataset.stored_filename
    return settings.upload_dir / f"{dataset.id}.v{version}.csv"


def current_path(dataset: Dataset) -> Path:
    return version_path(dataset, dataset.working_version)


def current_encoding(dataset: Dataset) -> str:
    return dataset.encoding_codec if dataset.working_version == 0 else WORKING_ENCODING


def apply_cleaning(
    dataset: Dataset, request: CleaningRequest, db: Session
) -> TransformationResult:
    with _LOCK:
        db.refresh(dataset)
        previous_version = dataset.working_version
        current = csv_service.read_dataframe(
            current_path(dataset), encoding=current_encoding(dataset)
        )

        next_version = previous_version + 1
        cleaned, result = cleaner.apply_cleaning(current, request, next_version)

        target = version_path(dataset, next_version)
        _write_csv_atomically(cleaned, target)

        try:
            db.add(
                Transformation(
                    dataset_id=dataset.id,
                    version=next_version,
                    operation=result.operation,
                    column=result.column,
                    parameters=json.dumps(_request_parameters(request)),
                    affected_rows=result.affected_rows,
                    rows_before=result.rows_before,
                    rows_after=result.rows_after,
                )
            )
            dataset.working_version = next_version
            dataset.row_count = len(cleaned)
            dataset.column_count = len(cleaned.columns)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            _remove_quietly(target)
            raise TransformationWriteError(
                "The cleaned dataset couldn't be recorded, so nothing was changed."
            ) from exc

        if previous_version > 0:
            _remove_previous_version(version_path(dataset, previous_version))

        return result


def remove_all_versions(dataset: Dataset) -> None:
    """Delete the working copies of a dataset. The original is removed by the caller."""
    for version in range(1, dataset.working_version + 1):
        _remove_quietly(version_path(dataset, version))


def _write_csv_atomically(df: pd.DataFrame, target: Path) -> None:
    temporary = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
    try:
        df.to_csv(temporary, index=False, encoding=WORKING_ENCODING)
        os.replace(temporary, target)
    except Exception as exc:
        # Any failure while writing must leave no partial file behind. The
        # original exception is chained so the cause stays visible.
        _remove_quietly(temporary)
        raise TransformationWriteError(
            "Couldn't write the cleaned dataset to disk. The dataset is unchanged."
        ) from exc


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        _logger.warning("Could not remove temporary file %s", path, exc_info=True)


def _remove_previous_version(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        # The transformation has already committed, so failing the request here
        # would misreport a success. The leftover file is logged for cleanup.
        _logger.warning("Could not remove superseded working copy %s", path, exc_info=True)


def _request_parameters(request: BaseModel) -> dict:
    return request.model_dump(exclude={"operation"}, mode="json")
