"""Immutable command, state, segment, and waveform records for Stage 6."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

type BVector = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class LightCommandRecord:
    command_index: int
    garden_id: str
    source_signal_index: int
    source_signal_time_us: int
    source_effective_time_us: int
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
    mapping_version: str
    phase_policy_version: str
    command_hold_policy_version: str
    inactive_output_policy_version: str
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LightStimulusStateRecord:
    state_index: int
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LightStimulusSegment:
    segment_index: int
    start_time_us: int
    end_time_us: int
    duration_us: int
    active: bool
    source_signal_index: int
    source_signal_time_us: int
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
    phase_cycles_at_end: float | None
    value_at_start: float
    value_at_end: float
    mapping_version: str
    phase_policy_version: str
    command_hold_policy_version: str
    inactive_output_policy_version: str
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LightWaveformSample:
    sample_index: int
    time_us: int
    time_seconds: float
    active: bool
    source_signal_index: int | None
    holder_id: str | None
    hue_degree: float | None
    render_hue_degree: float | None
    saturation: float
    blink_bpm: float | None
    phase_cycles: float | None
    value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
