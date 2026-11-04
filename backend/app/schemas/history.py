"""Response model for the transformation history endpoint.

The structured fields are the source of truth. `description` is a sentence
built from them by `services/history.py`, so the UI never has to parse
parameters itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TransformationRecord(BaseModel):
    id: int
    operation: str
    column: str | None = None
    # The validated request that produced this version, without `operation`.
    parameters: dict[str, Any]
    # Rows whose values changed or that were removed. Dropping a column records
    # every row, and renaming records zero; `operation` says which convention applies.
    affected_rows: int
    rows_before: int
    rows_after: int
    resulting_version: int = Field(description="Working version this step produced.")
    timestamp: datetime = Field(description="When the step was applied, in UTC.")
    description: str
