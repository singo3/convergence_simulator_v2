"""Strict persistent/session state contracts and JSON I/O."""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from symbiotic_sim_v2.digital_life.relation_memory.config import (
    PERSISTENT_STATE_SCOPE_BY_FIELD,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.session_state import (
    RelationMemorySessionState,
)


def test_fresh_persistent_state_and_scope_metadata_are_exact() -> None:
    state = RelationMemoryPersistentState.fresh("life-green")
    assert state.k_anchor == (0.5, 0.5, 0.5, 0.5)
    assert state.q == 0.5
    assert state.e == 0.0
    assert state.trial_count == state.session_count == 0
    assert state.profile_version == "symbiotic_signal_loop_reference_v1_0"
    assert state.algorithm_version == "adaptive_random_search_confirmed_v1"
    assert state.state_schema_version == "relation_memory_state_v2"
    assert PERSISTENT_STATE_SCOPE_BY_FIELD["e"] == "user_garden"
    assert PERSISTENT_STATE_SCOPE_BY_FIELD["k_anchor"] == "digital_life_core"


def test_persistent_state_json_round_trip_is_canonical_and_strict() -> None:
    state = RelationMemoryPersistentState.fresh("life-blue")
    encoded = state.to_json()
    assert RelationMemoryPersistentState.from_json(encoded) == state
    assert encoded == json.dumps(
        state.to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@pytest.mark.parametrize("field", tuple(RelationMemoryPersistentState.__dataclass_fields__))
def test_persistent_state_rejects_every_missing_field(field: str) -> None:
    values = RelationMemoryPersistentState.fresh("life-red").to_dict()
    del values[field]
    with pytest.raises(ValueError, match="missing"):
        RelationMemoryPersistentState.from_dict(values)


def test_persistent_state_rejects_unknown_duplicate_and_id_mismatch() -> None:
    values = RelationMemoryPersistentState.fresh("life-red").to_dict()
    with pytest.raises(ValueError, match="unknown"):
        RelationMemoryPersistentState.from_dict({**values, "unexpected": 1})
    with pytest.raises(ValueError, match="does not match"):
        RelationMemoryPersistentState.from_dict(
            values,
            expected_digital_life_id="life-green",
        )
    with pytest.raises(ValueError, match="duplicate"):
        RelationMemoryPersistentState.from_json(
            '{"digital_life_id":"life-red","digital_life_id":"life-red"}'
        )


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("q", math.nan),
        ("e", math.inf),
        ("trial_count", True),
        ("session_count", -1),
        ("k_anchor", (0.5, 0.5, 1.1, 0.5)),
        ("algorithm_version", "old"),
    ),
)
def test_persistent_state_rejects_invalid_values(field: str, invalid: object) -> None:
    values = RelationMemoryPersistentState.fresh("life-red").to_dict()
    values[field] = invalid
    with pytest.raises((TypeError, ValueError)):
        RelationMemoryPersistentState.from_dict(values)


def test_session_state_starts_without_treating_baseline_w_as_anchor() -> None:
    persistent = RelationMemoryPersistentState.fresh("life-green")
    session = RelationMemorySessionState.fresh(persistent)
    assert session.session_count_used == 0
    assert session.initial_k_anchor == persistent.k_anchor
    assert session.w_anchor_session is None
    assert not session.anchor_evaluated
    assert session.k_trial is None
    assert session.adaptation_phase == "anchor_evaluation"
    assert session.exploration_decision is None
    assert not session.candidate_generated
    assert session.adoption_result == "pending"
    assert dataclasses.is_dataclass(session)
    with pytest.raises(dataclasses.FrozenInstanceError):
        session.session_count_used = 1  # type: ignore[misc]
