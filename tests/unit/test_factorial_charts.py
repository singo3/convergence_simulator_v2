"""Factorial charts retain Stage 8A.3 session/BPM/Hue/life semantics."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    AUTONOMOUS_ARM,
    RANDOM_ARM,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.charts import (
    factor_plot_svg,
    participant_factorial_grid,
    participant_paired_lines_svg,
    user_type_factorial_grid,
    user_type_heatmap_svg,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    CONDITION_IDS,
)


def _bundle(condition: str, arm: str, index: int) -> BundleOutcome:
    life = ("life-red", "life-green", "life-blue")[index]
    return BundleOutcome(
        participant_id="fixture__p001",
        user_type_id="green_hue_dominant_broad_bpm",
        response_strength_scale=1.0,
        condition_id=condition,
        arm=arm,
        session_index=0,
        bundle_index=index,
        bundle_role="fixture",
        evaluation_quality="accepted",
        valid_for_analysis=True,
        baseline_rmssd_ms=20.0,
        bundle_rmssd_ms=21.0 + index,
        delta_rmssd_ms=1.0 + index,
        baseline_n=0.2,
        bundle_n=0.3,
        w=0.5,
        w_anchor_session=0.5 if arm == AUTONOMOUS_ARM else None,
        displayed_life_id=life,
        displayed_hue_degree=(5.0, 125.0, 250.0)[index],
        displayed_blink_bpm=(70.0, 100.0, 130.0)[index],
        displayed_b=(0.2, 0.5, 0.6, 0.5),
        anchor_or_trial="trial" if index == 1 else "anchor",
        adoption_result="accepted" if index == 2 else None,
        source_participant_id=None,
        source_session_index=None,
        source_bundle_index=None,
        target_rmssd_used_for_future_output=arm == AUTONOMOUS_ARM,
        physiology_seed=123,
        output_seed=456 if arm == RANDOM_ARM else None,
        event_digest="a" * 64,
        data_digest="b" * 64,
    )


def _session(condition: str, arm: str) -> SessionOutcome:
    return SessionOutcome(
        participant_id="fixture__p001",
        user_type_id="green_hue_dominant_broad_bpm",
        response_strength_scale=1.0,
        condition_id=condition,
        arm=arm,
        session_index=0,
        physiology_seed=123,
        baseline_rmssd_ms=20.0,
        bundle_rmssd_ms=(21.0, 22.0, 23.0),
        bundle_delta_rmssd_ms=(1.0, 2.0, 3.0),
        mean_valid_bundle_delta_rmssd_ms=2.0,
        median_valid_bundle_delta_rmssd_ms=2.0,
        holder_id="life-blue",
        bundle_life_ids=("life-red", "life-green", "life-blue"),
        bundle_hue_degrees=(5.0, 125.0, 250.0),
        bundle_blink_bpms=(70.0, 100.0, 130.0),
        representative_life_id="life-blue",
        representative_hue_degree=250.0,
        representative_blink_bpm=130.0,
        actual_bundle2_evaluation_output={"life": "life-blue"},
        final_committed_anchor=(0.3, 0.5, 0.5, 0.5) if arm == AUTONOMOUS_ARM else None,
        exploration_decision="explore" if arm == AUTONOMOUS_ARM else None,
        candidate_generated=arm == AUTONOMOUS_ARM,
        adoption_result="accepted" if arm == AUTONOMOUS_ARM else None,
        valid_bundle_count=3,
        session_valid=True,
        invalid_reason=None,
        source_participant_id=None,
        output_sequence_digest="c" * 64,
    )


def _records():
    bundles = tuple(
        _bundle(condition, arm, index)
        for condition in CONDITION_IDS
        for arm in (AUTONOMOUS_ARM, RANDOM_ARM)
        for index in range(3)
    )
    sessions = tuple(
        _session(condition, arm)
        for condition in CONDITION_IDS
        for arm in (AUTONOMOUS_ARM, RANDOM_ARM)
    )
    return bundles, sessions


def test_participant_grid_is_four_conditions_by_two_arms() -> None:
    bundles, sessions = _records()
    chart = participant_factorial_grid("fixture__p001", bundles, sessions)
    assert "data-layout='4-conditions-by-2-arms'" in chart
    assert chart.count("class='factorial-condition-panel'") == 4
    assert chart.count(">autonomous</text>") == 4
    assert chart.count(">pure random</text>") == 4


@pytest.mark.parametrize(
    "semantic",
    (
        "session index",
        "blink BPM",
        "actual Hue",
        "<circle",
        "<polygon",
        "<rect",
        "fill-opacity='0.42'",
    ),
)
def test_participant_chart_retains_axis_hue_shape_and_trial_semantics(
    semantic: str,
) -> None:
    bundles, sessions = _records()
    assert semantic in participant_factorial_grid("fixture__p001", bundles, sessions)


@pytest.mark.parametrize(
    "metric",
    (
        "nonflat_mean_effect_ms",
        "nonflat_positive_rate",
        "worst_user_type_effect_ms",
        "selection_enrichment_advantage",
        "holder_switch_rate",
    ),
)
def test_factor_plot_supports_required_switch_metric(metric: str) -> None:
    rows = [
        {
            "condition_id": condition,
            metric: float(index + 1),
        }
        for index, condition in enumerate(CONDITION_IDS)
    ]
    chart = factor_plot_svg(rows, metric=metric)
    assert "σ 1.0" in chart and "σ 0.5" in chart
    assert "gradual recovery" in chart and "full recovery" in chart


@pytest.mark.parametrize(
    "metric",
    (
        "late_delta_rmssd_advantage_ms",
        "positive_participant_rate",
        "full_pattern_selection_enrichment_advantage",
        "lagged_pattern_advantage",
    ),
)
def test_heatmap_supports_required_metric(metric: str) -> None:
    rows = [
        {
            "participant_id": "p1",
            "user_type_id": "green_hue_dominant_broad_bpm",
            "condition_id": condition,
            "late_delta_rmssd_advantage_ms": 1.0,
            "full_pattern_selection_enrichment_advantage": 0.2,
            "lagged_pattern_advantage": 0.1,
        }
        for condition in CONDITION_IDS
    ]
    chart = user_type_heatmap_svg(rows, metric=metric)
    assert "user-type-heatmap" in chart
    assert all(condition in chart for condition in CONDITION_IDS)


def test_paired_line_contains_all_four_required_contrasts() -> None:
    rows = [
        {
            "participant_id": "p1",
            "condition_id": condition,
            "late_delta_rmssd_advantage_ms": float(index),
        }
        for index, condition in enumerate(CONDITION_IDS)
    ]
    chart = participant_paired_lines_svg(rows)
    assert all(label in chart for label in ("A→B", "C→D", "A→C", "B→D"))


def test_user_type_panel_reuses_median_q1_q3_modal_life_hue_fields() -> None:
    rows = [
        {
            "condition_id": condition,
            "user_type_id": "green_hue_dominant_broad_bpm",
            "arm": arm,
            "session_index": 0,
            "median_bpm": 100.0,
            "bpm_q1": 90.0,
            "bpm_q3": 110.0,
            "bpm_lower95": 88.0,
            "bpm_upper95": 112.0,
            "modal_life_id": "life-green",
            "modal_life_share": 0.75,
            "modal_life_circular_mean_hue_degree": 125.0,
            "modal_life_circular_concentration": 0.9,
            "life_red_share": 0.1,
            "life_green_share": 0.75,
            "life_blue_share": 0.15,
        }
        for condition in CONDITION_IDS
        for arm in (AUTONOMOUS_ARM, RANDOM_ARM)
    ]
    chart = user_type_factorial_grid(rows)
    assert chart.count("user-type-trajectory") == 4
    assert "modal share 0.75" in chart


def test_chart_rejects_unknown_factor_metric() -> None:
    with pytest.raises(ValueError):
        factor_plot_svg([], metric="opaque_score")
