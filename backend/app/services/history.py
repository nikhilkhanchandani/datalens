"""Read-only view of the applied-transformation log.

`transformations` rows are the source of truth. This module reads them back,
checks that their parameters are readable, and builds the display sentence for
each step. Nothing here writes to the database or the file system.
"""

from __future__ import annotations

import json
from datetime import timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import CorruptHistoryError
from app.models.transformation import Transformation
from app.schemas.history import TransformationRecord


def list_transformations(dataset_id: str, db: Session) -> list[TransformationRecord]:
    """Every applied step for a dataset, oldest first."""
    rows = (
        db.query(Transformation)
        .filter(Transformation.dataset_id == dataset_id)
        .order_by(Transformation.id)
        .all()
    )
    return [to_record(row) for row in rows]


def to_record(row: Transformation) -> TransformationRecord:
    parameters = _load_parameters(row)
    # SQLite returns naive datetimes. They were written in UTC, so label them.
    timestamp = row.timestamp.replace(tzinfo=timezone.utc) if row.timestamp.tzinfo is None else row.timestamp
    return TransformationRecord(
        id=row.id,
        operation=row.operation,
        column=row.column,
        parameters=parameters,
        affected_rows=row.affected_rows,
        rows_before=row.rows_before,
        rows_after=row.rows_after,
        resulting_version=row.version,
        timestamp=timestamp,
        description=describe(row.operation, row.column, parameters, row.affected_rows),
    )


def _load_parameters(row: Transformation) -> dict[str, Any]:
    try:
        parameters = json.loads(row.parameters)
    except (TypeError, ValueError) as exc:
        raise _corrupt(row) from exc
    if not isinstance(parameters, dict):
        raise _corrupt(row)
    return parameters


def _corrupt(row: Transformation) -> CorruptHistoryError:
    return CorruptHistoryError(
        f"The stored history entry {row.id} for this dataset can't be read, "
        "so the history can't be shown."
    )


def describe(
    operation: str,
    column: str | None,
    parameters: dict[str, Any],
    affected_rows: int,
) -> str:
    """One readable sentence for a step, built from its structured fields."""
    if operation == "fill_missing":
        if parameters.get("strategy") == "remove_rows":
            return f"Removed {affected_rows} row(s) with a missing value in {_quote(column)}"
        text = (
            f"Filled {affected_rows} missing value(s) in {_quote(column)} "
            f"using {parameters.get('strategy')}"
        )
        if parameters.get("strategy") == "custom":
            text += f" ({_show_value(parameters.get('value'))})"
        return text

    if operation == "remove_duplicates":
        subset = parameters.get("subset")
        scope = f" (compared on {_quote_all(subset)})" if subset else ""
        return f"Removed {affected_rows} duplicate row(s){scope}"

    if operation == "normalize_text":
        actions = []
        if parameters.get("trim"):
            actions.append("trimmed whitespace")
        if parameters.get("blank_to_missing"):
            actions.append("turned blank cells into missing values")
        return (
            f"Cleaned text in {_quote_all(parameters.get('columns', []))}: "
            f"{' and '.join(actions)} ({affected_rows} row(s) changed)"
        )

    if operation == "drop_columns":
        names = parameters.get("columns", [])
        noun = "column" if len(names) == 1 else "columns"
        return f"Dropped {noun} {_quote_all(names)}"

    if operation == "rename_column":
        return f"Renamed {_quote(column)} to {_quote(parameters.get('new_name'))}"

    if operation == "convert_type":
        return (
            f"Converted {_quote(column)} to {parameters.get('target')} "
            f"({affected_rows} value(s))"
        )

    return f"Applied {operation}"


def _quote(name: Any) -> str:
    return f'"{name}"'


def _quote_all(names: Any) -> str:
    return ", ".join(_quote(name) for name in names)


def _show_value(value: Any) -> str:
    if isinstance(value, str):
        return _quote(value)
    return json.dumps(value)
