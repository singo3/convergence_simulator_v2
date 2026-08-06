"""Transparent human-MVP comparison gates and no-winner outcome."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    ALL_USER_TYPE_IDS,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    CONDITION_IDS,
    V2_REFERENCE_CONDITION,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.recommendation import (
    RECOMMENDATION_VOCABULARY,
    condition_summary_rows,
    recommend_condition,
)


def _rows(
    effects: dict[str, float] | None = None,
    *,
    participants_per_type: int = 2,
):
    selected_effects = effects or {
        CONDITION_IDS[0]: 1.0,
        CONDITION_IDS[1]: 1.2,
        CONDITION_IDS[2]: 0.8,
        CONDITION_IDS[3]: 0.7,
    }
    rows = []
    for condition_id in CONDITION_IDS:
        for user_type in ALL_USER_TYPE_IDS:
            for participant_index in range(participants_per_type):
                effect = (
                    0.05
                    if user_type == "flat_control"
                    else selected_effects[condition_id] + participant_index * 0.01
                )
                rows.append(
                    {
                        "participant_id": f"{user_type}__p{participant_index}",
                        "user_type_id": user_type,
                        "condition_id": condition_id,
                        "late_delta_rmssd_advantage_ms": effect,
                        "full_pattern_selection_enrichment_advantage": 0.2,
                        "lagged_pattern_advantage": 0.2,
                        "w_ceiling_blocked_rate": 0.0,
                        "autonomous_invalid_session_rate": 0.0,
                        "autonomous_reject_rate": 0.0,
                        "autonomous_holder_switch_rate": 0.25,
                    }
                )
    return rows


def test_reference_is_baseline_and_passing_b_can_be_preferred() -> None:
    summaries = condition_summary_rows(_rows())
    result = recommend_condition(summaries)
    assert result["baseline_condition_id"] == V2_REFERENCE_CONDITION
    assert result["preferred_condition_id"] == CONDITION_IDS[1]
    assert result["overall_decision"] == "alternative_preferred_for_human_mvp"
    assert result["formal_spec_adoption"] is False
    assert result["opaque_composite_score_used"] is False


def test_no_passing_alternative_keeps_reference() -> None:
    rows = _rows(
        {
            CONDITION_IDS[0]: 1.0,
            CONDITION_IDS[1]: 0.8,
            CONDITION_IDS[2]: 0.7,
            CONDITION_IDS[3]: 0.6,
        }
    )
    result = recommend_condition(condition_summary_rows(rows))
    assert result["overall_decision"] == "v2_reference_remains_preferred"
    assert result["preferred_condition_id"] == V2_REFERENCE_CONDITION


def test_type_failure_is_detected_with_strict_positive_rule() -> None:
    rows = _rows()
    for row in rows:
        if (
            row["condition_id"] == CONDITION_IDS[2]
            and row["user_type_id"] == "green_single_peak_narrow"
        ):
            row["late_delta_rmssd_advantage_ms"] = 0.0
    summary = next(
        item
        for item in condition_summary_rows(rows)
        if item["condition_id"] == CONDITION_IDS[2]
    )
    assert not summary["all_nonflat_type_means_positive"]
    assert "green_single_peak_narrow" in summary["type_specific_failures"]


@pytest.mark.parametrize(
    "field",
    (
        "nonflat_positive_participant_count",
        "nonflat_positive_rate",
        "nonflat_mean_effect_ms",
        "participant_effect_standard_deviation_ms",
        "flat_control_arm_difference_ms",
        "selection_enrichment_advantage",
        "lagged_coupling_advantage",
        "w_ceiling_blocked_rate",
        "invalid_session_rate",
        "reject_rate",
    ),
)
def test_condition_summary_exposes_transparent_metric(field: str) -> None:
    summary = condition_summary_rows(_rows())[0]
    assert field in summary
    assert summary[field] is not None


def test_partial_smoke_type_coverage_is_insufficient_not_false_preference() -> None:
    partial = [
        row
        for row in _rows()
        if row["user_type_id"]
        in {
            "red_hue_dominant_broad_bpm",
            "green_hue_dominant_broad_bpm",
            "flat_control",
        }
    ]
    result = recommend_condition(condition_summary_rows(partial))
    alternatives = [
        item
        for item in result["condition_decisions"]
        if item["condition_id"] != V2_REFERENCE_CONDITION
    ]
    assert all(item["recommendation"] == "insufficient_or_ambiguous" for item in alternatives)
    assert result["overall_decision"] == "v2_reference_remains_preferred"


def test_recommendation_vocabulary_is_closed() -> None:
    result = recommend_condition(condition_summary_rows(_rows()))
    assert all(
        item["recommendation"] in RECOMMENDATION_VOCABULARY
        for item in result["condition_decisions"]
    )


def test_missing_condition_summary_is_rejected() -> None:
    with pytest.raises(ValueError, match="all four"):
        recommend_condition(condition_summary_rows(_rows())[:-1])
