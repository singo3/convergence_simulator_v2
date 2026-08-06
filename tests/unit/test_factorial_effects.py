"""Participant-paired two-by-two effect identities and bootstrap aggregation."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    CONDITION_IDS,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.factorial_effects import (
    FACTORIAL_OUTCOMES,
    factorial_overall_effect_rows,
    factorial_participant_effect_rows,
    factorial_user_type_effect_rows,
    two_by_two_effects,
)


def _participant_rows(participant_id: str, user_type_id: str, offset: float = 0.0):
    values = (1.0, 2.0, 4.0, 8.0)
    rows = []
    for condition_id, value in zip(CONDITION_IDS, values, strict=True):
        rows.append(
            {
                "participant_id": participant_id,
                "user_type_id": user_type_id,
                "condition_id": condition_id,
                **{field: value + offset for field in FACTORIAL_OUTCOMES.values()},
            }
        )
    return rows


def test_direct_effects_and_interaction_identity() -> None:
    result = two_by_two_effects(a=1.0, b=2.0, c=4.0, d=8.0)
    assert result["sigma_effect_gradual_b_minus_a"] == 1.0
    assert result["sigma_effect_full_d_minus_c"] == 4.0
    assert result["recovery_effect_sigma100_c_minus_a"] == 3.0
    assert result["recovery_effect_sigma050_d_minus_b"] == 6.0
    assert result["interaction_sigma_by_recovery"] == 3.0
    assert result["interaction_recovery_by_sigma"] == 3.0
    assert result["interaction_identity_error"] == 0.0


@pytest.mark.parametrize("missing", ("a", "b", "c", "d"))
def test_missing_factor_cell_produces_explicit_null_effect(missing: str) -> None:
    values = {"a": 1.0, "b": 2.0, "c": 4.0, "d": 8.0}
    values[missing] = None
    assert all(value is None for value in two_by_two_effects(**values).values())


@pytest.mark.parametrize("outcome", tuple(FACTORIAL_OUTCOMES))
def test_participant_effect_rows_cover_required_outcomes(outcome: str) -> None:
    rows = factorial_participant_effect_rows(
        _participant_rows("p1", "green_hue_dominant_broad_bpm")
    )
    selected = next(item for item in rows if item["outcome"] == outcome)
    assert selected["participant_id"] == "p1"
    assert selected["interaction_identity_error"] == 0.0


def test_participant_pairing_rejects_missing_condition() -> None:
    with pytest.raises(ValueError, match="all four"):
        factorial_participant_effect_rows(
            _participant_rows("p1", "green_hue_dominant_broad_bpm")[:-1]
        )


def test_user_type_and_overall_bootstrap_are_participant_level() -> None:
    participants = factorial_participant_effect_rows(
        [
            *_participant_rows("p1", "green_hue_dominant_broad_bpm"),
            *_participant_rows("p2", "green_hue_dominant_broad_bpm", 1.0),
            *_participant_rows("p3", "red_hue_dominant_broad_bpm", 2.0),
        ]
    )
    by_type = factorial_user_type_effect_rows(participants)
    overall = factorial_overall_effect_rows(participants)
    selected_type = next(
        row
        for row in by_type
        if row["user_type_id"] == "green_hue_dominant_broad_bpm"
        and row["outcome"] == "late_delta_rmssd_advantage_ms"
    )
    assert selected_type["participant_count"] == 2
    assert selected_type["interaction_sigma_by_recovery_lower95"] is not None
    selected_overall = next(
        row
        for row in overall
        if row["outcome"] == "late_delta_rmssd_advantage_ms"
    )
    assert selected_overall["participant_count"] == 3
