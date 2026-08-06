"""Transparent simulation-only comparison for a future human MVP condition."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.analysis import (
    bootstrap_interval,
)

from .conditions import CONDITION_IDS, V2_REFERENCE_CONDITION
from .config import CONDITION_RECOMMENDATION_VERSION

RECOMMENDATION_VOCABULARY = (
    "preferred_for_human_mvp",
    "viable_tradeoff",
    "type_specific_risk",
    "no_advantage_over_reference",
    "insufficient_or_ambiguous",
)
EXPECTED_NONFLAT_USER_TYPE_COUNT = 8
EXPECTED_STANDARD_NONFLAT_PARTICIPANT_COUNT = 80
FLAT_ABSOLUTE_ARM_DIFFERENCE_MAX_MS = 0.25
WORST_TYPE_ALLOWED_DEGRADATION_MS = 0.25
VARIABILITY_ALLOWED_INCREASE_MS = 0.25
COUPLING_ALLOWED_DEGRADATION = 0.05


def condition_summary_rows(
    participant_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    by_condition: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in participant_rows:
        by_condition[str(row["condition_id"])].append(row)
    result: list[dict[str, Any]] = []
    for condition_id in CONDITION_IDS:
        rows = by_condition.get(condition_id, [])
        nonflat = [item for item in rows if item["user_type_id"] != "flat_control"]
        flat = [item for item in rows if item["user_type_id"] == "flat_control"]
        type_values: dict[str, list[float]] = defaultdict(list)
        for row in nonflat:
            value = row.get("late_delta_rmssd_advantage_ms")
            if value is not None:
                type_values[str(row["user_type_id"])].append(float(value))
        type_means = {
            user_type_id: statistics.fmean(values)
            for user_type_id, values in sorted(type_values.items())
            if values
        }
        effects = [
            float(row["late_delta_rmssd_advantage_ms"])
            for row in nonflat
            if row.get("late_delta_rmssd_advantage_ms") is not None
        ]
        flat_effects = [
            float(row["late_delta_rmssd_advantage_ms"])
            for row in flat
            if row.get("late_delta_rmssd_advantage_ms") is not None
        ]
        lower, upper = bootstrap_interval(
            effects,
            seed_parts=(condition_id, CONDITION_RECOMMENDATION_VERSION),
        )
        positive_count = sum(value > 0.0 for value in effects)
        full_coverage = len(type_means) == EXPECTED_NONFLAT_USER_TYPE_COUNT
        type_failures = tuple(
            user_type_id for user_type_id, value in type_means.items() if value <= 0.0
        )
        result.append(
            {
                "condition_id": condition_id,
                "full_nonflat_type_coverage": full_coverage,
                "represented_nonflat_user_type_count": len(type_means),
                "all_nonflat_type_means_positive": (full_coverage and not type_failures),
                "type_specific_failures": type_failures,
                "worst_user_type_effect_ms": (None if not type_means else min(type_means.values())),
                "worst_user_type_id": (
                    None
                    if not type_means
                    else min(type_means, key=lambda item: (type_means[item], item))
                ),
                "nonflat_positive_participant_count": positive_count,
                "nonflat_participant_count": len(effects),
                "standard_nonflat_participant_denominator": (
                    EXPECTED_STANDARD_NONFLAT_PARTICIPANT_COUNT
                ),
                "nonflat_positive_rate": (None if not effects else positive_count / len(effects)),
                "nonflat_mean_effect_ms": (None if not effects else statistics.fmean(effects)),
                "nonflat_effect_lower95_ms": lower,
                "nonflat_effect_upper95_ms": upper,
                "participant_effect_standard_deviation_ms": (
                    None if len(effects) < 2 else statistics.stdev(effects)
                ),
                "flat_control_arm_difference_ms": (
                    None if not flat_effects else statistics.fmean(flat_effects)
                ),
                "selection_enrichment_advantage": _mean_field(
                    nonflat,
                    "full_pattern_selection_enrichment_advantage",
                ),
                "lagged_coupling_advantage": _mean_field(
                    nonflat,
                    "lagged_pattern_advantage",
                ),
                "holder_switch_rate": _mean_field(
                    rows,
                    "autonomous_holder_switch_rate",
                ),
                "w_ceiling_blocked_rate": _mean_field(
                    rows,
                    "w_ceiling_blocked_rate",
                ),
                "invalid_session_rate": _mean_field(
                    rows,
                    "autonomous_invalid_session_rate",
                ),
                "reject_rate": _mean_field(
                    rows,
                    "autonomous_reject_rate",
                ),
                "formal_spec_adoption": False,
                "recommendation_version": CONDITION_RECOMMENDATION_VERSION,
            }
        )
    return tuple(result)


def _mean_field(rows: Sequence[Mapping[str, Any]], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return None if not values else statistics.fmean(values)


def _not_materially_lower(
    candidate: object,
    reference: object,
    margin: float,
) -> bool:
    return (
        candidate is not None
        and reference is not None
        and float(candidate) >= float(reference) - margin
    )


def recommend_condition(
    summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_id = {str(row["condition_id"]): row for row in summaries}
    if set(by_id) != set(CONDITION_IDS):
        raise ValueError("recommendation requires summaries for all four conditions")
    reference = by_id[V2_REFERENCE_CONDITION]
    condition_decisions: list[dict[str, Any]] = []
    passing: list[Mapping[str, Any]] = []
    for condition_id in CONDITION_IDS:
        row = by_id[condition_id]
        gates = {
            "all_eight_nonflat_type_means_positive": bool(row["all_nonflat_type_means_positive"]),
            "flat_absolute_arm_difference_le_0_25_ms": (
                row.get("flat_control_arm_difference_ms") is not None
                and abs(float(row["flat_control_arm_difference_ms"]))
                <= FLAT_ABSOLUTE_ARM_DIFFERENCE_MAX_MS
            ),
            "positive_participant_count_ge_reference": (
                int(row["nonflat_positive_participant_count"])
                >= int(reference["nonflat_positive_participant_count"])
            ),
            "nonflat_mean_effect_ge_reference": (
                row.get("nonflat_mean_effect_ms") is not None
                and reference.get("nonflat_mean_effect_ms") is not None
                and float(row["nonflat_mean_effect_ms"])
                >= float(reference["nonflat_mean_effect_ms"])
            ),
            "worst_type_not_materially_below_reference": _not_materially_lower(
                row.get("worst_user_type_effect_ms"),
                reference.get("worst_user_type_effect_ms"),
                WORST_TYPE_ALLOWED_DEGRADATION_MS,
            ),
            "participant_variability_not_materially_worse": (
                row.get("participant_effect_standard_deviation_ms") is not None
                and reference.get("participant_effect_standard_deviation_ms") is not None
                and float(row["participant_effect_standard_deviation_ms"])
                <= float(reference["participant_effect_standard_deviation_ms"])
                + VARIABILITY_ALLOWED_INCREASE_MS
            ),
            "enrichment_or_lag_not_materially_lower": (
                _not_materially_lower(
                    row.get("selection_enrichment_advantage"),
                    reference.get("selection_enrichment_advantage"),
                    COUPLING_ALLOWED_DEGRADATION,
                )
                or _not_materially_lower(
                    row.get("lagged_coupling_advantage"),
                    reference.get("lagged_coupling_advantage"),
                    COUPLING_ALLOWED_DEGRADATION,
                )
            ),
        }
        all_gates = all(gates.values())
        if condition_id != V2_REFERENCE_CONDITION and all_gates:
            passing.append(row)
        if condition_id == V2_REFERENCE_CONDITION:
            vocabulary = "preferred_for_human_mvp"
        elif not row.get("full_nonflat_type_coverage"):
            vocabulary = "insufficient_or_ambiguous"
        elif row.get("type_specific_failures"):
            vocabulary = "type_specific_risk"
        elif (
            row.get("nonflat_mean_effect_ms") is not None
            and reference.get("nonflat_mean_effect_ms") is not None
            and float(row["nonflat_mean_effect_ms"]) <= float(reference["nonflat_mean_effect_ms"])
            and int(row["nonflat_positive_participant_count"])
            <= int(reference["nonflat_positive_participant_count"])
        ):
            vocabulary = "no_advantage_over_reference"
        else:
            vocabulary = "viable_tradeoff"
        condition_decisions.append(
            {
                "condition_id": condition_id,
                "recommendation": vocabulary,
                "passes_all_preference_gates": all_gates,
                "gates": gates,
                "failed_gates": tuple(name for name, value in gates.items() if not value),
            }
        )
    if passing:
        selected = sorted(
            passing,
            key=lambda item: (
                -float(item["nonflat_mean_effect_ms"]),
                -int(item["nonflat_positive_participant_count"]),
                str(item["condition_id"]),
            ),
        )[0]
        selected_id = str(selected["condition_id"])
        overall_decision = "alternative_preferred_for_human_mvp"
        for item in condition_decisions:
            if item["condition_id"] == selected_id:
                item["recommendation"] = "preferred_for_human_mvp"
            elif item["condition_id"] == V2_REFERENCE_CONDITION:
                item["recommendation"] = "viable_tradeoff"
    else:
        selected_id = V2_REFERENCE_CONDITION
        overall_decision = "v2_reference_remains_preferred"
    return {
        "overall_decision": overall_decision,
        "preferred_condition_id": selected_id,
        "clear_winner": bool(passing),
        "condition_decisions": condition_decisions,
        "baseline_condition_id": V2_REFERENCE_CONDITION,
        "opaque_composite_score_used": False,
        "automatic_formal_adoption": False,
        "formal_spec_adoption": False,
        "simulation_only": True,
        "version": CONDITION_RECOMMENDATION_VERSION,
    }


__all__ = [
    "EXPECTED_NONFLAT_USER_TYPE_COUNT",
    "EXPECTED_STANDARD_NONFLAT_PARTICIPANT_COUNT",
    "FLAT_ABSOLUTE_ARM_DIFFERENCE_MAX_MS",
    "RECOMMENDATION_VOCABULARY",
    "condition_summary_rows",
    "recommend_condition",
]
