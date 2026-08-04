"""Cross-user aggregation of detached Stage 8A.1 replicate projections."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .config import CONDITION_SUMMARY_SCHEMA_VERSION, NONFLAT_USER_TYPE_IDS
from .plan import ConditionPoint
from .uncertainty import continuous_summary, wilson_interval


def _mean(values: Sequence[float | None]) -> float | None:
    selected = [value for value in values if value is not None]
    return None if not selected else statistics.fmean(selected)


def _first_structure_session(item: Mapping[str, Any]) -> float | None:
    values = [
        item.get("first_life_convergence_session"),
        item.get("first_bpm_convergence_session"),
        item.get("first_multi_attractor_session"),
    ]
    selected = [float(value) for value in values if value is not None]
    return None if not selected else min(selected)


def _user_breakdown(
    user_type_id: str,
    replicates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    completed = [item for item in replicates if item.get("completed")]
    total = len(replicates)
    denominator = len(completed)

    def interval_for(predicate) -> dict[str, Any]:
        return wilson_interval(sum(predicate(item) for item in completed), denominator)

    correct = interval_for(lambda item: item.get("truth_classification") == "correct_structure")
    diffuse = interval_for(
        lambda item: item.get("summary_classification") == "diffuse_or_unresolved"
    )
    spurious = interval_for(
        lambda item: item.get("truth_classification") == "spurious_structure_in_flat_control"
    )
    rotation = interval_for(
        lambda item: (
            item.get("mechanical_rotation", {}).get("classification")
            in {
                "mechanical_rotation_warning",
                "spurious_fatigue_driven_structure_warning",
            }
        )
    )
    life = interval_for(lambda item: bool(item.get("life_dominant_converged")))
    bpm = interval_for(lambda item: bool(item.get("bpm_common_converged")))
    multi = interval_for(lambda item: bool(item.get("multi_attractor_converged")))
    first_sessions = continuous_summary(_first_structure_session(item) for item in completed)
    return {
        "user_type_id": user_type_id,
        "replicate_count": total,
        "completed_replicate_count": denominator,
        "failed_replicate_count": sum(bool(item.get("failed")) for item in replicates),
        "correct_structure": correct,
        "diffuse": diffuse,
        "flat_spurious_structure": spurious,
        "mechanical_rotation_warning": rotation,
        "life_dominance": life,
        "bpm_common": bpm,
        "multi_attractor": multi,
        "first_structure_session": first_sessions,
        "return_within_2": continuous_summary(
            item.get("return_within_2_rate") for item in completed
        ),
        "post_convergence_outlier": continuous_summary(
            item.get("post_convergence_outlier_rate") for item in completed
        ),
        "holder_switch": continuous_summary(
            item.get("mechanical_rotation", {}).get("holder_switch_rate") for item in completed
        ),
        "bpm_cluster_width": continuous_summary(
            item.get("bpm_cluster_width") for item in completed
        ),
        "accepted_candidate_count": continuous_summary(
            item.get("accepted_count") for item in completed
        ),
    }


def aggregate_cross_user_condition(
    *,
    phase: str,
    point: ConditionPoint,
    maximum_sessions: int,
    replicates: Sequence[Mapping[str, Any]],
    expected_user_type_ids: tuple[str, ...],
) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in replicates:
        grouped[str(item["user_type_id"])].append(item)
    breakdown = {
        user_type_id: _user_breakdown(user_type_id, grouped[user_type_id])
        for user_type_id in expected_user_type_ids
    }
    all_replicates = [item for values in grouped.values() for item in values]
    completed = [item for item in all_replicates if item.get("completed")]
    expected_sessions = sum(int(item.get("sessions_expected", 0)) for item in all_replicates)
    completed_sessions = sum(int(item.get("sessions_completed", 0)) for item in all_replicates)
    nonflat = [
        breakdown[user_type] for user_type in NONFLAT_USER_TYPE_IDS if user_type in breakdown
    ]
    correct_rates = [item["correct_structure"]["rate"] for item in nonflat]
    correct_lowers = [item["correct_structure"]["lower95"] for item in nonflat]
    diffuse_rates = [item["diffuse"]["rate"] for item in nonflat]
    flat = breakdown.get("flat_control")
    w_blocked = wilson_interval(
        sum(
            item.get("w_ceiling", {}).get("classification") == "exploration_blocked_by_W_ceiling"
            for item in completed
        ),
        len(completed),
    )
    convergence = wilson_interval(
        sum(
            bool(item.get("life_dominant_converged"))
            or bool(item.get("bpm_common_converged"))
            or bool(item.get("multi_attractor_converged"))
            for item in completed
        ),
        len(completed),
    )
    first_values = [_first_structure_session(item) for item in completed]
    first_summary = continuous_summary(first_values)
    return_within_2 = continuous_summary(item.get("return_within_2_rate") for item in completed)
    post_outlier = continuous_summary(
        item.get("post_convergence_outlier_rate") for item in completed
    )
    accepted = sum(int(item.get("accepted_count", 0)) for item in completed)
    provisional = sum(
        int(item.get("w_ceiling", {}).get("provisional_success_count", 0)) for item in completed
    )
    summary = {
        "candidate_id": f"{phase}__{point.condition_key}",
        "condition_key": point.condition_key,
        "phase": phase,
        "selected_session_fatigue_target": (point.selected_session_fatigue_target),
        "sigma_multiplier": point.sigma_multiplier,
        "maximum_sessions": maximum_sessions,
        "expected_user_type_ids": list(expected_user_type_ids),
        "replicate_count": len(all_replicates),
        "completed_replicate_count": len(completed),
        "failed_replicate_count": sum(bool(item.get("failed")) for item in all_replicates),
        "failed_replicate_rate": (
            0.0
            if not all_replicates
            else sum(bool(item.get("failed")) for item in all_replicates) / len(all_replicates)
        ),
        "valid_session_rate": (
            0.0 if expected_sessions == 0 else completed_sessions / expected_sessions
        ),
        "worst_nonflat_correct_structure_rate": (
            None
            if not correct_rates or any(value is None for value in correct_rates)
            else min(correct_rates)
        ),
        "worst_nonflat_correct_structure_lower95": (
            None
            if not correct_lowers or any(value is None for value in correct_lowers)
            else min(correct_lowers)
        ),
        "mean_nonflat_correct_structure_rate": _mean(correct_rates),
        "mean_nonflat_correct_structure_lower95": _mean(correct_lowers),
        "mean_nonflat_diffuse_rate": _mean(diffuse_rates),
        "median_first_structure_session": first_summary["median"],
        "return_within_2_rate": return_within_2["mean"],
        "post_convergence_outlier_rate": post_outlier["mean"],
        "flat_spurious_structure_rate": (
            None if flat is None else flat["flat_spurious_structure"]["rate"]
        ),
        "flat_spurious_structure_upper95": (
            None if flat is None else flat["flat_spurious_structure"]["upper95"]
        ),
        "flat_mechanical_rotation_warning_rate": (
            None if flat is None else flat["mechanical_rotation_warning"]["rate"]
        ),
        "flat_rotation_upper95": (
            None if flat is None else flat["mechanical_rotation_warning"]["upper95"]
        ),
        "flat_holder_switch_rate": (None if flat is None else flat["holder_switch"]["mean"]),
        "W_ceiling_blocked_rate": w_blocked["rate"],
        "W_ceiling_blocked_upper95": w_blocked["upper95"],
        "accepted_candidate_count": accepted,
        "provisional_success_count": provisional,
        "convergence_rate": convergence["rate"],
        "life_dominance_specialist_rate": breakdown.get("green_hue_dominant_broad_bpm", {})
        .get("life_dominance", {})
        .get("lower95"),
        "bpm_common_specialist_rate": breakdown.get("bpm_common_100_hue_neutral", {})
        .get("bpm_common", {})
        .get("lower95"),
        "multi_attractor_specialist_rate": _mean(
            [
                breakdown.get(user_type, {}).get("multi_attractor", {}).get("lower95")
                for user_type in (
                    "three_life_bpm_equal",
                    "three_life_bpm_green_dominant",
                )
            ]
        ),
        "uncertainty": {
            "W_ceiling_blocked": w_blocked,
            "convergence": convergence,
            "first_structure_session": first_summary,
            "return_within_2": return_within_2,
            "post_convergence_outlier": post_outlier,
            "small_sample_warning": len(completed) < 10,
        },
        "user_type_breakdown": breakdown,
        "schema_version": CONDITION_SUMMARY_SCHEMA_VERSION,
    }
    return summary


def group_replicates_into_summaries(
    *,
    phase: str,
    maximum_sessions: int,
    replicate_payloads: Sequence[Mapping[str, Any]],
    expected_user_type_ids: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[tuple[float, float], list[Mapping[str, Any]]] = defaultdict(list)
    for item in replicate_payloads:
        key = (
            float(item["selected_session_fatigue_target"]),
            float(item["sigma_multiplier"]),
        )
        grouped[key].append(item)
    return tuple(
        aggregate_cross_user_condition(
            phase=phase,
            point=ConditionPoint(*key),
            maximum_sessions=maximum_sessions,
            replicates=grouped[key],
            expected_user_type_ids=expected_user_type_ids,
        )
        for key in sorted(grouped)
    )


__all__ = [
    "aggregate_cross_user_condition",
    "group_replicates_into_summaries",
]
