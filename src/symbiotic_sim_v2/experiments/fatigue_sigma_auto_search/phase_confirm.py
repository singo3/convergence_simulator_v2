"""Deterministic Phase 2 to Phase 3 candidate selection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .gates import GateResult
from .plan import ConditionPoint
from .ranking import robust_sort_key, select_specialist_candidates


def select_confirmation_conditions(
    summaries: tuple[Mapping[str, Any], ...],
    gates: Mapping[str, GateResult],
    pareto_records: tuple[Mapping[str, Any], ...],
    *,
    maximum_conditions: int,
) -> tuple[ConditionPoint, ...]:
    if maximum_conditions not in {3, 5}:
        raise ValueError("Phase 3 maximum must be three or five")
    by_id = {str(item["candidate_id"]): item for item in summaries}
    priority = list(
        sorted(
            (item for item in summaries if gates[str(item["candidate_id"])].passed),
            key=robust_sort_key,
        )
    )
    priority.extend(
        by_id[str(item["candidate_id"])] for item in pareto_records if item["pareto_rank"] == 1
    )
    specialists = select_specialist_candidates(summaries, gates)
    priority.extend(
        by_id[str(value["candidate_id"])] for value in specialists.values() if value is not None
    )
    priority.extend(sorted(summaries, key=robust_sort_key))
    selected: list[ConditionPoint] = []
    for summary in priority:
        point = ConditionPoint(
            float(summary["selected_session_fatigue_target"]),
            float(summary["sigma_multiplier"]),
        )
        if point not in selected:
            selected.append(point)
        if len(selected) == maximum_conditions:
            break
    return tuple(selected)


__all__ = ["select_confirmation_conditions"]
