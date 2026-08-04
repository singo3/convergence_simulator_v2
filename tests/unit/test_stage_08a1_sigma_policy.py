"""Scaled-reference sigma without changing any other relation-search decision."""

from __future__ import annotations

import inspect

import pytest

from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.session_state import (
    RelationMemorySessionState,
)
from symbiotic_sim_v2.digital_life.relation_memory.transitions import (
    RelationMemoryTransitionInput,
    apply_relation_memory_transition,
    apply_relation_memory_transition_with_sigma_multiplier,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.sigma_policy import (
    ScaledReferenceSigmaPolicy,
)


def bundle_zero(life_id: str = "life-red") -> RelationMemoryTransitionInput:
    return RelationMemoryTransitionInput(
        transition_index=0,
        signal_index=120,
        signal_time_us=120_000_000,
        digital_life_id=life_id,
        g=1,
        bundle_index=0,
        evaluation_id="bundle-0",
        evaluation_kind="bundle",
        evaluation_quality="valid",
        evaluation_is_valid=True,
        is_new_valid_evaluation=True,
        w=0.2,
        closing=False,
    )


def states(life_id: str = "life-red") -> tuple[
    RelationMemoryPersistentState,
    RelationMemorySessionState,
]:
    persistent = RelationMemoryPersistentState.fresh(life_id)
    return persistent, RelationMemorySessionState.fresh(persistent)


def test_multiplier_one_is_exactly_the_existing_transition() -> None:
    item = bundle_zero()
    reference = apply_relation_memory_transition(*states(), item)
    experimental = apply_relation_memory_transition_with_sigma_multiplier(
        *states(),
        item,
        sigma_multiplier=1.0,
    )
    assert experimental == reference
    assert experimental.record == reference.record


@pytest.mark.parametrize("multiplier", (0.25, 0.50, 1.0, 1.50))
def test_only_candidate_distance_is_scaled(multiplier: float) -> None:
    item = bundle_zero()
    reference = apply_relation_memory_transition(*states(), item)
    scaled = apply_relation_memory_transition_with_sigma_multiplier(
        *states(),
        item,
        sigma_multiplier=multiplier,
    )
    assert reference.record is not None and scaled.record is not None
    assert reference.record.sigma is not None and scaled.record.sigma is not None
    assert scaled.record.sigma == multiplier * reference.record.sigma
    assert scaled.record.p_explore == reference.record.p_explore
    assert scaled.record.p_explore_min == reference.record.p_explore_min
    assert scaled.record.u_explore == reference.record.u_explore
    assert scaled.record.exploration_decision == reference.record.exploration_decision
    assert scaled.record.epsilon_accept == reference.record.epsilon_accept
    assert scaled.record.direction_trial_index == reference.record.direction_trial_index
    assert scaled.record.direction_u_f == reference.record.direction_u_f
    assert scaled.record.direction_u_t == reference.record.direction_u_t
    assert scaled.record.direction_xi == reference.record.direction_xi
    assert scaled.persistent_state.trial_count == reference.persistent_state.trial_count
    assert scaled.record.k_trial is not None
    assert scaled.record.k_trial[1] == scaled.record.k_anchor_before[1]
    assert scaled.record.k_trial[3] == scaled.record.k_anchor_before[3]


def test_sigma_policy_reports_reference_and_effective_values_separately() -> None:
    policy = ScaledReferenceSigmaPolicy(1.25)
    decision = policy.at_w(0.7, 0.04, 0.4)
    assert decision.reference_sigma == pytest.approx(0.256)
    assert decision.multiplier == 1.25
    assert decision.effective_sigma == pytest.approx(0.32)
    assert decision.to_dict()["policy_version"] == "scaled_reference_sigma_v0_1"


@pytest.mark.parametrize(
    "invalid",
    (True, 0.249999, 1.500001, float("inf"), float("nan"), "1.0"),
)
def test_multiplier_rejects_bool_range_type_and_nonfinite(invalid: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ScaledReferenceSigmaPolicy(invalid)  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        apply_relation_memory_transition_with_sigma_multiplier(
            *states(),
            bundle_zero(),
            sigma_multiplier=invalid,
        )


def test_existing_transition_signature_is_unchanged_and_new_seed_inputs_are_absent() -> None:
    assert tuple(inspect.signature(apply_relation_memory_transition).parameters) == (
        "persistent_state",
        "session_state",
        "transition_input",
    )
    scaled_parameters = set(
        inspect.signature(
            apply_relation_memory_transition_with_sigma_multiplier
        ).parameters
    )
    assert scaled_parameters == {
        "persistent_state",
        "session_state",
        "transition_input",
        "sigma_multiplier",
    }
    assert scaled_parameters.isdisjoint({"condition_id", "condition_hash"})
