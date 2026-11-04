"""Dataset endpoints: upload, list, retrieve, delete, and profile.

Route handlers stay thin — they handle the HTTP boundary (status codes,
request/response shapes) and delegate real work to `services/csv_service.py`
(storage/validation) and `services/profiler.py` (analysis).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_dataset_or_404, load_dataframe
from app.core.exceptions import CSVParsingError, EncodingDetectionError
from app.db.session import get_db
from app.models.dataset import Dataset
from app.schemas.analysis import DatasetProfile
from app.schemas.dataset import DatasetResponse
from app.schemas.quality import QualityReport
from app.schemas.statistics import DatasetStatistics
from app.models.transformation import Transformation
from app.services import csv_service, encoding_service, profiler, quality, statistics, transformations

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post(
    "/upload", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED
)
async def upload_dataset(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> Dataset:
    csv_service.validate_filename(file.filename)
    saved = await csv_service.save_upload(file)

    try:
        detected_encoding = encoding_service.detect_encoding(saved.path)
        dataframe = csv_service.read_dataframe(
            saved.path, encoding=detected_encoding.codec_name
        )
    except (EncodingDetectionError, CSVParsingError):
        csv_service.delete_file(saved.path)
        raise

    dataset = Dataset(
        id=str(saved.dataset_id),
        original_filename=Path(file.filename or "dataset.csv").name,
        stored_filename=saved.path.name,
        row_count=len(dataframe),
        column_count=len(dataframe.columns),
        file_size_bytes=saved.size_bytes,
        encoding=detected_encoding.display_name,
        encoding_codec=detected_encoding.codec_name,
    )
    db.add(dataset)
    try:
        db.commit()
    except SQLAlchemyError:
        # Without a metadata row the stored file could never be found or deleted.
        db.rollback()
        csv_service.delete_file(saved.path)
        raise
    db.refresh(dataset)
    return dataset


@router.get("", response_model=list[DatasetResponse])
def list_datasets(db: Session = Depends(get_db)) -> list[Dataset]:
    return db.query(Dataset).order_by(Dataset.upload_timestamp.desc()).all()


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)) -> Dataset:
    return get_dataset_or_404(dataset_id, db)


@router.delete(
    "/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)) -> None:
    dataset = get_dataset_or_404(dataset_id, db)
    transformations.remove_all_versions(dataset)
    csv_service.delete_file(csv_service.dataset_file_path(dataset.stored_filename))
    db.query(Transformation).filter(Transformation.dataset_id == dataset.id).delete()
    db.delete(dataset)
    db.commit()


@router.get("/{dataset_id}/profile", response_model=DatasetProfile)
def get_dataset_profile(dataset_id: str, db: Session = Depends(get_db)) -> DatasetProfile:
    dataset = get_dataset_or_404(dataset_id, db)
    dataframe = load_dataframe(dataset)
    profile = profiler.profile_dataset(dataframe)
    encoding = dataset.encoding if dataset.working_version == 0 else "UTF-8 (cleaned working copy)"
    return profile.model_copy(update={"encoding": encoding})


@router.get("/{dataset_id}/quality", response_model=QualityReport)
def get_dataset_quality(dataset_id: str, db: Session = Depends(get_db)) -> QualityReport:
    dataset = get_dataset_or_404(dataset_id, db)
    dataframe = load_dataframe(dataset)
    return quality.analyze_quality(dataframe)


@router.get("/{dataset_id}/statistics", response_model=DatasetStatistics)
def get_dataset_statistics(
    dataset_id: str, db: Session = Depends(get_db)
) -> DatasetStatistics:
    dataset = get_dataset_or_404(dataset_id, db)
    dataframe = load_dataframe(dataset)
    return statistics.analyze_statistics(dataframe)
