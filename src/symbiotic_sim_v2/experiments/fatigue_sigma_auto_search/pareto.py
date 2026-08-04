"""Deterministic multi-objective Pareto frontier without a composite score."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .config import PARETO_EVALUATOR_VERSION
from .gates import GateResult

MAXIMIZE_OBJECTIVES = (
    "worst_nonflat_correct_structure_lower95",
    "mean_nonflat_correct_structure_lower95",
    "return_within_2_rate",
)
MINIMIZE_OBJECTIVES = (
    "flat_spurious_structure_upper95",
    "flat_rotation_upper95",
    "W_ceiling_blocked_upper95",
    "mean_nonflat_diffuse_rate",
    "median_first_structure_session",
    "post_convergence_outlier_rate",
)


def objective_vector(summary: Mapping[str, Any]) -> dict[str, float | None]:
    return {
        name: None if summary.get(name) is None else float(summary[name])
        for name in (*MAXIMIZE_OBJECTIVES, *MINIMIZE_OBJECTIVES)
    }


def _value(summary: Mapping[str, Any], field: str, *, maximize: bool) -> float:
    value = summary.get(field)
    if value is None:
        return -math.inf if maximize else math.inf
    return float(value)


def dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    comparisons: list[tuple[float, float, bool]] = []
    for field in MAXIMIZE_OBJECTIVES:
        comparisons.append(
            (
                _value(left, field, maximize=True),
                _value(right, field, maximize=True),
                True,
            )
        )
    for field in MINIMIZE_OBJECTIVES:
        comparisons.append(
            (
                _value(left, field, maximize=False),
                _value(right, field, maximize=False),
                False,
            )
        )
    at_least_as_good = all(
        left_value >= right_value if maximize else left_value <= right_value
        for left_value, right_value, maximize in comparisons
    )
    strictly_better = any(
        left_value > right_value if maximize else left_value < right_value
        for left_value, right_value, maximize in comparisons
    )
    return at_least_as_good and strictly_better


def evaluate_pareto_frontier(
    summaries: tuple[Mapping[str, Any], ...],
    gates: Mapping[str, GateResult],
) -> tuple[dict[str, Any], ...]:
    ordered = tuple(sorted(summaries, key=lambda item: str(item["candidate_id"])))
    remaining = {str(item["candidate_id"]): item for item in ordered}
    rank_by_id: dict[str, int] = {}
    rank = 1
    while remaining:
        frontier = [
            candidate_id
            for candidate_id, candidate in remaining.items()
            if not any(
                other_id != candidate_id and dominates(other, candidate)
                for other_id, other in remaining.items()
            )
        ]
        for candidate_id in sorted(frontier):
            rank_by_id[candidate_id] = rank
            remaining.pop(candidate_id)
        rank += 1
    records = []
    for summary in ordered:
        candidate_id = str(summary["candidate_id"])
        dominated_by = sorted(
            str(other["candidate_id"])
            for other in ordered
            if other is not summary and dominates(other, summary)
        )
        dominates_ids = sorted(
            str(other["candidate_id"])
            for other in ordered
            if other is not summary and dominates(summary, other)
        )
        gate = gates[candidate_id]
        records.append(
            {
                "candidate_id": candidate_id,
                "condition_key": summary["condition_key"],
                "pareto_rank": rank_by_id[candidate_id],
                "dominated_by": dominated_by,
                "dominates": dominates_ids,
                "objective_vector": objective_vector(summary),
                "gate_pass": gate.passed,
                "blockers": list(gate.blockers),
                "floating_point_policy": "exact_finite_binary64_no_epsilon",
                "evaluator_version": PARETO_EVALUATOR_VERSION,
            }
        )
    return tuple(records)


__all__ = [
    "MAXIMIZE_OBJECTIVES",
    "MINIMIZE_OBJECTIVES",
    "dominates",
    "evaluate_pareto_frontier",
    "objective_vector",
]
