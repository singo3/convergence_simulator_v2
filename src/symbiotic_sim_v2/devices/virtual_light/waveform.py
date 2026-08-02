"""Pure sine-wave value evaluation for logical HSV light output."""

from __future__ import annotations

import math

from symbiotic_sim_v2.devices.virtual_light.phase import normalize_phase_cycles


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def sine_value(
    phase_cycles: float,
    *,
    value_center: float,
    value_amplitude: float,
) -> float:
    """Evaluate the logical HSV Value at one phase in cycles."""

    phase = normalize_phase_cycles(phase_cycles)
    center = _finite("value_center", value_center)
    amplitude = _finite("value_amplitude", value_amplitude)
    if not 0.0 <= center <= 1.0:
        raise ValueError("value_center must be between 0 and 1")
    if amplitude < 0.0:
        raise ValueError("value_amplitude must be non-negative")
    if center - amplitude < 0.0 or center + amplitude > 1.0:
        raise ValueError("the sine value range must stay between 0 and 1")
    return center + amplitude * math.sin(math.tau * phase)
