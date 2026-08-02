"""Analytical first-order light-response dynamics on integer virtual time."""

from __future__ import annotations

import math

from symbiotic_sim_v2.simulation.time_utils import us_to_seconds
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig

_ROUNDING_TOLERANCE = 1e-12


def transition_time_constant_seconds(
    response_at_start: float,
    target: float,
    config: LightResponseConfig,
) -> float | None:
    _validate_unit("response_at_start", response_at_start)
    _validate_unit("target", target)
    if target > response_at_start:
        return config.response_onset_time_constant_seconds
    if target < response_at_start:
        return config.response_recovery_time_constant_seconds
    return None


def first_order_response_at(
    query_time_us: int,
    *,
    start_time_us: int,
    response_at_start: float,
    target: float,
    time_constant_seconds: float | None,
) -> float:
    for name, value in (("query_time_us", query_time_us), ("start_time_us", start_time_us)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if query_time_us < start_time_us:
        raise ValueError("query_time_us cannot precede start_time_us")
    _validate_unit("response_at_start", response_at_start)
    _validate_unit("target", target)
    if target == response_at_start:
        if time_constant_seconds is not None:
            _validate_positive_constant(time_constant_seconds)
        return response_at_start
    if time_constant_seconds is None:
        raise ValueError("a changing response requires a time constant")
    tau = _validate_positive_constant(time_constant_seconds)
    if query_time_us == start_time_us:
        return response_at_start
    elapsed_seconds = us_to_seconds(query_time_us - start_time_us)
    response = target + (response_at_start - target) * math.exp(-elapsed_seconds / tau)
    if response < 0.0 and response >= -_ROUNDING_TOLERANCE:
        return 0.0
    if response > 1.0 and response <= 1.0 + _ROUNDING_TOLERANCE:
        return 1.0
    if not 0.0 <= response <= 1.0:
        raise RuntimeError("analytical response escaped [0, 1]")
    return response


def _validate_unit(name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(f"{name} must be finite and between 0 and 1")
    return float(value)


def _validate_positive_constant(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) <= 0.0
    ):
        raise ValueError("time_constant_seconds must be finite and positive")
    return float(value)
