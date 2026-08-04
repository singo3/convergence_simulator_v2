"""Deterministic Stage 8A.1 life/BPM/multi-attractor diagnostics."""

from __future__ import annotations

import dataclasses

import pytest

from symbiotic_sim_v2.convergence.structured import (
    StructuredConvergenceConfig,
    StructuredConvergenceEvaluator,
    StructuredSessionObservation,
    classify_structured_convergence,
    evaluate_bpm_common,
    evaluate_life_dominance,
    evaluate_mechanical_rotation,
    evaluate_multi_attractor,
    evaluate_structured_convergence_history,
)


def observed(
    index: int,
    holder: str = "life-green",
    bpm: float = 100.0,
    hue: float = 125.0,
) -> StructuredSessionObservation:
    return StructuredSessionObservation(
        session_index=index,
        valid_for_convergence=True,
        holder_id=holder,
        hue_degree=hue,
        blink_bpm=bpm,
    )


def holders(values: str) -> tuple[StructuredSessionObservation, ...]:
    identities = {"G": "life-green", "R": "life-red", "B": "life-blue"}
    return tuple(observed(index, identities[value]) for index, value in enumerate(values))


def test_life_dominance_six_of_eight_allows_separated_and_latest_outlier() -> None:
    config = StructuredConvergenceConfig()
    result = evaluate_life_dominance(holders("GGRGGBGG"), config)
    assert result.confirmed
    assert result.dominant_life_id == "life-green"
    assert result.dominant_count == 6
    assert result.share == 0.75
    assert result.strict_consecutive_run == 2
    assert result.one_outlier_tolerant_longest_run == 5
    assert result.maximum_consecutive_outliers == 1
    assert result.return_within_one_session_count == 2
    assert result.return_within_one_session_rate == 1.0

    latest = evaluate_life_dominance(holders("GGGGGGGR"), config)
    assert latest.confirmed
    assert latest.latest_session_outlier
    assert latest.one_outlier_tolerant_longest_run == 8


def test_life_dominance_five_of_eight_and_two_consecutive_outliers_fail() -> None:
    config = StructuredConvergenceConfig()
    assert not evaluate_life_dominance(holders("GRGRGBGG"), config).confirmed
    consecutive = evaluate_life_dominance(holders("GGGRBGGG"), config)
    assert consecutive.dominant_count == 6
    assert consecutive.maximum_consecutive_outliers == 2
    assert not consecutive.confirmed


def test_life_dominance_tie_break_prefers_latest_occurrence_then_lexical() -> None:
    result = evaluate_life_dominance(holders("RBRBRBRB"), StructuredConvergenceConfig())
    assert result.dominant_count == 4
    assert result.one_outlier_tolerant_longest_run == 3
    assert result.dominant_life_id == "life-blue"


def test_life_dominance_never_uses_hue_or_bpm_proximity() -> None:
    values = tuple(
        observed(index, "life-green", bpm=10.0 + index * 20.0, hue=index * 45.0)
        for index in range(8)
    )
    result = evaluate_life_dominance(values, StructuredConvergenceConfig())
    assert result.confirmed
    assert result.dominant_count == 8


def test_bpm_common_finds_six_session_cross_life_horizontal_band() -> None:
    identities = ("life-red", "life-green", "life-blue")
    bpms = (92.0, 95.0, 98.0, 101.0, 104.0, 108.0, 145.0, 160.0)
    values = tuple(observed(i, identities[i % 3], bpm) for i, bpm in enumerate(bpms))
    result = evaluate_bpm_common(values, StructuredConvergenceConfig())
    assert result.confirmed
    assert result.support == 6
    assert result.member_session_indices == (0, 1, 2, 3, 4, 5)
    assert result.outlier_session_indices == (6, 7)
    assert result.bpm_range == 16.0
    assert result.cross_life
    assert result.participating_life_ids == ("life-blue", "life-green", "life-red")


