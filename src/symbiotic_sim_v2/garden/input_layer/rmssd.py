"""Evaluation-window RMSSD calculated only from valid canonical RRI microseconds."""

from __future__ import annotations

import math
from collections.abc import Sequence


def calculate_rmssd_ms(valid_rri_us: Sequence[int]) -> float | None:
    """Return RMSSD in milliseconds, or ``None`` for fewer than two inputs."""

    values = tuple(valid_rri_us)
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("RRI values must be integers")
        if value <= 0:
            raise ValueError("RRI values must be positive")
    if len(values) < 2:
        return None
    squared_differences = [
        (current - previous) ** 2 for previous, current in zip(values, values[1:], strict=False)
    ]
    return math.sqrt(sum(squared_differences) / len(squared_differences)) / 1_000.0
