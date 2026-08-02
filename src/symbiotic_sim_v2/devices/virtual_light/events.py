"""Formal Stage 6 light-stimulus output boundary and strict parser."""

from __future__ import annotations

import math
from dataclasses import dataclass

from symbiotic_sim_v2.devices.virtual_light.config import (
    LIGHT_STIMULUS_STATE_SCHEMA_VERSION,
)
from symbiotic_sim_v2.devices.virtual_light.records import (
    BVector,
    LightStimulusStateRecord,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.light_mapper.config import (
    ACTIVE_WAVEFORM,
    COMMAND_HOLD_POLICY_VERSION,
    HUE_RENDER_PERIOD_DEGREE,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_MAPPING_VERSION,
    PHASE_POLICY_VERSION,
)

LIGHT_STIMULUS_STATE_EVENT_TYPE = "light_stimulus_state"
LIGHT_STIMULUS_STATE_EVENT_SOURCE = "virtual_light_device"
LIGHT_STIMULUS_STATE_EVENT_PRIORITY = 67

_STATE_FIELDS = {
    "device_id",
    "source_signal_index",
    "source_signal_time_us",
    "effective_time_us",
    "active",
    "qualification_holder_id",
    "source_b_f",
    "source_b_a",
    "source_b_t",
    "source_b_d",
    "hue_degree",
    "render_hue_degree",
    "saturation",
    "value_center",
    "value_amplitude",
    "value_min",
    "value_max",
    "blink_bpm",
    "waveform",
    "phase_cycles_at_start",
    "value_at_start",
    "phase_reset",
    "physical_parameters_changed",
    "command_equivalent_to_previous",
    "mapping_version",
    "phase_policy_version",
    "command_hold_policy_version",
    "inactive_output_policy_version",
    "schema_version",
}


@dataclass(frozen=True, slots=True)
class LightStimulusStateInput:
    device_id: str
    source_signal_index: int
    source_signal_time_us: int
    effective_time_us: int
    active: bool
    qualification_holder_id: str | None
    source_b: BVector | None
    hue_degree: float | None
    render_hue_degree: float | None
    saturation: float
    value_center: float
    value_amplitude: float
    value_min: float
    value_max: float
    blink_bpm: float | None
    waveform: str
    phase_cycles_at_start: float | None
    value_at_start: float
    phase_reset: bool
    physical_parameters_changed: bool
    command_equivalent_to_previous: bool
    mapping_version: str
    phase_policy_version: str
    command_hold_policy_version: str
    inactive_output_policy_version: str
    schema_version: str


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_string(name: str, value: object) -> str | None:
    return None if value is None else _required_string(name, value)


def _non_negative_int(name: str, value: object) -> int:
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


def _optional_finite(name: str, value: object) -> float | None:
    return None if value is None else _finite(name, value)


def _unit(name: str, value: object) -> float:
    converted = _finite(name, value)
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def _boolean(name: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be boolean")
    return value


def _source_b(values: dict[str, object]) -> BVector | None:
    names = tuple(f"source_b_{axis}" for axis in ("f", "a", "t", "d"))
    raw = tuple(values[name] for name in names)
    if all(value is None for value in raw):
        return None
    if any(value is None for value in raw):
        raise ValueError("source B must be either fully present or fully null")
    converted = tuple(_finite(name, value) for name, value in zip(names, raw, strict=True))
    if any(not 0.0 <= value <= 1.0 for value in converted):
        raise ValueError("source B values must be between 0 and 1")
    return converted  # type: ignore[return-value]


def light_stimulus_state_payload(
    record: LightStimulusStateRecord,
) -> dict[str, object]:
    """Serialize one state record without GUI RGB or upstream physiology fields."""

    b = record.source_b
    return {
        "device_id": record.device_id,
        "source_signal_index": record.source_signal_index,
        "source_signal_time_us": record.source_signal_time_us,
        "effective_time_us": record.effective_time_us,
        "active": record.active,
        "qualification_holder_id": record.qualification_holder_id,
        "source_b_f": None if b is None else b[0],
        "source_b_a": None if b is None else b[1],
        "source_b_t": None if b is None else b[2],
        "source_b_d": None if b is None else b[3],
        "hue_degree": record.hue_degree,
        "render_hue_degree": record.render_hue_degree,
        "saturation": record.saturation,
        "value_center": record.value_center,
        "value_amplitude": record.value_amplitude,
        "value_min": record.value_min,
        "value_max": record.value_max,
        "blink_bpm": record.blink_bpm,
        "waveform": record.waveform,
        "phase_cycles_at_start": record.phase_cycles_at_start,
        "value_at_start": record.value_at_start,
        "phase_reset": record.phase_reset,
        "physical_parameters_changed": record.physical_parameters_changed,
        "command_equivalent_to_previous": record.command_equivalent_to_previous,
        "mapping_version": record.mapping_version,
        "phase_policy_version": record.phase_policy_version,
        "command_hold_policy_version": record.command_hold_policy_version,
        "inactive_output_policy_version": record.inactive_output_policy_version,
        "schema_version": record.schema_version,
    }


def parse_light_stimulus_state_event(
    event: SimulationEvent,
) -> LightStimulusStateInput:
    """Validate the exact GUI-independent boundary intended for future Stage 7."""

    if event.event_type != LIGHT_STIMULUS_STATE_EVENT_TYPE:
        raise ValueError("state handler received the wrong event type")
    if event.source != LIGHT_STIMULUS_STATE_EVENT_SOURCE:
        raise ValueError("state source must be virtual_light_device")
    if event.priority != LIGHT_STIMULUS_STATE_EVENT_PRIORITY:
        raise ValueError("state priority does not match the formal boundary")
    if not isinstance(event.payload, dict) or set(event.payload) != _STATE_FIELDS:
        raise ValueError("state payload fields do not match the formal schema")
    values = dict(event.payload)
    exact = {
        "mapping_version": LIGHT_MAPPING_VERSION,
        "phase_policy_version": PHASE_POLICY_VERSION,
        "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
        "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
        "schema_version": LIGHT_STIMULUS_STATE_SCHEMA_VERSION,
    }
    for name, expected in exact.items():
        if values[name] != expected:
            raise ValueError(f"{name} must be {expected}")
    effective_time_us = _non_negative_int(
        "effective_time_us", values["effective_time_us"]
    )
    if event.scheduled_time_us != effective_time_us:
        raise ValueError("state event must be scheduled at effective_time_us")
    source_signal_time_us = _non_negative_int(
        "source_signal_time_us", values["source_signal_time_us"]
    )
    if source_signal_time_us > effective_time_us:
        raise ValueError("source signal time cannot follow effective time")
    active = _boolean("active", values["active"])
    holder = _optional_string(
        "qualification_holder_id", values["qualification_holder_id"]
    )
    source_b = _source_b(values)
    hue = _optional_finite("hue_degree", values["hue_degree"])
    render_hue = _optional_finite(
        "render_hue_degree", values["render_hue_degree"]
    )
    saturation = _finite("saturation", values["saturation"])
    center = _finite("value_center", values["value_center"])
    amplitude = _finite("value_amplitude", values["value_amplitude"])
    value_min = _finite("value_min", values["value_min"])
    value_max = _finite("value_max", values["value_max"])
    bpm = _optional_finite("blink_bpm", values["blink_bpm"])
    waveform = _required_string("waveform", values["waveform"])
    phase = _optional_finite(
        "phase_cycles_at_start", values["phase_cycles_at_start"]
    )
    value_at_start = _finite("value_at_start", values["value_at_start"])
    phase_reset = _boolean("phase_reset", values["phase_reset"])
    changed = _boolean(
        "physical_parameters_changed", values["physical_parameters_changed"]
    )
    equivalent = _boolean(
        "command_equivalent_to_previous",
        values["command_equivalent_to_previous"],
    )
    if active:
        if (
            holder is None
            or source_b is None
            or hue is None
            or render_hue is None
            or bpm is None
            or phase is None
            or waveform != ACTIVE_WAVEFORM
        ):
            raise ValueError("active state fields are incomplete")
        if hue < 0.0:
            raise ValueError("active hue_degree must be non-negative")
        if not 0.0 <= render_hue < HUE_RENDER_PERIOD_DEGREE:
            raise ValueError("active render_hue_degree must be in [0, 360)")
        if not math.isclose(
            render_hue,
            hue % HUE_RENDER_PERIOD_DEGREE,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("render_hue_degree must be formal Hue modulo 360")
        _unit("saturation", saturation)
        _unit("value_center", center)
        if amplitude < 0.0:
            raise ValueError("value_amplitude must be non-negative")
        _unit("value_min", value_min)
        _unit("value_max", value_max)
        if not math.isclose(
            center - amplitude,
            value_min,
            rel_tol=0.0,
            abs_tol=1e-12,
        ) or not math.isclose(
            center + amplitude,
            value_max,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("active Value fields are inconsistent")
        if bpm <= 0.0:
            raise ValueError("active blink_bpm must be positive")
        if not 0.0 <= phase < 1.0:
            raise ValueError("active phase must be in [0, 1)")
        if not 0.0 <= value_at_start <= 1.0:
            raise ValueError("active value_at_start must be between 0 and 1")
        expected_value = center + amplitude * math.sin(math.tau * phase)
        if not math.isclose(
            value_at_start,
            expected_value,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("value_at_start must match the formal sine state")
    elif (
        holder is not None
        or source_b is not None
        or hue is not None
        or render_hue is not None
        or bpm is not None
        or phase is not None
        or saturation != 0.0
        or center != 0.0
        or amplitude != 0.0
        or value_min != 0.0
        or value_max != 0.0
        or value_at_start != 0.0
        or waveform != "off"
        or phase_reset
    ):
        raise ValueError("inactive state fields are inconsistent")
    return LightStimulusStateInput(
        device_id=_required_string("device_id", values["device_id"]),
        source_signal_index=_non_negative_int(
            "source_signal_index", values["source_signal_index"]
        ),
        source_signal_time_us=source_signal_time_us,
        effective_time_us=effective_time_us,
        active=active,
        qualification_holder_id=holder,
        source_b=source_b,
        hue_degree=hue,
        render_hue_degree=render_hue,
        saturation=saturation,
        value_center=center,
        value_amplitude=amplitude,
        value_min=value_min,
        value_max=value_max,
        blink_bpm=bpm,
        waveform=waveform,
        phase_cycles_at_start=phase,
        value_at_start=value_at_start,
        phase_reset=phase_reset,
        physical_parameters_changed=changed,
        command_equivalent_to_previous=equivalent,
        mapping_version=LIGHT_MAPPING_VERSION,
        phase_policy_version=PHASE_POLICY_VERSION,
        command_hold_policy_version=COMMAND_HOLD_POLICY_VERSION,
        inactive_output_policy_version=INACTIVE_OUTPUT_POLICY_VERSION,
        schema_version=LIGHT_STIMULUS_STATE_SCHEMA_VERSION,
    )
