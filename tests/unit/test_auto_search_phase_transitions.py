"""Coarse seed, refine neighborhood, and confirmation selection tests."""

from __future__ import annotations

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.gates import GateResult
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.phase_coarse import (
    select_refine_seeds,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.phase_confirm import (
    select_confirmation_conditions,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.phase_refine import (
    build_refine_conditions,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.plan import ConditionPoint


def _summary(index: int):
    return {
        "candidate_id": f"candidate-{index}",
        "condition_key": f"condition-{index}",
        "selected_session_fatigue_target": index * 0.03,
        "sigma_multiplier": 0.5 + index * 0.25,
        "worst_nonflat_correct_structure_lower95": 0.8 - index * 0.1,
        "mean_nonflat_correct_structure_lower95": 0.8 - index * 0.1,
        "flat_spurious_structure_upper95": 0.1 + index * 0.05,
        "flat_rotation_upper95": 0.1 + index * 0.05,
        "W_ceiling_blocked_upper95": 0.1 + index * 0.05,
        "return_within_2_rate": 0.8 - index * 0.1,
        "median_first_structure_session": 4 + index,
        "post_convergence_outlier_rate": 0.1 + index * 0.05,
        "life_dominance_specialist_rate": 0.8 - index * 0.1,
        "bpm_common_specialist_rate": 0.8 - index * 0.1,
        "multi_attractor_specialist_rate": 0.8 - index * 0.1,
    }


def _gate(item, passed=True):
    return GateResult(item["candidate_id"], passed, (), "gate", "v")


def _pareto(items):
    return tuple(
        {"candidate_id": item["candidate_id"], "pareto_rank": index + 1}
        for index, item in enumerate(items)
    )


def test_coarse_selection_is_deterministic_unique_and_max_four() -> None:
    summaries = tuple(_summary(index) for index in range(5))
    coarse = {item["candidate_id"]: _gate(item) for item in summaries}
    final = {item["candidate_id"]: _gate(item, index < 2) for index, item in enumerate(summaries)}
    selected = select_refine_seeds(
        tuple(reversed(summaries)),
        coarse,
        final,
        _pareto(summaries),
    )
    assert len(selected) == 4
    assert len(set(selected)) == 4
    assert selected[0] == ConditionPoint(0.0, 0.5)


def test_refine_neighborhood_has_standard_maximum_twelve() -> None:
    result = build_refine_conditions(
        (
            ConditionPoint(0.03, 0.5),
            ConditionPoint(0.08, 1.0),
            ConditionPoint(0.15, 1.5),
        ),
        maximum_conditions=12,
    )
    assert len(result) == 12
    assert result == tuple(sorted(set(result)))


def test_refine_neighborhood_has_robust_maximum_eighteen() -> None:
    result = build_refine_conditions(
        (
            ConditionPoint(0.03, 0.5),
            ConditionPoint(0.08, 1.0),
            ConditionPoint(0.10, 1.25),
            ConditionPoint(0.15, 1.5),
        ),
        maximum_conditions=18,
    )
    assert len(result) == 18


def test_refine_rejects_more_than_four_seeds() -> None:
    import pytest

    with pytest.raises(ValueError, match="four"):
        build_refine_conditions(
            tuple(ConditionPoint(index * 0.03, 1.0) for index in range(5)),
            maximum_conditions=12,
        )


def test_confirmation_selection_obeys_standard_and_robust_limits() -> None:
    summaries = tuple(_summary(index) for index in range(5))
    gates = {item["candidate_id"]: _gate(item) for item in summaries}
    standard = select_confirmation_conditions(
        summaries,
        gates,
        _pareto(summaries),
        maximum_conditions=3,
    )
    robust = select_confirmation_conditions(
        summaries,
        gates,
        _pareto(summaries),
        maximum_conditions=5,
    )
    assert len(standard) == 3
    assert len(robust) == 5
    assert standard == robust[:3]


def test_confirmation_deduplicates_specialist_overlap() -> None:
    summaries = (_summary(0),)
    gates = {summaries[0]["candidate_id"]: _gate(summaries[0])}
    result = select_confirmation_conditions(
        summaries,
        gates,
        _pareto(summaries),
        maximum_conditions=3,
    )
    assert result == (ConditionPoint(0.0, 0.5),)
