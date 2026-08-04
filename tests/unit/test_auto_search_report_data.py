"""Cross-user condition metric and uncertainty aggregation tests."""

from __future__ import annotations

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    ALL_USER_TYPE_IDS,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.plan import ConditionPoint
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.report_data import (
    aggregate_cross_user_condition,
)


def _replicate(user_type_id: str, *, correct=True, flat_spurious=False, warning=False):
    return {
        "condition_id": "condition",
        "user_type_id": user_type_id,
        "selected_session_fatigue_target": 0.05,
        "sigma_multiplier": 1.0,
        "replicate_index": 0,
        "replicate_master_seed": 1,
        "sessions_completed": 24,
        "sessions_expected": 24,
        "completed": True,
        "failed": False,
        "truth_classification": (
            "spurious_structure_in_flat_control"
            if flat_spurious
            else "correct_structure"
            if correct
            else "stable_suboptimal_structure"
        ),
        "summary_classification": "life_dominant_convergence"
        if correct
        else "diffuse_or_unresolved",
        "life_dominant_converged": correct,
        "bpm_common_converged": correct,
        "multi_attractor_converged": correct,
        "first_life_convergence_session": 5 if correct else None,
        "first_bpm_convergence_session": 6 if correct else None,
        "first_multi_attractor_session": 7 if correct else None,
        "return_within_2_rate": 0.8,
        "post_convergence_outlier_rate": 0.1,
        "bpm_cluster_width": 3.0,
        "accepted_count": 2,
        "mechanical_rotation": {
            "classification": "mechanical_rotation_warning" if warning else "no_warning",
            "holder_switch_rate": 0.2,
        },
        "w_ceiling": {
            "classification": "exploration_identifiable",
            "provisional_success_count": 3,
        },
    }


def test_cross_user_metrics_separate_nonflat_and_flat_control() -> None:
    replicates = tuple(
        _replicate(user_type, correct=user_type != "flat_control")
        for user_type in ALL_USER_TYPE_IDS
    )
    summary = aggregate_cross_user_condition(
        phase="confirm",
        point=ConditionPoint(0.05, 1.0),
        maximum_sessions=24,
        replicates=replicates,
        expected_user_type_ids=ALL_USER_TYPE_IDS,
    )
    assert summary["worst_nonflat_correct_structure_rate"] == 1.0
    assert summary["mean_nonflat_correct_structure_rate"] == 1.0
    assert summary["mean_nonflat_diffuse_rate"] == 0.0
    assert summary["flat_spurious_structure_rate"] == 0.0
    assert summary["flat_mechanical_rotation_warning_rate"] == 0.0
    assert summary["valid_session_rate"] == 1.0
    assert summary["accepted_candidate_count"] == 12
    assert summary["provisional_success_count"] == 18


def test_worst_user_type_controls_worst_rate() -> None:
    replicates = []
    for user_type in ALL_USER_TYPE_IDS:
        replicates.append(_replicate(user_type, correct=user_type != "flat_control"))
        if user_type == "green_single_peak_narrow":
            replicates.append(_replicate(user_type, correct=False))
        else:
            replicates.append(_replicate(user_type, correct=user_type != "flat_control"))
    summary = aggregate_cross_user_condition(
        phase="confirm",
        point=ConditionPoint(0.05, 1.0),
        maximum_sessions=24,
        replicates=tuple(replicates),
        expected_user_type_ids=ALL_USER_TYPE_IDS,
    )
    assert summary["worst_nonflat_correct_structure_rate"] == 0.5
    assert summary["mean_nonflat_correct_structure_rate"] == 0.9


def test_flat_spurious_and_rotation_have_upper_wilson_bounds() -> None:
    replicates = tuple(
        _replicate(
            user_type,
            correct=user_type != "flat_control",
            flat_spurious=user_type == "flat_control",
            warning=user_type == "flat_control",
        )
        for user_type in ALL_USER_TYPE_IDS
    )
    summary = aggregate_cross_user_condition(
        phase="coarse",
        point=ConditionPoint(0.05, 1.0),
        maximum_sessions=24,
        replicates=replicates,
        expected_user_type_ids=ALL_USER_TYPE_IDS,
    )
    assert summary["flat_spurious_structure_rate"] == 1.0
    assert summary["flat_spurious_structure_upper95"] == 1.0
    assert summary["flat_mechanical_rotation_warning_rate"] == 1.0
    assert summary["flat_rotation_upper95"] == 1.0


def test_missing_flat_control_remains_missing_and_not_favorable() -> None:
    users = ALL_USER_TYPE_IDS[:-1]
    summary = aggregate_cross_user_condition(
        phase="coarse",
        point=ConditionPoint(0.05, 1.0),
        maximum_sessions=24,
        replicates=tuple(_replicate(user_type) for user_type in users),
        expected_user_type_ids=users,
    )
    assert summary["flat_spurious_structure_rate"] is None
    assert summary["flat_rotation_upper95"] is None


def test_failed_replicate_lowers_valid_rate_and_is_audited() -> None:
    valid = _replicate("green_hue_dominant_broad_bpm")
    failed = {
        **valid,
        "replicate_index": 1,
        "sessions_completed": 2,
        "completed": False,
        "failed": True,
    }
    summary = aggregate_cross_user_condition(
        phase="coarse",
        point=ConditionPoint(0.05, 1.0),
        maximum_sessions=24,
        replicates=(valid, failed),
        expected_user_type_ids=("green_hue_dominant_broad_bpm",),
    )
    assert summary["failed_replicate_rate"] == 0.5
    assert summary["valid_session_rate"] == 26 / 48
    assert summary["uncertainty"]["small_sample_warning"] is True
