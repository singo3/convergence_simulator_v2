"""Stage 8A.3 analyses reused for autonomous-versus-shared-random effects."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.analysis import (
    contemporaneous_response_row,
    lagged_coupling_row,
    paired_arm_difference_rows,
    prediction_metrics_row,
    prospective_rows,
    rmssd_benefit_row,
    user_type_trajectory_rows,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
)

from .config import AUTONOMOUS_ARM, FACTORIAL_ANALYSIS_VERSION, SHARED_RANDOM_ARM
from .factorial_effects import (
    factorial_overall_effect_rows,
    factorial_participant_effect_rows,
    factorial_user_type_effect_rows,
)


def _mean(values: Sequence[object]) -> float | None:
    finite = [float(value) for value in values if value is not None]
    return None if not finite else statistics.fmean(finite)


def _difference(left: object, right: object) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def _holder_switch_rate(sessions: Sequence[SessionOutcome]) -> float | None:
    ordered = [
        item
        for item in sorted(sessions, key=lambda item: item.session_index)
        if item.representative_life_id is not None
    ]
    if len(ordered) < 2:
        return None
    return sum(
        left.representative_life_id != right.representative_life_id
        for left, right in zip(ordered, ordered[1:], strict=False)
    ) / (len(ordered) - 1)


def _life_shares(sessions: Sequence[SessionOutcome]) -> dict[str, float]:
    values = [item.representative_life_id for item in sessions if item.representative_life_id]
    counts = Counter(values)
    denominator = max(1, len(values))
    return {
        "life_red_share": counts["life-red"] / denominator,
        "life_green_share": counts["life-green"] / denominator,
        "life_blue_share": counts["life-blue"] / denominator,
    }


def _reject_rate(bundles: Sequence[BundleOutcome]) -> float:
    if not bundles:
        return 0.0
    return sum(not item.valid_for_analysis for item in bundles) / len(bundles)


def participant_condition_effect_rows(
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    *,
    session_audits: Sequence[Mapping[str, Any]],
    hue_bandwidth_degree: float = 5.0,
    bpm_bandwidth: float = 15.0,
    minimum_history_count: int = 3,
) -> tuple[dict[str, Any], ...]:
    session_groups: dict[tuple[str, str, str], list[SessionOutcome]] = defaultdict(list)
    bundle_groups: dict[tuple[str, str, str], list[BundleOutcome]] = defaultdict(list)
    for row in sessions:
        session_groups[(row.participant_id, row.condition_id, row.arm)].append(row)
    for row in bundles:
        bundle_groups[(row.participant_id, row.condition_id, row.arm)].append(row)
    benefits: list[dict[str, Any]] = []
    lagged_rows: list[dict[str, Any]] = []
    prospective_by_key: dict[tuple[str, str, str], tuple[dict[str, Any], ...]] = {}
    for key, grouped_sessions in sorted(session_groups.items()):
        benefits.append(rmssd_benefit_row(grouped_sessions))
        prospective = prospective_rows(
            bundle_groups.get(key, ()),
            grouped_sessions,
            hue_bandwidth_degree=hue_bandwidth_degree,
            bpm_bandwidth=bpm_bandwidth,
            minimum_history_count=minimum_history_count,
        )
        prospective_by_key[key] = prospective
        lagged_rows.append(lagged_coupling_row(grouped_sessions, prospective))
    paired = paired_arm_difference_rows(benefits, lagged_rows, sessions)
    paired_by_key = {
        (str(row["participant_id"]), str(row["condition_id"])): row
        for row in paired
        if row["comparator_arm"] == SHARED_RANDOM_ARM
    }
    audit_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in session_audits:
        audit_groups[(str(row["participant_id"]), str(row["condition_id"]))].append(row)
    result: list[dict[str, Any]] = []
    participant_conditions = sorted(
        {
            (participant_id, condition_id)
            for participant_id, condition_id, arm in session_groups
            if arm == AUTONOMOUS_ARM
        }
    )
    for participant_id, condition_id in participant_conditions:
        auto_key = (participant_id, condition_id, AUTONOMOUS_ARM)
        random_key = (participant_id, condition_id, SHARED_RANDOM_ARM)
        auto_sessions = session_groups[auto_key]
        random_sessions = session_groups[random_key]
        auto_bundles = bundle_groups.get(auto_key, ())
        random_bundles = bundle_groups.get(random_key, ())
        auto_prospective = prospective_by_key[auto_key]
        random_prospective = prospective_by_key[random_key]
        paired_row = paired_by_key[(participant_id, condition_id)]
        auto_lagged = next(
            row
            for row in lagged_rows
            if (
                row["participant_id"],
                row["condition_id"],
                row["arm"],
            )
            == auto_key
        )
        random_lagged = next(
            row
            for row in lagged_rows
            if (
                row["participant_id"],
                row["condition_id"],
                row["arm"],
            )
            == random_key
        )
        audits = audit_groups[(participant_id, condition_id)]
        final = max(auto_sessions, key=lambda item: item.session_index)
        user_type_id = auto_sessions[0].user_type_id
        auto_switch = _holder_switch_rate(auto_sessions)
        random_switch = _holder_switch_rate(random_sessions)
        result.append(
            {
                "participant_id": participant_id,
                "user_type_id": user_type_id,
                "condition_id": condition_id,
                "late_delta_rmssd_advantage_ms": paired_row.get("late_delta_rmssd_advantage_ms"),
                "late_minus_early_advantage_ms": paired_row.get("learning_gain_advantage_ms"),
                "slope_advantage": paired_row.get("slope_advantage"),
                "life_selection_enrichment_advantage": _difference(
                    _mean([item.get("life_selection_enrichment") for item in auto_prospective]),
                    _mean([item.get("life_selection_enrichment") for item in random_prospective]),
                ),
                "bpm_selection_enrichment_advantage": _difference(
                    _mean([item.get("bpm_selection_enrichment") for item in auto_prospective]),
                    _mean([item.get("bpm_selection_enrichment") for item in random_prospective]),
                ),
                "full_pattern_selection_enrichment_advantage": _difference(
                    _mean(
                        [item.get("full_pattern_selection_enrichment") for item in auto_prospective]
                    ),
                    _mean(
                        [
                            item.get("full_pattern_selection_enrichment")
                            for item in random_prospective
                        ]
                    ),
                ),
                "lagged_same_life_advantage": _difference(
                    auto_lagged.get("lag1_response_vs_same_life"),
                    random_lagged.get("lag1_response_vs_same_life"),
                ),
                "lagged_pattern_advantage": _difference(
                    auto_lagged.get("lag1_response_vs_pattern_closeness"),
                    random_lagged.get("lag1_response_vs_pattern_closeness"),
                ),
                "candidate_count": sum(bool(item.get("candidate_generated")) for item in audits),
                "accepted_candidate_count": sum(
                    bool(item.get("candidate_accepted")) for item in audits
                ),
                "provisional_success_count": sum(
                    bool(item.get("provisional_success")) for item in audits
                ),
                "w_ceiling_blocked_rate": (
                    0.0
                    if not audits
                    else sum(bool(item.get("w_ceiling_blocked")) for item in audits) / len(audits)
                ),
                "autonomous_holder_switch_rate": auto_switch,
                "random_holder_switch_rate": random_switch,
                "holder_switch_rate_advantage": _difference(auto_switch, random_switch),
                **_life_shares(auto_sessions),
                "final_hue_degree": final.representative_hue_degree,
                "final_blink_bpm": final.representative_blink_bpm,
                "autonomous_invalid_session_rate": sum(
                    not item.session_valid for item in auto_sessions
                )
                / len(auto_sessions),
                "random_invalid_session_rate": sum(
                    not item.session_valid for item in random_sessions
                )
                / len(random_sessions),
                "autonomous_reject_rate": _reject_rate(auto_bundles),
                "random_reject_rate": _reject_rate(random_bundles),
                "paired_valid_session_count": paired_row.get("paired_valid_session_count"),
                "analysis_unit": "participant",
                "bundle_rows_pooled_as_participants": False,
                "analysis_version": FACTORIAL_ANALYSIS_VERSION,
            }
        )
    return tuple(result)


def analyze_factorial_records(
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    *,
    session_audits: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[dict[str, Any], ...]]:
    groups: dict[tuple[str, str, str], list[SessionOutcome]] = defaultdict(list)
    bundle_groups: dict[tuple[str, str, str], list[BundleOutcome]] = defaultdict(list)
    for row in sessions:
        groups[(row.participant_id, row.condition_id, row.arm)].append(row)
    for row in bundles:
        bundle_groups[(row.participant_id, row.condition_id, row.arm)].append(row)
    contemporaneous: list[dict[str, Any]] = []
    prospective_all: list[dict[str, Any]] = []
    lagged: list[dict[str, Any]] = []
    prediction: list[dict[str, Any]] = []
    benefits: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        grouped_bundles = bundle_groups.get(key, ())
        prospective = prospective_rows(grouped_bundles, group)
        contemporaneous.append(contemporaneous_response_row(grouped_bundles))
        prospective_all.extend(prospective)
        lagged.append(lagged_coupling_row(group, prospective))
        prediction.append(prediction_metrics_row(group, prospective))
        benefits.append(rmssd_benefit_row(group))
    participant = participant_condition_effect_rows(
        bundles,
        sessions,
        session_audits=session_audits,
    )
    factorial_participant = factorial_participant_effect_rows(participant)
    return {
        "contemporaneous": tuple(contemporaneous),
        "prospective": tuple(prospective_all),
        "lagged": tuple(lagged),
        "prediction": tuple(prediction),
        "benefits": tuple(benefits),
        "paired": paired_arm_difference_rows(benefits, lagged, sessions),
        "participant_condition_effects": participant,
        "factorial_participant_effects": factorial_participant,
        "factorial_user_type_effects": factorial_user_type_effect_rows(factorial_participant),
        "factorial_overall_effects": factorial_overall_effect_rows(factorial_participant),
        "user_type_trajectory": user_type_trajectory_rows(sessions),
    }


__all__ = [
    "analyze_factorial_records",
    "participant_condition_effect_rows",
]
