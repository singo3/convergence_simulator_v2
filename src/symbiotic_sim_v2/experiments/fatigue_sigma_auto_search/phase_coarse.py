"""Deterministic Phase 1 seed-condition selection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .gates import GateResult
from .plan import ConditionPoint
from .ranking import robust_sort_key, select_specialist_candidates


def _point(summary: Mapping[str, Any]) -> ConditionPoint:
    return ConditionPoint(
        float(summary["selected_session_fatigue_target"]),
        float(summary["sigma_multiplier"]),
    )


def select_refine_seeds(
    summaries: tuple[Mapping[str, Any], ...],
    coarse_gates: Mapping[str, GateResult],
    final_gates: Mapping[str, GateResult],
    pareto_records: tuple[Mapping[str, Any], ...],
    *,
    maximum_seeds: int = 4,
) -> tuple[ConditionPoint, ...]:
    if maximum_seeds <= 0:
        raise ValueError("maximum_seeds must be positive")
    by_id = {str(item["candidate_id"]): item for item in summaries}
    priority: list[Mapping[str, Any]] = []
    priority.extend(
        sorted(
            (item for item in summaries if coarse_gates[str(item["candidate_id"])].passed),
            key=robust_sort_key,
        )
    )
    priority.extend(
        by_id[str(record["candidate_id"])]
        for record in pareto_records
        if record["pareto_rank"] == 1
    )
    priority.extend(
        sorted(
            (item for item in summaries if final_gates[str(item["candidate_id"])].passed),
            key=robust_sort_key,
        )
    )
    specialists = select_specialist_candidates(summaries, final_gates)
    priority.extend(
        by_id[str(value["candidate_id"])] for value in specialists.values() if value is not None
    )
    if not priority:
        priority.extend(sorted(summaries, key=robust_sort_key))
    selected: list[ConditionPoint] = []
    for summary in priority:
        point = _point(summary)
        if point not in selected:
            selected.append(point)
        if len(selected) == maximum_seeds:
            break
    return tuple(selected)


__all__ = ["select_refine_seeds"]
