"""Cleaning endpoint: apply one explicit transformation to a dataset.

Design: a single `POST /api/datasets/{id}/clean` route whose body is a
discriminated union on `operation`, rather than one endpoint per operation.
Each operation's body model enforces its own fields (unknown fields are
rejected), while the persistence path is shared: one lock, one atomic write,
one pointer swap. Splitting into six routes would duplicate that transaction
logic six times. A single route with dozens of optional parameters would be
the opposite mistake, because the validity of each field depends on the
operation.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_dataset_or_404
from app.db.session import get_db
from app.schemas.cleaning import CleaningRequest, TransformationResult
from app.services import transformations

router = APIRouter(prefix="/datasets", tags=["cleaning"])


@router.post("/{dataset_id}/clean", response_model=TransformationResult)
def apply_cleaning(
    dataset_id: str,
    request: Annotated[CleaningRequest, Body(...)],
    db: Session = Depends(get_db),
) -> TransformationResult:
    dataset = get_dataset_or_404(dataset_id, db)
    return transformations.apply_cleaning(dataset, request, db)
