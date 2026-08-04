"""Uncertainty-aware lexicographic robust and specialist ranking."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .config import CANDIDATE_RANKING_VERSION
from .gates import GateResult


def _maximize(value: Any) -> float:
    return math.inf if value is None else -float(value)


def _minimize(value: Any) -> float:
    return math.inf if value is None else float(value)


def robust_sort_key(summary: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _maximize(summary.get("worst_nonflat_correct_structure_lower95")),
        _maximize(summary.get("mean_nonflat_correct_structure_lower95")),
        _minimize(summary.get("flat_spurious_structure_upper95")),
        _minimize(summary.get("flat_rotation_upper95")),
        _minimize(summary.get("W_ceiling_blocked_upper95")),
        _maximize(summary.get("return_within_2_rate")),
        _minimize(summary.get("median_first_structure_session")),
        _minimize(summary.get("post_convergence_outlier_rate")),
        _minimize(summary.get("selected_session_fatigue_target")),
        abs(float(summary["sigma_multiplier"]) - 1.0),
        float(summary["selected_session_fatigue_target"]),
        float(summary["sigma_multiplier"]),
        str(summary["candidate_id"]),
    )


def rank_robust_candidates(
    summaries: tuple[Mapping[str, Any], ...],
    gates: Mapping[str, GateResult],
) -> tuple[dict[str, Any], ...]:
    passed = [item for item in summaries if gates[str(item["candidate_id"])].passed]
    return tuple(
        {
            **dict(item),
            "robust_rank": index,
            "ranking_version": CANDIDATE_RANKING_VERSION,
        }
        for index, item in enumerate(sorted(passed, key=robust_sort_key), start=1)
    )


def _specialist_key(metric: str, summary: Mapping[str, Any]) -> tuple[Any, ...]:
    return (_maximize(summary.get(metric)), *robust_sort_key(summary))


def _with_safety(summary: Mapping[str, Any], gate: GateResult) -> dict[str, Any]:
    return {
        "candidate_id": summary["candidate_id"],
        "condition_key": summary["condition_key"],
        "selected_session_fatigue_target": summary["selected_session_fatigue_target"],
        "sigma_multiplier": summary["sigma_multiplier"],
        "gate_pass": gate.passed,
        "blockers": list(gate.blockers),
        "flat_spurious_structure_upper95": summary.get("flat_spurious_structure_upper95"),
        "flat_rotation_upper95": summary.get("flat_rotation_upper95"),
        "W_ceiling_blocked_upper95": summary.get("W_ceiling_blocked_upper95"),
        "ranking_version": CANDIDATE_RANKING_VERSION,
    }


def select_specialist_candidates(
    summaries: tuple[Mapping[str, Any], ...],
    gates: Mapping[str, GateResult],
) -> dict[str, dict[str, Any] | None]:
    if not summaries:
        return {
            name: None
            for name in (
                "life_dominance_specialist",
                "bpm_common_specialist",
                "multi_attractor_specialist",
                "low_rotation_specialist",
                "conservative_compromise",
            )
        }
    ordered = tuple(sorted(summaries, key=lambda item: str(item["candidate_id"])))
    definitions = {
        "life_dominance_specialist": "life_dominance_specialist_rate",
        "bpm_common_specialist": "bpm_common_specialist_rate",
        "multi_attractor_specialist": "multi_attractor_specialist_rate",
    }
    selected: dict[str, dict[str, Any] | None] = {}
    for category, metric in definitions.items():
        candidate = min(ordered, key=lambda item: _specialist_key(metric, item))
        selected[category] = {
            **_with_safety(candidate, gates[str(candidate["candidate_id"])]),
            "specialist_metric": metric,
            "specialist_metric_value": candidate.get(metric),
        }
    rotation = min(
        ordered,
        key=lambda item: (
            _minimize(item.get("flat_rotation_upper95")),
            *robust_sort_key(item),
        ),
    )
    selected["low_rotation_specialist"] = _with_safety(
        rotation,
        gates[str(rotation["candidate_id"])],
    )
    conservative = min(
        ordered,
        key=lambda item: (
            float(item["selected_session_fatigue_target"]),
            abs(float(item["sigma_multiplier"]) - 1.0),
            *robust_sort_key(item),
        ),
    )
    selected["conservative_compromise"] = _with_safety(
        conservative,
        gates[str(conservative["candidate_id"])],
    )
    return selected


__all__ = [
    "rank_robust_candidates",
    "robust_sort_key",
    "select_specialist_candidates",
]
