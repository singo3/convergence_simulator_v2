"""Stage 5B tau-to-time policy and formal touch-event delivery."""

from __future__ import annotations

import math
from typing import Protocol

from symbiotic_sim_v2.digital_life.math import clip01
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.events import (
    DIGITAL_LIFE_TOUCH_EVENT_PRIORITY,
    DIGITAL_LIFE_TOUCH_EVENT_SOURCE,
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine

from .config import TOUCH_EVENT_SCHEMA_VERSION

MIN_TOUCH_OFFSET_US = 1
MAX_TOUCH_OFFSET_US = 999_998
TOUCH_OFFSET_SCALE_US = 999_997


class TouchIntentLike(Protocol):
    """Structural boundary accepted from a connected Digital Life."""

    signal_index: int
    signal_time_us: int
    digital_life_id: str
    b: tuple[float, float, float, float]
    tau: float | None
    touch_enabled: bool


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def tau_to_touch_offset_us(tau: object) -> int:
    """Map one logical tau to the reserved integer-microsecond touch interval."""

    return MIN_TOUCH_OFFSET_US + math.floor(clip01(tau) * TOUCH_OFFSET_SCALE_US)


def touch_arrival_time_us(signal_time_us: object, tau: object) -> int:
    """Return the absolute touch time without floating-point time accumulation."""

    if isinstance(signal_time_us, bool) or not isinstance(signal_time_us, int):
        raise TypeError("signal_time_us must be an integer")
    if signal_time_us < 0:
        raise ValueError("signal_time_us must be non-negative")
    return signal_time_us + tau_to_touch_offset_us(tau)


def schedule_touch_intent(
    engine: SimulationEngine,
    intent: TouchIntentLike,
) -> SimulationEvent:
    """Schedule one intent independently, exposing only ID and B to Garden."""

    if not isinstance(engine, SimulationEngine):
        raise TypeError("engine must be a SimulationEngine")
    if not isinstance(intent.touch_enabled, bool):
        raise TypeError("touch_enabled must be boolean")
    if not intent.touch_enabled:
        raise ValueError("a disabled TouchIntent cannot schedule a formal touch")
    if intent.tau is None:
        raise ValueError("an enabled TouchIntent requires tau")
    if isinstance(intent.signal_index, bool) or not isinstance(intent.signal_index, int):
        raise TypeError("signal_index must be an integer")
    if intent.signal_index < 0:
        raise ValueError("signal_index must be non-negative")
    if not isinstance(intent.digital_life_id, str) or not intent.digital_life_id.strip():
        raise ValueError("digital_life_id must be a non-empty string")
    if not isinstance(intent.b, tuple) or len(intent.b) != 4:
        raise ValueError("b must be an immutable four-element tuple")
    b_values = tuple(_unit(f"b[{index}]", value) for index, value in enumerate(intent.b))
    arrival_time_us = touch_arrival_time_us(intent.signal_time_us, intent.tau)
    return engine.schedule_at(
        arrival_time_us,
        DIGITAL_LIFE_TOUCH_EVENT_TYPE,
        source=DIGITAL_LIFE_TOUCH_EVENT_SOURCE,
        priority=DIGITAL_LIFE_TOUCH_EVENT_PRIORITY,
        payload={
            "digital_life_id": intent.digital_life_id,
            "signal_index": intent.signal_index,
            "signal_time_us": intent.signal_time_us,
            "b_f": b_values[0],
            "b_a": b_values[1],
            "b_t": b_values[2],
            "b_d": b_values[3],
            "schema_version": TOUCH_EVENT_SCHEMA_VERSION,
        },
    )
