"""Pure continuous F/T candidate generation for relation memory."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .direction import RelationMemorySearchDirection
from .reflect import reflect01


def _unit_vector(values: object) -> tuple[float, float, float, float]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("k_anchor must be a four-element sequence")
    if len(values) != 4:
        raise ValueError("k_anchor must contain four values")
    converted: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"k_anchor[{index}] must be a number")
        item = float(value)
        if not math.isfinite(item):
            raise ValueError(f"k_anchor[{index}] must be finite")
        if not 0.0 <= item <= 1.0:
            raise ValueError(f"k_anchor[{index}] must be between 0 and 1")
        converted.append(item)
    return tuple(converted)  # type: ignore[return-value]


def generate_candidate(
    k_anchor: object,
    sigma: object,
    direction: RelationMemorySearchDirection,
) -> tuple[float, float, float, float]:
    """Reflect only F/T; preserve A/D exactly and never quantize to cells."""

    anchor = _unit_vector(k_anchor)
    if isinstance(sigma, bool) or not isinstance(sigma, (int, float)):
        raise TypeError("sigma must be a number")
    distance = float(sigma)
    if not math.isfinite(distance):
        raise ValueError("sigma must be finite")
    if distance < 0.0:
        raise ValueError("sigma must be non-negative")
    if not isinstance(direction, RelationMemorySearchDirection):
        raise TypeError("direction must be a RelationMemorySearchDirection")
    return (
        reflect01(anchor[0] + distance * direction.xi[0]),
        anchor[1],
        reflect01(anchor[2] + distance * direction.xi[2]),
        anchor[3],
    )


__all__ = ["generate_candidate"]
