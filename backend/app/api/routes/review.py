"""Read-only Phase 6 endpoints: comparison, transformation history, and export.

All three only read. None of them writes to the upload directory or the
database, so they're safe to call at any time, including during a cleaning step
on the same dataset.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_dataset_or_404
from app.db.session import get_db
from app.schemas.comparison import ComparisonResponse
from app.schemas.history import TransformationRecord
from app.services import comparison, exporter, history

router = APIRouter(prefix="/datasets", tags=["review"])


@router.get("/{dataset_id}/comparison", response_model=ComparisonResponse)
def get_comparison(dataset_id: str, db: Session = Depends(get_db)) -> ComparisonResponse:
    dataset = get_dataset_or_404(dataset_id, db)
    return comparison.build_comparison(dataset, db)


@router.get("/{dataset_id}/transformations", response_model=list[TransformationRecord])
def get_transformations(
    dataset_id: str, db: Session = Depends(get_db)
) -> list[TransformationRecord]:
    get_dataset_or_404(dataset_id, db)
    return history.list_transformations(dataset_id, db)


@router.get("/{dataset_id}/export", response_class=FileResponse)
def export_dataset(dataset_id: str, db: Session = Depends(get_db)) -> FileResponse:
    dataset = get_dataset_or_404(dataset_id, db)
    return FileResponse(
        exporter.export_source(dataset),
        media_type="text/csv",
        filename=exporter.export_filename(dataset.original_filename, dataset.working_version),
    )
