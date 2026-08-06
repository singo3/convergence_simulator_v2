"""Strict Stage 8A.3.1 presets, plan counts, and run configuration."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    ALL_USER_TYPE_IDS,
    DEFAULT_BASE_MASTER_SEED,
    RETAIN_DETAILS_POLICIES,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import UINT32_MAX

from .conditions import (
    VALIDATION_MODEL_VERSION,
    FactorialValidationCondition,
    factorial_conditions,
    validate_factorial_matrix,
)

SHARED_RANDOM_COMPARATOR_VERSION = "shared_condition_independent_random_comparator_v0_1"
FACTORIAL_ANALYSIS_VERSION = "participant_paired_two_by_two_factorial_analysis_v0_1"
CONDITION_RECOMMENDATION_VERSION = "human_mvp_condition_comparison_v0_1"
FACTORIAL_REPORT_VERSION = "fatigue_recovery_sigma_factorial_report_v0_1"
FACTORIAL_PLAN_VERSION = "fatigue_recovery_sigma_factorial_plan_v1"
FACTORIAL_MANIFEST_VERSION = "fatigue_recovery_sigma_factorial_manifest_v1"
FACTORIAL_CODE_FINGERPRINT_VERSION = "fatigue_recovery_sigma_factorial_code_fingerprint_v0_1"
FACTORIAL_ARTIFACT_DIGEST_VERSION = "fatigue_recovery_sigma_factorial_artifact_digests_v1"

AUTONOMOUS_ARM = "autonomous_closed_loop"
SHARED_RANDOM_ARM = "pure_random_open_loop"
FACTORIAL_ARMS = (AUTONOMOUS_ARM, SHARED_RANDOM_ARM)
VALIDATION_PRESETS = ("smoke", "standard", "robust")
SMOKE_USER_TYPE_IDS = (
    "red_hue_dominant_broad_bpm",
    "green_hue_dominant_broad_bpm",
    "flat_control",
)

PRESET_DEFAULTS: Mapping[str, Mapping[str, Any]] = {
    "smoke": {
        "user_type_ids": SMOKE_USER_TYPE_IDS,
        "participants_per_type": 2,
        "maximum_sessions": 4,
        "maximum_actual_session_runs": 120,
    },
    "standard": {
        "user_type_ids": ALL_USER_TYPE_IDS,
        "participants_per_type": 10,
        "maximum_sessions": 24,
        "maximum_actual_session_runs": 10_800,
    },
    "robust": {
        "user_type_ids": ALL_USER_TYPE_IDS,
        "participants_per_type": 20,
        "maximum_sessions": 60,
        "maximum_actual_session_runs": 54_000,
    },
}
ABSOLUTE_MAXIMUM_ACTUAL_SESSION_RUNS = 54_000


def _strict_int(name: str, value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class FactorialValidationConfig:
    validation_preset: str
    conditions: tuple[FactorialValidationCondition, ...]
    user_type_ids: tuple[str, ...]
    participants_per_type: int
    maximum_sessions: int
    base_master_seed: int
    output_directory: str
    retain_details: str
    maximum_actual_session_runs: int
    validation_model_version: str = VALIDATION_MODEL_VERSION
    schema_version: str = FACTORIAL_PLAN_VERSION

    def __post_init__(self) -> None:
        if self.validation_preset not in VALIDATION_PRESETS:
            raise ValueError(f"unknown factorial validation preset: {self.validation_preset!r}")
        conditions = tuple(self.conditions)
        if any(not isinstance(item, FactorialValidationCondition) for item in conditions):
            raise TypeError("conditions must contain FactorialValidationCondition values")
        validate_factorial_matrix(conditions)
        user_types = tuple(self.user_type_ids)
        if not user_types or any(item not in ALL_USER_TYPE_IDS for item in user_types):
            raise ValueError("user_type_ids contain an unknown or empty selection")
        if len(set(user_types)) != len(user_types):
            raise ValueError("user_type_ids must be unique")
        participants = _strict_int("participants_per_type", self.participants_per_type, 1, 100)
        sessions = _strict_int("maximum_sessions", self.maximum_sessions, 4, 100)
        seed = _strict_int("base_master_seed", self.base_master_seed, 0, UINT32_MAX)
        budget = _strict_int(
            "maximum_actual_session_runs",
            self.maximum_actual_session_runs,
            1,
            ABSOLUTE_MAXIMUM_ACTUAL_SESSION_RUNS,
        )
        _required_text("output_directory", self.output_directory)
        if self.retain_details not in RETAIN_DETAILS_POLICIES:
            raise ValueError(f"retain_details must be one of {RETAIN_DETAILS_POLICIES}")
        if self.retain_details == "all" and self.validation_preset != "smoke":
            raise ValueError("retain_details=all is limited to smoke")
        if self.planned_actual_simulation_sessions > budget:
            raise ValueError(
                f"planned actual sessions {self.planned_actual_simulation_sessions} "
                f"exceed configured limit {budget}; the plan is not clipped"
            )
        if self.validation_model_version != VALIDATION_MODEL_VERSION:
            raise ValueError(f"validation_model_version must be {VALIDATION_MODEL_VERSION}")
        if self.schema_version != FACTORIAL_PLAN_VERSION:
            raise ValueError(f"schema_version must be {FACTORIAL_PLAN_VERSION}")
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "user_type_ids", user_types)
        object.__setattr__(self, "participants_per_type", participants)
        object.__setattr__(self, "maximum_sessions", sessions)
        object.__setattr__(self, "base_master_seed", seed)
        object.__setattr__(self, "maximum_actual_session_runs", budget)

    @property
    def participant_count(self) -> int:
        return len(self.user_type_ids) * self.participants_per_type

    @property
    def planned_autonomous_sessions(self) -> int:
        return len(self.conditions) * self.participant_count * self.maximum_sessions

    @property
    def planned_shared_random_sessions(self) -> int:
        return self.participant_count * self.maximum_sessions

    @property
    def planned_logical_comparison_sessions(self) -> int:
        return (
            len(self.conditions)
            * len(FACTORIAL_ARMS)
            * self.participant_count
            * self.maximum_sessions
        )

    @property
    def planned_actual_simulation_sessions(self) -> int:
        return self.planned_autonomous_sessions + self.planned_shared_random_sessions

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "conditions": [item.to_dict() for item in self.conditions],
            "user_type_ids": list(self.user_type_ids),
            "arms": list(FACTORIAL_ARMS),
            "participant_count": self.participant_count,
            "planned_autonomous_sessions": self.planned_autonomous_sessions,
            "planned_shared_random_sessions": self.planned_shared_random_sessions,
            "planned_logical_comparison_sessions": (self.planned_logical_comparison_sessions),
            "planned_actual_simulation_sessions": (self.planned_actual_simulation_sessions),
        }

    @classmethod
    def create(
        cls,
        *,
        validation_preset: str = "standard",
        participants_per_type: int | None = None,
        maximum_sessions: int | None = None,
        base_master_seed: int = DEFAULT_BASE_MASTER_SEED,
        output_directory: str = "artifacts/fatigue_recovery_sigma_factorial",
        retain_details: str = "compact",
    ) -> FactorialValidationConfig:
        if validation_preset not in PRESET_DEFAULTS:
            raise ValueError(f"unknown factorial validation preset: {validation_preset!r}")
        defaults = PRESET_DEFAULTS[validation_preset]
        participant_count = (
            int(defaults["participants_per_type"])
            if participants_per_type is None
            else participants_per_type
        )
        session_count = (
            int(defaults["maximum_sessions"]) if maximum_sessions is None else maximum_sessions
        )
        actual = (
            (len(factorial_conditions()) + 1)
            * len(defaults["user_type_ids"])
            * participant_count
            * session_count
        )
        return cls(
            validation_preset=validation_preset,
            conditions=factorial_conditions(),
            user_type_ids=tuple(defaults["user_type_ids"]),
            participants_per_type=participant_count,
            maximum_sessions=session_count,
            base_master_seed=base_master_seed,
            output_directory=output_directory,
            retain_details=retain_details,
            maximum_actual_session_runs=max(int(defaults["maximum_actual_session_runs"]), actual),
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> FactorialValidationConfig:
        if not isinstance(values, Mapping):
            raise TypeError("factorial config must be a mapping")
        normalized = dict(values)
        for derived in (
            "arms",
            "participant_count",
            "planned_autonomous_sessions",
            "planned_shared_random_sessions",
            "planned_logical_comparison_sessions",
            "planned_actual_simulation_sessions",
        ):
            normalized.pop(derived, None)
        expected = {field.name for field in fields(cls)}
        actual = set(normalized)
        if actual != expected:
            raise ValueError(
                "factorial config fields differ; "
                f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
            )
        normalized["conditions"] = tuple(
            FactorialValidationCondition.from_dict(item) for item in normalized["conditions"]
        )
        normalized["user_type_ids"] = tuple(normalized["user_type_ids"])
        result = cls(**normalized)
        encoded_actual = values.get("planned_actual_simulation_sessions")
        if (
            encoded_actual is not None
            and encoded_actual != result.planned_actual_simulation_sessions
        ):
            raise ValueError("encoded actual simulation count differs")
        return result

    @classmethod
    def from_json(cls, encoded: str) -> FactorialValidationConfig:
        value = json.loads(encoded)
        if not isinstance(value, Mapping):
            raise ValueError("factorial config JSON must contain an object")
        return cls.from_dict(value)


def factorial_plan_projection(config: FactorialValidationConfig) -> dict[str, Any]:
    return {
        "mode": "plan_only",
        "config": config.to_dict(),
        "condition_count": len(config.conditions),
        "arm_count": len(FACTORIAL_ARMS),
        "autonomous_sessions": config.planned_autonomous_sessions,
        "shared_random_sessions": config.planned_shared_random_sessions,
        "logical_comparison_sessions": config.planned_logical_comparison_sessions,
        "actual_simulation_sessions": config.planned_actual_simulation_sessions,
        "shared_random_executions_per_participant": 1,
        "yoked_arm_included": False,
        "simulation_jobs_executed": 0,
        "state_changed": False,
        "formal_spec_adoption": False,
        "validation_model_version": VALIDATION_MODEL_VERSION,
    }


__all__ = [
    "ABSOLUTE_MAXIMUM_ACTUAL_SESSION_RUNS",
    "AUTONOMOUS_ARM",
    "CONDITION_RECOMMENDATION_VERSION",
    "FACTORIAL_ANALYSIS_VERSION",
    "FACTORIAL_ARMS",
    "FACTORIAL_ARTIFACT_DIGEST_VERSION",
    "FACTORIAL_CODE_FINGERPRINT_VERSION",
    "FACTORIAL_MANIFEST_VERSION",
    "FACTORIAL_PLAN_VERSION",
    "FACTORIAL_REPORT_VERSION",
    "FactorialValidationConfig",
    "PRESET_DEFAULTS",
    "SHARED_RANDOM_ARM",
    "SHARED_RANDOM_COMPARATOR_VERSION",
    "SMOKE_USER_TYPE_IDS",
    "VALIDATION_PRESETS",
    "factorial_plan_projection",
]
