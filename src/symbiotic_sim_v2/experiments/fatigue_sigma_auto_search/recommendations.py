"""Recommendation projection which permits an explicit no-candidate result."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from .config import RECOMMENDATION_SCHEMA_VERSION
from .gates import GateResult
from .ranking import rank_robust_candidates, select_specialist_candidates


def build_recommendations(
    *,
    summaries: tuple[Mapping[str, Any], ...],
    gates: Mapping[str, GateResult],
    pareto_records: tuple[Mapping[str, Any], ...],
    generated_at: str,
    code_fingerprint: Mapping[str, Any],
    search_preset: str,
    reproduction_commands: tuple[str, ...],
) -> dict[str, Any]:
    robust = rank_robust_candidates(summaries, gates)
    specialists = select_specialist_candidates(summaries, gates)
    smoke_only = search_preset == "smoke"
    blocker_counts = Counter(
        blocker.split(":", 1)[0] for result in gates.values() for blocker in result.blockers
    )
    return {
        "status": (
            "smoke_diagnostic_only"
            if smoke_only
            else "robust_candidates_found"
            if robust
            else "no_robust_candidate"
        ),
        "generated_at": generated_at,
        "code_fingerprint": dict(code_fingerprint),
        "search_preset": search_preset,
        "robust_candidate": None if smoke_only or not robust else robust[0],
        "robust_compromise": None if smoke_only or not robust else robust[0],
        "robust_candidates": [] if smoke_only else list(robust),
        "specialist_candidates": (
            {name: None for name in specialists} if smoke_only else specialists
        ),
        "pareto_candidates": [dict(item) for item in pareto_records if item["pareto_rank"] == 1],
        "no_candidate_blockers": dict(sorted(blocker_counts.items())),
        "uncertainty": {
            "interval": "95% Wilson for proportions",
            "continuous": "count/mean/median/min/max/Q1/Q3",
            "small_replicate_warning": any(
                bool(item.get("uncertainty", {}).get("small_sample_warning")) for item in summaries
            ),
            "no_statistical_significance_claim": True,
            "no_human_effectiveness_claim": True,
        },
        "formal_spec_adoption": False,
        "smoke_does_not_establish_candidate_validity": smoke_only,
        "single_opaque_score_used": False,
        "reproduction_commands": list(reproduction_commands),
        "schema_version": RECOMMENDATION_SCHEMA_VERSION,
    }


__all__ = ["build_recommendations"]