def test_bpm_common_boundary_is_inclusive_and_five_support_fails() -> None:
    config = StructuredConvergenceConfig()
    boundary = tuple(
        observed(i, ("life-red", "life-green", "life-blue")[i % 3], bpm)
        for i, bpm in enumerate((90.0, 94.0, 98.0, 102.0, 106.0, 110.0, 145.0, 160.0))
    )
    assert evaluate_bpm_common(boundary, config).bpm_range == 20.0
    outside = tuple(
        observed(i, bpm=bpm)
        for i, bpm in enumerate((90.0, 94.0, 98.0, 102.0, 106.0, 111.0, 145.0, 160.0))
    )
    assert not evaluate_bpm_common(outside, config).confirmed


def test_bpm_common_subset_tie_prefers_newer_sessions_and_newest_medoid() -> None:
    values = tuple(
        observed(index, ("life-red", "life-green", "life-blue")[index % 3], bpm)
        for index, bpm in enumerate((80.0, 80.0, 90.0, 90.0, 100.0, 100.0, 110.0, 110.0))
    )
    result = evaluate_bpm_common(values, StructuredConvergenceConfig())
    assert result.member_session_indices == (2, 3, 4, 5, 6, 7)
    assert result.bpm_range == 20.0
    assert result.mean_absolute_deviation == pytest.approx(6.666666666666667)
    assert result.medoid_bpm == 100.0


def test_two_and_three_life_specific_attractors_are_recurrent_and_separated() -> None:
    two = tuple(
        [observed(i, "life-red", 55.0) for i in range(3)]
        + [observed(i, "life-green", 100.0) for i in range(3, 6)]
    )
    two_result = evaluate_multi_attractor(two, StructuredConvergenceConfig())
    assert two_result.confirmed
    assert two_result.two_attractor_flag
    assert not two_result.three_attractor_flag
    assert two_result.attractor_separation == 45.0

    three = tuple(
        [observed(i, "life-red", 55.0) for i in range(3)]
        + [observed(i, "life-green", 100.0) for i in range(3, 6)]
        + [observed(i, "life-blue", 145.0) for i in range(6, 9)]
    )
    three_result = evaluate_multi_attractor(three, StructuredConvergenceConfig())
    assert three_result.confirmed
    assert three_result.attractor_count == 3
    assert three_result.three_attractor_flag


def test_multi_attractor_rejects_insufficient_samples_fraction_and_close_centers() -> None:
    config = StructuredConvergenceConfig()
    insufficient = tuple(
        [observed(i, "life-red", 55.0) for i in range(2)]
        + [observed(i, "life-green", 100.0) for i in range(2, 5)]
    )
    assert not evaluate_multi_attractor(insufficient, config).confirmed

    low_fraction = tuple(
        [observed(i, "life-red", bpm) for i, bpm in enumerate((50, 55, 60, 100, 140))]
        + [observed(i, "life-green", 120.0) for i in range(5, 8)]
    )
    result = evaluate_multi_attractor(low_fraction, config)
    red = next(item for item in result.life_attractors if item.life_id == "life-red")
    assert red.support_fraction == 0.6
    assert not red.valid_attractor
    assert not result.confirmed

    close = tuple(
        [observed(i, "life-red", 90.0) for i in range(3)]
        + [observed(i, "life-green", 109.0) for i in range(3, 6)]
    )
    close_result = evaluate_multi_attractor(close, config)
    assert close_result.attractor_count == 2
    assert close_result.attractor_separation == 19.0
    assert not close_result.confirmed


def test_multi_attractor_allows_one_outlier_at_exact_support_fraction() -> None:
    values = tuple(
        [observed(i, "life-red", bpm) for i, bpm in enumerate((50, 55, 60, 120))]
        + [observed(i, "life-green", bpm) for i, bpm in enumerate((100, 102, 104), 4)]
    )
    result = evaluate_multi_attractor(values, StructuredConvergenceConfig())
    red = next(item for item in result.life_attractors if item.life_id == "life-red")
    assert red.support == 3
    assert red.support_fraction == 0.75
    assert red.outlier_session_indices == (3,)
    assert result.confirmed


