"""Stage 8A.1 paired grid, aggregation, budget, and cancellation tests."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from typing import Any

import pytest

from symbiotic_sim_v2.convergence.structured import (
    StructuredConvergenceConfig,
    StructuredSessionObservation,
    evaluate_structured_convergence_history,
)
from symbiotic_sim_v2.experiments.fatigue_sigma import (
    FatigueSigmaCondition,
    FatigueSigmaGridConfig,
    FatigueSigmaGridRunner,
    aggregate_condition,
    export_grid_csv,
    paired_replicate_master_seed,
    replicate_result_from_single,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.canonical import canonical_digest
from symbiotic_sim_v2.experiments.fatigue_sigma.result import (
    FatigueSigmaSingleConditionResult,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.runner import (
    FatigueSigmaSingleConditionRunner,
)


@pytest.fixture(scope="module")
def single_result_template() -> FatigueSigmaSingleConditionResult:
    runner = FatigueSigmaSingleConditionRunner(
        FatigueSigmaCondition.create(maximum_sessions=4)
    )
    runner.run_all()
    return runner.result()


def _fake_runner_factory(
    template: FatigueSigmaSingleConditionResult,
    instances: list[Any],
):
    class FakeRunner:
        def __init__(self, condition, *, compare_reference_arm=False) -> None:
            assert compare_reference_arm is False
            self.condition = condition
            self.steps = 0
            self.state_token = object()
            instances.append(self)

        @property
        def can_run_next_session(self) -> bool:
            return self.steps < self.condition.maximum_sessions

        @property
        def stopped_on_error(self) -> bool:
            return False

        def run_next_session(self) -> None:
            self.steps += 1

        def session_outcomes(self) -> tuple[int, ...]:
            return tuple(range(self.steps))

        def result(self) -> FatigueSigmaSingleConditionResult:
            return replace(
                template,
                condition=self.condition.to_dict(),
                sessions_completed=self.steps,
                sessions_valid=self.steps,
                stopped_on_error=False,
            )

    return FakeRunner


def _small_grid() -> FatigueSigmaGridConfig:
    return FatigueSigmaGridConfig(
        fatigue_targets=(0.03, 0.08),
        sigma_multipliers=(0.5, 1.0),
        maximum_sessions=4,
        replicate_count=2,
        base_master_seed=20260802,
    )


def test_grid_uses_paired_seeds_fresh_runners_and_order_independent_output(
    tmp_path,
    single_result_template,
) -> None:
    config = _small_grid()
    first_instances: list[Any] = []
    first = FatigueSigmaGridRunner(
        config,
        runner_factory=_fake_runner_factory(single_result_template, first_instances),
    ).run()
    second_instances: list[Any] = []
    reverse_order = tuple(
        reversed(
            tuple(
                (fatigue, sigma)
                for fatigue in config.fatigue_targets
                for sigma in config.sigma_multipliers
            )
        )
    )
    second = FatigueSigmaGridRunner(
        config,
        runner_factory=_fake_runner_factory(single_result_template, second_instances),
        condition_order=reverse_order,
    ).run()

    expected_seeds = tuple(
        paired_replicate_master_seed(config.base_master_seed, index)
        for index in range(config.replicate_count)
    )
    assert first.to_dict() == second.to_dict()
    assert first.paired_replicate_seeds == expected_seeds
    assert first.completed_session_runs == config.total_planned_session_runs == 32
    assert first.completed_conditions == config.condition_count == 4
    assert first.failed_conditions == 0
    assert not first.cancelled
    assert len(first.replicate_results) == 8
    assert len(first.condition_summaries) == 4
    assert len(first.experiment_conditions) == 8
    assert len(first.fatigue_trajectory) == 8 * 4 * 3
    assert len(first.sigma_trajectory) == 8 * 4
    assert len(first.structured_convergence_history) == 8 * 4
    assert all(
        item.to_dict()["accepted_candidate_count"] == item.accepted_count
        for item in first.condition_summaries
    )
    assert all(
        item.to_dict()["mechanical_rotation_rate"]
        == item.mechanical_rotation_rate
        for item in first.condition_summaries
    )
    assert all(instance.steps == 4 for instance in first_instances)
    assert len({id(instance.state_token) for instance in first_instances}) == 8
    for condition_id in {item.condition_id for item in first.replicate_results}:
        paired = tuple(
            item.replicate_master_seed
            for item in first.replicate_results
            if item.condition_id == condition_id
        )
        assert paired == expected_seeds

    before = dict(first.grid_digests)
    paths = export_grid_csv(tmp_path, first)
    assert first.grid_digests == before
    assert len(paths) == 9
    manifest = json.loads(paths["experiment_manifest"].read_text(encoding="utf-8"))
    assert manifest["formal_spec_adoption"] is False
    assert manifest["moving_preference"] is False
    assert manifest["Monte_Carlo"] is False


def test_real_conditions_share_physiology_seeds_but_not_runner_state() -> None:
    paired_seed = paired_replicate_master_seed(20260802, 3)
    narrow = FatigueSigmaSingleConditionRunner(
        FatigueSigmaCondition.create(
            selected_session_fatigue_target=0.03,
            sigma_multiplier=0.5,
            maximum_sessions=4,
            master_seed=paired_seed,
        )
    )
    broad = FatigueSigmaSingleConditionRunner(
        FatigueSigmaCondition.create(
            selected_session_fatigue_target=0.15,
            sigma_multiplier=1.5,
            maximum_sessions=4,
            master_seed=paired_seed,
        )
    )
    narrow.run_all()
    broad.run_all()

    assert tuple(item.physiology_root_seed for item in narrow.session_outcomes()) == (
        tuple(item.physiology_root_seed for item in broad.session_outcomes())
    )
    assert narrow.current_persistent_state_by_life() is not (
        broad.current_persistent_state_by_life()
    )
    assert narrow.current_simulation is not broad.current_simulation
    assert narrow.condition.condition_id != broad.condition.condition_id


def test_grid_cancel_at_session_boundary_does_not_publish_partial_replicate(
    single_result_template,
) -> None:
    instances: list[Any] = []
    progress: list[dict[str, Any]] = []
    runner = FatigueSigmaGridRunner(
        _small_grid(),
        runner_factory=_fake_runner_factory(single_result_template, instances),
    )

    result = runner.run(
        cancel_check=lambda: bool(progress)
        and progress[-1]["completed_session_runs"] >= 2,
        progress_callback=progress.append,
    )

    assert result.cancelled
    assert result.completed_session_runs == 2
    assert result.completed_conditions == result.failed_conditions == 0
    assert not result.replicate_results
    assert not result.condition_summaries
    assert len(instances) == 1 and instances[0].steps == 2
    assert [item["message"] for item in progress] == [
        "session_boundary",
        "session_boundary",
    ]


def test_grid_records_failed_replicate_without_committing_a_condition() -> None:
    def failing_simulation_factory(**_kwargs):
        raise RuntimeError("intentional grid failure")

    def failing_runner_factory(condition, *, compare_reference_arm=False):
        return FatigueSigmaSingleConditionRunner(
            condition,
            compare_reference_arm=compare_reference_arm,
            experimental_simulation_factory=failing_simulation_factory,
        )

    config = FatigueSigmaGridConfig(
        fatigue_targets=(0.05,),
        sigma_multipliers=(1.0,),
        maximum_sessions=4,
        replicate_count=1,
    )
    result = FatigueSigmaGridRunner(
        config,
        runner_factory=failing_runner_factory,
    ).run()

    assert result.completed_session_runs == 1
    assert result.completed_conditions == 0
    assert result.failed_conditions == 1
    assert len(result.replicate_results) == 1
    assert result.replicate_results[0].failed
    assert not result.replicate_results[0].completed
    assert result.condition_summaries[0].completed_replicate_count == 0
    assert result.condition_summaries[0].failed_replicate_count == 1
    assert result.experiment_conditions == ()
    assert result.fatigue_trajectory == ()
    assert result.sigma_trajectory == ()
    assert result.session_pattern_trajectory == ()
    assert result.structured_convergence_history == ()


def test_real_1x1x4_grid_exports_completed_replicate_audit_rows(
    tmp_path,
) -> None:
    config = FatigueSigmaGridConfig(
        fatigue_targets=(0.05,),
        sigma_multipliers=(1.0,),
        maximum_sessions=4,
        replicate_count=1,
        base_master_seed=20260802,
    )
    result = FatigueSigmaGridRunner(config).run()

    assert result.completed_conditions == 1
    assert result.failed_conditions == 0
    assert len(result.experiment_conditions) == 1
    assert len(result.fatigue_trajectory) == 12
    assert len(result.sigma_trajectory) == 4
    assert len(result.session_pattern_trajectory) >= 4
    assert len(result.structured_convergence_history) == 4
    for rows in (
        result.experiment_conditions,
        result.fatigue_trajectory,
        result.sigma_trajectory,
        result.session_pattern_trajectory,
        result.structured_convergence_history,
    ):
        assert all(
            row["condition_id"] == result.condition_summaries[0].condition_id
            for row in rows
        )
        assert all(row["replicate_index"] == 0 for row in rows)
        assert all(
            row["replicate_master_seed"] == result.paired_replicate_seeds[0]
            for row in rows
        )

    assert result.grid_digests["experiment_condition_digest"] == canonical_digest(
        result.experiment_conditions
    )
    assert result.grid_digests["fatigue_trajectory_digest"] == canonical_digest(
        result.fatigue_trajectory
    )
    assert result.grid_digests["sigma_trajectory_digest"] == canonical_digest(
        result.sigma_trajectory
    )
    assert result.grid_digests["structured_convergence_digest"] == canonical_digest(
        result.structured_convergence_history
    )

    first = export_grid_csv(tmp_path / "first", result)
    second = export_grid_csv(tmp_path / "second", result)
    assert {name: path.read_bytes() for name, path in first.items()} == {
        name: path.read_bytes() for name, path in second.items()
    }

    def rows(name: str) -> tuple[dict[str, str], ...]:
        with first[name].open(encoding="utf-8", newline="") as handle:
            return tuple(csv.DictReader(handle))

    condition_rows = rows("conditions")
    assert len(condition_rows) == 1
    assert condition_rows[0]["fatigue_policy_version"] == (
        "unselected_full_recovery_at_session_end_v0_1"
    )
    assert condition_rows[0]["sigma_scaling_policy_version"] == (
        "scaled_reference_sigma_v0_1"
    )
    assert condition_rows[0]["formal_spec_adoption"] == "false"
    assert condition_rows[0]["schema_version"] == "fatigue_sigma_condition_v1"
    assert len(rows("fatigue_trajectory")) == 12
    assert len(rows("sigma_trajectory")) == 4
    assert len(rows("session_pattern_trajectory")) >= 4
    assert len(rows("structured_convergence_history")) == 4

    heatmap_rows = rows("grid_heatmap")
    assert len(heatmap_rows) == 12
    assert {row["metric_name"] for row in heatmap_rows} == {
        "correct_structure_rate",
        "life_dominant_convergence_rate",
        "bpm_common_convergence_rate",
        "multi_attractor_convergence_rate",
        "diffuse_rate",
        "median_first_convergence_session",
        "post_convergence_outlier_rate",
        "return_within_1_rate",
        "holder_switch_rate",
        "mechanical_rotation_rate",
        "accepted_candidate_count",
        "w_ceiling_blocked_rate",
    }
    assert all(row["replicate_count"] == "1" for row in heatmap_rows)
    assert all(row["completed_replicate_count"] == "1" for row in heatmap_rows)
    assert all(row["failed_replicate_count"] == "0" for row in heatmap_rows)
    assert all(row["effective_sigma_min"] != "" for row in heatmap_rows)


def test_grid_budget_accepts_boundary_and_rejects_excess() -> None:
    sigma_values = tuple(0.25 + index * 0.05 for index in range(15))
    boundary = FatigueSigmaGridConfig(
        fatigue_targets=(0.05,),
        sigma_multipliers=sigma_values,
        maximum_sessions=100,
        replicate_count=20,
    )
    assert boundary.total_planned_session_runs == 30_000

    with pytest.raises(ValueError, match="exceed"):
        FatigueSigmaGridConfig(maximum_sessions=100, replicate_count=20)


def test_condition_aggregate_keeps_tradeoffs_and_excludes_failed_replicates(
    single_result_template,
) -> None:
    base = replicate_result_from_single(
        single_result_template,
        replicate_index=0,
        replicate_master_seed=11,
    )
    first = replace(
        base,
        completed=True,
        failed=False,
        summary_classification="life_dominant_convergence",
        truth_classification="correct_structure",
        life_dominant_converged=True,
        bpm_common_converged=False,
        multi_attractor_converged=False,
        single_life_pattern_converged=False,
        first_life_convergence_session=3,
        first_bpm_convergence_session=None,
        first_multi_attractor_session=None,
        dominant_life_share=0.75,
        bpm_cluster_width=None,
        post_convergence_outlier_rate=0.1,
        return_within_1_rate=0.8,
        return_within_2_rate=0.9,
        mechanical_rotation={
            "holder_switch_rate": 0.2,
            "three_distinct_life_window_rate": 0.1,
            "immediate_return_rate": 0.3,
            "three_life_cycle_rate": 0.0,
            "dominant_life_return_rate": 0.8,
        },
        w_ceiling={"classification": "exploration_blocked_by_W_ceiling"},
        explore_count=2,
        candidate_count=3,
        accepted_count=1,
        selected_life_mean_e=0.1,
        selected_life_max_e=0.2,
        nonselected_full_recovery_count=8,
        effective_sigma_mean=0.1,
        effective_sigma_min=0.05,
        effective_sigma_max=0.15,
        candidate_delta_hue=(1.0,),
        candidate_delta_bpm=(2.0,),
        result_digest="first",
    )
    second = replace(
        first,
        replicate_index=1,
        replicate_master_seed=22,
        summary_classification="life_specific_multi_attractor_convergence",
        truth_classification="partially_correct_structure",
        life_dominant_converged=False,
        bpm_common_converged=True,
        multi_attractor_converged=True,
        first_life_convergence_session=None,
        first_bpm_convergence_session=4,
        first_multi_attractor_session=6,
        dominant_life_share=0.5,
        bpm_cluster_width=12.0,
        post_convergence_outlier_rate=0.3,
        return_within_1_rate=0.6,
        return_within_2_rate=0.7,
        mechanical_rotation={
            "holder_switch_rate": 0.4,
            "three_distinct_life_window_rate": 0.3,
            "immediate_return_rate": 0.1,
            "three_life_cycle_rate": 0.2,
            "dominant_life_return_rate": 0.6,
        },
        w_ceiling={"classification": "exploration_identifiable"},
        explore_count=4,
        candidate_count=5,
        accepted_count=2,
        selected_life_mean_e=0.2,
        selected_life_max_e=0.3,
        nonselected_full_recovery_count=7,
        effective_sigma_mean=0.2,
        effective_sigma_min=0.1,
        effective_sigma_max=0.3,
        candidate_delta_hue=(3.0,),
        candidate_delta_bpm=(4.0,),
        result_digest="second",
    )
    failed = replace(
        first,
        replicate_index=2,
        completed=False,
        failed=True,
        summary_classification="diffuse_or_unresolved",
        explore_count=100,
        candidate_count=100,
        accepted_count=100,
        result_digest="failed",
    )

    summary = aggregate_condition((first, second, failed))
    assert summary.replicate_count == 3
    assert summary.completed_replicate_count == 2
    assert summary.failed_replicate_count == 1
    assert summary.life_dominant_convergence_rate == 0.5
    assert summary.bpm_common_convergence_rate == 0.5
    assert summary.multi_attractor_convergence_rate == 0.5
    assert summary.correct_structure_rate == 0.5
    assert summary.partial_structure_rate == 0.5
    assert summary.diffuse_rate == 0.0
    assert summary.median_first_life_convergence_session == 3.0
    assert summary.median_first_bpm_convergence_session == 4.0
    assert summary.median_first_multi_attractor_session == 6.0
    assert summary.mean_dominant_life_share == 0.625
    assert summary.mean_post_convergence_outlier_rate == pytest.approx(0.2)
    assert summary.holder_switch_rate == pytest.approx(0.3)
    assert summary.explore_count == 6
    assert summary.candidate_count == 8
    assert summary.accepted_count == 3
    assert summary.w_ceiling_blocked_rate == 0.5
    assert summary.nonselected_full_recovery_count == 15
    assert summary.candidate_delta_hue == (1.0, 3.0)
    assert summary.candidate_delta_bpm == (2.0, 4.0)
    assert "best_score" not in summary.to_dict()
    assert "composite_score" not in summary.to_dict()
    summary_body = summary.to_dict()
    attached_digest = summary_body.pop("condition_summary_digest")
    assert attached_digest == canonical_digest(summary_body)


def test_partial_replicate_is_incomplete_without_being_failed(
    single_result_template,
) -> None:
    condition = FatigueSigmaCondition.create(maximum_sessions=6)
    partial = replace(
        single_result_template,
        condition=condition.to_dict(),
        sessions_completed=2,
        sessions_valid=2,
        stopped_on_error=False,
    )
    replicate = replicate_result_from_single(
        partial,
        replicate_index=0,
        replicate_master_seed=11,
    )
    summary = aggregate_condition((replicate,))

    assert not replicate.completed
    assert not replicate.failed
    assert replicate.failure_reason is None
    assert summary.completed_replicate_count == 0
    assert summary.failed_replicate_count == 0


def _structured_single_result(
    template: FatigueSigmaSingleConditionResult,
    observations: tuple[StructuredSessionObservation, ...],
) -> FatigueSigmaSingleConditionResult:
    maximum_sessions = len(observations)
    condition = FatigueSigmaCondition.create(maximum_sessions=maximum_sessions)
    records = evaluate_structured_convergence_history(
        observations,
        StructuredConvergenceConfig(maximum_sessions=maximum_sessions),
    )
    return replace(
        template,
        condition=condition.to_dict(),
        sessions_completed=maximum_sessions,
        sessions_valid=maximum_sessions,
        stopped_on_error=False,
        structured_convergence_history=tuple(item.to_dict() for item in records),
        session_outcomes=tuple(
            {
                "exploration_decision": "hold",
                "candidate_generated": False,
                "candidate_accepted": False,
            }
            for _ in observations
        ),
        fatigue_trajectory=(),
        sigma_trajectory=(),
        truth_alignment_history=(),
    )


def test_post_convergence_outliers_respect_cross_life_bpm_membership(
    single_result_template,
) -> None:
    holder_ids = (
        "life-green",
        "life-green",
        "life-green",
        "life-green",
        "life-green",
        "life-green",
        "life-red",
        "life-green",
        "life-red",
    )
    observations = tuple(
        StructuredSessionObservation(
            session_index=index,
            valid_for_convergence=True,
            holder_id=holder_id,
            hue_degree=125.0,
            blink_bpm=100.0,
        )
        for index, holder_id in enumerate(holder_ids)
    )
    result = _structured_single_result(single_result_template, observations)
    final = result.structured_convergence_history[-1]
    assert final["life_dominance"]["latest_session_outlier"] is True
    assert final["bpm_common"]["cross_life"] is True
    assert observations[-1].session_index in final["bpm_common"][
        "member_session_indices"
    ]

    replicate = replicate_result_from_single(
        result,
        replicate_index=0,
        replicate_master_seed=11,
    )
    assert replicate.post_convergence_outlier_rate == 0.0


def test_post_convergence_outliers_respect_life_specific_attractor_membership(
    single_result_template,
) -> None:
    first_nine = tuple(
        (holder_id, bpm)
        for _ in range(3)
        for holder_id, bpm in (
            ("life-red", 55.0),
            ("life-green", 100.0),
            ("life-blue", 145.0),
        )
    )
    tail = tuple(("life-red", 55.0) for _ in range(7)) + (
        ("life-green", 100.0),
    )
    observations = tuple(
        StructuredSessionObservation(
            session_index=index,
            valid_for_convergence=True,
            holder_id=holder_id,
            hue_degree=125.0,
            blink_bpm=bpm,
        )
        for index, (holder_id, bpm) in enumerate((*first_nine, *tail))
    )
    result = _structured_single_result(single_result_template, observations)
    final = result.structured_convergence_history[-1]
    assert final["life_dominance"]["latest_session_outlier"] is True
    assert final["multi_attractor_converged"] is True
    assert any(
        observations[-1].session_index in attractor["member_session_indices"]
        for attractor in final["multi_attractor"]["life_attractors"]
        if attractor["valid_attractor"]
    )

    replicate = replicate_result_from_single(
        result,
        replicate_index=0,
        replicate_master_seed=11,
    )
    assert replicate.post_convergence_outlier_rate == 0.0
