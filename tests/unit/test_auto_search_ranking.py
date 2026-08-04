"""Robust lexicographic and specialist ranking tests."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.gates import GateResult
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.ranking import (
    rank_robust_candidates,
    select_specialist_candidates,
)


def _summary(name: str, **overrides):
    result = {
        "candidate_id": name,
        "condition_key": name,
        "worst_nonflat_correct_structure_lower95": 0.5,
        "mean_nonflat_correct_structure_lower95": 0.6,
        "flat_spurious_structure_upper95": 0.2,
        "flat_rotation_upper95": 0.2,
        "W_ceiling_blocked_upper95": 0.3,
        "return_within_2_rate": 0.5,
        "median_first_structure_session": 8.0,
        "post_convergence_outlier_rate": 0.1,
        "selected_session_fatigue_target": 0.05,
        "sigma_multiplier": 1.0,
        "life_dominance_specialist_rate": 0.4,
        "bpm_common_specialist_rate": 0.4,
        "multi_attractor_specialist_rate": 0.4,
    }
    result.update(overrides)
    return result


def _gate(item, passed=True):
    return GateResult(
        item["candidate_id"],
        passed,
        () if passed else ("blocked",),
        "balanced",
        "v",
    )


@pytest.mark.parametrize(
    ("field", "winner", "loser"),
    (
        ("worst_nonflat_correct_structure_lower95", 0.6, 0.5),
        ("mean_nonflat_correct_structure_lower95", 0.7, 0.6),
        ("flat_spurious_structure_upper95", 0.1, 0.2),
        ("flat_rotation_upper95", 0.1, 0.2),
        ("W_ceiling_blocked_upper95", 0.2, 0.3),
        ("return_within_2_rate", 0.6, 0.5),
        ("median_first_structure_session", 7.0, 8.0),
        ("post_convergence_outlier_rate", 0.05, 0.1),
        ("selected_session_fatigue_target", 0.03, 0.05),
    ),
)
def test_each_robust_ranking_dimension(field, winner, loser) -> None:
    first = _summary("winner", **{field: winner})
    second = _summary("loser", **{field: loser})
    gates = {"winner": _gate(first), "loser": _gate(second)}
    assert rank_robust_candidates((second, first), gates)[0]["candidate_id"] == "winner"


def test_sigma_distance_and_canonical_axes_are_final_ties() -> None:
    near = _summary("near", sigma_multiplier=1.125)
    far = _summary("far", sigma_multiplier=1.5)
    gates = {"near": _gate(near), "far": _gate(far)}
    assert rank_robust_candidates((far, near), gates)[0]["candidate_id"] == "near"


def test_gate_failed_candidate_is_not_robust_ranked() -> None:
    good = _summary("good")
    blocked = _summary("blocked", worst_nonflat_correct_structure_lower95=1.0)
    gates = {"good": _gate(good), "blocked": _gate(blocked, False)}
    ranked = rank_robust_candidates((blocked, good), gates)
    assert [item["candidate_id"] for item in ranked] == ["good"]


@pytest.mark.parametrize(
    ("category", "metric"),
    (
        ("life_dominance_specialist", "life_dominance_specialist_rate"),
        ("bpm_common_specialist", "bpm_common_specialist_rate"),
        ("multi_attractor_specialist", "multi_attractor_specialist_rate"),
    ),
)
def test_specialist_category_uses_its_metric_and_keeps_safety(category, metric) -> None:
    specialist = _summary("specialist", **{metric: 0.9})
    ordinary = _summary("ordinary", **{metric: 0.2})
    gates = {
        name: _gate(item) for name, item in (("specialist", specialist), ("ordinary", ordinary))
    }
    selected = select_specialist_candidates((ordinary, specialist), gates)[category]
    assert selected["candidate_id"] == "specialist"
    assert selected["flat_spurious_structure_upper95"] == 0.2
    assert selected["W_ceiling_blocked_upper95"] == 0.3


def test_low_rotation_and_conservative_candidates_are_distinct_categories() -> None:
    low_rotation = _summary(
        "low-rotation", flat_rotation_upper95=0.01, selected_session_fatigue_target=0.15
    )
    conservative = _summary(
        "conservative", flat_rotation_upper95=0.2, selected_session_fatigue_target=0.0
    )
    gates = {
        "low-rotation": _gate(low_rotation),
        "conservative": _gate(conservative),
    }
    selected = select_specialist_candidates((low_rotation, conservative), gates)
    assert selected["low_rotation_specialist"]["candidate_id"] == "low-rotation"
    assert selected["conservative_compromise"]["candidate_id"] == "conservative"


def test_empty_specialist_input_returns_explicit_none_categories() -> None:
    selected = select_specialist_candidates((), {})
    assert selected
    assert all(value is None for value in selected.values())
