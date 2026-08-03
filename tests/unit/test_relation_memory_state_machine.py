"""Complete pure 3Bundle confirmed-candidate state-machine fixtures."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.records import canonical_digest
from symbiotic_sim_v2.digital_life.relation_memory.session_state import (
    RelationMemorySessionState,
)
from symbiotic_sim_v2.digital_life.relation_memory.transitions import (
    RelationMemoryTransitionInput,
    RelationMemoryTransitionResult,
    apply_relation_memory_transition,
)


def initial(life_id: str = "life-red") -> tuple[
    RelationMemoryPersistentState,
    RelationMemorySessionState,
]:
    persistent = RelationMemoryPersistentState.fresh(life_id)
    return persistent, RelationMemorySessionState.fresh(persistent)


def evaluation(
    *,
    transition_index: int,
    signal_index: int,
    life_id: str = "life-red",
    g: int = 1,
    bundle_index: int | None,
    w: float,
    valid: bool = True,
    closing: bool = False,
) -> RelationMemoryTransitionInput:
    kind = "baseline" if bundle_index is None else "bundle"
    identifier = "baseline" if bundle_index is None else f"bundle-{bundle_index}"
    return RelationMemoryTransitionInput(
        transition_index=transition_index,
        signal_index=signal_index,
        signal_time_us=signal_index * 1_000_000,
        digital_life_id=life_id,
        g=g,
        bundle_index=bundle_index,
        evaluation_id=identifier,
        evaluation_kind=kind,
        evaluation_quality="valid" if valid else "rejected",
        evaluation_is_valid=valid,
        is_new_valid_evaluation=valid,
        w=w,
        closing=closing,
    )


def apply(
    states: tuple[RelationMemoryPersistentState, RelationMemorySessionState],
    item: RelationMemoryTransitionInput,
) -> tuple[
    tuple[RelationMemoryPersistentState, RelationMemorySessionState],
    RelationMemoryTransitionResult,
]:
    result = apply_relation_memory_transition(*states, item)
    return (result.persistent_state, result.session_state), result


def begin_explore(
    *,
    w_anchor: float = 0.2,
) -> tuple[
    tuple[RelationMemoryPersistentState, RelationMemorySessionState],
    RelationMemoryTransitionResult,
]:
    return apply(
        initial(),
        evaluation(
            transition_index=0,
            signal_index=120,
            bundle_index=0,
            w=w_anchor,
        ),
    )


def test_baseline_evaluation_is_audit_only_and_w_half_is_not_anchor() -> None:
    states, result = apply(
        initial(),
        evaluation(
            transition_index=0,
            signal_index=60,
            bundle_index=None,
            w=0.5,
        ),
    )
    persistent, session = states
    assert persistent == RelationMemoryPersistentState.fresh("life-red")
    assert session.w_anchor_session is None
    assert not session.anchor_evaluated
    assert session.adaptation_phase == "anchor_evaluation"
    assert not session.candidate_generated
    assert result.record is not None and result.record.w == 0.5


def test_green_standard_high_anchor_uses_strict_hold_without_candidate() -> None:
    states = initial("life-green")
    states, result = apply(
        states,
        evaluation(
            transition_index=0,
            signal_index=120,
            life_id="life-green",
            bundle_index=0,
            w=1.0,
        ),
    )
    persistent, session = states
    assert session.w_anchor_session == 1.0
    assert session.p_explore == pytest.approx(0.21497205669082545)
    assert session.u_explore == pytest.approx(0.8786907122888503)
    assert session.exploration_decision == "hold"
    assert session.adaptation_phase == "hold"
    assert session.adoption_result == "hold"
    assert not session.candidate_generated
    assert persistent.trial_count == 0
    assert result.k_current_after == persistent.k_anchor


def test_bundle0_explore_generates_one_candidate_for_next_signal_only() -> None:
    (persistent, session), result = begin_explore()
    assert session.w_anchor_session == 0.2
    assert session.exploration_decision == "explore"
    assert session.adaptation_phase == "trial"
    assert session.candidate_generated
    assert session.candidate_generation_trial_index == 0
    assert session.candidate_effective_signal_index == 121
    assert persistent.trial_count == 1
    assert persistent.k_anchor == (0.5, 0.5, 0.5, 0.5)
    assert session.k_trial == result.k_current_after
    assert result.k_current_before == persistent.k_anchor
    assert session.k_trial is not None
    assert session.k_trial[1] == persistent.k_anchor[1]
    assert session.k_trial[3] == persistent.k_anchor[3]


def test_second_bundle0_evaluation_cannot_generate_a_second_candidate() -> None:
    states, _ = begin_explore()
    persistent_before, session_before = states
    with pytest.raises(RuntimeError, match="one-candidate decision boundary"):
        apply(
            states,
            evaluation(
                transition_index=1,
                signal_index=121,
                bundle_index=0,
                w=0.1,
            ),
        )
    assert persistent_before.trial_count == 1
    assert session_before.candidate_generated


def test_confirmed_candidate_requires_two_strict_improvements_before_acceptance() -> None:
    states, generated = begin_explore()
    old_anchor = states[0].k_anchor
    candidate = states[1].k_trial
    states, provisional = apply(
        states,
        evaluation(
            transition_index=1,
            signal_index=180,
            bundle_index=1,
            w=0.35,
        ),
    )
    assert states[1].adaptation_phase == "confirmation"
    assert provisional.record is not None
    assert provisional.record.provisional_condition is True
    assert provisional.k_current_after == candidate
    assert states[0].k_anchor == old_anchor

    states, confirmation = apply(
        states,
        evaluation(
            transition_index=2,
            signal_index=240,
            bundle_index=2,
            w=0.33,
            closing=True,
        ),
    )
    persistent, session = states
    assert confirmation.record is not None
    assert confirmation.record.confirmation_condition_1 is True
    assert confirmation.record.confirmation_condition_2 is True
    assert confirmation.k_anchor_updated
    assert persistent.k_anchor == candidate
    assert persistent.trial_count == 1
    assert persistent.session_count == 1
    assert session.adaptation_phase == "accepted"
    assert session.adoption_result == "accepted"
    assert session.valid_trial_evaluation_count == 2
    assert session.k_trial is None
    assert session.session_finalized
    assert generated.record is not None
    assert canonical_digest([generated.record, provisional.record, confirmation.record]) == (
        canonical_digest([generated.record, provisional.record, confirmation.record])
    )


def test_bundle1_threshold_equality_fails_and_bundle2_returns_to_anchor() -> None:
    states, _ = begin_explore()
    anchor = states[1].w_anchor_session
    assert anchor is not None
    threshold = anchor + states[1].epsilon_accept
    states, provisional = apply(
        states,
        evaluation(
            transition_index=1,
            signal_index=180,
            bundle_index=1,
            w=threshold,
        ),
    )
    assert provisional.record is not None
    assert provisional.record.provisional_condition is False
    assert states[1].adaptation_phase == "return_anchor"
    assert provisional.k_current_after == states[0].k_anchor

    states, returned = apply(
        states,
        evaluation(
            transition_index=2,
            signal_index=240,
            bundle_index=2,
            w=0.24,
            closing=True,
        ),
    )
    assert states[0].k_anchor == (0.5, 0.5, 0.5, 0.5)
    assert states[1].anchor_return_w == 0.24
    assert states[1].w_anchor_session == 0.24
    assert states[1].adoption_result == "rejected_bundle1_threshold"
    assert returned.k_anchor_updated is False


@pytest.mark.parametrize(
    ("w_trial_1", "w_trial_2", "condition_1", "condition_2"),
    (
        (0.35, 0.2, False, True),
        (0.28, 0.21, True, False),
    ),
)
def test_confirmation_failure_or_mean_failure_rolls_back(
    w_trial_1: float,
    w_trial_2: float,
    condition_1: bool,
    condition_2: bool,
) -> None:
    states, _ = begin_explore()
    old_anchor = states[0].k_anchor
    states, _ = apply(
        states,
        evaluation(
            transition_index=1,
            signal_index=180,
            bundle_index=1,
            w=w_trial_1,
        ),
    )
    states, result = apply(
        states,
        evaluation(
            transition_index=2,
            signal_index=240,
            bundle_index=2,
            w=w_trial_2,
            closing=True,
        ),
    )
    assert result.record is not None
    assert result.record.confirmation_condition_1 is condition_1
    assert result.record.confirmation_condition_2 is condition_2
    assert states[0].k_anchor == old_anchor
    assert states[1].adaptation_phase == "rejected"
    assert states[1].adoption_result == "rejected_after_confirmation"


def test_bundle0_reject_never_sets_anchor_or_generates_candidate() -> None:
    states, rejected = apply(
        initial(),
        evaluation(
            transition_index=0,
            signal_index=120,
            bundle_index=0,
            w=0.5,
            valid=False,
        ),
    )
    assert states[1].w_anchor_session is None
    assert not states[1].anchor_evaluated
    assert not states[1].candidate_generated
    assert states[0].trial_count == 0
    assert states[1].adoption_result == "bundle0_evaluation_rejected"
    assert rejected.record is not None and rejected.record.w is None

    states, _ = apply(
        states,
        evaluation(
            transition_index=1,
            signal_index=240,
            bundle_index=2,
            w=0.5,
            valid=False,
            closing=True,
        ),
    )
    assert states[1].adaptation_phase == "completed_bundle0_rejected"
    assert states[0].session_count == 1


def test_bundle1_reject_keeps_same_trial_but_one_later_valid_value_cannot_adopt() -> None:
    states, _ = begin_explore()
    candidate = states[1].k_trial
    states, rejected = apply(
        states,
        evaluation(
            transition_index=1,
            signal_index=180,
            bundle_index=1,
            w=0.2,
            valid=False,
        ),
    )
    assert states[1].adaptation_phase == "trial_unconfirmed"
    assert rejected.k_current_after == candidate
    assert states[1].valid_trial_evaluation_count == 0

    states, final = apply(
        states,
        evaluation(
            transition_index=2,
            signal_index=240,
            bundle_index=2,
            w=0.9,
            closing=True,
        ),
    )
    assert states[1].valid_trial_evaluation_count == 1
    assert states[1].w_trial_1 is None
    assert states[1].w_trial_2 == 0.9
    assert states[1].adoption_result == "unconfirmed_evaluation_reject"
    assert states[1].k_trial is None
    assert states[0].k_anchor == (0.5, 0.5, 0.5, 0.5)
    assert final.k_anchor_updated is False


def test_bundle2_reject_rolls_back_and_does_not_create_second_candidate() -> None:
    states, _ = begin_explore()
    states, _ = apply(
        states,
        evaluation(
            transition_index=1,
            signal_index=180,
            bundle_index=1,
            w=0.35,
        ),
    )
    states, final = apply(
        states,
        evaluation(
            transition_index=2,
            signal_index=240,
            bundle_index=2,
            w=0.35,
            valid=False,
            closing=True,
        ),
    )
    assert states[0].trial_count == 1
    assert states[0].k_anchor == (0.5, 0.5, 0.5, 0.5)
    assert states[1].adoption_result == "unconfirmed_evaluation_reject"
    assert states[1].rollback_reason == "bundle2_evaluation_rejected"
    assert final.k_anchor_updated is False


def test_g_zero_has_no_candidate_or_anchor_w_but_session_count_still_closes() -> None:
    states, _ = apply(
        initial(),
        evaluation(
            transition_index=0,
            signal_index=120,
            g=0,
            bundle_index=0,
            w=0.2,
        ),
    )
    assert states[1].adaptation_phase == "completed_non_holder"
    assert states[1].adoption_result == "non_holder_no_adaptation"
    assert states[1].w_anchor_session is None
    assert states[0].trial_count == 0
    states, _ = apply(
        states,
        evaluation(
            transition_index=1,
            signal_index=240,
            g=0,
            bundle_index=2,
            w=0.3,
            closing=True,
        ),
    )
    assert states[0].session_count == 1
    assert states[0].k_anchor == (0.5, 0.5, 0.5, 0.5)
    assert states[1].session_finalized


def test_incremental_improvement_below_neutral_can_be_confirmed() -> None:
    states, _ = begin_explore(w_anchor=0.2)
    states, _ = apply(
        states,
        evaluation(
            transition_index=1,
            signal_index=180,
            bundle_index=1,
            w=0.30,
        ),
    )
    states, result = apply(
        states,
        evaluation(
            transition_index=2,
            signal_index=240,
            bundle_index=2,
            w=0.29,
            closing=True,
        ),
    )
    assert result.k_anchor_updated
    assert states[1].adoption_result == "accepted"
    assert states[1].w_trial_1 is not None and states[1].w_trial_1 < 0.5
    assert states[1].w_trial_2 is not None and states[1].w_trial_2 < 0.5


def test_unresolved_candidate_rolls_back_only_at_closing_and_counters_are_distinct() -> None:
    states, _ = begin_explore()
    persistent_before_close, session_before_close = states
    closing = RelationMemoryTransitionInput(
        transition_index=1,
        signal_index=240,
        signal_time_us=240_000_000,
        digital_life_id="life-red",
        g=1,
        bundle_index=None,
        evaluation_id=None,
        evaluation_kind=None,
        evaluation_quality=None,
        evaluation_is_valid=None,
        is_new_valid_evaluation=False,
        w=0.2,
        closing=True,
    )
    states, result = apply(states, closing)
    assert persistent_before_close.trial_count == states[0].trial_count == 1
    assert persistent_before_close.session_count == 0
    assert states[0].session_count == 1
    assert session_before_close.k_trial is not None
    assert states[1].k_trial is None
    assert states[1].adoption_result == "rolled_back_at_session_end"
    assert states[1].rollback_reason == "unresolved_candidate_at_session_end"
    assert result.k_current_after == states[0].k_anchor


def test_ordinary_signal_is_noop_and_finalized_session_rejects_more_updates() -> None:
    persistent, session = initial()
    ordinary = RelationMemoryTransitionInput(
        transition_index=0,
        signal_index=121,
        signal_time_us=121_000_000,
        digital_life_id="life-red",
        g=1,
        bundle_index=None,
        evaluation_id=None,
        evaluation_kind=None,
        evaluation_quality=None,
        evaluation_is_valid=None,
        is_new_valid_evaluation=False,
        w=0.5,
        closing=False,
    )
    result = apply_relation_memory_transition(persistent, session, ordinary)
    assert result.record is None
    assert result.persistent_state is persistent
    assert result.session_state is session

    finalized = replace(session, session_finalized=True, adaptation_phase="hold")
    with pytest.raises(RuntimeError, match="already finalized"):
        apply_relation_memory_transition(persistent, finalized, ordinary)
