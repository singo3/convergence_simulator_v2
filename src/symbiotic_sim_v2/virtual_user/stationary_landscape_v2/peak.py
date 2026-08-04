"""Pure Stage 8A.1 neutral/Gaussian axis preference mathematics."""

from __future__ import annotations

import math

from .config import StationaryPreferencePeakV2


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def circular_hue_distance(first_degree: object, second_degree: object) -> float:
    first = _finite("first_degree", first_degree)
    second = _finite("second_degree", second_degree)
    if not 0.0 <= first <= 360.0 or not 0.0 <= second <= 360.0:
        raise ValueError("Hue values must be between 0 and 360")
    raw = abs(first - second)
    return min(raw, 360.0 - raw)


def gaussian_match(distance: object, sigma: object) -> float:
    normalized_distance = _finite("distance", distance)
    normalized_sigma = _finite("sigma", sigma)
    if normalized_distance < 0.0:
        raise ValueError("distance must be non-negative")
    if normalized_sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return math.exp(-0.5 * (normalized_distance / normalized_sigma) ** 2)


def normalized_peak_distance(
    peak: StationaryPreferencePeakV2,
    *,
    hue_degree: object,
    blink_bpm: object,
) -> float:
    """Return hidden-truth distance while neutral axes contribute zero."""

    values = evaluate_peak_match(peak, hue_degree=hue_degree, blink_bpm=blink_bpm)
    hue_component = (
        0.0 if peak.hue_axis_mode == "neutral" else values[0] / peak.hue_sigma_degree  # type: ignore[operator]
    )
    bpm_component = (
        0.0 if peak.bpm_axis_mode == "neutral" else values[2] / peak.blink_sigma_bpm  # type: ignore[operator]
    )
    return math.hypot(hue_component, bpm_component)


def evaluate_peak_match(
    peak: StationaryPreferencePeakV2,
    *,
    hue_degree: object,
    blink_bpm: object,
) -> tuple[float | None, float, float | None, float, float]:
    """Return optional distances, axis matches, and maximum-combination input."""

    if not isinstance(peak, StationaryPreferencePeakV2):
        raise TypeError("peak must be a StationaryPreferencePeakV2")
    hue = _finite("hue_degree", hue_degree)
    bpm = _finite("blink_bpm", blink_bpm)
    if not 0.0 <= hue <= 360.0:
        raise ValueError("hue_degree must be between 0 and 360")
    if not 10.0 <= bpm <= 165.0:
        raise ValueError("blink_bpm must be between 10 and 165")
    if peak.hue_axis_mode == "neutral":
        hue_distance = None
        hue_match = 1.0
    else:
        assert peak.preferred_hue_degree is not None
        assert peak.hue_sigma_degree is not None
        hue_distance = circular_hue_distance(hue, peak.preferred_hue_degree)
        hue_match = gaussian_match(hue_distance, peak.hue_sigma_degree)
    if peak.bpm_axis_mode == "neutral":
        bpm_distance = None
        bpm_match = 1.0
    else:
        assert peak.preferred_blink_bpm is not None
        assert peak.blink_sigma_bpm is not None
        bpm_distance = abs(bpm - peak.preferred_blink_bpm)
        bpm_match = gaussian_match(bpm_distance, peak.blink_sigma_bpm)
    weighted_match = peak.peak_weight * hue_match * bpm_match
    if not 0.0 <= weighted_match <= 1.0:
        raise RuntimeError("weighted peak match escaped its analytical range")
    return hue_distance, hue_match, bpm_distance, bpm_match, weighted_match


__all__ = [
    "circular_hue_distance",
    "evaluate_peak_match",
    "gaussian_match",
    "normalized_peak_distance",
]
