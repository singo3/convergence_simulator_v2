"""Strict LightCommandEvent v1 boundary values and parser."""

from __future__ import annotations

import math
from dataclasses import dataclass

from symbiotic_sim_v2.domain.events import SimulationEvent

from .config import (
    ACTIVE_WAVEFORM,
    B_TO_I_MAPPING_VERSION,
    COMMAND_HOLD_POLICY_VERSION,
    CONTINUOUS_PHASE_POLICY_VERSION,
    HUE_RENDER_PERIOD_DEGREE,
    INACTIVE_OUTPUT_POLICY_VERSION,
    INACTIVE_WAVEFORM,
    LIGHT_COMMAND_SCHEMA_VERSION,
)
from .mapping import BVector
from .records import LightCommandRecord

LIGHT_COMMAND_EVENT_TYPE = "light_command"
LIGHT_COMMAND_EVENT_SOURCE = "garden_light_mapper"
LIGHT_COMMAND_EVENT_PRIORITY = 66

_LIGHT_COMMAND_FIELDS = {
    "garden_id",
    "source_signal_index",
    "source_signal_time_us",
    "source_effective_time_us",
    "command_effective_time_us",
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
    "mapping_version",
    "phase_policy_version",
    "command_hold_policy_version",
    "inactive_output_policy_version",
    "schema_version",
}


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


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _unit(name: str, value: object) -> float:
    converted = _finite(name, value)
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def _source_b(values: dict[str, object]) -> BVector | None:
    names = tuple(f"source_b_{axis}" for axis in ("f", "a", "t", "d"))
    raw = tuple(values[name] for name in names)
    if all(value is None for value in raw):
        return None
    if any(value is None for value in raw):
        raise ValueError("source B components must be all present or all null")
    return tuple(_unit(name, value) for name, value in zip(names, raw, strict=True))  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class LightCommandInput:
    garden_id: str
    source_signal_index: int
    source_signal_time_us: int
    source_effective_time_us: int
    command_effective_time_us: int
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
    mapping_version: str
    phase_policy_version: str
    command_hold_policy_version: str
    inactive_output_policy_version: str
    schema_version: str


