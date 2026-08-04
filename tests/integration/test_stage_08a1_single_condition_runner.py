"""Stage 8A.1 single-runner handoff, persistence, export, and error tests."""

from __future__ import annotations

import csv
import json
from dataclasses import replace

import pytest

from symbiotic_sim_v2.convergence.structured import (
    EDrivenSwitchRecord,
    StructuredConvergenceConfig,
    StructuredSessionObservation,
    evaluate_mechanical_rotation,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.experiments.fatigue_sigma import (
    FatigueSigmaCondition,
    export_single_condition_csv,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.canonical import canonical_digest
from symbiotic_sim_v2.experiments.fatigue_sigma.exports import (
    CONDITIONS_CSV,
    FATIGUE_CSV,
    HEATMAP_CSV,
    MANIFEST_JSON,
    PATTERN_CSV,
    REPLICATES_CSV,
    SIGMA_CSV,
    STRUCTURED_CSV,
    SUMMARIES_CSV,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.result import (
    _mechanical_classification,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.runner import (
    FatigueSigmaSingleConditionRunner,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.session_outcome import (
    ExperimentalSessionOutcome,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.state import (
    FatigueSigmaExperimentState,
    export_experiment_state_file,
    load_experiment_state_file,
)

LIFE_IDS = ("life-red", "life-green", "life-blue")


def _condition(*, maximum_sessions: int = 4) -> FatigueSigmaCondition:
    return FatigueSigmaCondition.create(
        maximum_sessions=maximum_sessions,
        master_seed=20260802,
    )


def _digest_tuple(runner: FatigueSigmaSingleConditionRunner) -> tuple[str, ...]:
    return tuple(runner.result().digests.values())


@pytest.fixture(scope="module")
def completed_four_runner() -> FatigueSigmaSingleConditionRunner:
    runner = FatigueSigmaSingleConditionRunner(_condition())
    runner.run_all()
    return runner


def test_run_all_incremental_resume_and_reset_are_digest_identical(tmp_path) -> None:
    condition = _condition()
    batch = FatigueSigmaSingleConditionRunner(condition)
    batch.run_all()

    incremental = FatigueSigmaSingleConditionRunner(condition)
    boundaries: list[tuple[int, int]] = []
    partial = incremental.run_all(
        cancel_check=lambda: len(boundaries) >= 2,
        boundary_callback=lambda completed, maximum: boundaries.append(
            (completed, maximum)
        ),
    )
    assert boundaries == [(1, 4), (2, 4)]
    assert partial.next_session_index == 2
    assert incremental.can_run_next_session
    assert not incremental.stopped_on_error
    encoded = incremental.state().to_json()
    decoded = FatigueSigmaExperimentState.from_json(encoded)
    path = export_experiment_state_file(tmp_path / "paused.json", decoded)
    resumed = FatigueSigmaSingleConditionRunner(
        resume_state=load_experiment_state_file(path),
    )
    resumed.run_all()

    one_at_a_time = FatigueSigmaSingleConditionRunner(condition)
    while one_at_a_time.can_run_next_session:
        one_at_a_time.run_next_session()

    assert batch.state() == resumed.state() == one_at_a_time.state()
    assert _digest_tuple(batch) == _digest_tuple(resumed) == _digest_tuple(
        one_at_a_time
    )
    assert tuple(item.session_index for item in batch.session_outcomes()) == tuple(
        range(4)
    )
    assert tuple(item.global_time_us for item in batch.session_outcomes()) == (
        240_000_000,
        480_000_000,
        720_000_000,
        960_000_000,
    )

    expected = _digest_tuple(batch)
    reset_state = batch.reset()
    assert reset_state.next_session_index == reset_state.completed_session_count == 0
    batch.run_all()
    assert _digest_tuple(batch) == expected


def test_twelve_session_preset_runs_to_limit_without_convergence_stop() -> None:
    runner = FatigueSigmaSingleConditionRunner(_condition(maximum_sessions=12))
    state = runner.run_all()
    result = runner.result()

    assert state.completed_session_count == state.valid_session_count == 12
    assert state.next_session_index == 12
    assert not runner.can_run_next_session
    assert len(result.structured_convergence_history) == 12
    assert result.structured_convergence_history[-1][
        "evaluated_at_session_index"
    ] == 11
    assert result.policy_flags["exploration_continues_after_convergence"] is True
    assert result.policy_flags["convergence_is_diagnostic_only"] is True
    assert result.policy_flags["moving_preference"] is False
    candidate_outcome = next(
        item for item in runner.session_outcomes() if item.candidate_generated
    )
    assert candidate_outcome.holder_id is not None
    initial_anchor = candidate_outcome.initial_persistent_state_by_life[
        candidate_outcome.holder_id
    ].k_anchor
    trial_rows = tuple(
        item
        for item in result.session_pattern_trajectory
        if item["session_index"] == candidate_outcome.session_index
        and item["point_kind"] == "trial"
    )
    assert len(trial_rows) == 2
    assert {item["bundle_index"] for item in trial_rows} == {1, 2}
    assert all(tuple(item["k_presented"]) != initial_anchor for item in trial_rows)
    assert {
        tuple(item["k_presented"]) for item in trial_rows
    } == {
        presentation.k_presented
        for presentation in candidate_outcome.bundle_presentations
        if presentation.k_presented != initial_anchor
    }


@pytest.mark.parametrize(
    ("user_type_id", "maximum_sessions", "expected_summary", "expected_truth"),
    (
        (
            "green_hue_dominant_broad_bpm",
            24,
            "single_life_pattern_convergence",
            "correct_structure",
        ),
        (
            "three_life_bpm_equal",
            60,
            "single_life_pattern_convergence",
            "partially_correct_structure",
        ),
    ),
)
def test_standard_and_long_presets_continue_to_the_requested_limit(
    user_type_id: str,
    maximum_sessions: int,
    expected_summary: str,
    expected_truth: str,
) -> None:
    runner = FatigueSigmaSingleConditionRunner(
        FatigueSigmaCondition.create(
            user_type_id=user_type_id,
            maximum_sessions=maximum_sessions,
            master_seed=20260802,
        )
    )
    state = runner.run_all()
    result = runner.result()

    assert state.completed_session_count == maximum_sessions
    assert state.valid_session_count == maximum_sessions
    assert result.sessions_completed == maximum_sessions
    assert result.structured_convergence is not None
    assert result.structured_convergence["evaluated_at_session_index"] == (
        maximum_sessions - 1
    )
    assert result.structured_convergence["summary_classification"] == expected_summary
    assert result.truth_alignment is not None
    assert result.truth_alignment["truth_classification"] == expected_truth
    assert result.policy_flags["exploration_continues_after_convergence"] is True
    assert any(
        record["life_dominant_converged"]
        for record in result.structured_convergence_history[:-1]
    )


def test_result_exposes_gui_projection_aliases_and_manifest_body_digest(
    completed_four_runner,
) -> None:
    result = completed_four_runner.result()
    manifest = dict(result.experiment_manifest)
    attached_digest = manifest.pop("experiment_manifest_digest")

    assert result.structured_convergence == result.structured_convergence_history[-1]
    assert result.latest_structured_convergence == result.structured_convergence
    assert result.latest_truth_alignment == result.truth_alignment
    assert result.fatigue_trajectory_digest == result.digests[
        "fatigue_trajectory_digest"
    ]
    assert result.sigma_trajectory_digest == result.digests[
        "sigma_trajectory_digest"
    ]
    assert result.structured_convergence_digest == result.digests[
        "structured_convergence_digest"
    ]
    assert attached_digest == canonical_digest(manifest)
    assert result.experiment_manifest_digest == attached_digest
    assert result.mechanical_rotation_diagnostics["classification"] in {
        "no_warning",
        "mechanical_rotation_warning",
        "spurious_fatigue_driven_structure_warning",
    }
    assert result.to_dict()["structured_convergence"] == dict(
        result.structured_convergence
    )


def test_final_experimental_state_digest_ignores_paired_reference_arm() -> None:
    condition = _condition()
    experiment_only = FatigueSigmaSingleConditionRunner(condition)
    paired = FatigueSigmaSingleConditionRunner(
        condition,
        compare_reference_arm=True,
    )
    experiment_only.run_all()
    paired.run_all()

    experiment_result = experiment_only.result()
    paired_result = paired.result()
    assert experiment_result.session_outcomes == paired_result.session_outcomes
    assert experiment_result.persistent_state == paired_result.persistent_state
    assert (
        experiment_result.digests["final_experimental_state_digest"]
        == paired_result.digests["final_experimental_state_digest"]
    )
    assert paired_result.reference_arm_result is not None


def test_strong_rotation_warns_without_e_correlation() -> None:
    identities = {
        "R": "life-red",
        "G": "life-green",
        "B": "life-blue",
    }
    observations = tuple(
        StructuredSessionObservation(
            session_index=index,
            valid_for_convergence=True,
            holder_id=identities[symbol],
            hue_degree=120.0,
            blink_bpm=100.0,
        )
        for index, symbol in enumerate("RGBRGBR")
    )
    mechanical = evaluate_mechanical_rotation(observations)
    no_e_warning = EDrivenSwitchRecord(
        holder_switch_count=6,
        evaluable_switch_count=6,
        lower_incoming_e_switch_count=0,
        lower_incoming_e_switch_rate=0.0,
        mean_incoming_e_advantage=0.0,
        e_driven_switch_warning=False,
    )

    assert (
        _mechanical_classification(
            mechanical,
            no_e_warning,
            StructuredConvergenceConfig(),
        )
        == "mechanical_rotation_warning"
    )


def test_experimental_full_recovery_and_reference_arm_handoff_are_separate() -> None:
    initial = {
        life_id: replace(RelationMemoryPersistentState.fresh(life_id), e=0.4)
        for life_id in LIFE_IDS
    }
    runner = FatigueSigmaSingleConditionRunner(
        _condition(),
        compare_reference_arm=True,
        initial_persistent_state_by_life=initial,
    )
    experimental = runner.run_next_session()
    reference = runner.reference_session_outcomes()[0]

    assert experimental.holder_id == reference.holder_id
    assert experimental.valid_for_convergence and reference.valid_for_convergence
    assert not experimental.reference_arm and reference.reference_arm
    selected = experimental.holder_id
    assert selected is not None
    for life_id in LIFE_IDS:
        experiment_fatigue = experimental.fatigue_trajectory_by_life[life_id]
        reference_fatigue = reference.fatigue_trajectory_by_life[life_id]
        experiment_final = experimental.final_persistent_state_by_life[life_id]
        reference_final = reference.final_persistent_state_by_life[life_id]
        if life_id == selected:
            assert experiment_fatigue["selected_active_signal_count"] == 180
            assert experiment_fatigue["full_recovery_applied"] is False
            assert experiment_final.e > 0.4
        else:
            assert experiment_fatigue["selected_active_signal_count"] == 0
            assert experiment_fatigue["e_before_session_end_policy"] > 0.0
            assert experiment_fatigue["full_recovery_applied"] is True
            assert experiment_final.e == 0.0
            assert reference_fatigue["full_recovery_applied"] is False
            assert reference_final.e > 0.0

    second = runner.run_next_session()
    paired_second = runner.reference_session_outcomes()[1]
    assert dict(second.initial_persistent_state_by_life) == dict(
        experimental.final_persistent_state_by_life
    )
    assert dict(paired_second.initial_persistent_state_by_life) == dict(
        reference.final_persistent_state_by_life
    )
    result = runner.result()
    assert result.reference_arm_metadata["enabled"] is True
    assert result.reference_arm_result is not None
    assert result.reference_arm_result["unselected_full_recovery"] is False
    assert result.reference_arm_result["sigma_multiplier"] == 1.0
    assert FatigueSigmaExperimentState.from_json(runner.state().to_json()) == (
        runner.state()
    )
    tampered = runner.state().to_dict()
    tampered["reference_current_persistent_state_by_life"]["life-green"][
        "e"
    ] = 0.123
    with pytest.raises(ValueError, match="reference state differs"):
        FatigueSigmaExperimentState.from_dict(tampered)


def test_factory_error_is_audited_without_atomic_state_commit() -> None:
    def failing_factory(**_kwargs):
        raise RuntimeError("intentional Stage 8A.1 factory failure")

    runner = FatigueSigmaSingleConditionRunner(
        _condition(),
        experimental_simulation_factory=failing_factory,
    )
    before = dict(runner.current_persistent_state_by_life())
    outcome = runner.run_next_session()
    state = runner.state()

    assert not outcome.engine_completed
    assert not outcome.valid_for_convergence
    assert outcome.invalid_reason is not None
    assert outcome.invalid_reason.startswith("factory_error:RuntimeError")
    assert not outcome.final_persistent_state_by_life
    assert state.stopped_on_error
    assert state.completed_session_count == state.valid_session_count == 0
    assert dict(state.current_persistent_state_by_life) == before
    assert FatigueSigmaExperimentState.from_json(state.to_json()) == state
    with pytest.raises(RuntimeError, match="stopped"):
        runner.run_next_session()


def test_state_rejects_current_state_or_handoff_chain_tampering(
    completed_four_runner,
) -> None:
    encoded = completed_four_runner.state().to_dict()
    encoded["current_persistent_state_by_life"]["life-green"]["e"] = 0.123
    with pytest.raises(ValueError, match="atomic handoff"):
        FatigueSigmaExperimentState.from_dict(encoded)

    encoded = completed_four_runner.state().to_dict()
    encoded["session_outcomes"][1]["initial_persistent_state_by_life"][
        "life-green"
    ]["e"] = 0.123
    with pytest.raises(ValueError, match="handoff chain"):
        FatigueSigmaExperimentState.from_dict(encoded)

    encoded = completed_four_runner.state().to_dict()
    encoded["session_outcomes"][-1]["final_persistent_state_by_life"][
        "life-red"
    ]["e"] = 0.123
    encoded["current_persistent_state_by_life"]["life-red"]["e"] = 0.123
    with pytest.raises(ValueError, match="fatigue|final E"):
        FatigueSigmaExperimentState.from_dict(encoded)

    outcome = completed_four_runner.session_outcomes()[0].to_dict()
    outcome["local_time_us"] = 239_000_000
    outcome["global_time_us"] = 239_000_000
    with pytest.raises(ValueError, match="240[- ]second|240000000"):
        ExperimentalSessionOutcome.from_dict(outcome)


def test_csv_export_is_deterministic_and_does_not_change_digests(
    tmp_path,
    completed_four_runner,
) -> None:
    result = completed_four_runner.result()
    before = dict(result.digests)
    first = export_single_condition_csv(tmp_path / "first", result)
    second = export_single_condition_csv(tmp_path / "second", result)

    assert result.digests == before
    assert {path.name for path in first.values()} == {
        CONDITIONS_CSV,
        FATIGUE_CSV,
        SIGMA_CSV,
        PATTERN_CSV,
        STRUCTURED_CSV,
        REPLICATES_CSV,
        SUMMARIES_CSV,
        HEATMAP_CSV,
        MANIFEST_JSON,
    }
    assert {key: path.read_bytes() for key, path in first.items()} == {
        key: path.read_bytes() for key, path in second.items()
    }

    with first["fatigue_trajectory"].open(encoding="utf-8", newline="") as file:
        fatigue_rows = tuple(csv.DictReader(file))
    assert len(fatigue_rows) == 12
    assert sum(row["full_recovery_applied"] == "true" for row in fatigue_rows) == 8

    manifest = json.loads(first["experiment_manifest"].read_text(encoding="utf-8"))
    assert manifest["formal_spec_adoption"] is False
    assert manifest["unselected_full_recovery"] is True
    assert manifest["moving_preference"] is False
    assert manifest["p_explore_modified"] is False
    assert manifest["epsilon_accept_modified"] is False
    assert manifest["q_coefficients_modified"] is False
    assert manifest["Monte_Carlo"] is False
