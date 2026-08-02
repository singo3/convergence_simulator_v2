"""Fixed v2.0-reference RMSSD-to-N normalization."""

from __future__ import annotations

import math


def normalize_rmssd_to_n(
    rmssd_ms: int | float,
    rmssd_min_ms: int | float = 15.0,
    rmssd_max_ms: int | float = 80.0,
) -> float:
    """Map RMSSD to N using only the fixed clipped linear equation."""

    for name, value in (
        ("rmssd_ms", rmssd_ms),
        ("rmssd_min_ms", rmssd_min_ms),
        ("rmssd_max_ms", rmssd_max_ms),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a number")
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
    minimum = float(rmssd_min_ms)
    maximum = float(rmssd_max_ms)
    if minimum >= maximum:
        raise ValueError("rmssd_min_ms must be less than rmssd_max_ms")
    raw = (float(rmssd_ms) - minimum) / (maximum - minimum)
    return min(1.0, max(0.0, raw))
