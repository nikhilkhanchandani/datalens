"""ORM model for an applied transformation (internal record).

Each successful cleaning step is recorded so the working copy's history can be
audited. Phase 5 only writes these rows; the user-facing history view and
undo are later work.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Transformation(Base):
    __tablename__ = "transformations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(32))
    column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The validated request, serialized as JSON.
    parameters: Mapped[str] = mapped_column(Text)
    affected_rows: Mapped[int] = mapped_column(Integer)
    rows_before: Mapped[int] = mapped_column(Integer)
    rows_after: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
