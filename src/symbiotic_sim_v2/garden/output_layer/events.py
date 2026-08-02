"""Stage 5B formal event constants and strict boundary parsers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.config import (
    DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
    GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION,
    GARDEN_QUALIFIED_B_SCHEMA_VERSION,
    QUALIFIED_B_EMISSION_POLICY_VERSION,
)

DIGITAL_LIFE_TOUCH_EVENT_TYPE = "digital_life_touch"
DIGITAL_LIFE_TOUCH_EVENT_SOURCE = "digital_life"
DIGITAL_LIFE_TOUCH_EVENT_PRIORITY = 60

GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE = "garden_output_no_touch_finalize"
GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE = "garden_output_round_finalize"
GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE = "runtime"
GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY = 31
GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY = 70
GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_SOURCE = GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE
GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_SOURCE = GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE

GARDEN_QUALIFIED_B_EVENT_TYPE = "garden_qualified_b"
GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE = "garden_interoceptive_feedback"
GARDEN_OUTPUT_EVENT_SOURCE = "garden_output"
GARDEN_QUALIFIED_B_EVENT_PRIORITY = 65
GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY = 80
GARDEN_QUALIFIED_B_EVENT_SOURCE = GARDEN_OUTPUT_EVENT_SOURCE
GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_SOURCE = GARDEN_OUTPUT_EVENT_SOURCE

GARDEN_HOLDER_RELEASE_EVENT_TYPE = "garden_holder_release"
GARDEN_HOLDER_RELEASE_EVENT_PRIORITY = 90
GARDEN_HOLDER_RELEASE_EVENT_SOURCE = GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE

_TOUCH_FIELDS = {
    "digital_life_id",
    "signal_index",
    "signal_time_us",
    "b_f",
    "b_a",
    "b_t",
    "b_d",
    "schema_version",
}
_FEEDBACK_FIELDS = {
    "garden_id",
    "recipient_digital_life_id",
    "signal_index",
    "signal_time_us",
    "s",
    "qualification_holder_id",
    "returned_b_f",
    "returned_b_a",
    "returned_b_t",
    "returned_b_d",
    "attribution_source",
    "closing_evaluation_attribution",
    "schema_version",
}
_QUALIFIED_B_FIELDS = {
    "garden_id",
    "signal_index",
    "signal_time_us",
    "effective_time_us",
    "s",
    "active",
    "qualification_holder_id",
    "b_f",
    "b_a",
    "b_t",
    "b_d",
    "emission_policy_version",
    "schema_version",
}


@dataclass(frozen=True, slots=True)
class DigitalLifeTouchInput:
    digital_life_id: str
    signal_index: int
    signal_time_us: int
    b: tuple[float, float, float, float]
    arrival_time_us: int


@dataclass(frozen=True, slots=True)
class GardenInteroceptiveFeedbackInput:
    garden_id: str
    recipient_digital_life_id: str
    signal_index: int
    signal_time_us: int
    s: int
    qualification_holder_id: str | None
    returned_b: tuple[float, float, float, float] | None
    attribution_source: str
    closing_evaluation_attribution: bool


@dataclass(frozen=True, slots=True)
class GardenQualifiedBInput:
    garden_id: str
    signal_index: int
    signal_time_us: int
    effective_time_us: int
    s: int
    active: bool
    qualification_holder_id: str | None
    b: tuple[float, float, float, float] | None
    emission_policy_version: str


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_string(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _required_string(name, value)


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _binary(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("s must be an integer")
    if value not in (0, 1):
        raise ValueError("s must be 0 or 1")
    return value


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def _b_values(
    values: dict[str, object], prefix: str
) -> tuple[float, float, float, float] | None:
    names = tuple(f"{prefix}{axis}" for axis in ("f", "a", "t", "d"))
    raw = tuple(values[name] for name in names)
    if all(value is None for value in raw):
        return None
    if any(value is None for value in raw):
        raise ValueError("B components must be either all present or all null")
    return tuple(_unit(name, value) for name, value in zip(names, raw, strict=True))  # type: ignore[return-value]


def parse_digital_life_touch_event(event: SimulationEvent) -> DigitalLifeTouchInput:
    if event.event_type != DIGITAL_LIFE_TOUCH_EVENT_TYPE:
        raise ValueError("touch handler received the wrong event type")
    if event.source != DIGITAL_LIFE_TOUCH_EVENT_SOURCE:
        raise ValueError("touch source must be digital_life")
    if event.priority != DIGITAL_LIFE_TOUCH_EVENT_PRIORITY:
        raise ValueError("touch priority does not match the formal boundary")
    if not isinstance(event.payload, dict) or set(event.payload) != _TOUCH_FIELDS:
        raise ValueError("touch payload fields do not match the formal schema")
    values = dict(event.payload)
    if values["schema_version"] != DIGITAL_LIFE_TOUCH_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {DIGITAL_LIFE_TOUCH_SCHEMA_VERSION}"
        )
    b = _b_values(values, "b_")
    if b is None:
        raise ValueError("a formal touch requires B")
    return DigitalLifeTouchInput(
        digital_life_id=_required_string("digital_life_id", values["digital_life_id"]),
        signal_index=_non_negative_int("signal_index", values["signal_index"]),
        signal_time_us=_non_negative_int("signal_time_us", values["signal_time_us"]),
        b=b,
        arrival_time_us=event.scheduled_time_us,
    )


def parse_garden_interoceptive_feedback_event(
    event: SimulationEvent,
) -> GardenInteroceptiveFeedbackInput:
    if event.event_type != GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE:
        raise ValueError("feedback handler received the wrong event type")
    if event.source != GARDEN_OUTPUT_EVENT_SOURCE:
        raise ValueError("feedback source must be garden_output")
    if event.priority != GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY:
        raise ValueError("feedback priority does not match the formal boundary")
    if not isinstance(event.payload, dict) or set(event.payload) != _FEEDBACK_FIELDS:
        raise ValueError("feedback payload fields do not match the formal schema")
    values = dict(event.payload)
    if values["schema_version"] != GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION:
        raise ValueError(
            "schema_version must be "
            f"{GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION}"
        )
    s = _binary(values["s"])
    closing = values["closing_evaluation_attribution"]
    if not isinstance(closing, bool):
        raise TypeError("closing_evaluation_attribution must be boolean")
    active_b = _b_values(values, "returned_b_")
    holder = _optional_string(
        "qualification_holder_id", values["qualification_holder_id"]
    )
    source = _required_string("attribution_source", values["attribution_source"])
    if source not in {"none", "current_signal_touch", "last_active_touch"}:
        raise ValueError("attribution_source is not recognized")
    if source == "none" and (active_b is not None or holder is not None or closing):
        raise ValueError("none attribution cannot carry a holder or returned B")
    if source == "current_signal_touch" and (
        s != 1 or active_b is None or holder is None or closing
    ):
        raise ValueError("current touch attribution requires an active signal and B")
    if source == "last_active_touch" and (
        s != 0 or active_b is None or holder is None or not closing
    ):
        raise ValueError("last active attribution is reserved for the closing signal")
    return GardenInteroceptiveFeedbackInput(
        garden_id=_required_string("garden_id", values["garden_id"]),
        recipient_digital_life_id=_required_string(
            "recipient_digital_life_id", values["recipient_digital_life_id"]
        ),
        signal_index=_non_negative_int("signal_index", values["signal_index"]),
        signal_time_us=_non_negative_int("signal_time_us", values["signal_time_us"]),
        s=s,
        qualification_holder_id=holder,
        returned_b=active_b,
        attribution_source=source,
        closing_evaluation_attribution=closing,
    )


def parse_garden_qualified_b_event(event: SimulationEvent) -> GardenQualifiedBInput:
    if event.event_type != GARDEN_QUALIFIED_B_EVENT_TYPE:
        raise ValueError("qualified B handler received the wrong event type")
    if event.source != GARDEN_OUTPUT_EVENT_SOURCE:
        raise ValueError("qualified B source must be garden_output")
    if event.priority != GARDEN_QUALIFIED_B_EVENT_PRIORITY:
        raise ValueError("qualified B priority does not match the formal boundary")
    if not isinstance(event.payload, dict) or set(event.payload) != _QUALIFIED_B_FIELDS:
        raise ValueError("qualified B payload fields do not match the formal schema")
    values = dict(event.payload)
    if values["schema_version"] != GARDEN_QUALIFIED_B_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {GARDEN_QUALIFIED_B_SCHEMA_VERSION}")
    if values["emission_policy_version"] != QUALIFIED_B_EMISSION_POLICY_VERSION:
        raise ValueError(
            "emission_policy_version must be "
            f"{QUALIFIED_B_EMISSION_POLICY_VERSION}"
        )
    active = values["active"]
    if not isinstance(active, bool):
        raise TypeError("active must be boolean")
    s = _binary(values["s"])
    holder = _optional_string(
        "qualification_holder_id", values["qualification_holder_id"]
    )
    b = _b_values(values, "b_")
    signal_time_us = _non_negative_int("signal_time_us", values["signal_time_us"])
    effective_time_us = _non_negative_int(
        "effective_time_us", values["effective_time_us"]
    )
    if event.scheduled_time_us != effective_time_us:
        raise ValueError("qualified B must be scheduled at effective_time_us")
    if active != (s == 1):
        raise ValueError("active and s are inconsistent")
    if active and (holder is None or b is None):
        raise ValueError("active output requires one holder and B")
    if not active and (holder is not None or b is not None):
        raise ValueError("inactive output cannot carry a holder or B")
    if active and not (
        signal_time_us < effective_time_us < signal_time_us + 1_000_000
    ):
        raise ValueError("active effective_time_us must be within its signal interval")
    if not active and effective_time_us != signal_time_us:
        raise ValueError("inactive effective_time_us must equal signal_time_us")
    return GardenQualifiedBInput(
        garden_id=_required_string("garden_id", values["garden_id"]),
        signal_index=_non_negative_int("signal_index", values["signal_index"]),
        signal_time_us=signal_time_us,
        effective_time_us=effective_time_us,
        s=s,
        active=active,
        qualification_holder_id=holder,
        b=b,
        emission_policy_version=QUALIFIED_B_EMISSION_POLICY_VERSION,
    )
