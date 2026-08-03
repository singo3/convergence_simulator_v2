"""Strict immutable configuration for the Stage 7 light-response assumption."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields
from typing import Any

LIGHT_RESPONSE_MODEL_VERSION = "stationary_light_responsive_virtual_user_v0_2"
PHYSICAL_PROJECTION_VERSION = "physical_light_stimulus_projection_v0_1"
PREFERENCE_MODEL_VERSION = "stationary_hue_bpm_gaussian_preference_v0_1"
RESPONSE_DYNAMICS_VERSION = "first_order_light_response_v0_1"
PHYSIOLOGY_COUPLING_VERSION = "light_response_rsa_mean_rri_coupling_v0_1"
HEARTBEAT_CAUSALITY_POLICY_VERSION = "sample_light_response_at_heartbeat_start_v0_1"
LIGHT_RESPONSE_INPUT_SCHEMA_VERSION = "light_stimulus_state_event_v1"
LIGHT_RESPONSE_SEGMENT_SCHEMA_VERSION = "light_response_segment_v2"
LIGHT_RESPONSE_DYNAMICS_EPOCH_SCHEMA_VERSION = "light_response_dynamics_epoch_v1"
PHYSICAL_STIMULUS_CHANGE_POLICY_VERSION = "physical_stimulus_parameter_change_v0_1"
PHYSICAL_LIGHT_PARAMETER_SIGNATURE_VERSION = (
    "physical_light_parameter_signature_v0_1"
)
SEGMENT_SPLIT_POLICY_VERSION = (
    "split_audit_on_physical_change_keep_response_on_same_target_v0_1"
)
RESPONSIVE_HEARTBEAT_SCHEMA_VERSION = "light_responsive_heartbeat_record_v1"
DIAGNOSTIC_SAMPLING_POLICY_VERSION = "fixed_virtual_grid_100ms_v0_1"
RESPONSE_SAMPLING_VERSION = DIAGNOSTIC_SAMPLING_POLICY_VERSION
MATCH_COMBINATION = "product"
STAGE_7_SIMULATION_END_TIME_US = 240_000_000


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _bounded(name: str, value: object, minimum: float, maximum: float) -> float:
    converted = _finite_number(name, value)
    if not minimum <= converted <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return converted


@dataclass(frozen=True, slots=True)
class LightResponseConfig:
    """Versioned stationary preference, response, and coupling parameters."""

    model_version: str = LIGHT_RESPONSE_MODEL_VERSION
    physical_projection_version: str = PHYSICAL_PROJECTION_VERSION
    preference_model_version: str = PREFERENCE_MODEL_VERSION
    response_dynamics_version: str = RESPONSE_DYNAMICS_VERSION
    physiology_coupling_version: str = PHYSIOLOGY_COUPLING_VERSION
    heartbeat_causality_policy_version: str = HEARTBEAT_CAUSALITY_POLICY_VERSION
    input_schema_version: str = LIGHT_RESPONSE_INPUT_SCHEMA_VERSION
    response_segment_schema_version: str = LIGHT_RESPONSE_SEGMENT_SCHEMA_VERSION
    response_dynamics_epoch_schema_version: str = (
        LIGHT_RESPONSE_DYNAMICS_EPOCH_SCHEMA_VERSION
    )
    physical_stimulus_change_policy_version: str = (
        PHYSICAL_STIMULUS_CHANGE_POLICY_VERSION
    )
    physical_light_parameter_signature_version: str = (
        PHYSICAL_LIGHT_PARAMETER_SIGNATURE_VERSION
    )
    segment_split_policy_version: str = SEGMENT_SPLIT_POLICY_VERSION
    responsive_heartbeat_schema_version: str = RESPONSIVE_HEARTBEAT_SCHEMA_VERSION
    enabled: bool = True
    preference_stationary: bool = True
    preferred_hue_degree: float = 125.0
    hue_sigma_degree: float = 5.0
    preferred_blink_bpm: float = 87.5
    blink_sigma_bpm: float = 30.0
    match_combination: str = MATCH_COMBINATION
    maximum_respiratory_amplitude_gain_ms: float = 30.0
    maximum_mean_rri_increase_ms: float = 15.0
    response_onset_time_constant_seconds: float = 8.0
    response_recovery_time_constant_seconds: float = 12.0
    response_min: float = 0.0
    response_max: float = 1.0
    diagnostic_sample_interval_us: int = 100_000
    simulation_end_time_us: int = STAGE_7_SIMULATION_END_TIME_US

    def __post_init__(self) -> None:
        exact_versions = {
            "model_version": LIGHT_RESPONSE_MODEL_VERSION,
            "physical_projection_version": PHYSICAL_PROJECTION_VERSION,
            "preference_model_version": PREFERENCE_MODEL_VERSION,
            "response_dynamics_version": RESPONSE_DYNAMICS_VERSION,
            "physiology_coupling_version": PHYSIOLOGY_COUPLING_VERSION,
            "heartbeat_causality_policy_version": HEARTBEAT_CAUSALITY_POLICY_VERSION,
            "input_schema_version": LIGHT_RESPONSE_INPUT_SCHEMA_VERSION,
            "response_segment_schema_version": LIGHT_RESPONSE_SEGMENT_SCHEMA_VERSION,
            "response_dynamics_epoch_schema_version": (
                LIGHT_RESPONSE_DYNAMICS_EPOCH_SCHEMA_VERSION
            ),
            "physical_stimulus_change_policy_version": (
                PHYSICAL_STIMULUS_CHANGE_POLICY_VERSION
            ),
            "physical_light_parameter_signature_version": (
                PHYSICAL_LIGHT_PARAMETER_SIGNATURE_VERSION
            ),
            "segment_split_policy_version": SEGMENT_SPLIT_POLICY_VERSION,
            "responsive_heartbeat_schema_version": RESPONSIVE_HEARTBEAT_SCHEMA_VERSION,
            "match_combination": MATCH_COMBINATION,
        }
        for name, expected in exact_versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be boolean")
        if not isinstance(self.preference_stationary, bool):
            raise TypeError("preference_stationary must be boolean")
        if not self.preference_stationary:
            raise ValueError("preference_stationary must be true")

        ranges = {
            "preferred_hue_degree": (0.0, 360.0),
            "hue_sigma_degree": (0.0, 180.0),
            "preferred_blink_bpm": (10.0, 165.0),
        }
        for name, (minimum, maximum) in ranges.items():
            value = _bounded(name, getattr(self, name), minimum, maximum)
            if name == "hue_sigma_degree" and value == 0.0:
                raise ValueError("hue_sigma_degree must be positive")
            object.__setattr__(self, name, value)
        blink_sigma = _finite_number("blink_sigma_bpm", self.blink_sigma_bpm)
        if blink_sigma <= 0.0:
            raise ValueError("blink_sigma_bpm must be positive")
        object.__setattr__(self, "blink_sigma_bpm", blink_sigma)

        for name in (
            "maximum_respiratory_amplitude_gain_ms",
            "maximum_mean_rri_increase_ms",
        ):
            value = _finite_number(name, getattr(self, name))
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)
        for name in (
            "response_onset_time_constant_seconds",
            "response_recovery_time_constant_seconds",
        ):
            value = _finite_number(name, getattr(self, name))
            if value <= 0.0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)

        response_min = _finite_number("response_min", self.response_min)
        response_max = _finite_number("response_max", self.response_max)
        if response_min != 0.0:
            raise ValueError("response_min must be exactly 0")
        if response_max != 1.0:
            raise ValueError("response_max must be exactly 1")
        object.__setattr__(self, "response_min", response_min)
        object.__setattr__(self, "response_max", response_max)
        if (
            isinstance(self.diagnostic_sample_interval_us, bool)
            or not isinstance(self.diagnostic_sample_interval_us, int)
        ):
            raise TypeError("diagnostic_sample_interval_us must be an integer")
        if self.diagnostic_sample_interval_us <= 0:
            raise ValueError("diagnostic_sample_interval_us must be positive")
        if (
            isinstance(self.simulation_end_time_us, bool)
            or not isinstance(self.simulation_end_time_us, int)
        ):
            raise TypeError("simulation_end_time_us must be an integer")
        if self.simulation_end_time_us != STAGE_7_SIMULATION_END_TIME_US:
            raise ValueError(
                f"simulation_end_time_us must be {STAGE_7_SIMULATION_END_TIME_US}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> LightResponseConfig:
        if not isinstance(values, dict):
            raise TypeError("config values must be a dictionary")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            missing = sorted(expected - actual)
            unknown = sorted(actual - expected)
            raise ValueError(f"config fields differ; missing={missing}, unknown={unknown}")
        return cls(**values)

    @classmethod
    def from_json(cls, encoded: str) -> LightResponseConfig:
        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("config JSON must contain an object")
        return cls.from_dict(values)
