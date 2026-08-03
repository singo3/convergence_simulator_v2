"""Observable same-life circular-Hue/BPM pattern distance."""

from __future__ import annotations

import math

from .config import RollingConvergenceConfig
from .records import SessionPatternObservation


def _circular_hue_distance(first_degree: float, second_degree: float) -> float:
    """Keep primary geometry independent from the hidden preference package."""

    raw = abs(first_degree - second_degree)
    return min(raw, 360.0 - raw)


def pattern_distance(
    first: SessionPatternObservation,
    second: SessionPatternObservation,
    config: RollingConvergenceConfig,
) -> float:
    """Calculate normalized ellipse distance, rejecting cross-life comparisons."""

    if not isinstance(first, SessionPatternObservation) or not isinstance(
        second, SessionPatternObservation
    ):
        raise TypeError("patterns must be SessionPatternObservation values")
    if not isinstance(config, RollingConvergenceConfig):
        raise TypeError("config must be a RollingConvergenceConfig")
    if not first.valid_for_convergence or not second.valid_for_convergence:
        raise ValueError("pattern distance requires valid session observations")
    if first.holder_id != second.holder_id:
        raise ValueError("pattern distance requires the same Digital Life ID")
    if (
        first.hue_degree is None
        or second.hue_degree is None
        or first.blink_bpm is None
        or second.blink_bpm is None
    ):
        raise RuntimeError("valid observations lost their physical pattern")
    hue_distance = _circular_hue_distance(first.hue_degree, second.hue_degree)
    bpm_distance = abs(first.blink_bpm - second.blink_bpm)
    return math.hypot(
        hue_distance / config.hue_tolerance_degree,
        bpm_distance / config.blink_bpm_tolerance,
    )


def patterns_are_near(
    first: SessionPatternObservation,
    second: SessionPatternObservation,
    config: RollingConvergenceConfig,
) -> bool:
    """Use the inclusive tolerance ellipse required by Stage 8A."""

    return pattern_distance(first, second, config) <= 1.0


__all__ = ["pattern_distance", "patterns_are_near"]
