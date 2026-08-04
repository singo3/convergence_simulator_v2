"""Strict, resumable Stage 8A.1 state with atomic persistent-state handoff."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    relation_memory_state_map_from_dict,
    relation_memory_state_map_to_dict,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.condition import (
    FatigueSigmaCondition,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    EXPERIMENTAL_MULTI_SESSION_STATE_SCHEMA_VERSION,
    FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    physiology_root_seed_for_session,
)

from .session_outcome import ExperimentalSessionOutcome


def _strict_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate experiment-state field: {key}")
        result[key] = value
    return result


def _life_ids(values: Mapping[str, object]) -> tuple[str, str, str]:
    ids = tuple(values)
    canonical = tuple(
        digital_life_config_for_role(role).digital_life_id
        for role in ("red", "green", "blue")
    )
    if (
        len(ids) != 3
        or any(not isinstance(value, str) for value in ids)
        or set(ids) != set(canonical)
    ):
        raise ValueError("Stage 8A.1 state requires the fixed three-life roster")
    return ids  # type: ignore[return-value]


def _state_map(
    values: Mapping[str, RelationMemoryPersistentState] | Mapping[str, Any],
    *,
    expected_ids: Sequence[str] | None = None,
) -> Mapping[str, RelationMemoryPersistentState]:
    if not isinstance(values, Mapping):
        raise TypeError("persistent state map must be a mapping")
    ids = _life_ids(values) if expected_ids is None else tuple(expected_ids)
    raw = {
        life_id: value.to_dict()
        if isinstance(value, RelationMemoryPersistentState)
        else value
        for life_id, value in values.items()
    }
    return relation_memory_state_map_from_dict(
        raw,
        expected_digital_life_ids=ids,
    )


@dataclass(frozen=True, slots=True)
class FatigueSigmaExperimentState:
    """Everything required to resume at the next independent session boundary."""

    condition: FatigueSigmaCondition
    initial_persistent_state_by_life: Mapping[str, RelationMemoryPersistentState]
    current_persistent_state_by_life: Mapping[str, RelationMemoryPersistentState]
    session_outcomes: tuple[ExperimentalSessionOutcome, ...]
    reference_arm_enabled: bool
    reference_initial_persistent_state_by_life: Mapping[
        str, RelationMemoryPersistentState
    ]
    reference_current_persistent_state_by_life: Mapping[
        str, RelationMemoryPersistentState
    ]
    reference_session_outcomes: tuple[ExperimentalSessionOutcome, ...]
    next_session_index: int
    stopped_on_error: bool
    lab_model_version: str = FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION
    schema_version: str = EXPERIMENTAL_MULTI_SESSION_STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.condition, FatigueSigmaCondition):
            raise TypeError("condition must be a FatigueSigmaCondition")
        if not isinstance(self.reference_arm_enabled, bool):
            raise TypeError("reference_arm_enabled must be boolean")
        if not isinstance(self.stopped_on_error, bool):
            raise TypeError("stopped_on_error must be boolean")
        if isinstance(self.next_session_index, bool) or not isinstance(
            self.next_session_index, int
        ):
            raise TypeError("next_session_index must be an integer")
        if not 0 <= self.next_session_index <= self.condition.maximum_sessions:
            raise ValueError("next_session_index exceeds the condition boundary")
        initial = _state_map(self.initial_persistent_state_by_life)
        ids = tuple(initial)
        current = _state_map(
            self.current_persistent_state_by_life,
            expected_ids=ids,
        )
        outcomes = tuple(
            value
            if isinstance(value, ExperimentalSessionOutcome)
            else ExperimentalSessionOutcome.from_dict(value)
            for value in self.session_outcomes
        )
        reference_initial = _state_map(
            self.reference_initial_persistent_state_by_life,
            expected_ids=ids,
        )
        reference_current = _state_map(
            self.reference_current_persistent_state_by_life,
            expected_ids=ids,
        )
        reference_outcomes = tuple(
            value
            if isinstance(value, ExperimentalSessionOutcome)
            else ExperimentalSessionOutcome.from_dict(value)
            for value in self.reference_session_outcomes
        )
        if dict(reference_initial) != dict(initial):
            raise ValueError(
                "reference initial state must equal the experimental initial state"
            )
        if len(outcomes) != self.next_session_index:
            raise ValueError("outcome count differs from next_session_index")
        if any(item.session_index != index for index, item in enumerate(outcomes)):
            raise ValueError("experimental outcome indices are not contiguous")
        if self.reference_arm_enabled:
            if len(reference_outcomes) != len(outcomes):
                raise ValueError("paired reference outcome history is incomplete")
            if any(not item.reference_arm for item in reference_outcomes):
                raise ValueError("reference history contains an experimental outcome")
            if any(
                item.session_index != index
                for index, item in enumerate(reference_outcomes)
            ):
                raise ValueError("reference outcome indices are not contiguous")
        elif reference_outcomes:
            raise ValueError("disabled reference arm cannot carry outcomes")
        if any(item.reference_arm for item in outcomes):
            raise ValueError("experimental history contains a reference outcome")
        expected_current = initial
        expected_reference_current = reference_initial
        for index, outcome in enumerate(outcomes):
            expected_seed = physiology_root_seed_for_session(
                master_seed=self.condition.master_seed,
                stationary_user_type_id=self.condition.user_type_id,
                session_index=index,
                policy=self.condition.session_seed_policy,
            )
            if outcome.user_type_id != self.condition.user_type_id:
                raise ValueError(
                    "experimental outcome user type differs from the condition"
                )
            if outcome.physiology_root_seed != expected_seed:
                raise ValueError(
                    "experimental outcome root seed differs from the seed policy"
                )
            if dict(outcome.initial_persistent_state_by_life) != dict(expected_current):
                raise ValueError("experimental outcome handoff chain is discontinuous")
            reference_outcome = (
                reference_outcomes[index] if self.reference_arm_enabled else None
            )
            if reference_outcome is not None:
                if reference_outcome.user_type_id != self.condition.user_type_id:
                    raise ValueError(
                        "reference outcome user type differs from the condition"
                    )
                if reference_outcome.physiology_root_seed != expected_seed:
                    raise ValueError(
                        "reference outcome root seed differs from the seed policy"
                    )
                if (
                    reference_outcome.physiology_root_seed
                    != outcome.physiology_root_seed
                ):
                    raise ValueError("paired arm root seeds differ")
                if dict(reference_outcome.initial_persistent_state_by_life) != dict(
                    expected_reference_current
                ):
                    raise ValueError("reference outcome handoff chain is discontinuous")
                if (
                    reference_outcome.valid_for_convergence
                    != outcome.valid_for_convergence
                ):
                    raise ValueError(
                        "paired outcomes must share one atomic convergence validity"
                    )
            for record in outcome.sigma_trajectory_by_life.values():
                if record.get("sigma_multiplier") != self.condition.sigma_multiplier:
                    raise ValueError(
                        "experimental sigma audit differs from the condition"
                    )
            for record in outcome.fatigue_trajectory_by_life.values():
                if (
                    record.get("selected_session_fatigue_target")
                    != self.condition.selected_session_fatigue_target
                ):
                    raise ValueError(
                        "experimental fatigue audit differs from the condition"
                    )
            if reference_outcome is not None:
                for record in reference_outcome.sigma_trajectory_by_life.values():
                    if record.get("sigma_multiplier") != 1.0:
                        raise ValueError(
                            "reference sigma audit must retain multiplier 1.0"
                        )
                for record in reference_outcome.fatigue_trajectory_by_life.values():
                    if record.get("selected_session_fatigue_target") != 0.15:
                        raise ValueError(
                            "reference fatigue audit must retain target 0.15"
                        )
            paired_commit = outcome.valid_for_convergence and (
                reference_outcome is None
                or reference_outcome.valid_for_convergence
            )
            if not paired_commit and index != len(outcomes) - 1:
                raise ValueError("no session may follow an invalid paired attempt")
            if paired_commit:
                expected_current = outcome.final_persistent_state_by_life
                if reference_outcome is not None:
                    expected_reference_current = (
                        reference_outcome.final_persistent_state_by_life
                    )
        if dict(current) != dict(expected_current):
            raise ValueError("current experimental state differs from atomic handoff")
        if dict(reference_current) != dict(expected_reference_current):
            raise ValueError("current reference state differs from atomic handoff")
        latest_pair_failed = bool(
            outcomes
            and (
                not outcomes[-1].valid_for_convergence
                or (
                    self.reference_arm_enabled
                    and not reference_outcomes[-1].valid_for_convergence
                )
            )
        )
        if self.stopped_on_error != latest_pair_failed:
            raise ValueError("stopped_on_error differs from the latest outcome")
        if self.lab_model_version != FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION:
            raise ValueError("lab_model_version is not recognized")
        if self.schema_version != EXPERIMENTAL_MULTI_SESSION_STATE_SCHEMA_VERSION:
            raise ValueError("schema_version is not recognized")
        for name, value in {
            "initial_persistent_state_by_life": initial,
            "current_persistent_state_by_life": current,
            "session_outcomes": outcomes,
            "reference_initial_persistent_state_by_life": reference_initial,
            "reference_current_persistent_state_by_life": reference_current,
            "reference_session_outcomes": reference_outcomes,
        }.items():
            object.__setattr__(self, name, value)

    @property
    def completed_session_count(self) -> int:
        return sum(item.engine_completed for item in self.session_outcomes)

    @property
    def valid_session_count(self) -> int:
        return sum(item.valid_for_convergence for item in self.session_outcomes)

    def to_dict(self) -> dict[str, Any]:
        ids = tuple(self.initial_persistent_state_by_life)

        def states(
            value: Mapping[str, RelationMemoryPersistentState],
        ) -> dict[str, Any]:
            return relation_memory_state_map_to_dict(
                value,
                expected_digital_life_ids=ids,
            )

        return {
            "condition": self.condition.to_dict(),
            "initial_persistent_state_by_life": states(
                self.initial_persistent_state_by_life
            ),
            "current_persistent_state_by_life": states(
                self.current_persistent_state_by_life
            ),
            "session_outcomes": [item.to_dict() for item in self.session_outcomes],
            "reference_arm_enabled": self.reference_arm_enabled,
            "reference_initial_persistent_state_by_life": states(
                self.reference_initial_persistent_state_by_life
            ),
            "reference_current_persistent_state_by_life": states(
                self.reference_current_persistent_state_by_life
            ),
            "reference_session_outcomes": [
                item.to_dict() for item in self.reference_session_outcomes
            ],
            "next_session_index": self.next_session_index,
            "stopped_on_error": self.stopped_on_error,
            "lab_model_version": self.lab_model_version,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> FatigueSigmaExperimentState:
        if not isinstance(values, Mapping):
            raise TypeError("experiment state values must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                f"experiment state fields differ; missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        normalized = dict(values)
        normalized["condition"] = FatigueSigmaCondition.from_dict(
            normalized["condition"]
        )
        normalized["session_outcomes"] = tuple(normalized["session_outcomes"])
        normalized["reference_session_outcomes"] = tuple(
            normalized["reference_session_outcomes"]
        )
        return cls(**normalized)

    @classmethod
    def from_json(cls, encoded: str) -> FatigueSigmaExperimentState:
        if not isinstance(encoded, str):
            raise TypeError("encoded experiment state must be a string")
        parsed = json.loads(encoded, object_pairs_hook=_strict_pairs)
        if not isinstance(parsed, dict):
            raise ValueError("experiment state JSON must contain an object")
        return cls.from_dict(parsed)


def export_experiment_state_file(
    path: Path,
    state: FatigueSigmaExperimentState,
) -> Path:
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    if not isinstance(state, FatigueSigmaExperimentState):
        raise TypeError("state must be a FatigueSigmaExperimentState")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.to_json() + "\n", encoding="utf-8")
    return path


def load_experiment_state_file(path: Path) -> FatigueSigmaExperimentState:
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    return FatigueSigmaExperimentState.from_json(path.read_text(encoding="utf-8"))


__all__ = [
    "FatigueSigmaExperimentState",
    "export_experiment_state_file",
    "load_experiment_state_file",
]
