"""Strict JSON state for pausing and resuming a Stage 8A run."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from types import MappingProxyType
from typing import Any

from symbiotic_sim_v2.convergence.config import RollingConvergenceConfig
from symbiotic_sim_v2.convergence.records import RollingConvergenceRecord
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    relation_memory_state_map_from_dict,
    relation_memory_state_map_to_dict,
)

from .config import (
    MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION,
    MultiSessionRunnerConfig,
)
from .session_outcome import SessionOutcome
from .session_seed import physiology_root_seed_for_session

MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION = "multi_session_relation_state_v1"
INITIAL_CONVERGENCE_STATE = "insufficient_valid_sessions"


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate multi-session state field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _expected_ids(values: object) -> tuple[str, str, str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("expected_digital_life_ids must be a three-element sequence")
    normalized = tuple(values)
    if len(normalized) != 3:
        raise ValueError("Stage 8A requires exactly three Digital Life IDs")
    if any(not isinstance(value, str) or not value.strip() for value in normalized):
        raise ValueError("Digital Life IDs must be non-empty strings")
    if len(set(normalized)) != 3:
        raise ValueError("Digital Life IDs must be unique")
    return normalized  # type: ignore[return-value]


def _versions(value: object) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError("versions must be a mapping")
    normalized: dict[str, str] = {}
    for name, version in value.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("version names must be non-empty strings")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("version values must be non-empty strings")
        normalized[name] = version
    if not normalized:
        raise ValueError("versions must not be empty")
    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class MultiSessionRelationState:
    """Every committed input needed to continue the next independent session."""

    runner_version: str
    schema_version: str
    user_type_id: str
    master_seed: int
    seed_policy: str
    convergence_config: RollingConvergenceConfig
    completed_session_count: int
    valid_session_count: int
    next_session_index: int
    current_persistent_state_by_life: Mapping[str, RelationMemoryPersistentState]
    session_outcomes: tuple[SessionOutcome, ...]
    convergence_records: tuple[RollingConvergenceRecord, ...]
    first_convergence_session_index: int | None
    current_convergence_state: str
    versions: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.runner_version != MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION:
            raise ValueError(
                f"runner_version must be {MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION}"
            )
        if self.schema_version != MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION}"
            )
        if not isinstance(self.user_type_id, str) or not self.user_type_id.strip():
            raise ValueError("user_type_id must be a non-empty string")
        config = MultiSessionRunnerConfig(
            user_type_id=self.user_type_id,
            master_seed=self.master_seed,
            session_seed_policy=self.seed_policy,
            convergence_config=self.convergence_config,
            runner_version=self.runner_version,
        )
        completed = _non_negative_int(
            "completed_session_count", self.completed_session_count
        )
        valid = _non_negative_int("valid_session_count", self.valid_session_count)
        next_index = _non_negative_int("next_session_index", self.next_session_index)
        if valid > completed:
            raise ValueError("valid_session_count cannot exceed completed_session_count")

        raw_states = self.current_persistent_state_by_life
        if not isinstance(raw_states, Mapping):
            raise TypeError("current_persistent_state_by_life must be a mapping")
        life_ids = _expected_ids(tuple(raw_states))
        state_values = {
            life_id: (
                state.to_dict()
                if isinstance(state, RelationMemoryPersistentState)
                else state
            )
            for life_id, state in raw_states.items()
        }
        persistent_states = relation_memory_state_map_from_dict(
            state_values,
            expected_digital_life_ids=life_ids,
        )
        outcomes = tuple(
            value if isinstance(value, SessionOutcome) else SessionOutcome.from_dict(value)
            for value in self.session_outcomes
        )
        records = tuple(
            value
            if isinstance(value, RollingConvergenceRecord)
            else RollingConvergenceRecord.from_dict(value)
            for value in self.convergence_records
        )
        if len(outcomes) != next_index:
            raise ValueError("next_session_index must equal the recorded attempt count")
        if next_index > config.maximum_sessions:
            raise ValueError("recorded attempt count exceeds maximum_sessions")
        if tuple(outcome.session_index for outcome in outcomes) != tuple(range(next_index)):
            raise ValueError("session outcome indices must be contiguous from zero")
        if any(outcome.user_type_id != self.user_type_id for outcome in outcomes):
            raise ValueError("every session outcome must use the run user type")
        if any(
            outcome.physiology_root_seed
            != physiology_root_seed_for_session(
                master_seed=self.master_seed,
                stationary_user_type_id=self.user_type_id,
                session_index=outcome.session_index,
                policy=self.seed_policy,
            )
            for outcome in outcomes
        ):
            raise ValueError("session outcome root seed differs from the seed policy")
        if any(not outcome.engine_completed for outcome in outcomes[:-1]):
            raise ValueError("no session may follow an incomplete attempt")
        for outcome in outcomes:
            if not outcome.engine_completed:
                continue
            trial_deltas: dict[str, int] = {}
            for life_id, before in outcome.initial_persistent_state_by_life.items():
                after = outcome.final_persistent_state_by_life[life_id]
                if after.session_count != before.session_count + 1:
                    raise ValueError(
                        "a completed outcome must increment every session_count once"
                    )
                trial_delta = after.trial_count - before.trial_count
                if trial_delta not in (0, 1):
                    raise ValueError(
                        "a completed outcome may increment each trial_count at most once"
                    )
                trial_deltas[life_id] = trial_delta
                if (
                    after.profile_version != before.profile_version
                    or after.algorithm_version != before.algorithm_version
                    or after.state_schema_version != before.state_schema_version
                ):
                    raise ValueError(
                        "persistent-state versions changed within a session outcome"
                    )
            expected_trial_count = 1 if outcome.candidate_generated else 0
            if sum(trial_deltas.values()) != expected_trial_count:
                raise ValueError(
                    "trial_count increments must exactly match candidate generation"
                )
            if (
                outcome.candidate_generated
                and outcome.holder_id is not None
                and trial_deltas[outcome.holder_id] != 1
            ):
                raise ValueError("only the holder may increment trial_count")
            holder_trial = outcome.holder_k_trial
            if outcome.candidate_generated != (holder_trial is not None):
                raise ValueError(
                    "candidate generation differs from the saved physical trial audit"
                )
            for life_id, initial_anchor in outcome.initial_k_anchor_by_life.items():
                expected_anchor = (
                    holder_trial
                    if life_id == outcome.holder_id and outcome.candidate_accepted
                    else initial_anchor
                )
                if outcome.final_k_anchor_by_life[life_id] != expected_anchor:
                    raise ValueError(
                        "saved final anchor differs from the adoption result"
                    )
        for previous, current in zip(outcomes, outcomes[1:], strict=False):
            if dict(previous.final_persistent_state_by_life) != dict(
                current.initial_persistent_state_by_life
            ):
                raise ValueError(
                    "persistent state handoff differs between consecutive sessions"
                )
        if completed != sum(outcome.engine_completed for outcome in outcomes):
            raise ValueError("completed_session_count differs from session outcomes")
        if valid != sum(outcome.valid_for_convergence for outcome in outcomes):
            raise ValueError("valid_session_count differs from session outcomes")
        if len(records) != len(outcomes):
            raise ValueError("every session outcome requires one convergence record")
        if any(
            record.evaluated_at_session_index != outcome.session_index
            for record, outcome in zip(records, outcomes, strict=True)
        ):
            raise ValueError("convergence records and session outcomes are misaligned")
        if any(
            record.local_time_us != outcome.local_time_us
            or record.global_time_us != outcome.global_time_us
            for record, outcome in zip(records, outcomes, strict=True)
        ):
            raise ValueError("convergence and session outcome times are misaligned")

        first = self.first_convergence_session_index
        if first is not None:
            first = _non_negative_int("first_convergence_session_index", first)
        if records:
            latest = records[-1]
            if first != latest.first_convergence_session_index:
                raise ValueError("first convergence index differs from the latest record")
            if self.current_convergence_state != latest.convergence_state:
                raise ValueError("current convergence state differs from the latest record")
        elif first is not None or self.current_convergence_state != INITIAL_CONVERGENCE_STATE:
            raise ValueError("an empty run must use the initial convergence state")

        last_committed = None
        for outcome in outcomes:
            if outcome.engine_completed and len(outcome.final_persistent_state_by_life) == 3:
                last_committed = outcome.final_persistent_state_by_life
        expected_current = (
            last_committed
            if last_committed is not None
            else None
            if not outcomes
            else outcomes[0].initial_persistent_state_by_life
        )
        if expected_current is not None and any(
            persistent_states[life_id] != expected_current[life_id]
            for life_id in life_ids
        ):
            raise ValueError("current persistent states differ from the latest commit")
        versions = _versions(self.versions)

        object.__setattr__(self, "master_seed", config.master_seed)
        object.__setattr__(self, "seed_policy", config.session_seed_policy)
        object.__setattr__(self, "convergence_config", config.convergence_config)
        object.__setattr__(self, "completed_session_count", completed)
        object.__setattr__(self, "valid_session_count", valid)
        object.__setattr__(self, "next_session_index", next_index)
        object.__setattr__(self, "current_persistent_state_by_life", persistent_states)
        object.__setattr__(self, "session_outcomes", outcomes)
        object.__setattr__(self, "convergence_records", records)
        object.__setattr__(self, "first_convergence_session_index", first)
        object.__setattr__(self, "versions", versions)

    @property
    def stopped_on_error(self) -> bool:
        return bool(self.session_outcomes and not self.session_outcomes[-1].engine_completed)

    def to_dict(self) -> dict[str, Any]:
        life_ids = tuple(self.current_persistent_state_by_life)
        return {
            "runner_version": self.runner_version,
            "schema_version": self.schema_version,
            "user_type_id": self.user_type_id,
            "master_seed": self.master_seed,
            "seed_policy": self.seed_policy,
            "convergence_config": self.convergence_config.to_dict(),
            "completed_session_count": self.completed_session_count,
            "valid_session_count": self.valid_session_count,
            "next_session_index": self.next_session_index,
            "current_persistent_state_by_life": relation_memory_state_map_to_dict(
                self.current_persistent_state_by_life,
                expected_digital_life_ids=life_ids,
            ),
            "session_outcomes": [outcome.to_dict() for outcome in self.session_outcomes],
            "convergence_records": [record.to_dict() for record in self.convergence_records],
            "first_convergence_session_index": self.first_convergence_session_index,
            "current_convergence_state": self.current_convergence_state,
            "versions": dict(self.versions),
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
    def from_dict(
        cls,
        values: Mapping[str, Any],
        *,
        expected_digital_life_ids: Sequence[str],
    ) -> MultiSessionRelationState:
        if not isinstance(values, Mapping):
            raise TypeError("multi-session state values must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                f"multi-session state fields differ; missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        normalized = dict(values)
        expected_ids = _expected_ids(expected_digital_life_ids)
        states = normalized["current_persistent_state_by_life"]
        normalized["current_persistent_state_by_life"] = (
            relation_memory_state_map_from_dict(
                states,
                expected_digital_life_ids=expected_ids,
            )
        )
        convergence = normalized["convergence_config"]
        if not isinstance(convergence, RollingConvergenceConfig):
            normalized["convergence_config"] = RollingConvergenceConfig.from_dict(
                convergence
            )
        normalized["session_outcomes"] = tuple(
            value
            if isinstance(value, SessionOutcome)
            else SessionOutcome.from_dict(value)
            for value in normalized["session_outcomes"]
        )
        normalized["convergence_records"] = tuple(
            value
            if isinstance(value, RollingConvergenceRecord)
            else RollingConvergenceRecord.from_dict(value)
            for value in normalized["convergence_records"]
        )
        result = cls(**normalized)
        if tuple(result.current_persistent_state_by_life) != expected_ids:
            raise ValueError("multi-session state Digital Life roster order differs")
        return result

    @classmethod
    def from_json(
        cls,
        encoded: str,
        *,
        expected_digital_life_ids: Sequence[str],
    ) -> MultiSessionRelationState:
        if not isinstance(encoded, str):
            raise TypeError("encoded multi-session state must be a string")
        values = json.loads(
            encoded,
            object_pairs_hook=_strict_object_pairs,
            parse_constant=_reject_constant,
        )
        if not isinstance(values, dict):
            raise ValueError("multi-session state JSON must contain an object")
        return cls.from_dict(
            values,
            expected_digital_life_ids=expected_digital_life_ids,
        )


def export_multi_session_state_file(
    path: Path,
    state: MultiSessionRelationState,
) -> Path:
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    if not isinstance(state, MultiSessionRelationState):
        raise TypeError("state must be a MultiSessionRelationState")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.to_json() + "\n", encoding="utf-8")
    return path


def load_multi_session_state_file(
    path: Path,
    *,
    expected_digital_life_ids: Sequence[str],
) -> MultiSessionRelationState:
    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    return MultiSessionRelationState.from_json(
        path.read_text(encoding="utf-8"),
        expected_digital_life_ids=expected_digital_life_ids,
    )


__all__ = [
    "INITIAL_CONVERGENCE_STATE",
    "MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION",
    "MultiSessionRelationState",
    "export_multi_session_state_file",
    "load_multi_session_state_file",
]
