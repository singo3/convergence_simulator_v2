"""Immutable audit records and canonical digests for Stage 5C."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from .config import (
    ADAPTIVE_DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION,
    ADAPTIVE_DIGITAL_LIFE_SIGNAL_RECORD_SCHEMA_VERSION,
    ALGORITHM_VERSION,
    PROFILE_VERSION,
    RELATION_MEMORY_PERSISTENT_STATE_RECORD_SCHEMA_VERSION,
    RELATION_MEMORY_SESSION_STATE_RECORD_SCHEMA_VERSION,
    RELATION_MEMORY_TRANSITION_RECORD_SCHEMA_VERSION,
    RELATION_UPDATE_EFFECTIVE_POLICY_VERSION,
    STATE_SCHEMA_VERSION,
)

KVector = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class RelationMemoryTransitionRecord:
    transition_index: int
    signal_index: int
    signal_time_us: int
    digital_life_id: str
    g: int
    bundle_index: int | None
    evaluation_id: str | None
    evaluation_quality: str | None
    evaluation_is_valid: bool | None
    w: float | None
    phase_before: str
    phase_after: str
    exploration_decision: str | None
    curiosity: float
    sigma_min: float
    sigma_max: float
    sigma: float | None
    epsilon_accept: float
    p_explore_min: float
    p_explore: float | None
    u_explore: float | None
    direction_trial_index: int | None
    direction_u_f: float | None
    direction_u_t: float | None
    direction_norm: float | None
    direction_xi: KVector | None
    k_anchor_before: KVector
    k_current_before: KVector
    k_trial: KVector | None
    k_current_after: KVector
    k_anchor_after: KVector
    w_anchor_session_before: float | None
    w_anchor_session_after: float | None
    w_trial_1_before: float | None
    w_trial_1_after: float | None
    w_trial_2_before: float | None
    w_trial_2_after: float | None
    provisional_condition: bool | None
    confirmation_condition_1: bool | None
    confirmation_condition_2: bool | None
    candidate_mean_w: float | None
    trial_count_before: int
    trial_count_after: int
    session_count_used: int
    session_count_after: int
    adoption_result: str
    rollback_reason: str | None
    candidate_effective_signal_index: int | None
    relation_update_effective_policy_version: str = (
        RELATION_UPDATE_EFFECTIVE_POLICY_VERSION
    )
    algorithm_version: str = ALGORITHM_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION
    schema_version: str = RELATION_MEMORY_TRANSITION_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RelationMemoryPersistentStateRecord:
    record_index: int
    state_position: str
    digital_life_id: str
    k_anchor: KVector
    q: float
    e: float
    trial_count: int
    session_count: int
    profile_version: str = PROFILE_VERSION
    algorithm_version: str = ALGORITHM_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION
    schema_version: str = RELATION_MEMORY_PERSISTENT_STATE_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RelationMemorySessionStateRecord:
    record_index: int
    signal_index: int
    signal_time_us: int
    digital_life_id: str
    session_count_used: int
    initial_k_anchor: KVector
    w_anchor_session: float | None
    anchor_evaluated: bool
    k_trial: KVector | None
    w_trial_1: float | None
    w_trial_2: float | None
    adaptation_phase: str
    exploration_decision: str | None
    u_explore: float | None
    p_explore: float | None
    sigma: float | None
    direction_xi: KVector | None
    epsilon_accept: float
    candidate_generated: bool
    candidate_generation_trial_index: int | None
    candidate_effective_signal_index: int | None
    adoption_result: str
    rollback_reason: str | None
    anchor_return_w: float | None
    valid_trial_evaluation_count: int
    session_finalized: bool
    schema_version: str = RELATION_MEMORY_SESSION_STATE_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AdaptiveDigitalLifeSecondRoundRecord:
    signal_index: int
    signal_time_us: int
    digital_life_id: str
    g: int
    evaluation_id: str | None
    evaluation_quality: str | None
    is_new_valid_evaluation: bool
    w: float
    q_before: float
    q_after: float
    e_before: float
    e_after: float
    k_anchor_before: KVector
    k_current_before: KVector
    k_current_after: KVector
    k_anchor_after: KVector
    relation_phase_before: str
    relation_phase_after: str
    relation_transition_index: int | None
    closing_evaluation_attribution: bool
    schema_version: str = ADAPTIVE_DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AdaptiveDigitalLifeSignalRecord:
    signal_index: int
    signal_time_us: int
    digital_life_id: str
    role: str
    s: int
    bundle_index: int | None
    phase: str
    evaluation_id: str | None
    evaluation_quality: str | None
    is_new_valid_evaluation: bool
    g: int
    w: float
    k_anchor_before: KVector
    k_current_before: KVector
    k_presented: KVector
    b_presented: KVector
    relation_phase_before: str
    relation_phase_after: str
    k_current_after: KVector
    k_anchor_after: KVector
    candidate_effective_next_signal: bool
    q_before: float
    q_after: float
    e_before: float
    e_after: float
    schema_version: str = ADAPTIVE_DIGITAL_LIFE_SIGNAL_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_digest(records: object) -> str:
    """Hash canonical compact UTF-8 JSON and reject non-finite values."""

    def normalize(value: object) -> object:
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        if isinstance(value, tuple):
            return [normalize(item) for item in value]
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in value.items()}
        return value

    canonical = json.dumps(
        normalize(records),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "AdaptiveDigitalLifeSecondRoundRecord",
    "AdaptiveDigitalLifeSignalRecord",
    "KVector",
    "RelationMemoryPersistentStateRecord",
    "RelationMemorySessionStateRecord",
    "RelationMemoryTransitionRecord",
    "canonical_digest",
]
