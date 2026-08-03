"""Stage 8A runner, handoff, resume, reset, and non-interference integration."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.convergence import RollingConvergenceConfig
from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.multi_session import (
    MultiSessionRelationMemoryRunner,
    MultiSessionRelationState,
    MultiSessionRunnerConfig,
    convergence_history_digest,
    final_multi_session_state_digest,
    session_outcome_digest,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig


def four_session_config() -> MultiSessionRunnerConfig:
    return MultiSessionRunnerConfig(
        convergence_config=RollingConvergenceConfig(maximum_sessions=4)
    )


def digest_tuple(runner: MultiSessionRelationMemoryRunner) -> tuple[str, str, str]:
    state = runner.state()
    return (
        session_outcome_digest(state.session_outcomes),
        convergence_history_digest(state.convergence_records),
        final_multi_session_state_digest(state),
    )


def test_one_session_uses_unsigned_seed_and_commits_all_three_persistent_states() -> None:
    runner = MultiSessionRelationMemoryRunner(four_session_config())
    outcome = runner.run_next_session()

    assert outcome.valid_for_convergence
    assert outcome.engine_completed
    assert outcome.physiology_root_seed == 2_264_431_022
    assert outcome.local_time_us == 240_000_000
    assert outcome.global_time_us == 240_000_000
    convergence = runner.convergence_records()[0]
    truth = runner.truth_alignment_records()[0]
    assert convergence.local_time_us == truth.local_time_us == outcome.local_time_us
    assert convergence.global_time_us == truth.global_time_us == outcome.global_time_us
    assert outcome.holder_id in runner.digital_life_ids
    assert len(outcome.final_persistent_state_by_life) == 3
    assert set(outcome.session_count_before_by_life.values()) == {0}
    assert set(outcome.session_count_after_by_life.values()) == {1}
    assert outcome.baseline_evaluation is not None
    assert outcome.baseline_evaluation.is_valid
    assert outcome.session_digest == runner.current_simulation.engine.deterministic_digest()
    assert all(
        presentation.session_index == outcome.session_index
        and presentation.first_global_time_us
        == presentation.first_effective_time_us
        and presentation.last_global_time_us
        == presentation.last_effective_time_us
        for presentation in outcome.bundle_presentations
    )


def test_each_session_is_a_new_engine_with_exact_handoff_and_local_resets() -> None:
    observations = []

    def observing_factory(**kwargs):
        simulation = create_adaptive_relation_memory_closed_loop_simulation(**kwargs)
        components = adaptive_digital_life_components(simulation)
        observations.append(
            {
                "engine": simulation.engine,
                "components": tuple(components.values()),
                "initial": {
                    life_id: component.initial_persistent_state()
                    for life_id, component in components.items()
                },
                "session": {
                    life_id: component.relation_memory_session_state()
                    for life_id, component in components.items()
                },
                "garden_input": simulation.garden_input_component.snapshot(),
                "garden_output": simulation.garden_output_component.snapshot(),
                "response_config": simulation.light_response_config,
            }
        )
        return simulation

    runner = MultiSessionRelationMemoryRunner(
        four_session_config(),
        session_simulation_factory=observing_factory,
    )
    first = runner.run_next_session()
    first_final = dict(first.final_persistent_state_by_life)
    second = runner.run_next_session()

    assert len(observations) == 2
    assert observations[0]["engine"] is not observations[1]["engine"]
    assert all(
        left is not right
        for left, right in zip(
            observations[0]["components"],
            observations[1]["components"],
            strict=True,
        )
    )
    assert observations[1]["initial"] == first_final
    assert observations[0]["response_config"] is observations[1]["response_config"]
    assert second.user_type_id == first.user_type_id == "green_narrow_moderate"
    for observed in observations:
        garden_input = observed["garden_input"]
        garden_output = observed["garden_output"]
        assert not garden_input.baseline_available
        assert garden_input.n_baseline_session is None
        assert garden_input.n_current is None
        assert garden_output.qualification_holder_id is None
        assert garden_output.last_assigned_holder_id is None
        assert garden_output.total_touch_count == 0
        assert all(
            state.w_anchor_session is None
            and state.k_trial is None
            and state.w_trial_1 is None
            and state.w_trial_2 is None
            and state.adaptation_phase == "anchor_evaluation"
            and state.exploration_decision is None
            for state in observed["session"].values()
        )
    assert all(
        observations[1]["initial"][life_id].e == first_final[life_id].e
        for life_id in runner.digital_life_ids
    )


def test_next_session_run_all_pause_and_json_resume_have_identical_digests() -> None:
    config = four_session_config()
    batch = MultiSessionRelationMemoryRunner(config)
    batch.run_all()

    incremental = MultiSessionRelationMemoryRunner(config)
    incremental.run_next_session()
    incremental.run_next_session()
    paused_state = MultiSessionRelationState.from_json(
        incremental.state().to_json(),
        expected_digital_life_ids=incremental.digital_life_ids,
    )
    resumed = MultiSessionRelationMemoryRunner(config, resume_state=paused_state)
    resumed.run_all()

    one_by_one = MultiSessionRelationMemoryRunner(config)
    while one_by_one.can_run_next_session:
        one_by_one.run_next_session()

    assert batch.state() == resumed.state() == one_by_one.state()
    assert digest_tuple(batch) == digest_tuple(resumed) == digest_tuple(one_by_one)
    assert tuple(outcome.session_index for outcome in batch.session_outcomes()) == (
        0,
        1,
        2,
        3,
    )
    assert tuple(outcome.global_time_us for outcome in batch.session_outcomes()) == (
        240_000_000,
        480_000_000,
        720_000_000,
        960_000_000,
    )


def test_direct_state_resume_is_independent_of_persistent_state_mapping_order() -> None:
    config = four_session_config()
    incremental = MultiSessionRelationMemoryRunner(config)
    incremental.run_next_session()
    saved = incremental.state()

    resumed = MultiSessionRelationMemoryRunner(config, resume_state=saved)
    resumed.run_all()

    uninterrupted = MultiSessionRelationMemoryRunner(config)
    uninterrupted.run_all()
    assert resumed.state() == uninterrupted.state()
    assert digest_tuple(resumed) == digest_tuple(uninterrupted)


def test_runner_accepts_only_the_unchanged_fixed_stage5c_roster() -> None:
    fixed_configs = tuple(
        digital_life_config_for_role(role) for role in ("red", "green", "blue")
    )
    reordered = MultiSessionRelationMemoryRunner(
        four_session_config(),
        digital_life_configs=tuple(reversed(fixed_configs)),
    )
    assert set(reordered.digital_life_ids) == {
        "life-red",
        "life-green",
        "life-blue",
    }

    modified = (
        fixed_configs[0],
        replace(fixed_configs[1], initial_q=0.6),
        fixed_configs[2],
    )
    with pytest.raises(ValueError, match="unchanged Stage 5C role configs"):
        MultiSessionRelationMemoryRunner(
            four_session_config(),
            digital_life_configs=modified,
        )


def test_resume_rechecks_holder_id_role_against_the_configured_roster() -> None:
    original = MultiSessionRelationMemoryRunner(four_session_config())
    original.run_next_session()
    state = original.state()
    outcome = state.session_outcomes[0]
    assert outcome.holder_role is not None
    wrong_role = "red" if outcome.holder_role != "red" else "blue"
    object.__setattr__(outcome, "holder_role", wrong_role)

    with pytest.raises(ValueError, match="holder ID and configured role"):
        MultiSessionRelationMemoryRunner(
            four_session_config(),
            resume_state=state,
        )


def test_reset_replays_the_same_sessions_and_digests() -> None:
    runner = MultiSessionRelationMemoryRunner(four_session_config())
    runner.run_all()
    expected = digest_tuple(runner)
    reset_state = runner.reset()

    assert reset_state.completed_session_count == 0
    assert reset_state.next_session_index == 0
    assert not reset_state.session_outcomes
    runner.run_all()
    assert digest_tuple(runner) == expected


def test_resumed_reset_preserves_a_custom_run_origin() -> None:
    life_ids = ("life-red", "life-green", "life-blue")
    initial = {
        life_id: replace(
            RelationMemoryPersistentState.fresh(life_id),
            q=0.61 + index * 0.01,
            e=0.72 + index * 0.01,
        )
        for index, life_id in enumerate(life_ids)
    }
    original = MultiSessionRelationMemoryRunner(
        four_session_config(),
        initial_persistent_state_by_life=initial,
    )
    original.run_next_session()
    saved = MultiSessionRelationState.from_json(
        original.state().to_json(),
        expected_digital_life_ids=life_ids,
    )
    resumed = MultiSessionRelationMemoryRunner(
        four_session_config(),
        resume_state=saved,
    )

    resumed.reset()
    assert dict(resumed.current_persistent_state_by_life()) == initial
    assert dict(resumed.initial_persistent_state_by_life()) == initial


def test_error_attempt_is_recorded_without_commit_and_stops_the_runner() -> None:
    def failing_factory(**_kwargs):
        raise RuntimeError("intentional session factory failure")

    runner = MultiSessionRelationMemoryRunner(
        four_session_config(),
        session_simulation_factory=failing_factory,
    )
    before = dict(runner.current_persistent_state_by_life())
    outcome = runner.run_next_session()
    state = runner.state()

    assert not outcome.engine_completed
    assert not outcome.valid_for_convergence
    assert outcome.invalid_reason.startswith("factory_error:RuntimeError")
    assert state.completed_session_count == 0
    assert state.valid_session_count == 0
    assert state.next_session_index == 1
    assert dict(state.current_persistent_state_by_life) == before
    assert runner.stopped_on_error
    with pytest.raises(RuntimeError, match="stopped"):
        runner.run_next_session()

    with pytest.raises(ValueError, match="240-second closing"):
        replace(
            outcome,
            engine_completed=True,
            session_digest="0" * 64,
        )

    tampered = state.to_dict()
    tampered["current_persistent_state_by_life"]["life-green"]["q"] = 0.123
    with pytest.raises(ValueError, match="latest commit"):
        MultiSessionRelationState.from_dict(
            tampered,
            expected_digital_life_ids=runner.digital_life_ids,
        )


def test_invalid_factory_product_is_a_clean_recorded_failure() -> None:
    runner = MultiSessionRelationMemoryRunner(
        four_session_config(),
        session_simulation_factory=lambda **_kwargs: object(),
    )
    before = dict(runner.current_persistent_state_by_life())

    outcome = runner.run_next_session()

    assert not outcome.engine_completed
    assert outcome.invalid_reason.startswith("factory_error:TypeError")
    assert outcome.holder_id is None
    assert not outcome.final_persistent_state_by_life
    assert outcome.session_digest is None
    assert runner.state().next_session_index == 1
    assert dict(runner.current_persistent_state_by_life()) == before
    assert runner.stopped_on_error


def test_runner_rejects_unsaved_physiology_template_variation() -> None:
    changed = replace(
        VirtualUserConfig(duration_seconds=240),
        mean_heart_rate_bpm=60.0,
    )
    with pytest.raises(ValueError, match="fixed default physiology template"):
        MultiSessionRelationMemoryRunner(
            four_session_config(),
            virtual_user_config_template=changed,
        )


def test_reused_completed_engine_is_an_incomplete_noncommitting_attempt() -> None:
    simulations = []

    def reused_factory(**kwargs):
        if not simulations:
            simulations.append(
                create_adaptive_relation_memory_closed_loop_simulation(**kwargs)
            )
        return simulations[0]

    runner = MultiSessionRelationMemoryRunner(
        four_session_config(),
        session_simulation_factory=reused_factory,
    )
    first = runner.run_next_session()
    committed = dict(runner.current_persistent_state_by_life())
    second = runner.run_next_session()
    state = runner.state()

    assert first.engine_completed
    assert not second.engine_completed
    assert not second.valid_for_convergence
    assert "session factory reused an engine" in second.invalid_reason
    assert state.completed_session_count == 1
    assert state.valid_session_count == 1
    assert state.next_session_index == 2
    assert dict(state.current_persistent_state_by_life) == committed
    assert state.stopped_on_error
    assert runner.stopped_on_error
    assert second.initial_persistent_state_by_life == committed
    assert second.holder_id is None
    assert second.holder_role is None
    assert not second.final_k_anchor_by_life
    assert not second.final_persistent_state_by_life
    assert not second.bundle_presentations
    assert second.baseline_evaluation is None
    assert second.bundle_0_evaluation is None
    assert second.bundle_1_evaluation is None
    assert second.bundle_2_evaluation is None
    assert second.session_digest is None

    restored = MultiSessionRelationState.from_json(
        state.to_json(),
        expected_digital_life_ids=runner.digital_life_ids,
    )
    resumed = MultiSessionRelationMemoryRunner(
        four_session_config(),
        resume_state=restored,
    )
    assert resumed.stopped_on_error
    assert dict(resumed.current_persistent_state_by_life()) == committed
    with pytest.raises(RuntimeError, match="stopped"):
        resumed.run_next_session()


def test_convergence_is_diagnostic_only_and_does_not_stop_later_sessions() -> None:
    config = MultiSessionRunnerConfig(
        convergence_config=RollingConvergenceConfig(maximum_sessions=6)
    )
    runner = MultiSessionRelationMemoryRunner(config)
    state = runner.run_all()

    assert state.completed_session_count == 6
    assert state.first_convergence_session_index is not None
    assert state.first_convergence_session_index < 5
    assert all(outcome.engine_completed for outcome in state.session_outcomes)
    assert any(
        outcome.session_index > state.first_convergence_session_index
        for outcome in state.session_outcomes
    )


def test_twenty_four_session_run_completes_with_contiguous_counts_and_digests() -> None:
    runner = MultiSessionRelationMemoryRunner()
    state = runner.run_all()

    assert state.completed_session_count == 24
    assert state.valid_session_count == 24
    assert state.next_session_index == 24
    assert len(state.session_outcomes) == len(state.convergence_records) == 24
    assert all(
        outcome.session_count_after_by_life[life_id] == outcome.session_index + 1
        for outcome in state.session_outcomes
        for life_id in runner.digital_life_ids
    )
    assert len(session_outcome_digest(state.session_outcomes)) == 64
    assert len(convergence_history_digest(state.convergence_records)) == 64


def test_repeat_seed_policy_changes_only_physiology_seed_schedule() -> None:
    from symbiotic_sim_v2.runtime.multi_session import (
        REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION,
    )

    config = replace(
        four_session_config(),
        session_seed_policy=REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION,
    )
    runner = MultiSessionRelationMemoryRunner(config)
    runner.run_all()
    assert {outcome.physiology_root_seed for outcome in runner.session_outcomes()} == {
        config.master_seed
    }
