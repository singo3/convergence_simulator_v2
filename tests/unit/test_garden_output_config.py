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
    STANDARD_DIGITAL_LIFE_IDS,
    GardenOutputConfig,
)


def test_default_config_pins_all_stage_5b_versions_and_three_ids() -> None:
    config = GardenOutputConfig()

    assert config.model_version == GARDEN_OUTPUT_MODEL_VERSION
    assert config.qualification_state_schema_version == (
        GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION
    )
    assert config.touch_schema_version == DIGITAL_LIFE_TOUCH_SCHEMA_VERSION
    assert config.feedback_schema_version == (
        GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION
    )
    assert config.qualified_b_schema_version == GARDEN_QUALIFIED_B_SCHEMA_VERSION
    assert config.expected_digital_life_ids == STANDARD_DIGITAL_LIFE_IDS
    assert config.round_finalize_offset_us == 999_999


def test_json_round_trip_is_exact_and_rejects_missing_or_unknown_fields() -> None:
    config = GardenOutputConfig()
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
        ("assignment_rule", "central_winner"),
        ("tie_break_rule", "role_order"),
        ("round_finalize_offset_us", True),
        ("round_finalize_offset_us", 999_998),
        ("expected_digital_life_ids", ("life-blue", "life-green")),
        (
            "expected_digital_life_ids",
            ("life-blue", "life-green", "life-green"),
        ),
        (
            "expected_digital_life_ids",
            ("life-red", "life-green", "life-blue"),
        ),
    ),
)
def test_invalid_config_values_are_rejected_without_silent_normalization(
    field: str,
    value: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(GardenOutputConfig(), **{field: value})
