"""Garden Light Mapper configuration boundary tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.garden.light_mapper.config import (
    B_TO_I_MAPPING_VERSION,
    COMMAND_HOLD_POLICY_VERSION,
    CONTINUOUS_PHASE_POLICY_VERSION,
    GARDEN_LIGHT_MAPPER_MODEL_VERSION,
    GARDEN_QUALIFIED_B_INPUT_SCHEMA_VERSION,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_COMMAND_SCHEMA_VERSION,
    GardenLightMapperConfig,
)


def test_standard_mapper_config_is_exact_and_json_round_trips() -> None:
    config = GardenLightMapperConfig()
    assert config.model_version == GARDEN_LIGHT_MAPPER_MODEL_VERSION
    assert config.mapping_version == B_TO_I_MAPPING_VERSION
    assert config.input_schema_version == GARDEN_QUALIFIED_B_INPUT_SCHEMA_VERSION
    assert config.output_schema_version == LIGHT_COMMAND_SCHEMA_VERSION
    assert config.phase_policy_version == CONTINUOUS_PHASE_POLICY_VERSION
    assert config.command_hold_policy_version == COMMAND_HOLD_POLICY_VERSION
    assert config.inactive_output_policy_version == INACTIVE_OUTPUT_POLICY_VERSION
    assert config.hue_scale_degree == 360.0
    assert (config.blink_bpm_min, config.blink_bpm_max) == (10.0, 165.0)
    assert (config.value_min, config.value_center, config.value_max) == (
        0.35,
        0.425,
        0.50,
    )
    assert GardenLightMapperConfig.from_json(config.to_json()) == config


@pytest.mark.parametrize("field", tuple(GardenLightMapperConfig.__dataclass_fields__))
def test_mapper_config_rejects_every_missing_field(field: str) -> None:
    values = GardenLightMapperConfig().to_dict()
    del values[field]
    with pytest.raises(ValueError, match="missing"):
        GardenLightMapperConfig.from_dict(values)


def test_mapper_config_rejects_unknown_field() -> None:
    values = GardenLightMapperConfig().to_dict()
    values["future"] = True
    with pytest.raises(ValueError, match="unknown"):
        GardenLightMapperConfig.from_dict(values)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("model_version", "wrong"),
        ("mapping_version", "wrong"),
        ("input_schema_version", "wrong"),
        ("output_schema_version", "wrong"),
        ("phase_policy_version", "wrong"),
        ("command_hold_policy_version", "wrong"),
        ("inactive_output_policy_version", "wrong"),
        ("waveform", "square"),
    ),
)
def test_mapper_config_rejects_version_or_policy_mismatch(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValueError):
        replace(GardenLightMapperConfig(), **{field: value})


@pytest.mark.parametrize(
    "field",
    (
        "hue_scale_degree",
        "blink_bpm_min",
        "blink_bpm_max",
        "saturation",
        "value_center",
        "value_amplitude",
        "value_min",
        "value_max",
    ),
)
def test_mapper_config_rejects_bool_and_non_finite_numbers(field: str) -> None:
    config = GardenLightMapperConfig()
    with pytest.raises(TypeError):
        replace(config, **{field: True})
    with pytest.raises(ValueError, match="finite"):
        replace(config, **{field: float("nan")})


def test_mapper_config_validates_value_identity_and_axis_usage() -> None:
    config = GardenLightMapperConfig()
    with pytest.raises(ValueError, match="value_min"):
        replace(config, value_min=0.34)
    with pytest.raises(ValueError, match="value_max"):
        replace(config, value_max=0.51)
    with pytest.raises(ValueError, match="use_a_axis"):
        replace(config, use_a_axis=True)
    with pytest.raises(ValueError, match="use_t_axis"):
        replace(config, use_t_axis=False)


def test_mapper_config_accepts_consistent_finite_reference_parameters() -> None:
    config = replace(
        GardenLightMapperConfig(),
        hue_scale_degree=720.0,
        blink_bpm_min=20.0,
        blink_bpm_max=200.0,
        value_center=0.4,
        value_amplitude=0.1,
        value_min=0.3,
        value_max=0.5,
    )
    assert GardenLightMapperConfig.from_dict(config.to_dict()) == config
