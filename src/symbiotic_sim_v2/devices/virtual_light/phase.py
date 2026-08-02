"""Analytic virtual-time phase integration for the Stage 6 sine light."""

from __future__ import annotations

import math

MICROSECONDS_PER_MINUTE = 60_000_000


def _time_us(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def normalize_phase_cycles(phase_cycles: object) -> float:
    """Return a finite cycle value normalized to the half-open interval [0, 1)."""

    return _finite("phase_cycles", phase_cycles) % 1.0


def phase_cycles_at(
    time_us: int,
    *,
    start_time_us: int,
    phase_cycles_at_start: float,
    blink_bpm: float,
) -> float:
    """Evaluate phase directly from integer virtual timestamps, without frame dt."""

    query_time_us = _time_us("time_us", time_us)
    origin_time_us = _time_us("start_time_us", start_time_us)
    if query_time_us < origin_time_us:
        raise ValueError("time_us must be at or after start_time_us")
    phase_at_start = _finite("phase_cycles_at_start", phase_cycles_at_start)
    if not 0.0 <= phase_at_start < 1.0:
        raise ValueError("phase_cycles_at_start must be in [0, 1)")
    bpm = _finite("blink_bpm", blink_bpm)
    if bpm <= 0.0:
        raise ValueError("blink_bpm must be positive")
    elapsed_us = query_time_us - origin_time_us
    return (phase_at_start + bpm * elapsed_us / MICROSECONDS_PER_MINUTE) % 1.0
