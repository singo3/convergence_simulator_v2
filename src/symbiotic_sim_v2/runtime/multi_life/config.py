"""Immutable Stage 5B multi-life runtime configuration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

THREE_DIGITAL_LIFE_RUNTIME_MODEL_VERSION = "three_digital_life_runtime_v0_1"
TAU_TOUCH_DELIVERY_POLICY_VERSION = "tau_to_microsecond_touch_delivery_v0_1"
TOUCH_EVENT_SCHEMA_VERSION = "digital_life_touch_event_v1"
TOUCH_EQUAL_TIME_TIE_BREAK_RULE = "lexicographic_digital_life_id_on_equal_arrival_us"

EXPECTED_DIGITAL_LIFE_IDS = ("life-blue", "life-green", "life-red")
ROUND_FINALIZE_OFFSET_US = 999_999


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class MultiLifeRuntimeConfig:
    """Configuration for orchestration only, never for winner selection."""

    runtime_model_version: str = THREE_DIGITAL_LIFE_RUNTIME_MODEL_VERSION
    tau_delivery_policy_version: str = TAU_TOUCH_DELIVERY_POLICY_VERSION
    touch_event_schema_version: str = TOUCH_EVENT_SCHEMA_VERSION
    tie_break_rule: str = TOUCH_EQUAL_TIME_TIE_BREAK_RULE
    expected_digital_life_ids: tuple[str, str, str] = EXPECTED_DIGITAL_LIFE_IDS
    round_finalize_offset_us: int = ROUND_FINALIZE_OFFSET_US

    def __post_init__(self) -> None:
        exact_values = {
            "runtime_model_version": THREE_DIGITAL_LIFE_RUNTIME_MODEL_VERSION,
            "tau_delivery_policy_version": TAU_TOUCH_DELIVERY_POLICY_VERSION,
            "touch_event_schema_version": TOUCH_EVENT_SCHEMA_VERSION,
            "tie_break_rule": TOUCH_EQUAL_TIME_TIE_BREAK_RULE,
            "round_finalize_offset_us": ROUND_FINALIZE_OFFSET_US,
        }
        for name, expected in exact_values.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")

        if not isinstance(self.expected_digital_life_ids, (tuple, list)):
            raise TypeError("expected_digital_life_ids must be a three-element sequence")
        life_ids = tuple(self.expected_digital_life_ids)
        if len(life_ids) != 3:
            raise ValueError("expected_digital_life_ids must contain exactly three IDs")
        if any(not isinstance(life_id, str) or not life_id.strip() for life_id in life_ids):
            raise ValueError("every expected Digital Life ID must be a non-empty string")
        if len(set(life_ids)) != len(life_ids):
            raise ValueError("expected Digital Life IDs must be unique")
        if life_ids != EXPECTED_DIGITAL_LIFE_IDS:
            raise ValueError(
                "expected_digital_life_ids must be the canonical lexicographic ID order"
            )
        _non_negative_int("round_finalize_offset_us", self.round_finalize_offset_us)
        object.__setattr__(self, "expected_digital_life_ids", life_ids)

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
    def from_dict(cls, values: dict[str, Any]) -> MultiLifeRuntimeConfig:
        if not isinstance(values, dict):
            raise TypeError("runtime config values must be a dictionary")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(f"missing runtime config fields: {', '.join(sorted(missing))}")
        if unknown := actual - expected:
            raise ValueError(f"unknown runtime config fields: {', '.join(sorted(unknown))}")
        normalized = dict(values)
        if isinstance(normalized["expected_digital_life_ids"], list):
            normalized["expected_digital_life_ids"] = tuple(
                normalized["expected_digital_life_ids"]
            )
        return cls(**normalized)

    @classmethod
    def from_json(cls, encoded: str) -> MultiLifeRuntimeConfig:
        if not isinstance(encoded, str):
            raise TypeError("encoded runtime config must be a string")
        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("runtime config JSON must contain an object")
        return cls.from_dict(values)
