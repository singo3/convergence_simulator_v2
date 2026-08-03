"""Hidden stationary truth remains separate from primary convergence."""

from __future__ import annotations

import json

import pytest

from symbiotic_sim_v2.convergence import (
    RollingConvergenceConfig,
    SessionPatternObservation,
    TruthAlignmentRecord,
    evaluate_convergence_history,
    evaluate_truth_alignment,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    stationary_user_type_profile,
)


def observed(
    index: int,
    hue: float,
    bpm: float,
    holder: str,
) -> SessionPatternObservation:
    return SessionPatternObservation(
        session_index=index,
        valid_for_convergence=True,
        invalid_reason=None,
        holder_id=holder,
        hue_degree=hue,
        blink_bpm=bpm,
        exploration_decision="hold",
        candidate_generated=False,
        candidate_accepted=False,
    )


def converged_at(hue: float, bpm: float, holder: str):
    values = [observed(index, hue, bpm, holder) for index in range(4)]
    return evaluate_convergence_history(values, RollingConvergenceConfig())[-1]


def test_peak_center_is_correct_convergence_with_zero_gap() -> None:
    config = RollingConvergenceConfig()
    convergence = converged_at(129.0, 125.0, "life-green")
    truth = evaluate_truth_alignment(
        convergence,
        stationary_user_type_profile("green_narrow_moderate"),
        config,
    )
    assert truth.truth_classification == "correct_convergence"
    assert truth.preference_match_at_medoid == 1.0
    assert truth.global_maximum_preference_match == 1.0
    assert truth.response_gap == 0.0
    assert truth.nearest_peak_id == "green"
    assert truth.distance_to_nearest_peak_center == 0.0


def test_stable_suboptimal_and_dual_local_global_are_distinct() -> None:
    config = RollingConvergenceConfig()
    narrow_off = evaluate_truth_alignment(
        converged_at(125.0, 80.0, "life-green"),
        stationary_user_type_profile("green_narrow_moderate"),
        config,
    )
    assert narrow_off.truth_classification == "stable_suboptimal"
    assert narrow_off.response_gap is not None and narrow_off.response_gap > 0.05

    dual = stationary_user_type_profile("red_blue_dual_peak")
    local = evaluate_truth_alignment(
        converged_at(6.0, 70.0, "life-red"),
        dual,
        config,
    )
    global_peak = evaluate_truth_alignment(
        converged_at(252.0, 120.0, "life-blue"),
        dual,
        config,
    )
    assert local.nearest_peak_id == "red-local"
    assert local.preference_match_at_medoid == 0.75
    assert local.response_gap == 0.25
    assert local.truth_classification == "stable_suboptimal"
    assert global_peak.nearest_peak_id == "blue-global"
    assert global_peak.preference_match_at_medoid == 1.0
    assert global_peak.truth_classification == "correct_convergence"


def test_flat_control_is_not_applicable_even_when_primary_converges() -> None:
    truth = evaluate_truth_alignment(
        converged_at(129.0, 125.0, "life-green"),
        stationary_user_type_profile("flat_control"),
        RollingConvergenceConfig(),
    )
    assert truth.truth_classification == "no_preference_control"
    assert truth.primary_converged
    assert truth.global_maximum_preference_match == 0.0
    assert truth.preference_match_at_medoid is None
    assert truth.response_gap is None
    assert truth.nearest_peak_id is None


def test_nonconverged_truth_does_not_select_a_hidden_peak() -> None:
    config = RollingConvergenceConfig()
    record = evaluate_convergence_history(
        [
            observed(0, 7.0, 70.0, "life-red"),
            observed(1, 129.0, 125.0, "life-green"),
            observed(2, 252.0, 120.0, "life-blue"),
            observed(3, 7.0, 150.0, "life-red"),
        ],
        config,
    )[-1]
    truth = evaluate_truth_alignment(
        record,
        stationary_user_type_profile("green_broad_strong"),
        config,
    )
    assert truth.truth_classification == "not_converged"
    assert truth.nearest_peak_id is None
    assert truth.response_gap is None


def test_truth_record_json_round_trip_is_canonical_and_strict() -> None:
    truth = evaluate_truth_alignment(
        converged_at(129.0, 125.0, "life-green"),
        stationary_user_type_profile("green_narrow_moderate"),
        RollingConvergenceConfig(),
    )
    assert TruthAlignmentRecord.from_json(truth.to_json()) == truth
    assert truth.to_json() == json.dumps(
        truth.to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    values = truth.to_dict()
    values.pop("response_gap")
    with pytest.raises(ValueError, match="missing"):
        TruthAlignmentRecord.from_dict(values)
