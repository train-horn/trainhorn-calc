"""Shared input validation and unit helpers (internal)."""

from __future__ import annotations

import math
from typing import Any

FEET_PER_METER = 3.280839895013123  # exact: 1 ft = 0.3048 m
METERS_PER_FOOT = 0.3048

LENGTH_UNITS = ("ft", "m")


class InputError(ValueError):
    """Raised when a calculator receives an invalid argument.

    Subclasses :class:`ValueError`, so ``except ValueError`` also catches it.
    """


def number(name: str, value: Any) -> float:
    """Return ``value`` as a finite float or raise :class:`InputError`."""
    if isinstance(value, bool):
        raise InputError(f"{name} must be a number, got a bool")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise InputError(f"{name} must be a number, got {value!r}") from None
    if not math.isfinite(result):
        raise InputError(f"{name} must be finite, got {value!r}")
    return result


def positive(name: str, value: Any) -> float:
    result = number(name, value)
    if result <= 0:
        raise InputError(f"{name} must be greater than 0, got {result:g}")
    return result


def non_negative(name: str, value: Any) -> float:
    result = number(name, value)
    if result < 0:
        raise InputError(f"{name} must be 0 or greater, got {result:g}")
    return result


def length_unit(unit: Any) -> str:
    if not isinstance(unit, str) or unit.strip().lower() not in LENGTH_UNITS:
        raise InputError(f"unit must be one of {', '.join(LENGTH_UNITS)}; got {unit!r}")
    return unit.strip().lower()


def to_meters(value: float, unit: str) -> float:
    return value * METERS_PER_FOOT if unit == "ft" else value


def from_meters(value: float, unit: str) -> float:
    return value / METERS_PER_FOOT if unit == "ft" else value
