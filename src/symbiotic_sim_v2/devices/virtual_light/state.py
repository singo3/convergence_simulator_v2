"""Immutable point-in-time state returned by the virtual light device."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.devices.virtual_light.records import BVector


@dataclass(frozen=True, slots=True)
class LightStateSnapshot:
    device_id: str
    model_version: str
    current_time_us: int
    active: bool
    current_holder_id: str | None
    source_signal_index: int | None
    command_effective_time_us: int | None
    command_age_us: int | None
    source_b: BVector | None
    hue_degree: float | None
    render_hue_degree: float | None
    saturation: float
    blink_bpm: float | None
    waveform: str
    phase_cycles: float | None
    current_value: float
    command_count: int
    state_event_count: int
    closed_segment_count: int
    active_command_count: int
    inactive_command_count: int
    phase_reset_count: int
    phase_continuation_count: int
    physical_parameter_change_count: int
    equivalent_command_count: int
    completed: bool
