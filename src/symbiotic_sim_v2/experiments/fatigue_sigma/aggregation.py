"""Replicate and condition aggregation without a forced composite score."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, replace
from typing import Any

from .canonical import canonical_digest
from .config import (
    FATIGUE_SIGMA_CONDITION_SUMMARY_SCHEMA_VERSION,
    FATIGUE_SIGMA_REPLICATE_RESULT_SCHEMA_VERSION,
)
from .result import FatigueSigmaSingleConditionResult


def _mean(values: list[float]) -> float | None:
    return None if not values else statistics.fmean(values)


def _median(values: list[float | int]) -> float | None:
    return None if not values else float(statistics.median(values))


def _rate(count: int, total: int) -> float:
    return 0.0 if total == 0 else count / total


def _first_confirmed(history: tuple[dict[str, Any], ...], field: str) -> int | None:
    return next(
        (int(item["evaluated_at_session_index"]) for item in history if item[field]),
        None,
    )


def _post_convergence_structure_outlier(
    record: dict[str, Any],
    *,
    first_life: int | None,
    first_bpm: int | None,
    first_multi: int | None,
) -> bool:
    """Whether the newest vote lies outside every established structure.

    A holder change is not an outlier when the vote remains inside a confirmed
    cross-life BPM band or its life-specific attractor.  For mixed structures,
    membership in any established structure is enough to count as an inlier.
    """

    session_index = int(record["evaluated_at_session_index"])
    structure_outliers: list[bool] = []
    if first_life is not None and session_index > first_life:
        structure_outliers.append(
            bool(record["life_dominance"]["latest_session_outlier"])
        )
    if first_bpm is not None and session_index > first_bpm:
        member_indices = set(record["bpm_common"]["member_session_indices"])
        structure_outliers.append(session_index not in member_indices)
    if first_multi is not None and session_index > first_multi:
        valid_members = {
            int(member)
            for attractor in record["multi_attractor"]["life_attractors"]
            if attractor["valid_attractor"]
            for member in attractor["member_session_indices"]
        }
        structure_outliers.append(session_index not in valid_members)
    return bool(structure_outliers) and all(structure_outliers)


@dataclass(frozen=True, slots=True)
class FatigueSigmaReplicateResult:
    condition_id: str
    user_type_id: str
    selected_session_fatigue_target: float
    sigma_multiplier: float
    replicate_index: int
    replicate_master_seed: int
    sessions_completed: int
    sessions_expected: int
    completed: bool
    failed: bool
    failure_reason: str | None
    summary_classification: str
    truth_classification: str
    life_dominant_converged: bool
    bpm_common_converged: bool
    multi_attractor_converged: bool
    single_life_pattern_converged: bool
    first_life_convergence_session: int | None
    first_bpm_convergence_session: int | None
    first_multi_attractor_session: int | None
    dominant_life_share: float | None
    bpm_cluster_width: float | None
    post_convergence_outlier_rate: float
    return_within_1_rate: float
    return_within_2_rate: float
    mechanical_rotation: dict[str, Any]
    w_ceiling: dict[str, Any]
    explore_count: int
    candidate_count: int
    accepted_count: int
    selected_life_mean_e: float | None
    selected_life_max_e: float | None
    nonselected_full_recovery_count: int
    effective_sigma_mean: float | None
    effective_sigma_min: float | None
    effective_sigma_max: float | None
    candidate_delta_hue: tuple[float, ...]
    candidate_delta_bpm: tuple[float, ...]
    result_digest: str
    schema_version: str = FATIGUE_SIGMA_REPLICATE_RESULT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            name: (list(value) if isinstance(value, tuple) else value)
            for name, value in {
                field: getattr(self, field)
                for field in self.__dataclass_fields__
            }.items()
        }


def replicate_result_from_single(
    result: FatigueSigmaSingleConditionResult,
    *,
    replicate_index: int,
    replicate_master_seed: int,
) -> FatigueSigmaReplicateResult:
    if not isinstance(result, FatigueSigmaSingleConditionResult):
        raise TypeError("result must be a FatigueSigmaSingleConditionResult")
    history = tuple(dict(item) for item in result.structured_convergence_history)
    latest = None if not history else history[-1]
    classification = (
        "insufficient_sessions" if latest is None else latest["summary_classification"]
    )
    truth = result.truth_alignment
    truth_classification = (
        "not_converged" if truth is None else str(truth["truth_classification"])
    )
    first_life = _first_confirmed(history, "life_dominant_converged")
    first_bpm = _first_confirmed(history, "bpm_common_converged")
    first_multi = _first_confirmed(history, "multi_attractor_converged")
    first_values = tuple(
        value for value in (first_life, first_bpm, first_multi) if value is not None
    )
    first_any = None if not first_values else min(first_values)
    post_records = (
        ()
        if first_any is None
        else tuple(
            item
            for item in history
            if item["evaluated_at_session_index"] > first_any
        )
    )
    post_outliers = sum(
        _post_convergence_structure_outlier(
            item,
            first_life=first_life,
            first_bpm=first_bpm,
            first_multi=first_multi,
        )
        for item in post_records
    )
    selected_e = [
        float(item["e_after_session_end_policy"])
        for item in result.fatigue_trajectory
        if item.get("selected_life")
    ]
    effective_sigmas = [
        float(item["effective_sigma"])
        for item in result.sigma_trajectory
        if item.get("effective_sigma") is not None
    ]
    delta_hue = tuple(
        float(item["resulting_delta_hue"])
        for item in result.sigma_trajectory
        if item.get("resulting_delta_hue") is not None
    )
    delta_bpm = tuple(
        float(item["resulting_delta_bpm"])
        for item in result.sigma_trajectory
        if item.get("resulting_delta_bpm") is not None
    )
    latest_life = {} if latest is None else latest["life_dominance"]
    latest_bpm = {} if latest is None else latest["bpm_common"]
    life = False if latest is None else bool(latest["life_dominant_converged"])
    bpm = False if latest is None else bool(latest["bpm_common_converged"])
    multi = False if latest is None else bool(latest["multi_attractor_converged"])
    expected_sessions = int(result.condition["maximum_sessions"])
    failed = result.stopped_on_error
    completed = not failed and result.sessions_completed == expected_sessions
    failure_reason = next(
        (
            str(item["invalid_reason"])
            for item in reversed(result.session_outcomes)
            if item.get("invalid_reason") is not None
        ),
        None,
    )
    payload = {
        "condition_id": result.condition["condition_id"],
        "replicate_index": replicate_index,
        "replicate_master_seed": replicate_master_seed,
        "single_result_digest": result.digests["replicate_result_digest"],
    }
    return FatigueSigmaReplicateResult(
        condition_id=str(result.condition["condition_id"]),
        user_type_id=str(result.condition["user_type_id"]),
        selected_session_fatigue_target=float(
            result.condition["selected_session_fatigue_target"]
        ),
        sigma_multiplier=float(result.condition["sigma_multiplier"]),
        replicate_index=replicate_index,
        replicate_master_seed=replicate_master_seed,
        sessions_completed=result.sessions_completed,
        sessions_expected=expected_sessions,
        completed=completed,
        failed=failed,
        failure_reason=failure_reason,
        summary_classification=classification,
        truth_classification=truth_classification,
        life_dominant_converged=life,
        bpm_common_converged=bpm,
        multi_attractor_converged=multi,
        single_life_pattern_converged=life and bpm,
        first_life_convergence_session=first_life,
        first_bpm_convergence_session=first_bpm,
        first_multi_attractor_session=first_multi,
        dominant_life_share=(
            None if not latest_life else latest_life.get("share")
        ),
        bpm_cluster_width=(
            None if not latest_bpm else latest_bpm.get("bpm_range")
        ),
        post_convergence_outlier_rate=_rate(post_outliers, len(post_records)),
        return_within_1_rate=float(
            latest_life.get("return_within_one_session_rate", 0.0)
        ),
        return_within_2_rate=float(
            latest_life.get("return_within_two_sessions_rate", 0.0)
        ),
        mechanical_rotation=dict(result.mechanical_rotation_diagnostics),
        w_ceiling=dict(result.w_ceiling_diagnostics),
        explore_count=sum(
            item.get("exploration_decision") == "explore"
            for item in result.session_outcomes
        ),
        candidate_count=sum(
            bool(item.get("candidate_generated")) for item in result.session_outcomes
        ),
        accepted_count=sum(
            bool(item.get("candidate_accepted")) for item in result.session_outcomes
        ),
        selected_life_mean_e=_mean(selected_e),
        selected_life_max_e=None if not selected_e else max(selected_e),
        nonselected_full_recovery_count=sum(
            bool(item.get("full_recovery_applied"))
            for item in result.fatigue_trajectory
        ),
        effective_sigma_mean=_mean(effective_sigmas),
        effective_sigma_min=None if not effective_sigmas else min(effective_sigmas),
        effective_sigma_max=None if not effective_sigmas else max(effective_sigmas),
        candidate_delta_hue=delta_hue,
        candidate_delta_bpm=delta_bpm,
        result_digest=canonical_digest(payload),
    )


@dataclass(frozen=True, slots=True)
class FatigueSigmaConditionSummary:
    condition_id: str
    user_type_id: str
    selected_session_fatigue_target: float
    sigma_multiplier: float
    maximum_sessions: int
    replicate_count: int
    completed_replicate_count: int
    failed_replicate_count: int
    life_dominant_convergence_rate: float
    bpm_common_convergence_rate: float
    multi_attractor_convergence_rate: float
    single_life_pattern_convergence_rate: float
    diffuse_rate: float
    correct_structure_rate: float
    partial_structure_rate: float
    stable_suboptimal_rate: float
    flat_spurious_structure_rate: float
    median_first_life_convergence_session: float | None
    median_first_bpm_convergence_session: float | None
    median_first_multi_attractor_session: float | None
    mean_dominant_life_share: float | None
    median_dominant_life_share: float | None
    mean_bpm_cluster_width: float | None
    mean_post_convergence_outlier_rate: float | None
    mean_return_within_1_rate: float | None
    mean_return_within_2_rate: float | None
    holder_switch_rate: float | None
    three_distinct_life_window_rate: float | None
    immediate_return_rate: float | None
    three_life_cycle_rate: float | None
    dominant_life_return_rate: float | None
    explore_count: int
    candidate_count: int
    accepted_count: int
    w_ceiling_blocked_rate: float
    selected_life_mean_e: float | None
    selected_life_max_e: float | None
    nonselected_full_recovery_count: int
    effective_sigma_mean: float | None
    effective_sigma_min: float | None
    effective_sigma_max: float | None
    candidate_delta_hue: tuple[float, ...]
    candidate_delta_bpm: tuple[float, ...]
    condition_summary_digest: str
    schema_version: str = FATIGUE_SIGMA_CONDITION_SUMMARY_SCHEMA_VERSION

    @property
    def median_first_convergence_session(self) -> float | None:
        values = tuple(
            value
            for value in (
                self.median_first_life_convergence_session,
                self.median_first_bpm_convergence_session,
                self.median_first_multi_attractor_session,
            )
            if value is not None
        )
        return None if not values else min(values)

    @property
    def post_convergence_outlier_rate(self) -> float | None:
        return self.mean_post_convergence_outlier_rate

    @property
    def return_within_1_rate(self) -> float | None:
        return self.mean_return_within_1_rate

    @property
    def mechanical_rotation_rate(self) -> float | None:
        values = tuple(
            value
            for value in (
                self.three_distinct_life_window_rate,
                self.immediate_return_rate,
                self.three_life_cycle_rate,
            )
            if value is not None
        )
        return None if not values else max(values)

    @property
    def accepted_candidate_count(self) -> int:
        return self.accepted_count

    def to_dict(self) -> dict[str, Any]:
        values = {
            name: (list(value) if isinstance(value, tuple) else value)
            for name, value in {
                field: getattr(self, field)
                for field in self.__dataclass_fields__
            }.items()
        }
        values.update(
            {
                "median_first_convergence_session": (
                    self.median_first_convergence_session
                ),
                "post_convergence_outlier_rate": (
                    self.post_convergence_outlier_rate
                ),
                "return_within_1_rate": self.return_within_1_rate,
                "mechanical_rotation_rate": self.mechanical_rotation_rate,
                "accepted_candidate_count": self.accepted_candidate_count,
            }
        )
        return values


def aggregate_condition(
    replicates: tuple[FatigueSigmaReplicateResult, ...],
) -> FatigueSigmaConditionSummary:
    if not replicates:
        raise ValueError("at least one replicate is required")
    first = replicates[0]
    if any(
        (
            item.condition_id,
            item.user_type_id,
            item.selected_session_fatigue_target,
            item.sigma_multiplier,
            item.sessions_expected,
        )
        != (
            first.condition_id,
            first.user_type_id,
            first.selected_session_fatigue_target,
            first.sigma_multiplier,
            first.sessions_expected,
        )
        for item in replicates
    ):
        raise ValueError("replicates do not belong to one condition")
    completed = tuple(item for item in replicates if item.completed)
    denominator = len(completed)

    def flag_rate(name: str) -> float:
        return _rate(sum(bool(getattr(item, name)) for item in completed), denominator)

    def truth_rate(value: str) -> float:
        return _rate(
            sum(item.truth_classification == value for item in completed),
            denominator,
        )

    def numeric(name: str) -> list[float]:
        return [
            float(value)
            for item in completed
            for value in (getattr(item, name),)
            if value is not None
        ]

    mechanical_names = (
        "holder_switch_rate",
        "three_distinct_life_window_rate",
        "immediate_return_rate",
        "three_life_cycle_rate",
        "dominant_life_return_rate",
    )
    mechanical = {
        name: _mean(
            [
                float(item.mechanical_rotation[name])
                for item in completed
                if name in item.mechanical_rotation
            ]
        )
        for name in mechanical_names
    }
    delta_hue = tuple(value for item in completed for value in item.candidate_delta_hue)
    delta_bpm = tuple(value for item in completed for value in item.candidate_delta_bpm)
    summary = FatigueSigmaConditionSummary(
        condition_id=first.condition_id,
        user_type_id=first.user_type_id,
        selected_session_fatigue_target=first.selected_session_fatigue_target,
        sigma_multiplier=first.sigma_multiplier,
        maximum_sessions=first.sessions_expected,
        replicate_count=len(replicates),
        completed_replicate_count=denominator,
        failed_replicate_count=sum(item.failed for item in replicates),
        life_dominant_convergence_rate=flag_rate("life_dominant_converged"),
        bpm_common_convergence_rate=flag_rate("bpm_common_converged"),
        multi_attractor_convergence_rate=flag_rate("multi_attractor_converged"),
        single_life_pattern_convergence_rate=flag_rate(
            "single_life_pattern_converged"
        ),
        diffuse_rate=_rate(
            sum(
                item.summary_classification == "diffuse_or_unresolved"
                for item in completed
            ),
            denominator,
        ),
        correct_structure_rate=truth_rate("correct_structure"),
        partial_structure_rate=truth_rate("partially_correct_structure"),
        stable_suboptimal_rate=truth_rate("stable_suboptimal_structure"),
        flat_spurious_structure_rate=truth_rate(
            "spurious_structure_in_flat_control"
        ),
        median_first_life_convergence_session=_median(
            [
                item.first_life_convergence_session
                for item in completed
                if item.first_life_convergence_session is not None
            ]
        ),
        median_first_bpm_convergence_session=_median(
            [
                item.first_bpm_convergence_session
                for item in completed
                if item.first_bpm_convergence_session is not None
            ]
        ),
        median_first_multi_attractor_session=_median(
            [
                item.first_multi_attractor_session
                for item in completed
                if item.first_multi_attractor_session is not None
            ]
        ),
        mean_dominant_life_share=_mean(numeric("dominant_life_share")),
        median_dominant_life_share=_median(numeric("dominant_life_share")),
        mean_bpm_cluster_width=_mean(numeric("bpm_cluster_width")),
        mean_post_convergence_outlier_rate=_mean(
            numeric("post_convergence_outlier_rate")
        ),
        mean_return_within_1_rate=_mean(numeric("return_within_1_rate")),
        mean_return_within_2_rate=_mean(numeric("return_within_2_rate")),
        holder_switch_rate=mechanical["holder_switch_rate"],
        three_distinct_life_window_rate=mechanical[
            "three_distinct_life_window_rate"
        ],
        immediate_return_rate=mechanical["immediate_return_rate"],
        three_life_cycle_rate=mechanical["three_life_cycle_rate"],
        dominant_life_return_rate=mechanical["dominant_life_return_rate"],
        explore_count=sum(item.explore_count for item in completed),
        candidate_count=sum(item.candidate_count for item in completed),
        accepted_count=sum(item.accepted_count for item in completed),
        w_ceiling_blocked_rate=_rate(
            sum(
                item.w_ceiling.get("classification")
                == "exploration_blocked_by_W_ceiling"
                for item in completed
            ),
            denominator,
        ),
        selected_life_mean_e=_mean(numeric("selected_life_mean_e")),
        selected_life_max_e=(
            None
            if not numeric("selected_life_max_e")
            else max(numeric("selected_life_max_e"))
        ),
        nonselected_full_recovery_count=sum(
            item.nonselected_full_recovery_count for item in completed
        ),
        effective_sigma_mean=_mean(numeric("effective_sigma_mean")),
        effective_sigma_min=(
            None
            if not numeric("effective_sigma_min")
            else min(numeric("effective_sigma_min"))
        ),
        effective_sigma_max=(
            None
            if not numeric("effective_sigma_max")
            else max(numeric("effective_sigma_max"))
        ),
        candidate_delta_hue=delta_hue,
        candidate_delta_bpm=delta_bpm,
        condition_summary_digest="",
    )
    body = summary.to_dict()
    body.pop("condition_summary_digest")
    return replace(summary, condition_summary_digest=canonical_digest(body))


__all__ = [
    "FatigueSigmaConditionSummary",
    "FatigueSigmaReplicateResult",
    "aggregate_condition",
    "replicate_result_from_single",
]
