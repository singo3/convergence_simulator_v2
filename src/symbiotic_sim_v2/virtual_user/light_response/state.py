"""Read-only current state of the Stage 7 light-responsive virtual user."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LightResponsiveVirtualUserSnapshot:
    user_id: str
    base_model_version: str
    light_response_model_version: str
    heartbeat_count: int
    current_heartbeat_time_us: int | None
    latest_true_rri_ms: float | None
    latest_instantaneous_hr_bpm: float | None
    current_light_active: bool
    current_render_hue_degree: float | None
    current_blink_bpm: float | None
    current_hue_match: float | None
    current_bpm_match: float | None
    current_preference_match: float
    current_response_target: float
    current_response_level: float
    base_respiratory_amplitude_ms: float
    effective_respiratory_amplitude_ms: float
    current_respiratory_gain_ms: float
    base_mean_rri_ms: float
    effective_mean_rri_ms: float
    current_mean_rri_increase_ms: float
    light_input_count: int
    physical_stimulus_change_count: int
    response_target_change_count: int
    physical_audit_segment_count: int
    response_dynamics_epoch_count: int
    response_segment_count: int
    clamped_beat_count: int
    completed: bool

    @property
    def physical_parameter_change_count(self) -> int:
        """Compatibility spelling for physical-stimulus parameter changes."""

        return self.physical_stimulus_change_count

    @property
    def audit_segment_count(self) -> int:
        return self.physical_audit_segment_count
