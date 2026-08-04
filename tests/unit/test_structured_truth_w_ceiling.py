"""Separate hidden-truth, rotation-E, and W-ceiling Stage 8A.1 audits."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.convergence.structured import (
    StructuredConvergenceConfig,
    StructuredConvergenceEvaluator,
    StructuredSessionObservation,
    WCeilingObservation,
    evaluate_e_driven_switches,
    evaluate_structured_truth_alignment,
    evaluate_w_ceiling,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    stationary_user_type_profile_v2,
)


def observed(index: int, holder: str, hue: float, bpm: float) -> StructuredSessionObservation:
    return StructuredSessionObservation(index, True, holder, hue, bpm)


def evaluate(values: tuple[StructuredSessionObservation, ...]):
    evaluator = StructuredConvergenceEvaluator(
        StructuredConvergenceConfig(maximum_sessions=max(18, len(values)))
    )
    for value in values:
        record = evaluator.append(value)
    return record


def test_truth_alignment_detects_life_common_and_three_attractor_modes() -> None:
    life_values = tuple(observed(i, "life-green", 125.0, 20.0 + i * 15) for i in range(8))
    life_record = evaluate(life_values)
    life_truth = evaluate_structured_truth_alignment(
        life_values,
        life_record,
        stationary_user_type_profile_v2("green_hue_dominant_broad_bpm"),
    )
    assert life_truth.structure_mode_match
    assert life_truth.expected_dominant_life_match
    assert life_truth.truth_classification == "correct_structure"
    assert life_truth.recent_high_preference_hit_rate == 1.0

    identities = ("life-red", "life-green", "life-blue")
    common_values = tuple(
        observed(i, identities[i % 3], i * 40.0, 100.0 + (i % 3 - 1) * 2.0) for i in range(8)
    )
    common_record = evaluate(common_values)
    common_truth = evaluate_structured_truth_alignment(
        common_values,
        common_record,
        stationary_user_type_profile_v2("bpm_common_100_hue_neutral"),
    )
    assert common_truth.structure_mode_match
    assert common_truth.expected_common_bpm_gap is not None
    assert common_truth.expected_common_bpm_gap <= 2.0
    assert common_truth.truth_classification == "correct_structure"

    multi_values = tuple(
        [observed(i, "life-red", 5.0, 55.0) for i in range(3)]
        + [observed(i, "life-green", 125.0, 100.0) for i in range(3, 6)]
        + [observed(i, "life-blue", 250.0, 145.0) for i in range(6, 9)]
    )
    multi_record = evaluate(multi_values)
    multi_truth = evaluate_structured_truth_alignment(
        multi_values,
        multi_record,
        stationary_user_type_profile_v2("three_life_bpm_equal"),
    )
    assert multi_truth.structure_mode_match
    assert multi_truth.expected_attractor_coverage_count == 3
    assert multi_truth.expected_attractor_coverage_rate == 1.0
    assert tuple(item.hit_count for item in multi_truth.peak_hit_count_by_peak) == (3, 3, 3)
    assert multi_truth.truth_classification == "correct_structure"


def test_truth_alignment_distinguishes_partial_suboptimal_and_flat_spurious() -> None:
    wrong_green = tuple(observed(i, "life-green", 200.0, 30.0 + i * 15) for i in range(8))
    wrong_record = evaluate(wrong_green)
    wrong_truth = evaluate_structured_truth_alignment(
        wrong_green,
        wrong_record,
        stationary_user_type_profile_v2("green_hue_dominant_broad_bpm"),
    )
    assert wrong_truth.structure_mode_match
    assert wrong_truth.truth_classification == "stable_suboptimal_structure"
    assert wrong_truth.recent_high_preference_hit_rate == 0.0

    diffuse = tuple(
        observed(i, ("life-red", "life-green", "life-blue")[i % 3], i * 30.0, 20 + i * 18)
        for i in range(8)
    )
    diffuse_truth = evaluate_structured_truth_alignment(
        diffuse,
        evaluate(diffuse),
        stationary_user_type_profile_v2("green_single_peak_narrow"),
    )
    assert diffuse_truth.truth_classification in {
        "not_converged",
        "stable_suboptimal_structure",
    }

    cyclic = tuple(
        observed(
            i,
            ("life-red", "life-green", "life-blue")[i % 3],
            (5.0, 125.0, 250.0)[i % 3],
            (55.0, 100.0, 145.0)[i % 3],
        )
        for i in range(12)
    )
    flat_truth = evaluate_structured_truth_alignment(
        cyclic,
        evaluate(cyclic),
        stationary_user_type_profile_v2("flat_control"),
    )
    assert flat_truth.flat_control_spurious_structure_flag
    assert flat_truth.truth_classification == "spurious_structure_in_flat_control"


def test_weighted_truth_requires_green_dominance_and_a_secondary_attractor() -> None:
    values = tuple(
        [observed(i, "life-red", 5.0, 55.0) for i in range(3)]
        + [observed(i, "life-green", 125.0, 100.0) for i in range(3, 10)]
        + [observed(i, "life-blue", 250.0, 145.0) for i in range(10, 13)]
    )
    truth = evaluate_structured_truth_alignment(
        values,
        evaluate(values),
        stationary_user_type_profile_v2("three_life_bpm_green_dominant"),
    )
    assert truth.expected_dominant_life_match
    assert truth.weighted_secondary_attractor_present


def test_w_ceiling_strict_boundaries_and_classifications_do_not_tune_coefficients() -> None:
    identifiable = WCeilingObservation(0, 0.80, 0.05, 0.86, 0.85, True, False)
    assert identifiable.provisional_success
    assert identifiable.confirmation_success
    assert not identifiable.mathematically_impossible_provisional_adoption
    first = evaluate_w_ceiling((identifiable,))
    assert first.classification == "exploration_identifiable"
    assert first.candidate_generation_count == 1
    assert first.provisional_success_count == 1
    assert first.confirmation_success_count == 1
    assert first.best_observed_trial_w_gap == pytest.approx(0.06)

    exact_boundary = WCeilingObservation(1, 0.93, 0.07, 1.0, 1.0, True, False)
    assert exact_boundary.mathematically_impossible_provisional_adoption
    assert not exact_boundary.provisional_success
    blocked = evaluate_w_ceiling((exact_boundary,))
    assert blocked.classification == "exploration_blocked_by_W_ceiling"
    assert blocked.w_anchor_session_ge_one_minus_epsilon_count == 1
    assert blocked.w_trial_ceiling_count == 2

    partial = evaluate_w_ceiling((identifiable, exact_boundary))
    assert partial.classification == "exploration_partly_saturated"
    assert partial.mathematically_impossible_provisional_adoption_count == 1


def test_w_ceiling_allows_rejected_trial_measurements_and_selected_audit_counts() -> None:
    rejected = WCeilingObservation(0, 0.60, 0.05, None, None, True, False)
    record = evaluate_w_ceiling((rejected,))
    assert record.candidate_generation_count == 1
    assert record.provisional_success_count == 0
    assert record.accepted_count == 0


def test_e_driven_switch_audit_is_separate_from_primary_convergence() -> None:
    snapshots = (
        {
            "holder_id": "life-green",
            "e_at_session_start_by_life": {
                "life-green": 0.10,
                "life-red": 0.0,
                "life-blue": 0.0,
            },
        },
        {
            "holder_id": "life-red",
            "e_at_session_start_by_life": {
                "life-green": 0.10,
                "life-red": 0.0,
                "life-blue": 0.0,
            },
        },
        {
            "holder_id": "life-green",
            "e_at_session_start_by_life": {
                "life-green": 0.0,
                "life-red": 0.08,
                "life-blue": 0.0,
            },
        },
        {
            "holder_id": "life-blue",
            "e_at_session_start_by_life": {
                "life-green": 0.06,
                "life-red": 0.0,
                "life-blue": 0.0,
            },
        },
    )
    result = evaluate_e_driven_switches(snapshots)
    assert result.holder_switch_count == 3
    assert result.evaluable_switch_count == 3
    assert result.lower_incoming_e_switch_count == 3
    assert result.lower_incoming_e_switch_rate == 1.0
    assert result.e_driven_switch_warning
