"""Reflection into the continuous unit interval used by Stage 5C candidates."""

from __future__ import annotations

import math
from collections.abc import Sequence


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("value must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("value must be finite")
    return converted


def reflect01(value: object) -> float:
    """Reflect one finite value using positive modulo with period two."""

    converted = _finite(value)
    positive_modulo = converted % 2.0
    return 1.0 - abs(1.0 - positive_modulo)


def reflect01_vector(values: Sequence[object]) -> tuple[float, ...]:
    """Apply :func:`reflect01` element-wise without clipping or rounding."""

    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("values must be a sequence")
    return tuple(reflect01(value) for value in values)


__all__ = ["reflect01", "reflect01_vector"]
