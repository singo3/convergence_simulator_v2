"""Immutable Stage 6 Garden Light Mapper records and snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .mapping import BVector


@dataclass(frozen=True, slots=True)
class LightCommandRecord:
    command_index: int
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

    @property
    def effective_time_us(self) -> int:
        """Return the concise record/CSV alias for command effective time."""

        return self.command_effective_time_us

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GardenLightMapperSnapshot:
    garden_id: str
    model_version: str
    mapping_version: str
    input_schema_version: str
    output_schema_version: str
    command_count: int
    active_command_count: int
    inactive_command_count: int
    last_source_signal_index: int | None
    last_source_effective_time_us: int | None
    current_command: LightCommandRecord | None
