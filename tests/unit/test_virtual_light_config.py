"""Strict Stage 6 virtual-light configuration tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.devices.virtual_light.config import (
    LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION,
    LIGHT_STIMULUS_STATE_SCHEMA_VERSION,
    VIRTUAL_LIGHT_DEVICE_MODEL_VERSION,
    WAVEFORM_SAMPLE_POLICY_VERSION,
    VirtualLightDeviceConfig,
)
from symbiotic_sim_v2.garden.light_mapper.config import (
    COMMAND_HOLD_POLICY_VERSION,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_COMMAND_SCHEMA_VERSION,
    PHASE_POLICY_VERSION,
)


def test_default_config_pins_every_stage6_device_version_and_grid() -> None:
    config = VirtualLightDeviceConfig()

    assert config.device_id == "virtual-pc-light-001"
    assert config.model_version == VIRTUAL_LIGHT_DEVICE_MODEL_VERSION
    assert config.input_schema_version == LIGHT_COMMAND_SCHEMA_VERSION
    assert config.output_schema_version == LIGHT_STIMULUS_STATE_SCHEMA_VERSION
    assert config.segment_schema_version == LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION
    assert config.phase_policy_version == PHASE_POLICY_VERSION
    assert config.command_hold_policy_version == COMMAND_HOLD_POLICY_VERSION
    assert config.inactive_output_policy_version == INACTIVE_OUTPUT_POLICY_VERSION
    assert config.waveform_sample_policy_version == WAVEFORM_SAMPLE_POLICY_VERSION
    assert config.diagnostic_sample_interval_us == 20_000
    assert config.simulation_end_time_us == 240_000_000


def test_config_json_round_trip_is_exact_and_rejects_missing_or_unknown() -> None:
    config = VirtualLightDeviceConfig()
    assert VirtualLightDeviceConfig.from_json(config.to_json()) == config

    missing = config.to_dict()
    missing.pop("device_id")
    with pytest.raises(ValueError, match="missing"):
        VirtualLightDeviceConfig.from_dict(missing)

    unknown = config.to_dict()
    unknown["future"] = True
    with pytest.raises(ValueError, match="unknown"):
        VirtualLightDeviceConfig.from_dict(unknown)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("device_id", " "),
        ("model_version", "other"),
        ("input_schema_version", "other"),
        ("output_schema_version", "other"),
        ("segment_schema_version", "other"),
        ("phase_policy_version", "other"),
        ("command_hold_policy_version", "other"),
        ("inactive_output_policy_version", "other"),
        ("waveform_sample_policy_version", "other"),
        ("diagnostic_sample_interval_us", True),
        ("diagnostic_sample_interval_us", 0),
        ("simulation_end_time_us", False),
        ("simulation_end_time_us", -1),
        ("simulation_end_time_us", 240_000_001),
    ),
)
def test_config_rejects_wrong_versions_bool_and_invalid_grid(
    field: str,
    value: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(VirtualLightDeviceConfig(), **{field: value})