def parse_light_command_event(event: SimulationEvent) -> LightCommandInput:
    """Parse exactly one formal I command without accepting hidden inputs."""

    if event.event_type != LIGHT_COMMAND_EVENT_TYPE:
        raise ValueError("light command handler received the wrong event type")
    if event.source != LIGHT_COMMAND_EVENT_SOURCE:
        raise ValueError("light command source must be garden_light_mapper")
    if event.priority != LIGHT_COMMAND_EVENT_PRIORITY:
        raise ValueError("light command priority must be 66")
    if not isinstance(event.payload, dict) or set(event.payload) != _LIGHT_COMMAND_FIELDS:
        raise ValueError("light command payload fields do not match the formal schema")
    values = dict(event.payload)
    exact = {
        "mapping_version": B_TO_I_MAPPING_VERSION,
        "phase_policy_version": CONTINUOUS_PHASE_POLICY_VERSION,
        "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
        "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
        "schema_version": LIGHT_COMMAND_SCHEMA_VERSION,
    }
    for name, expected in exact.items():
        if values[name] != expected:
            raise ValueError(f"{name} must be {expected}")

    active = values["active"]
    if not isinstance(active, bool):
        raise TypeError("active must be boolean")
    source_signal_index = _non_negative_int(
        "source_signal_index", values["source_signal_index"]
    )
    source_signal_time_us = _non_negative_int(
        "source_signal_time_us", values["source_signal_time_us"]
    )
    source_effective_time_us = _non_negative_int(
        "source_effective_time_us", values["source_effective_time_us"]
    )
    command_effective_time_us = _non_negative_int(
        "command_effective_time_us", values["command_effective_time_us"]
    )
    if not (
        event.scheduled_time_us
        == source_effective_time_us
        == command_effective_time_us
    ):
        raise ValueError("light command time fields must equal its scheduled time")
    if source_effective_time_us < source_signal_time_us:
        raise ValueError("source effective time cannot precede its signal")

    holder = _optional_string(
        "qualification_holder_id", values["qualification_holder_id"]
    )
    source_b = _source_b(values)
    waveform = _required_string("waveform", values["waveform"])
    if active:
        if holder is None or source_b is None:
            raise ValueError("active light command requires holder and source B")
        hue_degree = _finite("hue_degree", values["hue_degree"])
        render_hue_degree = _finite(
            "render_hue_degree", values["render_hue_degree"]
        )
        if hue_degree < 0.0:
            raise ValueError("hue_degree must be non-negative")
        if not 0.0 <= render_hue_degree < HUE_RENDER_PERIOD_DEGREE:
            raise ValueError("render_hue_degree must be in [0, 360)")
        if not math.isclose(
            render_hue_degree,
            hue_degree % HUE_RENDER_PERIOD_DEGREE,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("render_hue_degree must be formal Hue modulo 360")
        saturation = _unit("saturation", values["saturation"])
        value_center = _unit("value_center", values["value_center"])
        value_amplitude = _finite("value_amplitude", values["value_amplitude"])
        value_min = _unit("value_min", values["value_min"])
        value_max = _unit("value_max", values["value_max"])
        blink_bpm = _finite("blink_bpm", values["blink_bpm"])
        if value_amplitude < 0.0:
            raise ValueError("value_amplitude must be non-negative")
        if not math.isclose(
            value_center - value_amplitude,
            value_min,
            rel_tol=0.0,
            abs_tol=1e-12,
        ) or not math.isclose(
            value_center + value_amplitude,
            value_max,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("light Value center/amplitude/min/max are inconsistent")
        if blink_bpm <= 0.0:
            raise ValueError("blink_bpm must be positive")
        if waveform != ACTIVE_WAVEFORM:
            raise ValueError(f"active waveform must be {ACTIVE_WAVEFORM}")
    else:
        if holder is not None or source_b is not None:
            raise ValueError("inactive light command cannot carry holder or source B")
        if values["hue_degree"] is not None or values["render_hue_degree"] is not None:
            raise ValueError("inactive light command cannot carry Hue")
        if values["blink_bpm"] is not None:
            raise ValueError("inactive light command cannot carry blink BPM")
        for name in (
            "saturation",
            "value_center",
            "value_amplitude",
            "value_min",
            "value_max",
        ):
            if _finite(name, values[name]) != 0.0:
                raise ValueError(f"inactive {name} must be zero")
        if waveform != INACTIVE_WAVEFORM:
            raise ValueError(f"inactive waveform must be {INACTIVE_WAVEFORM}")
        hue_degree = None
        render_hue_degree = None
        saturation = 0.0
        value_center = 0.0
        value_amplitude = 0.0
        value_min = 0.0
        value_max = 0.0
        blink_bpm = None

    return LightCommandInput(
        garden_id=_required_string("garden_id", values["garden_id"]),
        source_signal_index=source_signal_index,
        source_signal_time_us=source_signal_time_us,
        source_effective_time_us=source_effective_time_us,
        command_effective_time_us=command_effective_time_us,
        active=active,
        qualification_holder_id=holder,
        source_b=source_b,
        hue_degree=hue_degree,
        render_hue_degree=render_hue_degree,
        saturation=saturation,
        value_center=value_center,
        value_amplitude=value_amplitude,
        value_min=value_min,
        value_max=value_max,
        blink_bpm=blink_bpm,
        waveform=waveform,
        mapping_version=B_TO_I_MAPPING_VERSION,
        phase_policy_version=CONTINUOUS_PHASE_POLICY_VERSION,
        command_hold_policy_version=COMMAND_HOLD_POLICY_VERSION,
        inactive_output_policy_version=INACTIVE_OUTPUT_POLICY_VERSION,
        schema_version=LIGHT_COMMAND_SCHEMA_VERSION,
    )


def light_command_payload(record: LightCommandRecord) -> dict[str, object]:
    """Return the exact formal payload for one immutable command record."""

    b = record.source_b
    return {
        "garden_id": record.garden_id,
        "source_signal_index": record.source_signal_index,
        "source_signal_time_us": record.source_signal_time_us,
        "source_effective_time_us": record.source_effective_time_us,
        "command_effective_time_us": record.command_effective_time_us,
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
        "mapping_version": record.mapping_version,
        "phase_policy_version": record.phase_policy_version,
        "command_hold_policy_version": record.command_hold_policy_version,
        "inactive_output_policy_version": record.inactive_output_policy_version,
        "schema_version": record.schema_version,
    }
