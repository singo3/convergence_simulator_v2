"""Immutable Stage 5B Garden output-qualification configuration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

GARDEN_OUTPUT_MODEL_VERSION = "relax_with_light_garden_output_qualification_v0_2"
GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION = "garden_qualification_state_v1"
DIGITAL_LIFE_TOUCH_SCHEMA_VERSION = "digital_life_touch_event_v2"
GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION = (
    "garden_interoceptive_feedback_event_v1"
)
GARDEN_QUALIFIED_B_SCHEMA_VERSION = "garden_qualified_b_event_v2"
QUALIFIED_B_EMISSION_POLICY_VERSION = "qualified_b_on_holder_touch_v0_1"

FIRST_TOUCH_ASSIGNMENT_RULE = "first_touch_when_empty"
HOLD_WHILE_ACTIVE_RULE = "while_s_is_1"
RELEASE_AFTER_CLOSING_RULE = "after_closing_second_round_when_s_is_0"
LEXICOGRAPHIC_EQUAL_TIME_TIE_BREAK = (
    "lexicographic_digital_life_id_on_equal_arrival_us"
)
ROUND_FINALIZE_OFFSET_US = 999_999


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class GardenOutputConfig:
    """Exact Garden qualification boundary used by the Stage 5B runtime."""

    expected_digital_life_ids: tuple[str, str, str]
    garden_id: str = "relax-with-light"
    model_version: str = GARDEN_OUTPUT_MODEL_VERSION
    qualification_state_schema_version: str = (
        GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION
    )
    touch_schema_version: str = DIGITAL_LIFE_TOUCH_SCHEMA_VERSION
    feedback_schema_version: str = GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION
    qualified_b_schema_version: str = GARDEN_QUALIFIED_B_SCHEMA_VERSION
    qualified_b_emission_policy_version: str = QUALIFIED_B_EMISSION_POLICY_VERSION
    assignment_rule: str = FIRST_TOUCH_ASSIGNMENT_RULE
    hold_rule: str = HOLD_WHILE_ACTIVE_RULE
    release_rule: str = RELEASE_AFTER_CLOSING_RULE
    tie_break_rule: str = LEXICOGRAPHIC_EQUAL_TIME_TIE_BREAK
    round_finalize_offset_us: int = ROUND_FINALIZE_OFFSET_US

    def __post_init__(self) -> None:
        _required_string("garden_id", self.garden_id)
        exact = {
            "model_version": GARDEN_OUTPUT_MODEL_VERSION,
            "qualification_state_schema_version": (
                GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION
            ),
            "touch_schema_version": DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
            "feedback_schema_version": GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION,
            "qualified_b_schema_version": GARDEN_QUALIFIED_B_SCHEMA_VERSION,
            "qualified_b_emission_policy_version": (
                QUALIFIED_B_EMISSION_POLICY_VERSION
            ),
            "assignment_rule": FIRST_TOUCH_ASSIGNMENT_RULE,
            "hold_rule": HOLD_WHILE_ACTIVE_RULE,
            "release_rule": RELEASE_AFTER_CLOSING_RULE,
            "tie_break_rule": LEXICOGRAPHIC_EQUAL_TIME_TIE_BREAK,
        }
        for name, expected in exact.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")

        ids = self.expected_digital_life_ids
        if not isinstance(ids, (tuple, list)):
            raise TypeError("expected_digital_life_ids must be a three-element sequence")
        normalized_ids = tuple(
            _required_string(f"expected_digital_life_ids[{index}]", value)
            for index, value in enumerate(ids)
        )
        if len(normalized_ids) != 3:
            raise ValueError("exactly three Digital Life IDs are required")
        if len(set(normalized_ids)) != 3:
            raise ValueError("expected Digital Life IDs must be unique")
        normalized_ids = tuple(sorted(normalized_ids))
        offset = _required_positive_int(
            "round_finalize_offset_us", self.round_finalize_offset_us
        )
        if offset != ROUND_FINALIZE_OFFSET_US:
            raise ValueError(
                f"round_finalize_offset_us must be {ROUND_FINALIZE_OFFSET_US}"
            )
        object.__setattr__(self, "expected_digital_life_ids", normalized_ids)

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
    def from_dict(cls, values: dict[str, Any]) -> GardenOutputConfig:
        if not isinstance(values, dict):
            raise TypeError("config values must be a dictionary")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(f"missing config fields: {', '.join(sorted(missing))}")
        if unknown := actual - expected:
            raise ValueError(f"unknown config fields: {', '.join(sorted(unknown))}")
        normalized = dict(values)
        if isinstance(normalized["expected_digital_life_ids"], list):
            normalized["expected_digital_life_ids"] = tuple(
                normalized["expected_digital_life_ids"]
            )
        return cls(**normalized)

    @classmethod
    def from_json(cls, encoded: str) -> GardenOutputConfig:
        if not isinstance(encoded, str):
            raise TypeError("encoded config must be a string")
        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("config JSON must contain an object")
        return cls.from_dict(values)
