"""Multi-objective Pareto direction, missing-value, and ordering tests."""

from __future__ import annotations

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.gates import GateResult
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.pareto import (
    dominates,
    evaluate_pareto_frontier,
)


def _candidate(name: str, *, good: float, bad: float) -> dict[str, object]:
    return {
        "candidate_id": name,
        "condition_key": name,
        "worst_nonflat_correct_structure_lower95": good,
        "mean_nonflat_correct_structure_lower95": good,
        "return_within_2_rate": good,
        "flat_spurious_structure_upper95": bad,
        "flat_rotation_upper95": bad,
        "W_ceiling_blocked_upper95": bad,
        "mean_nonflat_diffuse_rate": bad,
        "median_first_structure_session": bad * 10,
        "post_convergence_outlier_rate": bad,
    }


def _gates(*summaries):
    return {
        item["candidate_id"]: GateResult(
            candidate_id=item["candidate_id"],
            passed=True,
            blockers=(),
            gate_kind="balanced_robust",
            gate_version="test",
        )
        for item in summaries
    }


def test_one_candidate_is_frontier_rank_one() -> None:
    candidate = _candidate("a", good=0.5, bad=0.2)
    records = evaluate_pareto_frontier((candidate,), _gates(candidate))
    assert records[0]["pareto_rank"] == 1
    assert records[0]["dominated_by"] == []
    assert records[0]["dominates"] == []


def test_candidate_dominates_when_all_objectives_are_at_least_as_good() -> None:
    better = _candidate("better", good=0.8, bad=0.1)
    worse = _candidate("worse", good=0.4, bad=0.4)
    assert dominates(better, worse)
    assert not dominates(worse, better)
    records = evaluate_pareto_frontier((worse, better), _gates(worse, better))
    by_id = {item["candidate_id"]: item for item in records}
    assert by_id["better"]["pareto_rank"] == 1
    assert by_id["worse"]["pareto_rank"] == 2
    assert by_id["worse"]["dominated_by"] == ["better"]


def test_mixed_tradeoff_is_non_dominated() -> None:
    high_effect = _candidate("effect", good=0.8, bad=0.3)
    high_safety = _candidate("safety", good=0.5, bad=0.1)
    records = evaluate_pareto_frontier((high_effect, high_safety), _gates(high_effect, high_safety))
    assert {item["pareto_rank"] for item in records} == {1}


def test_duplicate_objective_vectors_do_not_dominate_each_other() -> None:
    first = _candidate("a", good=0.5, bad=0.2)
    second = _candidate("b", good=0.5, bad=0.2)
    assert not dominates(first, second)
    records = evaluate_pareto_frontier((second, first), _gates(second, first))
    assert tuple(item["candidate_id"] for item in records) == ("a", "b")
    assert all(item["pareto_rank"] == 1 for item in records)


def test_missing_objective_is_disadvantaged_not_favorable() -> None:
    complete = _candidate("complete", good=0.5, bad=0.2)
    missing = _candidate("missing", good=0.5, bad=0.2)
    missing["return_within_2_rate"] = None
    assert dominates(complete, missing)


def test_missing_on_both_sides_can_still_leave_a_tradeoff() -> None:
    first = _candidate("a", good=0.8, bad=0.3)
    second = _candidate("b", good=0.5, bad=0.1)
    first["return_within_2_rate"] = None
    second["return_within_2_rate"] = None
    assert not dominates(first, second)
    assert not dominates(second, first)


def test_gate_status_and_blockers_are_carried_to_pareto_record() -> None:
    candidate = _candidate("a", good=0.5, bad=0.2)
    gates = {"a": GateResult("a", False, ("flat:0.3>0.25",), "balanced", "v")}
    record = evaluate_pareto_frontier((candidate,), gates)[0]
    assert record["gate_pass"] is False
    assert record["blockers"] == ["flat:0.3>0.25"]
    assert record["floating_point_policy"] == "exact_finite_binary64_no_epsilon"


def test_three_fronts_are_ranked_deterministically() -> None:
    candidates = tuple(
        _candidate(name, good=good, bad=bad)
        for name, good, bad in (
            ("c", 0.2, 0.6),
            ("a", 0.8, 0.1),
            ("b", 0.5, 0.3),
        )
    )
    records = evaluate_pareto_frontier(candidates, _gates(*candidates))
    assert [(item["candidate_id"], item["pareto_rank"]) for item in records] == [
        ("a", 1),
        ("b", 2),
        ("c", 3),
    ]