@pytest.mark.parametrize(
    ("sufficient", "life", "bpm", "multi", "expected"),
    (
        (False, False, False, False, "insufficient_sessions"),
        (True, True, True, False, "single_life_pattern_convergence"),
        (True, True, False, False, "life_dominant_convergence"),
        (True, False, True, False, "bpm_common_convergence"),
        (True, False, False, True, "life_specific_multi_attractor_convergence"),
        (True, True, False, True, "mixed_structured_convergence"),
        (True, False, True, True, "mixed_structured_convergence"),
        (True, False, False, False, "diffuse_or_unresolved"),
    ),
)
def test_summary_classification_has_no_single_forced_score(
    sufficient: bool,
    life: bool,
    bpm: bool,
    multi: bool,
    expected: str,
) -> None:
    assert (
        classify_structured_convergence(
            sufficient_sessions=sufficient,
            life_dominant=life,
            bpm_common=bpm,
            multi_attractor=multi,
        )
        == expected
    )


def test_mechanical_rotation_rates_match_literal_holder_patterns() -> None:
    aba = evaluate_mechanical_rotation(holders("GRG"))
    assert aba.holder_switch_rate == 1.0
    assert aba.immediate_return_rate == 1.0
    assert aba.three_distinct_life_window_rate == 0.0
    assert aba.dominant_life_return_rate == 1.0
    assert aba.mean_sessions_between_same_life_selections == 2.0

    abca = evaluate_mechanical_rotation(holders("GRBG"))
    assert abca.holder_switch_rate == 1.0
    assert abca.three_distinct_life_window_rate == 1.0
    assert abca.immediate_return_rate == 0.0
    assert abca.three_life_cycle_rate == 1.0
    assert abca.dominant_life_return_rate == 0.5
    assert abca.mean_sessions_between_same_life_selections == 3.0


def test_evaluator_preserves_early_three_of_four_as_separate_auxiliary_signal() -> None:
    first_four = tuple(observed(index, bpm=100.0 + index) for index in range(4))
    records = evaluate_structured_convergence_history(
        first_four,
        StructuredConvergenceConfig(maximum_sessions=4),
    )
    final = records[-1]
    assert final.early_single_life_pattern_signal
    assert not final.life_dominant_converged
    assert final.summary_classification == "insufficient_sessions"


def test_structured_record_exposes_independent_continuity_return_and_scores() -> None:
    final = evaluate_structured_convergence_history(
        holders("GGGGRGGG"),
        StructuredConvergenceConfig(),
    )[-1]
    encoded = final.to_dict()

    assert encoded["strict_consecutive_run"] == 4
    assert encoded["latest_session_outlier"] is False
    assert encoded["one_gap_tolerant_continuity_flag"] is True
    assert encoded["one_gap_tolerant_continuity_score"] == 1.0
    assert encoded["temporary_outlier_and_return_flag"] is True
    assert encoded["temporary_outlier_and_return_score"] == 1.0
    assert encoded["life_dominance_score"] == 0.875
    assert 0.0 <= encoded["bpm_common_score"] <= 1.0
    assert 0.0 <= encoded["multi_attractor_score"] <= 1.0
    assert 0.0 <= encoded["mechanical_rotation_score"] <= 1.0


def test_append_replay_invalid_exclusion_and_immutability_are_deterministic() -> None:
    values = list(holders("GGRGGBGG"))
    values.insert(
        2,
        StructuredSessionObservation(
            session_index=2,
            valid_for_convergence=False,
            holder_id=None,
            hue_degree=None,
            blink_bpm=None,
            invalid_reason="baseline_rejected",
        ),
    )
    values = [dataclasses.replace(value, session_index=index) for index, value in enumerate(values)]
    evaluator = StructuredConvergenceEvaluator(StructuredConvergenceConfig(maximum_sessions=9))
    for value in values:
        latest = evaluator.append(value)
    replay = evaluate_structured_convergence_history(
        tuple(values),
        StructuredConvergenceConfig(maximum_sessions=9),
    )
    assert evaluator.records() == replay
    assert latest.valid_session_count == 8
    assert evaluator.latest_classification == latest.summary_classification
    with pytest.raises(dataclasses.FrozenInstanceError):
        latest.summary_classification = "diffuse_or_unresolved"  # type: ignore[misc]
