"""Stage 5B Garden output configuration contract tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.garden.output_layer.config import (
    DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
    GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION,
    GARDEN_OUTPUT_MODEL_VERSION,
    GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION,
    GARDEN_QUALIFIED_B_SCHEMA_VERSION,
    QUALIFIED_B_EMISSION_POLICY_VERSION,
    GardenOutputConfig,
)

ROSTER = ("alpha", "middle", "zeta")


def test_injected_config_pins_all_stage_5b1_versions_and_lexical_roster() -> None:
    config = GardenOutputConfig(expected_digital_life_ids=("zeta", "alpha", "middle"))

    assert config.model_version == GARDEN_OUTPUT_MODEL_VERSION
    assert config.qualification_state_schema_version == (
        GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION
    )
    assert config.touch_schema_version == DIGITAL_LIFE_TOUCH_SCHEMA_VERSION
    assert config.feedback_schema_version == (
        GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION
    )
    assert config.qualified_b_schema_version == GARDEN_QUALIFIED_B_SCHEMA_VERSION
    assert config.qualified_b_emission_policy_version == (
        QUALIFIED_B_EMISSION_POLICY_VERSION
    )
    assert config.expected_digital_life_ids == ROSTER
    assert config.round_finalize_offset_us == 999_999


def test_json_round_trip_is_exact_and_rejects_missing_or_unknown_fields() -> None:
    config = GardenOutputConfig(expected_digital_life_ids=ROSTER)
    assert GardenOutputConfig.from_json(config.to_json()) == config

    values = config.to_dict()
    values.pop("hold_rule")
    with pytest.raises(ValueError, match="missing"):
        GardenOutputConfig.from_dict(values)

    values = config.to_dict()
    values["future"] = True
    with pytest.raises(ValueError, match="unknown"):
        GardenOutputConfig.from_dict(values)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("model_version", "other"),
        ("touch_schema_version", "other"),
        ("qualified_b_emission_policy_version", "other"),
        ("assignment_rule", "central_winner"),
        ("tie_break_rule", "role_order"),
        ("round_finalize_offset_us", True),
        ("round_finalize_offset_us", 999_998),
        ("expected_digital_life_ids", ("life-blue", "life-green")),
        (
            "expected_digital_life_ids",
            ("life-blue", "life-green", "life-green"),
        ),
        ("expected_digital_life_ids", ("alpha", " ", "zeta")),
    ),
)
def test_invalid_config_values_are_rejected(
    field: str,
    value: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(
            GardenOutputConfig(expected_digital_life_ids=ROSTER),
            **{field: value},
        )


def test_roster_is_required_and_arbitrary_ids_are_supported() -> None:
    with pytest.raises(TypeError):
        GardenOutputConfig()  # type: ignore[call-arg]

    config = GardenOutputConfig(
        expected_digital_life_ids=("life-omega", "life-beta", "life-kappa")
    )
    assert config.expected_digital_life_ids == (
        "life-beta",
        "life-kappa",
        "life-omega",
    )
