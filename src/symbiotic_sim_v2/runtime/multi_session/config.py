"""Immutable orchestration configuration for the Stage 8A runner."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from symbiotic_sim_v2.convergence.config import RollingConvergenceConfig
from symbiotic_sim_v2.virtual_user.stationary_landscape.presets import (
    DEFAULT_STATIONARY_USER_TYPE,
    stationary_user_type_profile,
)

from .session_seed import (
    DEFAULT_MASTER_SEED,
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    SESSION_SEED_POLICIES,
    UINT32_MAX,
)

MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION = (
    "multi_session_relation_memory_runner_v0_1"
)


@dataclass(frozen=True, slots=True)
class MultiSessionRunnerConfig:
    """Select one fixed user type and diagnostic policy for an entire run."""

    user_type_id: str = DEFAULT_STATIONARY_USER_TYPE
    master_seed: int = DEFAULT_MASTER_SEED
    session_seed_policy: str = (
        DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION
    )
    convergence_config: RollingConvergenceConfig = RollingConvergenceConfig()
    runner_version: str = MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.user_type_id, str) or not self.user_type_id.strip():
            raise ValueError("user_type_id must be a non-empty string")
        # Resolve now so a run can never change to an unknown profile halfway.
        stationary_user_type_profile(self.user_type_id)
        if isinstance(self.master_seed, bool) or not isinstance(self.master_seed, int):
            raise TypeError("master_seed must be an integer")
        if not 0 <= self.master_seed <= UINT32_MAX:
            raise ValueError(f"master_seed must be between 0 and {UINT32_MAX}")
        if self.session_seed_policy not in SESSION_SEED_POLICIES:
            raise ValueError("session_seed_policy is not recognized")
        if not isinstance(self.convergence_config, RollingConvergenceConfig):
            raise TypeError("convergence_config must be a RollingConvergenceConfig")
        if self.runner_version != MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION:
            raise ValueError(
                f"runner_version must be {MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION}"
            )

    @property
    def maximum_sessions(self) -> int:
        return self.convergence_config.maximum_sessions

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_type_id": self.user_type_id,
            "master_seed": self.master_seed,
            "session_seed_policy": self.session_seed_policy,
            "convergence_config": self.convergence_config.to_dict(),
            "runner_version": self.runner_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> MultiSessionRunnerConfig:
        if not isinstance(values, Mapping):
            raise TypeError("runner config values must be a mapping")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if actual != expected:
            raise ValueError(
                f"runner config fields differ; missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        normalized = dict(values)
        convergence = normalized["convergence_config"]
        if not isinstance(convergence, RollingConvergenceConfig):
            normalized["convergence_config"] = RollingConvergenceConfig.from_dict(
                convergence
            )
        return cls(**normalized)

    @classmethod
    def from_json(cls, encoded: str) -> MultiSessionRunnerConfig:
        if not isinstance(encoded, str):
            raise TypeError("encoded runner config must be a string")
        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("runner config JSON must contain an object")
        return cls.from_dict(values)


__all__ = [
    "MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION",
    "MultiSessionRunnerConfig",
]
