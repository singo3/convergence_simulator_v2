"""Immutable Stage 8A.3.1 two-by-two condition contracts."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from typing import Any

from symbiotic_sim_v2.digital_life.math import ETA_E, RHO_E
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    selected_session_eta,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import canonical_json

PROJECT_VERSION = "0.14.0"
VALIDATION_MODEL_VERSION = "fatigue_recovery_sigma_factorial_validation_v0_1"
FACTORIAL_CONDITION_VERSION = "fatigue_recovery_sigma_factorial_condition_v1"
FATIGUE_FACTOR_VERSION = "fatigue_recovery_factor_v0_1"
SIGMA_FACTOR_VERSION = "exploration_width_factor_v0_1"

DOCUMENT_VERSION = "v2.0"
PROFILE_VERSION = "symbiotic_signal_loop_reference_v1_0"
ALGORITHM_VERSION = "adaptive_random_search_confirmed_v1"
STATE_SCHEMA_VERSION = "relation_memory_state_v2"

FATIGUE_ACCUMULATION_POLICY = "v2_reference_eta"
WITHIN_SESSION_RECOVERY_POLICY = "v2_reference_rho"
GRADUAL_REFERENCE_ONLY = "gradual_reference_only"
UNSELECTED_FULL_RECOVERY = "unselected_full_recovery"
SESSION_END_RECOVERY_POLICIES = (
    GRADUAL_REFERENCE_ONLY,
    UNSELECTED_FULL_RECOVERY,
)

V2_REFERENCE_CONDITION = "v2_reference"
V2_RECOVERY_SIGMA050_CONDITION = "v2_recovery_sigma050"
FULL_RECOVERY_SIGMA100_CONDITION = "full_recovery_sigma100"
PROVISIONAL_CONDITION = "provisional_f15_sigma050"
CONDITION_IDS = (
    V2_REFERENCE_CONDITION,
    V2_RECOVERY_SIGMA050_CONDITION,
    FULL_RECOVERY_SIGMA100_CONDITION,
    PROVISIONAL_CONDITION,
)

EFFECTIVE_SELECTED_SESSION_FATIGUE_TARGET = 0.15
REFERENCE_ETA = 1.0 - 0.85 ** (1.0 / 180.0)
REFERENCE_RHO = 1.0 - 0.90 ** (1.0 / 180.0)


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


@dataclass(frozen=True, slots=True)
class FactorialValidationCondition:
    condition_id: str
    fatigue_accumulation_policy: str
    effective_selected_session_fatigue_target: float
    eta_selected: float
    within_session_recovery_policy: str
    rho: float
    session_end_recovery_policy: str
    sigma_multiplier: float
    formal_spec_adoption: bool = False
    document_version: str = DOCUMENT_VERSION
    profile_version: str = PROFILE_VERSION
    algorithm_version: str = ALGORITHM_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION
    validation_model_version: str = VALIDATION_MODEL_VERSION
    condition_version: str = FACTORIAL_CONDITION_VERSION
    fatigue_factor_version: str = FATIGUE_FACTOR_VERSION
    sigma_factor_version: str = SIGMA_FACTOR_VERSION

    def __post_init__(self) -> None:
        if self.condition_id not in CONDITION_IDS:
            raise ValueError(f"unknown factorial condition: {self.condition_id!r}")
        if self.fatigue_accumulation_policy != FATIGUE_ACCUMULATION_POLICY:
            raise ValueError(f"fatigue_accumulation_policy must be {FATIGUE_ACCUMULATION_POLICY}")
        target = _finite(
            "effective_selected_session_fatigue_target",
            self.effective_selected_session_fatigue_target,
        )
        eta = _finite("eta_selected", self.eta_selected)
        rho = _finite("rho", self.rho)
        sigma = _finite("sigma_multiplier", self.sigma_multiplier)
        if target != EFFECTIVE_SELECTED_SESSION_FATIGUE_TARGET:
            raise ValueError("effective selected-session fatigue target must equal 0.15")
        if eta != ETA_E or eta != REFERENCE_ETA:
            raise ValueError("eta_selected must equal the v2.0 reference eta")
        if selected_session_eta(target) != eta:
            raise ValueError("target-derived eta differs from eta_selected")
        if self.within_session_recovery_policy != WITHIN_SESSION_RECOVERY_POLICY:
            raise ValueError(
                f"within_session_recovery_policy must be {WITHIN_SESSION_RECOVERY_POLICY}"
            )
        if rho != RHO_E or rho != REFERENCE_RHO:
            raise ValueError("rho must equal the v2.0 reference rho")
        if self.session_end_recovery_policy not in SESSION_END_RECOVERY_POLICIES:
            raise ValueError("session_end_recovery_policy is not recognized")
        if sigma not in {0.5, 1.0}:
            raise ValueError("sigma_multiplier must be exactly 1.0 or 0.5")
        if not isinstance(self.formal_spec_adoption, bool):
            raise TypeError("formal_spec_adoption must be boolean")
        if self.formal_spec_adoption:
            raise ValueError("formal_spec_adoption must remain false")
        expected_factors = {
            V2_REFERENCE_CONDITION: (GRADUAL_REFERENCE_ONLY, 1.0),
            V2_RECOVERY_SIGMA050_CONDITION: (GRADUAL_REFERENCE_ONLY, 0.5),
            FULL_RECOVERY_SIGMA100_CONDITION: (UNSELECTED_FULL_RECOVERY, 1.0),
            PROVISIONAL_CONDITION: (UNSELECTED_FULL_RECOVERY, 0.5),
        }[self.condition_id]
        if (self.session_end_recovery_policy, sigma) != expected_factors:
            raise ValueError("condition ID differs from its fixed two-by-two factors")
        versions = {
            "document_version": DOCUMENT_VERSION,
            "profile_version": PROFILE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "validation_model_version": VALIDATION_MODEL_VERSION,
            "condition_version": FACTORIAL_CONDITION_VERSION,
            "fatigue_factor_version": FATIGUE_FACTOR_VERSION,
            "sigma_factor_version": SIGMA_FACTOR_VERSION,
        }
        for name, expected in versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")
        object.__setattr__(
            self,
            "effective_selected_session_fatigue_target",
            target,
        )
        object.__setattr__(self, "eta_selected", eta)
        object.__setattr__(self, "rho", rho)
        object.__setattr__(self, "sigma_multiplier", sigma)

    @property
    def uses_full_recovery(self) -> bool:
        return self.session_end_recovery_policy == UNSELECTED_FULL_RECOVERY

    @property
    def is_stage8a3_reference_equivalent(self) -> bool:
        return self.condition_id == V2_REFERENCE_CONDITION

    @property
    def is_stage8a3_provisional_equivalent(self) -> bool:
        return self.condition_id == PROVISIONAL_CONDITION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
    ) -> FactorialValidationCondition:
        if not isinstance(values, Mapping):
            raise TypeError("factorial condition must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                "factorial condition fields differ; "
                f"missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> FactorialValidationCondition:
        value = json.loads(encoded, object_pairs_hook=_strict_pairs)
        if not isinstance(value, Mapping):
            raise ValueError("factorial condition JSON must contain an object")
        return cls.from_dict(value)


def _condition(
    condition_id: str,
    recovery: str,
    sigma: float,
) -> FactorialValidationCondition:
    return FactorialValidationCondition(
        condition_id=condition_id,
        fatigue_accumulation_policy=FATIGUE_ACCUMULATION_POLICY,
        effective_selected_session_fatigue_target=(EFFECTIVE_SELECTED_SESSION_FATIGUE_TARGET),
        eta_selected=ETA_E,
        within_session_recovery_policy=WITHIN_SESSION_RECOVERY_POLICY,
        rho=RHO_E,
        session_end_recovery_policy=recovery,
        sigma_multiplier=sigma,
    )


def factorial_conditions() -> tuple[FactorialValidationCondition, ...]:
    conditions = (
        _condition(V2_REFERENCE_CONDITION, GRADUAL_REFERENCE_ONLY, 1.0),
        _condition(V2_RECOVERY_SIGMA050_CONDITION, GRADUAL_REFERENCE_ONLY, 0.5),
        _condition(FULL_RECOVERY_SIGMA100_CONDITION, UNSELECTED_FULL_RECOVERY, 1.0),
        _condition(PROVISIONAL_CONDITION, UNSELECTED_FULL_RECOVERY, 0.5),
    )
    validate_factorial_matrix(conditions)
    return conditions


def factorial_condition(condition_id: str) -> FactorialValidationCondition:
    try:
        return next(item for item in factorial_conditions() if item.condition_id == condition_id)
    except StopIteration as exc:
        raise ValueError(f"unknown factorial condition: {condition_id!r}") from exc


def validate_factorial_matrix(
    conditions: Sequence[FactorialValidationCondition],
) -> None:
    values = tuple(conditions)
    if len(values) != 4 or {item.condition_id for item in values} != set(CONDITION_IDS):
        raise ValueError("factorial matrix must contain A/B/C/D exactly once")
    if len({item.eta_selected for item in values}) != 1:
        raise ValueError("all factorial conditions must share eta")
    if len({item.rho for item in values}) != 1:
        raise ValueError("all factorial conditions must share within-session rho")
    if len({item.effective_selected_session_fatigue_target for item in values}) != 1:
        raise ValueError("all factorial conditions must share fatigue target")
    observed = {(item.session_end_recovery_policy, item.sigma_multiplier) for item in values}
    expected = {
        (GRADUAL_REFERENCE_ONLY, 1.0),
        (GRADUAL_REFERENCE_ONLY, 0.5),
        (UNSELECTED_FULL_RECOVERY, 1.0),
        (UNSELECTED_FULL_RECOVERY, 0.5),
    }
    if observed != expected:
        raise ValueError("factorial matrix must vary recovery and sigma only")


__all__ = [
    "ALGORITHM_VERSION",
    "CONDITION_IDS",
    "DOCUMENT_VERSION",
    "EFFECTIVE_SELECTED_SESSION_FATIGUE_TARGET",
    "FACTORIAL_CONDITION_VERSION",
    "FATIGUE_ACCUMULATION_POLICY",
    "FATIGUE_FACTOR_VERSION",
    "FULL_RECOVERY_SIGMA100_CONDITION",
    "FactorialValidationCondition",
    "GRADUAL_REFERENCE_ONLY",
    "PROFILE_VERSION",
    "PROJECT_VERSION",
    "PROVISIONAL_CONDITION",
    "REFERENCE_ETA",
    "REFERENCE_RHO",
    "SESSION_END_RECOVERY_POLICIES",
    "SIGMA_FACTOR_VERSION",
    "STATE_SCHEMA_VERSION",
    "UNSELECTED_FULL_RECOVERY",
    "V2_RECOVERY_SIGMA050_CONDITION",
    "V2_REFERENCE_CONDITION",
    "VALIDATION_MODEL_VERSION",
    "WITHIN_SESSION_RECOVERY_POLICY",
    "factorial_condition",
    "factorial_conditions",
    "validate_factorial_matrix",
]
