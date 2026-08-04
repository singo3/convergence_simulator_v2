"""Named canonical digests used by Stage 8A.1 result schemas."""

from __future__ import annotations

from typing import Any

from .canonical import canonical_digest


def experiment_condition_digest(value: Any) -> str:
    return canonical_digest(value)


def fatigue_trajectory_digest(value: Any) -> str:
    return canonical_digest(value)


def sigma_trajectory_digest(value: Any) -> str:
    return canonical_digest(value)


def structured_convergence_digest(value: Any) -> str:
    return canonical_digest(value)


def replicate_result_digest(value: Any) -> str:
    return canonical_digest(value)


def condition_summary_digest(value: Any) -> str:
    return canonical_digest(value)


def grid_summary_digest(value: Any) -> str:
    return canonical_digest(value)


def experiment_manifest_digest(value: Any) -> str:
    return canonical_digest(value)


def final_experimental_state_digest(value: Any) -> str:
    return canonical_digest(value)


__all__ = [
    "condition_summary_digest",
    "experiment_condition_digest",
    "experiment_manifest_digest",
    "fatigue_trajectory_digest",
    "final_experimental_state_digest",
    "grid_summary_digest",
    "replicate_result_digest",
    "sigma_trajectory_digest",
    "structured_convergence_digest",
]
