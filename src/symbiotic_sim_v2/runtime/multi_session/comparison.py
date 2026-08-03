"""Independent fixed-user-type comparison runs for Stage 8A diagnostics."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    stationary_user_type_ids,
)

from .config import MultiSessionRunnerConfig
from .runner import MultiSessionRelationMemoryRunner, SessionSimulationFactory

KVector = tuple[float, float, float, float]


def _optional_finite(name: str, value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number or null")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _counter(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _mapping(name: str, value: object, converter: Callable[[str, object], Any]):
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result = {
        life_id: converter(f"{name}[{life_id}]", item)
        for life_id, item in value.items()
    }
    if len(result) != 3:
        raise ValueError(f"{name} must contain exactly three Digital Lives")
    if any(not isinstance(life_id, str) or not life_id.strip() for life_id in result):
        raise ValueError(f"{name} keys must be non-empty Digital Life IDs")
    return MappingProxyType(result)


def _vector(name: str, value: object) -> KVector:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise TypeError(f"{name} must be a four-element sequence")
    values = tuple(_optional_finite(name, item) for item in value)
    if any(item is None or not 0.0 <= item <= 1.0 for item in values):
        raise ValueError(f"{name} values must be between 0 and 1")
    return values  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class StationaryUserTypeComparisonRow:
    user_type_id: str
    completed_session_count: int
    valid_session_count: int
    first_convergence_session_index: int | None
    current_convergence_state: str
    dominant_holder_id: str | None
    dominant_hue_degree: float | None
    dominant_blink_bpm: float | None
    cluster_support: int
    window_size: int
    truth_classification: str
    response_gap: float | None
    explore_count: int
    hold_count: int
    accepted_candidate_count: int
    convergence_loss_count: int
    post_convergence_outlier_rate: float
    final_k_anchor_by_life: Mapping[str, KVector]
    final_session_count_by_life: Mapping[str, int]
    final_trial_count_by_life: Mapping[str, int]

    def __post_init__(self) -> None:
        if not isinstance(self.user_type_id, str) or not self.user_type_id.strip():
            raise ValueError("user_type_id must be a non-empty string")
        for name in (
            "completed_session_count",
            "valid_session_count",
            "cluster_support",
            "window_size",
            "explore_count",
            "hold_count",
            "accepted_candidate_count",
            "convergence_loss_count",
        ):
            object.__setattr__(self, name, _counter(name, getattr(self, name)))
        first = self.first_convergence_session_index
        if first is not None:
            first = _counter("first_convergence_session_index", first)
        if (
            not isinstance(self.current_convergence_state, str)
            or not self.current_convergence_state
        ):
            raise ValueError("current_convergence_state must be a non-empty string")
        if self.dominant_holder_id is not None and (
            not isinstance(self.dominant_holder_id, str)
            or not self.dominant_holder_id.strip()
        ):
            raise ValueError("dominant_holder_id must be a non-empty string or null")
        hue = _optional_finite("dominant_hue_degree", self.dominant_hue_degree)
        bpm = _optional_finite("dominant_blink_bpm", self.dominant_blink_bpm)
        gap = _optional_finite("response_gap", self.response_gap)
        rate = _optional_finite(
            "post_convergence_outlier_rate", self.post_convergence_outlier_rate
        )
        assert rate is not None
        if not 0.0 <= rate <= 1.0:
            raise ValueError("post_convergence_outlier_rate must be between 0 and 1")
        if not isinstance(self.truth_classification, str) or not self.truth_classification:
            raise ValueError("truth_classification must be a non-empty string")
        final_k = _mapping("final_k_anchor_by_life", self.final_k_anchor_by_life, _vector)
        sessions = _mapping(
            "final_session_count_by_life",
            self.final_session_count_by_life,
            _counter,
        )
        trials = _mapping(
            "final_trial_count_by_life",
            self.final_trial_count_by_life,
            _counter,
        )
        if not (set(final_k) == set(sessions) == set(trials)):
            raise ValueError("comparison final state maps must use one roster")
        object.__setattr__(self, "first_convergence_session_index", first)
        object.__setattr__(self, "dominant_hue_degree", hue)
        object.__setattr__(self, "dominant_blink_bpm", bpm)
        object.__setattr__(self, "response_gap", gap)
        object.__setattr__(self, "post_convergence_outlier_rate", rate)
        object.__setattr__(self, "final_k_anchor_by_life", final_k)
        object.__setattr__(self, "final_session_count_by_life", sessions)
        object.__setattr__(self, "final_trial_count_by_life", trials)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_type_id": self.user_type_id,
            "completed_session_count": self.completed_session_count,
            "valid_session_count": self.valid_session_count,
            "first_convergence_session_index": self.first_convergence_session_index,
            "current_convergence_state": self.current_convergence_state,
            "dominant_holder_id": self.dominant_holder_id,
            "dominant_hue_degree": self.dominant_hue_degree,
            "dominant_blink_bpm": self.dominant_blink_bpm,
            "cluster_support": self.cluster_support,
            "window_size": self.window_size,
            "truth_classification": self.truth_classification,
            "response_gap": self.response_gap,
            "explore_count": self.explore_count,
            "hold_count": self.hold_count,
            "accepted_candidate_count": self.accepted_candidate_count,
            "convergence_loss_count": self.convergence_loss_count,
            "post_convergence_outlier_rate": self.post_convergence_outlier_rate,
            "final_k_anchor_by_life": {
                life_id: list(vector)
                for life_id, vector in self.final_k_anchor_by_life.items()
            },
            "final_session_count_by_life": dict(self.final_session_count_by_life),
            "final_trial_count_by_life": dict(self.final_trial_count_by_life),
        }


@dataclass(frozen=True, slots=True)
class StationaryUserTypeComparison:
    config_by_user_type: Mapping[str, MultiSessionRunnerConfig]
    rows: tuple[StationaryUserTypeComparisonRow, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.config_by_user_type, Mapping):
            raise TypeError("config_by_user_type must be a mapping")
        configs = MappingProxyType(dict(self.config_by_user_type))
        rows = tuple(self.rows)
        if any(not isinstance(row, StationaryUserTypeComparisonRow) for row in rows):
            raise TypeError("rows must contain StationaryUserTypeComparisonRow values")
        if tuple(configs) != tuple(row.user_type_id for row in rows):
            raise ValueError("comparison configs and rows must have identical order")
        object.__setattr__(self, "config_by_user_type", configs)
        object.__setattr__(self, "rows", rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_by_user_type": {
                user_type_id: config.to_dict()
                for user_type_id, config in self.config_by_user_type.items()
            },
            "rows": [row.to_dict() for row in self.rows],
        }


def compare_stationary_user_types(
    config: MultiSessionRunnerConfig,
    *,
    initial_persistent_state_by_life: Mapping[
        str, RelationMemoryPersistentState
    ]
    | None = None,
    session_simulation_factory: SessionSimulationFactory | None = None,
) -> StationaryUserTypeComparison:
    """Run every preset independently with identical non-profile settings."""

    if not isinstance(config, MultiSessionRunnerConfig):
        raise TypeError("config must be a MultiSessionRunnerConfig")
    configs: dict[str, MultiSessionRunnerConfig] = {}
    rows: list[StationaryUserTypeComparisonRow] = []
    for user_type_id in stationary_user_type_ids():
        type_config = replace(config, user_type_id=user_type_id)
        configs[user_type_id] = type_config
        runner_arguments: dict[str, object] = {
            "initial_persistent_state_by_life": initial_persistent_state_by_life,
        }
        if session_simulation_factory is not None:
            runner_arguments["session_simulation_factory"] = session_simulation_factory
        runner = MultiSessionRelationMemoryRunner(type_config, **runner_arguments)
        state = runner.run_all()
        convergence = (
            None
            if not state.convergence_records
            else state.convergence_records[-1]
        )
        truth = (
            None
            if not runner.truth_alignment_records()
            else runner.truth_alignment_records()[-1]
        )
        outcomes = state.session_outcomes
        final_states = state.current_persistent_state_by_life
        total_after = (
            0
            if convergence is None
            else convergence.post_convergence_cluster_member_count
            + convergence.post_convergence_outlier_count
        )
        outliers = (
            0 if convergence is None else convergence.post_convergence_outlier_count
        )
        rows.append(
            StationaryUserTypeComparisonRow(
                user_type_id=user_type_id,
                completed_session_count=state.completed_session_count,
                valid_session_count=state.valid_session_count,
                first_convergence_session_index=state.first_convergence_session_index,
                current_convergence_state=state.current_convergence_state,
                dominant_holder_id=None if convergence is None else convergence.holder_id,
                dominant_hue_degree=(
                    None if convergence is None else convergence.medoid_hue_degree
                ),
                dominant_blink_bpm=(
                    None if convergence is None else convergence.medoid_blink_bpm
                ),
                cluster_support=0 if convergence is None else convergence.support_count,
                window_size=0 if convergence is None else convergence.window_size,
                truth_classification=(
                    "not_converged" if truth is None else truth.truth_classification
                ),
                response_gap=None if truth is None else truth.response_gap,
                explore_count=sum(
                    outcome.exploration_decision == "explore" for outcome in outcomes
                ),
                hold_count=sum(
                    outcome.exploration_decision == "hold" for outcome in outcomes
                ),
                accepted_candidate_count=sum(
                    outcome.candidate_accepted for outcome in outcomes
                ),
                convergence_loss_count=(
                    0 if convergence is None else convergence.convergence_lost_count
                ),
                post_convergence_outlier_rate=(
                    0.0 if total_after == 0 else outliers / total_after
                ),
                final_k_anchor_by_life={
                    life_id: state_value.k_anchor
                    for life_id, state_value in final_states.items()
                },
                final_session_count_by_life={
                    life_id: state_value.session_count
                    for life_id, state_value in final_states.items()
                },
                final_trial_count_by_life={
                    life_id: state_value.trial_count
                    for life_id, state_value in final_states.items()
                },
            )
        )
    return StationaryUserTypeComparison(
        config_by_user_type=configs,
        rows=tuple(rows),
    )


__all__ = [
    "StationaryUserTypeComparison",
    "StationaryUserTypeComparisonRow",
    "compare_stationary_user_types",
]
