"""Strict Stage 8A.1 outcome/state integrity and paired atomicity checks."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma import FatigueSigmaCondition
from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    FATIGUE_SIGMA_REPLICATE_RESULT_SCHEMA_VERSION,
    FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.runner import (
    FatigueSigmaSingleConditionRunner,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.session_outcome import (
    ExperimentalSessionOutcome,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.state import (
    FatigueSigmaExperimentState,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    physiology_root_seed_for_session,
)


def _condition(*, maximum_sessions: int = 4) -> FatigueSigmaCondition:
    return FatigueSigmaCondition.create(
        maximum_sessions=maximum_sessions,
        master_seed=20260802,
    )


@pytest.fixture(scope="module")
def paired_two_session_runner() -> FatigueSigmaSingleConditionRunner:
    runner = FatigueSigmaSingleConditionRunner(
        _condition(),
        compare_reference_arm=True,
    )
    runner.run_next_session()
    runner.run_next_session()
    return runner


@pytest.mark.parametrize("arm", ["experimental", "reference"])
def test_state_recomputes_every_paired_physiology_seed(
    paired_two_session_runner,
    arm,
) -> None:
    encoded = paired_two_session_runner.state().to_dict()
    key = "session_outcomes" if arm == "experimental" else "reference_session_outcomes"
    encoded[key][1]["physiology_root_seed"] ^= 1

    with pytest.raises(ValueError, match="root seed|seed policy"):
        FatigueSigmaExperimentState.from_dict(encoded)


@pytest.mark.parametrize("arm", ["experimental", "reference"])
def test_state_requires_condition_user_type_in_both_arms(
    paired_two_session_runner,
    arm,
) -> None:
    encoded = paired_two_session_runner.state().to_dict()
    key = "session_outcomes" if arm == "experimental" else "reference_session_outcomes"
    encoded[key][0]["user_type_id"] = "flat_control"

    with pytest.raises(ValueError, match="user type"):
        FatigueSigmaExperimentState.from_dict(encoded)


def test_state_requires_identical_run_initial_state_for_paired_arms(
    paired_two_session_runner,
) -> None:
    encoded = paired_two_session_runner.state().to_dict()
    encoded["reference_initial_persistent_state_by_life"]["life-green"]["q"] = 0.4

    with pytest.raises(ValueError, match="reference initial state"):
        FatigueSigmaExperimentState.from_dict(encoded)


def test_state_rejects_any_session_after_an_invalid_atomic_pair(
    paired_two_session_runner,
) -> None:
    encoded = paired_two_session_runner.state().to_dict()
    for key in ("session_outcomes", "reference_session_outcomes"):
        encoded[key][0]["valid_for_convergence"] = False
        encoded[key][0]["invalid_reason"] = "synthetic_pair_failure"

    with pytest.raises(ValueError, match="no session may follow"):
        FatigueSigmaExperimentState.from_dict(encoded)


def test_outcome_trial_count_increment_is_bounded_and_matches_candidate_flag(
    paired_two_session_runner,
) -> None:
    encoded = paired_two_session_runner.session_outcomes()[0].to_dict()
    encoded["final_persistent_state_by_life"]["life-green"]["trial_count"] += 2

    with pytest.raises(ValueError, match="trial_count at most once"):
        ExperimentalSessionOutcome.from_dict(encoded)

    encoded = paired_two_session_runner.session_outcomes()[0].to_dict()
    encoded["final_persistent_state_by_life"]["life-red"]["trial_count"] += 1
    with pytest.raises(ValueError, match="exactly match candidate generation"):
        ExperimentalSessionOutcome.from_dict(encoded)


def test_session_outcome_schema_is_distinct_from_replicate_aggregate(
    paired_two_session_runner,
) -> None:
    encoded = paired_two_session_runner.session_outcomes()[0].to_dict()

    assert encoded["schema_version"] == FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION
    assert encoded["schema_version"] != FATIGUE_SIGMA_REPLICATE_RESULT_SCHEMA_VERSION


def test_only_holder_may_increment_trial_count_for_a_generated_candidate(
    paired_two_session_runner,
) -> None:
    encoded = paired_two_session_runner.session_outcomes()[0].to_dict()
    holder = encoded["holder_id"]
    nonholder = next(
        life_id
        for life_id in encoded["final_persistent_state_by_life"]
        if life_id != holder
    )
    encoded["final_persistent_state_by_life"][nonholder]["trial_count"] += 1
    encoded["candidate_generated"] = True
    encoded["exploration_decision"] = "explore"
    sigma = encoded["sigma_trajectory_by_life"][holder]
    sigma["candidate_generated"] = True

    with pytest.raises(ValueError, match="only the holder"):
        ExperimentalSessionOutcome.from_dict(encoded)


def test_outcome_holder_anchor_enums_and_record_ids_are_strict(
    paired_two_session_runner,
) -> None:
    source = paired_two_session_runner.session_outcomes()[0]

    encoded = source.to_dict()
    holder_k = list(encoded["holder_final_k_anchor"])
    holder_k[0] += 0.01
    encoded["holder_final_k_anchor"] = holder_k
    with pytest.raises(ValueError, match="holder_final_k_anchor"):
        ExperimentalSessionOutcome.from_dict(encoded)

    encoded = source.to_dict()
    encoded["exploration_decision"] = "future_mode"
    with pytest.raises(ValueError, match="exploration_decision"):
        ExperimentalSessionOutcome.from_dict(encoded)

    encoded = source.to_dict()
    encoded["adoption_result"] = "future_result"
    with pytest.raises(ValueError, match="adoption_result"):
        ExperimentalSessionOutcome.from_dict(encoded)

    encoded = source.to_dict()
    encoded["fatigue_trajectory_by_life"]["life-red"]["digital_life_id"] = (
        "life-blue"
    )
    with pytest.raises(ValueError, match="fatigue record Digital Life ID"):
        ExperimentalSessionOutcome.from_dict(encoded)

    encoded = source.to_dict()
    holder = encoded["holder_id"]
    encoded["sigma_trajectory_by_life"][holder]["digital_life_id"] = "life-red"
    with pytest.raises(ValueError, match="sigma record Digital Life ID"):
        ExperimentalSessionOutcome.from_dict(encoded)


def test_outcome_bundle_presentations_are_bound_to_session_and_holder(
    paired_two_session_runner,
) -> None:
    encoded = paired_two_session_runner.session_outcomes()[0].to_dict()
    encoded["bundle_presentations"][0]["holder_id"] = next(
        life_id
        for life_id in ("life-red", "life-green", "life-blue")
        if life_id != encoded["holder_id"]
    )

    with pytest.raises(ValueError, match="presentation holder"):
        ExperimentalSessionOutcome.from_dict(encoded)


def test_reference_factory_failure_invalidates_both_arms_without_state_commit() -> None:
    def failing_reference_factory(**_kwargs):
        raise RuntimeError("intentional reference failure")

    runner = FatigueSigmaSingleConditionRunner(
        _condition(),
        compare_reference_arm=True,
        reference_simulation_factory=failing_reference_factory,
    )
    before = dict(runner.current_persistent_state_by_life())
    experimental = runner.run_next_session()
    reference = runner.reference_session_outcomes()[0]
    state = runner.state()
    result = runner.result()

    assert experimental.engine_completed
    assert experimental.final_persistent_state_by_life
    assert not experimental.valid_for_convergence
    assert experimental.invalid_reason is not None
    assert experimental.invalid_reason.startswith("paired_reference_invalid:")
    assert not reference.engine_completed
    assert not reference.valid_for_convergence
    assert state.stopped_on_error
    assert state.completed_session_count == 1
    assert state.valid_session_count == result.sessions_valid == 0
    assert dict(state.current_persistent_state_by_life) == before
    assert result.structured_convergence_history[-1]["valid_session_count"] == 0
    assert FatigueSigmaExperimentState.from_json(state.to_json()) == state


def test_handoff_validation_failure_invalidates_both_completed_audits(
    monkeypatch,
) -> None:
    runner = FatigueSigmaSingleConditionRunner(
        _condition(),
        compare_reference_arm=True,
    )
    before = dict(runner.current_persistent_state_by_life())

    def reject_handoff(*_args, **_kwargs):
        raise RuntimeError("synthetic strict handoff rejection")

    monkeypatch.setattr(runner, "_validate_handoff", reject_handoff)
    experimental = runner.run_next_session()
    reference = runner.reference_session_outcomes()[0]

    assert experimental.engine_completed and reference.engine_completed
    assert experimental.final_persistent_state_by_life
    assert reference.final_persistent_state_by_life
    assert not experimental.valid_for_convergence
    assert not reference.valid_for_convergence
    assert "handoff_validation_error" in (experimental.invalid_reason or "")
    assert "handoff_validation_error" in (reference.invalid_reason or "")
    assert dict(runner.current_persistent_state_by_life()) == before
    assert runner.state().valid_session_count == 0
    assert runner.stopped_on_error


def test_saved_seed_is_the_exact_condition_policy_value(
    paired_two_session_runner,
) -> None:
    condition = paired_two_session_runner.condition
    for index, (experimental, reference) in enumerate(
        zip(
            paired_two_session_runner.session_outcomes(),
            paired_two_session_runner.reference_session_outcomes(),
            strict=True,
        )
    ):
        expected = physiology_root_seed_for_session(
            master_seed=condition.master_seed,
            stationary_user_type_id=condition.user_type_id,
            session_index=index,
            policy=condition.session_seed_policy,
        )
        assert experimental.physiology_root_seed == reference.physiology_root_seed
        assert experimental.physiology_root_seed == expected


def test_completed_invalid_outcome_can_preserve_engine_audit() -> None:
    runner = FatigueSigmaSingleConditionRunner(_condition())
    original = runner.run_next_session()
    invalidated = replace(
        original,
        valid_for_convergence=False,
        invalid_reason="synthetic_audit_only_failure",
    )

    assert invalidated.engine_completed
    assert invalidated.final_persistent_state_by_life == (
        original.final_persistent_state_by_life
    )
    assert not invalidated.valid_for_convergence
