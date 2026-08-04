"""Immutable Stage 8A.1 experiment and grid conditions."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any

from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    UINT32_MAX,
)

from .config import (
    BASE_PROFILE_VERSION,
    DEFAULT_MASTER_SEED,
    DEFAULT_MAXIMUM_SESSIONS,
    DEFAULT_REPLICATE_COUNT,
    DEFAULT_SELECTED_SESSION_FATIGUE_TARGET,
    DEFAULT_SIGMA_MULTIPLIER,
    DEFAULT_UNSELECTED_SESSION_END_RECOVERY_FRACTION,
    DEFAULT_USER_TYPE_V2,
    FATIGUE_SIGMA_CONDITION_SCHEMA_VERSION,
    FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
    MAXIMUM_TOTAL_SESSION_RUNS,
    QUICK_FATIGUE_TARGETS,
    QUICK_SIGMA_MULTIPLIERS,
    SCALED_REFERENCE_SIGMA_POLICY_VERSION,
    STANDARD_FATIGUE_TARGETS,
    STANDARD_SIGMA_MULTIPLIERS,
    STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION,
    UNSELECTED_FULL_RECOVERY_POLICY_VERSION,
)


def _strict_json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate condition field: {key}")
        result[key] = value
    return result


def _finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _strict_int(name: str, value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _known_user_type(user_type_id: object) -> str:
    if not isinstance(user_type_id, str) or not user_type_id.strip():
        raise ValueError("user_type_id must be a non-empty string")
    from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
        stationary_user_type_profile_v2,
    )

    stationary_user_type_profile_v2(user_type_id)
    return user_type_id


def condition_id_for(
    user_type_id: str,
    selected_session_fatigue_target: float,
    sigma_multiplier: float,
    maximum_sessions: int,
) -> str:
    """Return a readable stable identity which is never used as a random key."""

    return (
        f"{user_type_id}__fatigue_{selected_session_fatigue_target:.6f}"
        f"__sigma_{sigma_multiplier:.6f}__sessions_{maximum_sessions}"
    )


@dataclass(frozen=True, slots=True)
class FatigueSigmaCondition:
    """One validated experimental-arm condition."""

    condition_id: str
    user_type_id: str
    fatigue_policy_version: str
    selected_session_fatigue_target: float
    unselected_session_end_recovery_fraction: float
    sigma_scaling_policy_version: str
    sigma_multiplier: float
    maximum_sessions: int
    master_seed: int
    session_seed_policy: str
    structured_convergence_config_version: str
    formal_spec_adoption: bool
    base_profile_version: str
    experiment_profile_version: str
    schema_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.condition_id, str) or not self.condition_id.strip():
            raise ValueError("condition_id must be a non-empty string")
        user_type_id = _known_user_type(self.user_type_id)
        target = _finite_float(
            "selected_session_fatigue_target",
            self.selected_session_fatigue_target,
        )
        if not 0.0 <= target <= 0.20:
            raise ValueError("selected_session_fatigue_target must be within [0, 0.20]")
        recovery = _finite_float(
            "unselected_session_end_recovery_fraction",
            self.unselected_session_end_recovery_fraction,
        )
        if recovery != 1.0:
            raise ValueError(
                "Stage 8A.1 unselected_session_end_recovery_fraction must be 1.0"
            )
        multiplier = _finite_float("sigma_multiplier", self.sigma_multiplier)
        if not 0.25 <= multiplier <= 1.50:
            raise ValueError("sigma_multiplier must be within [0.25, 1.50]")
        maximum_sessions = _strict_int(
            "maximum_sessions", self.maximum_sessions, 4, 100
        )
        master_seed = _strict_int("master_seed", self.master_seed, 0, UINT32_MAX)
        if (
            self.session_seed_policy
            != DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION
        ):
            raise ValueError(
                "session_seed_policy must be "
                f"{DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION}"
            )
        expected_versions = {
            "fatigue_policy_version": UNSELECTED_FULL_RECOVERY_POLICY_VERSION,
            "sigma_scaling_policy_version": SCALED_REFERENCE_SIGMA_POLICY_VERSION,
            "structured_convergence_config_version": (
                STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION
            ),
            "base_profile_version": BASE_PROFILE_VERSION,
            "experiment_profile_version": FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
            "schema_version": FATIGUE_SIGMA_CONDITION_SCHEMA_VERSION,
        }
        for name, expected in expected_versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")
        if not isinstance(self.formal_spec_adoption, bool):
            raise TypeError("formal_spec_adoption must be boolean")
        if self.formal_spec_adoption:
            raise ValueError("formal_spec_adoption must be false")
        object.__setattr__(self, "user_type_id", user_type_id)
        object.__setattr__(self, "selected_session_fatigue_target", target)
        object.__setattr__(
            self, "unselected_session_end_recovery_fraction", recovery
        )
        object.__setattr__(self, "sigma_multiplier", multiplier)
        object.__setattr__(self, "maximum_sessions", maximum_sessions)
        object.__setattr__(self, "master_seed", master_seed)

    @classmethod
    def create(
        cls,
        *,
        user_type_id: str = DEFAULT_USER_TYPE_V2,
        selected_session_fatigue_target: float = (
            DEFAULT_SELECTED_SESSION_FATIGUE_TARGET
        ),
        sigma_multiplier: float = DEFAULT_SIGMA_MULTIPLIER,
        maximum_sessions: int = DEFAULT_MAXIMUM_SESSIONS,
        master_seed: int = DEFAULT_MASTER_SEED,
        condition_id: str | None = None,
        session_seed_policy: str = (
            DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION
        ),
    ) -> FatigueSigmaCondition:
        selected_id = condition_id or condition_id_for(
            user_type_id,
            float(selected_session_fatigue_target),
            float(sigma_multiplier),
            maximum_sessions,
        )
        return cls(
            condition_id=selected_id,
            user_type_id=user_type_id,
            fatigue_policy_version=UNSELECTED_FULL_RECOVERY_POLICY_VERSION,
            selected_session_fatigue_target=selected_session_fatigue_target,
            unselected_session_end_recovery_fraction=(
                DEFAULT_UNSELECTED_SESSION_END_RECOVERY_FRACTION
            ),
            sigma_scaling_policy_version=SCALED_REFERENCE_SIGMA_POLICY_VERSION,
            sigma_multiplier=sigma_multiplier,
            maximum_sessions=maximum_sessions,
            master_seed=master_seed,
            session_seed_policy=session_seed_policy,
            structured_convergence_config_version=(
                STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION
            ),
            formal_spec_adoption=False,
            base_profile_version=BASE_PROFILE_VERSION,
            experiment_profile_version=FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
            schema_version=FATIGUE_SIGMA_CONDITION_SCHEMA_VERSION,
        )

    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> FatigueSigmaCondition:
        if not isinstance(values, Mapping):
            raise TypeError("condition values must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                f"condition fields differ; missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> FatigueSigmaCondition:
        if not isinstance(encoded, str):
            raise TypeError("encoded condition must be a string")
        values = json.loads(encoded, object_pairs_hook=_strict_json_object_pairs)
        if not isinstance(values, dict):
            raise ValueError("condition JSON must contain an object")
        return cls.from_dict(values)


def _finite_sequence(
    name: str,
    values: Sequence[float],
    minimum: float,
    maximum: float,
) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a numeric sequence")
    normalized = tuple(_finite_float(name, value) for value in values)
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    if any(not minimum <= value <= maximum for value in normalized):
        raise ValueError(f"{name} values must be within [{minimum}, {maximum}]")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} values must be unique")
    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class FatigueSigmaGridConfig:
    """Canonical paired-replicate condition grid with an explicit budget."""

    user_type_id: str = DEFAULT_USER_TYPE_V2
    fatigue_targets: tuple[float, ...] = STANDARD_FATIGUE_TARGETS
    sigma_multipliers: tuple[float, ...] = STANDARD_SIGMA_MULTIPLIERS
    maximum_sessions: int = DEFAULT_MAXIMUM_SESSIONS
    replicate_count: int = DEFAULT_REPLICATE_COUNT
    base_master_seed: int = DEFAULT_MASTER_SEED

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_type_id", _known_user_type(self.user_type_id))
        object.__setattr__(
            self,
            "fatigue_targets",
            _finite_sequence("fatigue_targets", self.fatigue_targets, 0.0, 0.20),
        )
        object.__setattr__(
            self,
            "sigma_multipliers",
            _finite_sequence(
                "sigma_multipliers", self.sigma_multipliers, 0.25, 1.50
            ),
        )
        object.__setattr__(
            self,
            "maximum_sessions",
            _strict_int("maximum_sessions", self.maximum_sessions, 4, 100),
        )
        object.__setattr__(
            self,
            "replicate_count",
            _strict_int("replicate_count", self.replicate_count, 1, 20),
        )
        object.__setattr__(
            self,
            "base_master_seed",
            _strict_int("base_master_seed", self.base_master_seed, 0, UINT32_MAX),
        )
        if self.total_planned_session_runs > MAXIMUM_TOTAL_SESSION_RUNS:
            raise ValueError(
                "planned session runs exceed the Stage 8A.1 limit of "
                f"{MAXIMUM_TOTAL_SESSION_RUNS}"
            )

    @property
    def condition_count(self) -> int:
        return len(self.fatigue_targets) * len(self.sigma_multipliers)

    @property
    def total_planned_session_runs(self) -> int:
        return self.condition_count * self.replicate_count * self.maximum_sessions

    def conditions(self, *, replicate_master_seed: int) -> tuple[FatigueSigmaCondition, ...]:
        return tuple(
            FatigueSigmaCondition.create(
                user_type_id=self.user_type_id,
                selected_session_fatigue_target=fatigue,
                sigma_multiplier=sigma,
                maximum_sessions=self.maximum_sessions,
                master_seed=replicate_master_seed,
            )
            for fatigue in self.fatigue_targets
            for sigma in self.sigma_multipliers
        )

    @classmethod
    def quick(
        cls,
        *,
        user_type_id: str = DEFAULT_USER_TYPE_V2,
        base_master_seed: int = DEFAULT_MASTER_SEED,
    ) -> FatigueSigmaGridConfig:
        return cls(
            user_type_id=user_type_id,
            fatigue_targets=QUICK_FATIGUE_TARGETS,
            sigma_multipliers=QUICK_SIGMA_MULTIPLIERS,
            maximum_sessions=12,
            replicate_count=3,
            base_master_seed=base_master_seed,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_type_id": self.user_type_id,
            "fatigue_targets": list(self.fatigue_targets),
            "sigma_multipliers": list(self.sigma_multipliers),
            "maximum_sessions": self.maximum_sessions,
            "replicate_count": self.replicate_count,
            "base_master_seed": self.base_master_seed,
            "condition_count": self.condition_count,
            "total_planned_session_runs": self.total_planned_session_runs,
        }


__all__ = [
    "FatigueSigmaCondition",
    "FatigueSigmaGridConfig",
    "condition_id_for",
]
