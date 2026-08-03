"""Pure Stage 8A stationary Gaussian peak mathematics."""

from __future__ import annotations

import math

from .config import StationaryPreferencePeak


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def circular_hue_distance(first_degree: object, second_degree: object) -> float:
    """Return the shortest distance on the closed 0/360-degree circle."""

    first = _finite("first_degree", first_degree)
    second = _finite("second_degree", second_degree)
    if not 0.0 <= first <= 360.0 or not 0.0 <= second <= 360.0:
        raise ValueError("Hue values must be between 0 and 360")
    raw = abs(first - second)
    return min(raw, 360.0 - raw)


def gaussian_match(distance: object, sigma: object) -> float:
    """Evaluate one unweighted zero-centered Gaussian similarity."""

    normalized_distance = _finite("distance", distance)
    normalized_sigma = _finite("sigma", sigma)
    if normalized_distance < 0.0:
        raise ValueError("distance must be non-negative")
    if normalized_sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return math.exp(-0.5 * (normalized_distance / normalized_sigma) ** 2)


def evaluate_peak_match(
    peak: StationaryPreferencePeak,
    *,
    hue_degree: object,
    blink_bpm: object,
) -> tuple[float, float, float, float, float]:
    """Return Hue distance/match, BPM distance/match, and weighted product."""

    if not isinstance(peak, StationaryPreferencePeak):
        raise TypeError("peak must be a StationaryPreferencePeak")
    hue = _finite("hue_degree", hue_degree)
    bpm = _finite("blink_bpm", blink_bpm)
    if not 0.0 <= hue <= 360.0:
        raise ValueError("hue_degree must be between 0 and 360")
    if not 10.0 <= bpm <= 165.0:
        raise ValueError("blink_bpm must be between 10 and 165")
    hue_distance = circular_hue_distance(hue, peak.preferred_hue_degree)
    bpm_distance = abs(bpm - peak.preferred_blink_bpm)
    hue_match = gaussian_match(hue_distance, peak.hue_sigma_degree)
    bpm_match = gaussian_match(bpm_distance, peak.blink_sigma_bpm)
    weighted_match = peak.peak_weight * hue_match * bpm_match
    if not 0.0 <= weighted_match <= 1.0:
        raise RuntimeError("weighted peak match escaped its analytical range")
    return hue_distance, hue_match, bpm_distance, bpm_match, weighted_match


__all__ = ["circular_hue_distance", "evaluate_peak_match", "gaussian_match"]
