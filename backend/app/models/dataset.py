"""ORM model for an uploaded dataset's metadata.

The raw CSV itself lives on disk under `settings.upload_dir`, named by a
generated UUID (see `services/csv_service.py`). Only lightweight metadata
is persisted here, which keeps SQLite fast regardless of how large the
uploaded files get.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    upload_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    row_count: Mapped[int] = mapped_column(Integer)
    column_count: Mapped[int] = mapped_column(Integer)
    file_size_bytes: Mapped[int] = mapped_column(Integer)

    # Human-readable label (e.g. "Windows-1252"), exposed via the API as-is.
    encoding: Mapped[str] = mapped_column(String(32))
    # Python codec name (e.g. "cp1252") used to re-read the file with
    # Pandas on every subsequent request. Internal only — not exposed.
    encoding_codec: Mapped[str] = mapped_column(String(32))

    # 0 means the analysed dataset is the original upload. N > 0 means it is
    # working-copy version N, stored as `{id}.v{N}.csv` (see services/transformations.py).
    working_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
