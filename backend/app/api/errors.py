"""Readable summaries of request-validation failures.

Pydantic reports a failed discriminated union as one set of errors for every
member of the union. For a cleaning request, that buries the one useful message
(for example "'keep' isn't allowed for remove_duplicates") under dozens of
unrelated ones. This module keeps only the errors for the operation the client
named, and says so plainly when the operation itself is unknown.
"""

from __future__ import annotations

from typing import Any

from app.schemas.cleaning import OPERATION_MODELS

_MODEL_OPERATION = {model.__name__: operation for operation, model in OPERATION_MODELS.items()}


def summarize_validation_errors(errors: list[dict[str, Any]], body: Any) -> str:
    operation = body.get("operation") if isinstance(body, dict) else None

    if isinstance(operation, str) and operation not in OPERATION_MODELS:
        return (
            f"'{operation}' isn't a cleaning operation. Use one of: "
            f"{', '.join(OPERATION_MODELS)}."
        )

    relevant = [error for error in errors if _belongs_to(error, operation)]
    problems = [_describe(error, operation) for error in relevant] or [
        _describe(error, operation) for error in errors
    ]
    return "The request isn't valid: " + "; ".join(dict.fromkeys(problems)) + "."


def _belongs_to(error: dict[str, Any], operation: str | None) -> bool:
    location = error.get("loc", ())
    if operation is None or len(location) < 2:
        return True
    model = location[1]
    return not isinstance(model, str) or _MODEL_OPERATION.get(model) == operation


def _describe(error: dict[str, Any], operation: str | None) -> str:
    location = [str(part) for part in error.get("loc", ())]
    field = ".".join(part for part in location[2:] if part != "__root__") if len(location) > 2 else "request"
    if error.get("type") == "extra_forbidden":
        return f"'{field}' isn't a valid option for '{operation or 'this'}' requests"
    if error.get("type") == "missing":
        return f"'{field}' is required"
    return f"{field}: {error.get('msg', 'invalid value')}"
