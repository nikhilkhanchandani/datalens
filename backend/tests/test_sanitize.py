"""Unit tests for the shared JSON-safety helpers."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from app.core.sanitize import safe_float, to_json_safe


def test_safe_float_passes_through_finite_numbers() -> None:
    assert safe_float(3.14) == 3.14
    assert safe_float(0) == 0.0


def test_safe_float_converts_nan_to_none() -> None:
    assert safe_float(float("nan")) is None


def test_safe_float_converts_infinity_to_none() -> None:
    assert safe_float(float("inf")) is None
    assert safe_float(float("-inf")) is None


def test_safe_float_handles_none_and_non_numeric() -> None:
    assert safe_float(None) is None
    assert safe_float("not a number") is None


def test_to_json_safe_converts_numpy_scalars() -> None:
    assert to_json_safe(np.int64(5)) == 5
    assert isinstance(to_json_safe(np.int64(5)), int)
    assert to_json_safe(np.float64(2.5)) == 2.5
    assert to_json_safe(np.bool_(True)) is True


def test_to_json_safe_converts_nan_and_infinity_to_none() -> None:
    assert to_json_safe(np.float64("nan")) is None
    assert to_json_safe(float("inf")) is None
    assert to_json_safe(float("-inf")) is None


def test_to_json_safe_converts_timestamps() -> None:
    ts = pd.Timestamp("2022-01-15")
    assert to_json_safe(ts) == "2022-01-15T00:00:00"


def test_to_json_safe_converts_nat_to_none() -> None:
    assert to_json_safe(pd.NaT) is None


def test_to_json_safe_passes_through_plain_values() -> None:
    assert to_json_safe("hello") == "hello"
    assert to_json_safe(42) == 42


def test_sanitized_values_are_valid_json() -> None:
    values = [
        to_json_safe(np.float64("nan")),
        to_json_safe(float("inf")),
        to_json_safe(np.int64(7)),
        to_json_safe(pd.Timestamp("2022-01-01")),
    ]
    serialized = json.dumps(values)
    round_tripped = json.loads(serialized)
    assert round_tripped == [None, None, 7, "2022-01-01T00:00:00"]
    assert all(not isinstance(v, float) or math.isfinite(v) for v in round_tripped if v is not None)
