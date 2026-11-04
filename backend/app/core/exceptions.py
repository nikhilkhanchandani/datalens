"""Domain-specific exceptions with HTTP semantics attached.

Each exception knows which HTTP status code it should map to, so a single
handler (registered once in `main.py`) can translate any `DataLensError`
into a consistent `{"error": ..., "message": ...}` JSON body instead of
scattering try/except-and-format-a-response blocks across route handlers.
"""

from fastapi import status


class DataLensError(Exception):
    """Base class for all expected, user-facing application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidFileTypeError(DataLensError):
    status_code = status.HTTP_400_BAD_REQUEST


class EmptyFileError(DataLensError):
    status_code = status.HTTP_400_BAD_REQUEST


class FileTooLargeError(DataLensError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class CSVParsingError(DataLensError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class EncodingDetectionError(DataLensError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class DatasetNotFoundError(DataLensError):
    status_code = status.HTTP_404_NOT_FOUND


class ColumnNotFoundError(DataLensError):
    status_code = status.HTTP_404_NOT_FOUND


class IncompatibleColumnTypeError(DataLensError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class InsufficientDataError(DataLensError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class InvalidParameterError(DataLensError):
    status_code = status.HTTP_400_BAD_REQUEST


class NoOpTransformationError(DataLensError):
    """The requested cleaning would change nothing, so nothing is written."""

    status_code = status.HTTP_409_CONFLICT


class InvalidConversionError(DataLensError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class TransformationWriteError(DataLensError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class DatasetFileMissingError(DataLensError):
    """A version file the database points at is missing from disk."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class CorruptHistoryError(DataLensError):
    """A stored transformation row can't be read back. Its data is not trusted."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
