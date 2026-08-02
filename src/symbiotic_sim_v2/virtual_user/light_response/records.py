"""Immutable Stage 7 receipt, response, heartbeat, and sample diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.virtual_user.diagnostics import HeartbeatRecord
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
)

type SourceBVector = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class LightResponseSegment:
    segment_index: int
    start_time_us: int
    end_time_us: int
    duration_us: int
    light_active: bool
    render_hue_degree: float | None
    blink_bpm: float | None
    hue_match: float | None
    bpm_match: float | None
    preference_match: float
    response_target: float
    response_at_start: float
    response_at_end: float
    time_constant_seconds: float | None
    preference_model_version: str
    response_dynamics_version: str
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LightStimulusReceiptRecord:
    receipt_index: int
    event_time_us: int
    source_signal_index: int
    active: bool
    qualification_holder_id: str | None
    source_b: SourceBVector | None
    physical_stimulus: PhysicalLightStimulus
    hue_match: float | None
    bpm_match: float | None
    preference_match: float
    response_target: float
    target_changed: bool
    response_before: float
    response_after_at_same_time: float
    provenance_used_by_physiology: bool
    physical_projection_version: str
    preference_model_version: str
    input_schema_version: str

    @property
    def projection_version(self) -> str:
        return self.physical_projection_version

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LightResponsiveHeartbeatRecord(HeartbeatRecord):
    response_sample_time_us: int
    light_active_at_heartbeat: bool
    perceived_render_hue_degree: float | None
    perceived_blink_bpm: float | None
    hue_match: float | None
    bpm_match: float | None
    preference_match: float
    response_target: float
    response_level: float
    base_mean_rri_ms: float
    effective_mean_rri_ms: float
    mean_rri_increase_ms: float
    base_respiratory_amplitude_ms: float
    effective_respiratory_amplitude_ms: float
    respiratory_amplitude_gain_ms: float
    heartbeat_causality_policy_version: str
    schema_version: str

    @property
    def causality_policy_version(self) -> str:
        return self.heartbeat_causality_policy_version

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LightResponseSample:
    sample_index: int
    time_us: int
    time_seconds: float
    light_active: bool
    render_hue_degree: float | None
    blink_bpm: float | None
    preference_match: float
    response_target: float
    response_level: float
    effective_respiratory_amplitude_ms: float
    effective_mean_rri_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
