"""JSON-safety helpers shared by every analysis service.

Pandas/NumPy routinely produce values that are not valid JSON on their own:

- `NaN` and `+/-Infinity` have no JSON representation. Python's `json`
  module will happily *emit* the non-standard literals `NaN`/`Infinity`
  (`json.dumps(float("inf"))` succeeds), but that output is not valid JSON
  per spec, and strict parsers — including the browser's `JSON.parse`,
  which this project's frontend relies on — reject it outright.
- NumPy scalar types (`np.int64`, `np.float64`, `np.bool_`, ...) and
  Pandas' `Timestamp`/`NaT` are not native Python types `json`/Pydantic
  know how to serialize.

Every analysis service should route numbers and raw cell values through
these helpers before they reach a Pydantic response model, rather than
relying on each call site to remember all of the above.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def safe_float(value: Any) -> float | None:
    """Convert a numeric value to a JSON-safe float, or `None` if it isn't one.

    `None` covers three cases uniformly: the value was already missing, it
    was NaN, or it was +/-Infinity — all of which mean "no valid number
    here" from the API consumer's point of view.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def safe_coefficient(value: Any) -> float | None:
    """A JSON-safe correlation-style coefficient, rounded to 6 decimal places.

    Floating-point arithmetic can return 0.9999999999999999 for a perfect
    correlation; rounding removes that noise without changing any meaningful
    digit.
    """
    number = safe_float(value)
    return None if number is None else round(number, 6)


def to_json_safe(value: Any) -> Any:
    """Coerce a single NumPy/Pandas scalar into a plain JSON-serializable value."""
    if value is None:
        return None
    if value is pd.NaT:
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return safe_float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value
