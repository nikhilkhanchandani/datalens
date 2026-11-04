"""Cleaned-CSV export: which file to send, and what to call it.

Export doesn't rebuild the CSV. The working copy is already a complete CSV
written by Phase 5, so the export streams that exact file. The bytes sent are
the bytes the analysis reads, and nothing is written to disk along the way.

Read-only: this module never creates, modifies, or deletes a file.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.exceptions import DatasetFileMissingError
from app.models.dataset import Dataset
from app.services import transformations

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_STEM_LENGTH = 100
_FALLBACK_STEM = "dataset"


def export_source(dataset: Dataset) -> Path:
    """The file to send: the working copy, or the original if nothing was changed."""
    path = transformations.current_path(dataset)
    if not path.exists():
        raise DatasetFileMissingError(
            "The file to export for this dataset is missing from disk."
        )
    return path


def export_filename(original_filename: str, working_version: int) -> str:
    """`<safe stem>_cleaned.csv` after changes, `<safe stem>_original.csv` otherwise."""
    suffix = "cleaned" if working_version > 0 else "original"
    return f"{_safe_stem(original_filename)}_{suffix}.csv"


def _safe_stem(original_filename: str) -> str:
    # Drop any directory part first, then keep only a conservative character set.
    # Users' names can contain spaces, parentheses, or non-ASCII letters, and none
    # of those should reach a Content-Disposition header.
    base = original_filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = Path(base).stem
    cleaned = _UNSAFE_CHARS.sub("_", stem).strip("._-")[:_MAX_STEM_LENGTH].strip("._-")
    return cleaned or _FALLBACK_STEM
