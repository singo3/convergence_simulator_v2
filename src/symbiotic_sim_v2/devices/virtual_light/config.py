"""Immutable configuration for the Stage 6 virtual PC light device."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.garden.light_mapper.config import (
    COMMAND_HOLD_POLICY_VERSION,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_COMMAND_SCHEMA_VERSION,
    PHASE_POLICY_VERSION,
)

VIRTUAL_LIGHT_DEVICE_MODEL_VERSION = "virtual_pc_light_device_v0_1"
LIGHT_STIMULUS_STATE_SCHEMA_VERSION = "light_stimulus_state_event_v1"
LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION = "light_stimulus_segment_v1"
WAVEFORM_SAMPLE_POLICY_VERSION = "fixed_virtual_grid_20ms_v0_1"


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class VirtualLightDeviceConfig:
    """Fixed identity, schema, phase, and diagnostic-grid contract."""

    device_id: str = "virtual-pc-light-001"
    model_version: str = VIRTUAL_LIGHT_DEVICE_MODEL_VERSION
    input_schema_version: str = LIGHT_COMMAND_SCHEMA_VERSION
    output_schema_version: str = LIGHT_STIMULUS_STATE_SCHEMA_VERSION
    segment_schema_version: str = LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION
    phase_policy_version: str = PHASE_POLICY_VERSION
    command_hold_policy_version: str = COMMAND_HOLD_POLICY_VERSION
    inactive_output_policy_version: str = INACTIVE_OUTPUT_POLICY_VERSION
    waveform_sample_policy_version: str = WAVEFORM_SAMPLE_POLICY_VERSION
    diagnostic_sample_interval_us: int = 20_000
    simulation_end_time_us: int = 240_000_000

    def __post_init__(self) -> None:
        _required_string("device_id", self.device_id)
        exact = {
            "model_version": VIRTUAL_LIGHT_DEVICE_MODEL_VERSION,
            "input_schema_version": LIGHT_COMMAND_SCHEMA_VERSION,
            "output_schema_version": LIGHT_STIMULUS_STATE_SCHEMA_VERSION,
            "segment_schema_version": LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION,
            "phase_policy_version": PHASE_POLICY_VERSION,
            "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
            "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
            "waveform_sample_policy_version": WAVEFORM_SAMPLE_POLICY_VERSION,
        }
        for name, expected in exact.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")
        interval_us = _positive_int(
            "diagnostic_sample_interval_us", self.diagnostic_sample_interval_us
        )
        end_time_us = _positive_int(
            "simulation_end_time_us", self.simulation_end_time_us
        )
        if end_time_us % interval_us:
            raise ValueError(
                "simulation_end_time_us must be divisible by "
                "diagnostic_sample_interval_us"
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
    def from_dict(cls, values: dict[str, Any]) -> VirtualLightDeviceConfig:
        if not isinstance(values, dict):
            raise TypeError("config values must be a dictionary")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(f"missing config fields: {', '.join(sorted(missing))}")
        if unknown := actual - expected:
            raise ValueError(f"unknown config fields: {', '.join(sorted(unknown))}")
        return cls(**values)

    @classmethod
    def from_json(cls, encoded: str) -> VirtualLightDeviceConfig:
        if not isinstance(encoded, str):
            raise TypeError("encoded config must be a string")
        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("config JSON must contain an object")
        return cls.from_dict(values)
