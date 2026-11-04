"""CSV upload handling: validation, safe on-disk storage, and parsing.

Uploaded files are never trusted: the original filename is only used for
display, the content is streamed to disk under a generated UUID (so a user
can never control a path on the server), and size is enforced *while*
streaming rather than after the fact, so an oversized upload is never fully
buffered in memory or written to disk before being rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pandas as pd
from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import (
    CSVParsingError,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
)

ALLOWED_EXTENSION = ".csv"
_CHUNK_SIZE = 1024 * 1024  # 1 MB per read, regardless of total file size

# Pandas' C parser reports a field-count mismatch as a one-line message like
# "Expected 3 fields in line 4, saw 4\n". We parse that back out to build a
# message that tells a user *what to go look at*, instead of surfacing a
# C-parser error verbatim.
_FIELD_COUNT_MISMATCH_PATTERN = re.compile(
    r"Expected (?P<expected>\d+) fields in line (?P<line>\d+), saw (?P<saw>\d+)"
)


@dataclass
class SavedUpload:
    dataset_id: UUID
    path: Path
    size_bytes: int


def validate_filename(filename: str | None) -> None:
    """Reject anything that isn't plausibly a CSV before we touch the disk."""
    if not filename or Path(filename).suffix.lower() != ALLOWED_EXTENSION:
        raise InvalidFileTypeError(f"Only {ALLOWED_EXTENSION} files are supported.")


async def save_upload(file: UploadFile) -> SavedUpload:
    """Stream an uploaded file to disk under a generated UUID.

    Raises `FileTooLargeError` as soon as the configured limit is crossed
    (without finishing the read) and `EmptyFileError` if nothing was written.
    """
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    dataset_id = uuid4()
    destination = settings.upload_dir / f"{dataset_id}.csv"
    max_bytes = settings.max_upload_size_bytes

    size = 0
    try:
        with destination.open("wb") as buffer:
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise FileTooLargeError(
                        f"File exceeds the {settings.max_upload_size_mb} MB upload limit."
                    )
                buffer.write(chunk)
    except FileTooLargeError:
        destination.unlink(missing_ok=True)
        raise

    if size == 0:
        destination.unlink(missing_ok=True)
        raise EmptyFileError("Uploaded file is empty.")

    return SavedUpload(dataset_id=dataset_id, path=destination, size_bytes=size)


def dataset_file_path(stored_filename: str) -> Path:
    return get_settings().upload_dir / stored_filename


def read_dataframe(path: Path, encoding: str = "utf-8-sig") -> pd.DataFrame:
    """Parse a stored CSV into a DataFrame, translating Pandas' parsing
    exceptions into our own domain error so routes don't need to know
    anything about Pandas internals.

    `encoding` should be the codec name resolved by
    `services/encoding_service.py` at upload time (stored on the `Dataset`
    row) — defaulting to `utf-8-sig` here only covers the common case for
    direct/test callers that skip detection.
    """
    try:
        return pd.read_csv(path, encoding=encoding)
    except pd.errors.EmptyDataError as exc:
        raise CSVParsingError("CSV file has no columns to parse.") from exc
    except pd.errors.ParserError as exc:
        raise CSVParsingError(_explain_parser_error(exc)) from exc
    except UnicodeDecodeError as exc:
        raise CSVParsingError(
            f"Could not decode file using encoding '{encoding}'."
        ) from exc


def _explain_parser_error(exc: pd.errors.ParserError) -> str:
    """Translate Pandas' raw tokenizer error into an actionable message.

    The most common cause of "Expected N fields, saw M" is a value that
    contains the delimiter (or a stray quote) without being properly
    quoted, which shifts every field after it on that line. We can't safely
    guess the real field boundaries — doing so risks silently misaligning
    data into the wrong columns — so we still reject the file, but point
    the user at the specific line and likely cause instead of a raw
    C-parser message.
    """
    match = _FIELD_COUNT_MISMATCH_PATTERN.search(str(exc))
    if match is None:
        return f"Could not parse CSV: {exc}"

    expected = int(match["expected"])
    line = int(match["line"])
    saw = int(match["saw"])
    difference = abs(saw - expected)
    noun = "value" if difference == 1 else "values"
    direction = "extra" if saw > expected else "missing"

    return (
        f"Row {line} has {saw} values but the header defines {expected} columns "
        f"({difference} {direction} {noun}). This usually means a value in that "
        "row contains a comma, quote, or line break that isn't properly escaped "
        "— check that row (and nearby rows) in the source file."
    )


def delete_file(path: Path) -> None:
    path.unlink(missing_ok=True)
