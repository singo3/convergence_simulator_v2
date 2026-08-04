"""Stage 8A.2 deterministic plan and neighborhood tests."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    AutoSearchConfig,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.plan import (
    ConditionPoint,
    build_search_plan,
    canonical_number,
    local_neighborhood,
)


@pytest.mark.parametrize(
    ("preset", "planned"),
    (("smoke", 32), ("quick", 1_296), ("standard", 32_400), ("robust", 122_400)),
)
def test_preset_maximum_planned_sessions(preset, planned) -> None:
    plan = build_search_plan(AutoSearchConfig.create(search_preset=preset))
    assert plan.maximum_planned_session_runs == planned


@pytest.mark.parametrize(
    ("preset", "phase", "conditions", "sessions", "replicates", "runs"),
    (
        ("smoke", "coarse", 4, 4, 1, 32),
        ("quick", "coarse", 9, 12, 2, 1_296),
        ("standard", "coarse", 30, 24, 3, 12_960),
        ("standard", "refine", 0, 24, 5, 0),
        ("standard", "confirm", 0, 60, 10, 0),
        ("robust", "refine", 0, 60, 10, 0),
        ("robust", "confirm", 0, 60, 20, 0),
    ),
)
def test_phase_shape(preset, phase, conditions, sessions, replicates, runs) -> None:
    selected = build_search_plan(AutoSearchConfig.create(search_preset=preset)).phase(phase)
    assert selected.condition_count == conditions
    assert selected.maximum_sessions == sessions
    assert selected.replicate_count == replicates
    assert selected.planned_session_runs == runs


@pytest.mark.parametrize(
    ("preset", "budget"),
    (("smoke", 31), ("quick", 1_295), ("standard", 32_399), ("robust", 122_399)),
)
def test_budget_excess_is_an_error_not_a_clip(preset, budget) -> None:
    config = AutoSearchConfig.create(
        search_preset=preset,
        maximum_total_session_runs=budget,
    )
    with pytest.raises(ValueError, match="exceed"):
        build_search_plan(config)


def test_reference_runs_are_reported_separately_from_budget() -> None:
    plan = build_search_plan(
        AutoSearchConfig.create(search_preset="standard", include_reference_arm=True)
    )
    assert plan.maximum_planned_session_runs == 32_400
    assert plan.reference_session_runs == 4_320
    assert plan.to_dict()["budget_includes_reference_cache_runs"] is False


@pytest.mark.parametrize(
    ("value", "expected"),
    ((0.03, 0.03), ("0.0450004", 0.045), ("1.1249996", 1.125), (0, 0.0)),
)
def test_canonical_number(value, expected) -> None:
    assert canonical_number(value) == expected


def test_condition_identity_uses_canonical_six_decimal_axes() -> None:
    point = ConditionPoint(0.03, 1.0)
    assert point.condition_key == "fatigue_0.030000__sigma_1.000000"
    assert ConditionPoint(0.0300001, 1.0000001) == point


@pytest.mark.parametrize(
    ("fatigue", "sigma"),
    ((-0.001, 1.0), (0.201, 1.0), (0.05, 0.249), (0.05, 1.501)),
)
def test_condition_bounds_are_rejected_without_clipping(fatigue, sigma) -> None:
    with pytest.raises(ValueError, match="outside"):
        ConditionPoint(fatigue, sigma)


def test_local_neighborhood_is_bounded_deduplicated_and_sorted() -> None:
    seeds = (ConditionPoint(0.0, 0.25), ConditionPoint(0.0, 0.25))
    result = local_neighborhood(seeds, maximum_conditions=20)
    assert result == (
        ConditionPoint(0.0, 0.25),
        ConditionPoint(0.0, 0.375),
        ConditionPoint(0.015, 0.25),
        ConditionPoint(0.015, 0.375),
    )


@pytest.mark.parametrize("limit", (1, 4, 12, 18))
def test_neighborhood_obeys_deterministic_maximum(limit) -> None:
    result = local_neighborhood(
        (ConditionPoint(0.08, 1.0), ConditionPoint(0.15, 1.5)),
        maximum_conditions=limit,
    )
    assert len(result) <= limit
    assert result == tuple(sorted(set(result)))


def test_plan_round_trip_reconstructs_dynamic_conditions() -> None:
    plan = build_search_plan(AutoSearchConfig.create(search_preset="standard"))
    updated = plan.with_phase_conditions(
        "refine",
        (ConditionPoint(0.035, 0.875), ConditionPoint(0.05, 1.0)),
    )
    assert type(plan).from_dict(updated.to_dict()) == updated
