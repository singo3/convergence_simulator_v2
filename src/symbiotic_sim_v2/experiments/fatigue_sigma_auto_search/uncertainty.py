"""Small-sample uncertainty summaries used by Stage 8A.2 reports."""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable
from typing import Any

WILSON_Z_95 = 1.959963984540054


def wilson_interval(successes: int, total: int) -> dict[str, float | int | None]:
    if isinstance(successes, bool) or not isinstance(successes, int):
        raise TypeError("successes must be an integer")
    if isinstance(total, bool) or not isinstance(total, int):
        raise TypeError("total must be an integer")
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Wilson counts must satisfy 0 <= successes <= total")
    if total == 0:
        return {"successes": 0, "total": 0, "rate": None, "lower95": None, "upper95": None}
    rate = successes / total
    z2 = WILSON_Z_95**2
    denominator = 1.0 + z2 / total
    center = (rate + z2 / (2.0 * total)) / denominator
    margin = (
        WILSON_Z_95 * math.sqrt(rate * (1.0 - rate) / total + z2 / (4.0 * total**2)) / denominator
    )
    return {
        "successes": successes,
        "total": total,
        "rate": rate,
        "lower95": max(0.0, center - margin),
        "upper95": min(1.0, center + margin),
    }


def _percentile(sorted_values: tuple[float, ...], probability: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def continuous_summary(values: Iterable[float | int | None]) -> dict[str, Any]:
    normalized = tuple(sorted(float(value) for value in values if value is not None))
    if not normalized:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "q1": None,
            "q3": None,
        }
    return {
        "count": len(normalized),
        "mean": statistics.fmean(normalized),
        "median": float(statistics.median(normalized)),
        "min": normalized[0],
        "max": normalized[-1],
        "q1": _percentile(normalized, 0.25),
        "q3": _percentile(normalized, 0.75),
    }


__all__ = ["continuous_summary", "wilson_interval"]
