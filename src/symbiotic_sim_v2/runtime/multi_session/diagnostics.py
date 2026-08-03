"""Observation-only Stage 8A digests and six CSV exports."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.convergence import (
    RollingConvergenceRecord,
    TruthAlignmentRecord,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    relation_memory_state_map_to_dict,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    StationaryUserTypeProfile,
    stationary_user_type_ids,
    stationary_user_type_profile,
)

from .comparison import StationaryUserTypeComparison
from .session_outcome import SessionOutcome
from .state import MultiSessionRelationState

STATIONARY_USER_TYPES_CSV_FILENAME = "stage_08a_stationary_user_types.csv"
SESSION_OUTCOMES_CSV_FILENAME = "stage_08a_session_outcomes.csv"
CONVERGENCE_HISTORY_CSV_FILENAME = "stage_08a_convergence_history.csv"
PATTERN_TRAJECTORY_CSV_FILENAME = "stage_08a_pattern_trajectory.csv"
PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME = (
    "stage_08a_persistent_state_trajectory.csv"
)
USER_TYPE_COMPARISON_CSV_FILENAME = "stage_08a_user_type_comparison.csv"

STATIONARY_USER_TYPES_CSV_FIELDS = (
    "user_type_id",
    "display_name_ja",
    "description_ja",
    "peak_count",
    "peak_id",
    "preferred_hue_degree",
    "hue_sigma_degree",
    "preferred_blink_bpm",
    "blink_sigma_bpm",
    "peak_weight",
    "maximum_respiratory_amplitude_gain_ms",
    "maximum_mean_rri_increase_ms",
    "onset_time_constant_seconds",
    "recovery_time_constant_seconds",
    "landscape_version",
    "peak_model_version",
    "multi_peak_combination_version",
    "schema_version",
)
SESSION_OUTCOMES_CSV_FIELDS = (
    "session_index",
    "local_time_us",
    "global_time_us",
    "valid",
    "invalid_reason",
    "root_seed",
    "holder",
    "holder_role",
    "initial_k_anchor_by_life",
    "final_k_anchor_by_life",
    "initial_hue_degree",
    "initial_blink_bpm",
    "final_hue_degree",
    "final_blink_bpm",
    "holder_k_trial",
    "bundle_presentations",
    "exploration_decision",
    "candidate_generated",
    "adoption_result",
    "holder_W_anchor_session",
    "holder_W_trial_1",
    "holder_W_trial_2",
    "session_count_before_by_life",
    "session_count_after_by_life",
    "trial_count_before_by_life",
    "trial_count_after_by_life",
    "cluster_member",
    "outlier",
    "convergence_state",
    "truth_classification",
    "session_digest",
)
CONVERGENCE_HISTORY_CSV_FIELDS = (
    "evaluated_at_session_index",
    "local_time_us",
    "global_time_us",
    "window_session_indices",
    "valid_window_session_indices",
    "support_count",
    "window_size",
    "required_sessions",
    "holder_id",
    "member_session_indices",
    "outlier_session_indices",
    "medoid_hue_degree",
    "medoid_blink_bpm",
    "maximum_pairwise_distance",
    "mean_pairwise_distance",
    "convergence_state",
    "currently_converged",
    "first_convergence_session_index",
    "response_gap",
    "truth_classification",
)
PATTERN_TRAJECTORY_CSV_FIELDS = (
    "session_index",
    "point_kind",
    "bundle_index",
    "segment_index",
    "first_signal_index",
    "last_signal_index",
    "local_time_us",
    "global_time_us",
    "last_local_time_us",
    "last_global_time_us",
    "valid",
    "holder_id",
    "k_presented",
    "b_presented",
    "hue_degree",
    "blink_bpm",
    "cluster_member",
    "outlier",
    "medoid_session_index",
    "medoid_hue_degree",
    "medoid_blink_bpm",
)
PERSISTENT_STATE_TRAJECTORY_CSV_FIELDS = (
    "session_index",
    "local_time_us",
    "global_time_us",
    "state_position",
    "digital_life_id",
    "k_anchor",
    "q",
    "e",
    "trial_count",
    "session_count",
    "profile_version",
    "algorithm_version",
    "state_schema_version",
)
USER_TYPE_COMPARISON_CSV_FIELDS = (
    "user_type_id",
    "completed_session_count",
    "valid_session_count",
    "first_convergence_session_index",
    "current_convergence_state",
    "dominant_holder_id",
    "dominant_hue_degree",
    "dominant_blink_bpm",
    "cluster_support",
    "window_size",
    "truth_classification",
    "response_gap",
    "explore_count",
    "hold_count",
    "accepted_candidate_count",
    "convergence_loss_count",
    "post_convergence_outlier_rate",
    "final_k_anchor_by_life",
    "final_session_count_by_life",
    "final_trial_count_by_life",
)


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stationary_user_type_digest(
    profiles: Sequence[StationaryUserTypeProfile] | None = None,
) -> str:
    selected = (
        tuple(stationary_user_type_profile(value) for value in stationary_user_type_ids())
        if profiles is None
        else tuple(profiles)
    )
    return _canonical_digest([profile.to_dict() for profile in selected])


def session_outcome_digest(outcomes: Sequence[SessionOutcome]) -> str:
    return _canonical_digest([outcome.to_dict() for outcome in outcomes])


def convergence_history_digest(records: Sequence[RollingConvergenceRecord]) -> str:
    return _canonical_digest([record.to_dict() for record in records])


def multi_session_persistent_state_digest(state: MultiSessionRelationState) -> str:
    if not isinstance(state, MultiSessionRelationState):
        raise TypeError("state must be a MultiSessionRelationState")
    return _canonical_digest(state.to_dict())


final_multi_session_state_digest = multi_session_persistent_state_digest


def user_type_comparison_digest(comparison: StationaryUserTypeComparison) -> str:
    if not isinstance(comparison, StationaryUserTypeComparison):
        raise TypeError("comparison must be a StationaryUserTypeComparison")
    return _canonical_digest(comparison.to_dict())


def multi_session_summary(
    state: MultiSessionRelationState,
    profile: StationaryUserTypeProfile,
    truth_records: Sequence[TruthAlignmentRecord],
    *,
    initial_persistent_state_by_life: Mapping[
        str, RelationMemoryPersistentState
    ],
    comparison: StationaryUserTypeComparison | None = None,
) -> dict[str, object]:
    """Build the common GUI/headless summary without changing any run state."""

    if not isinstance(state, MultiSessionRelationState):
        raise TypeError("state must be a MultiSessionRelationState")
    if not isinstance(profile, StationaryUserTypeProfile):
        raise TypeError("profile must be a StationaryUserTypeProfile")
    truths = tuple(truth_records)
    if len(truths) != len(state.session_outcomes):
        raise ValueError("truth records must align one-to-one with session outcomes")
    if any(
        truth.evaluated_at_session_index != outcome.session_index
        or truth.local_time_us != outcome.local_time_us
        or truth.global_time_us != outcome.global_time_us
        for truth, outcome in zip(truths, state.session_outcomes, strict=True)
    ):
        raise ValueError("truth records and session outcomes are misaligned")
    life_ids = tuple(state.current_persistent_state_by_life)
    initial_values = relation_memory_state_map_to_dict(
        initial_persistent_state_by_life,
        expected_digital_life_ids=life_ids,
    )
    final_values = relation_memory_state_map_to_dict(
        state.current_persistent_state_by_life,
        expected_digital_life_ids=life_ids,
    )
    latest_convergence = (
        None if not state.convergence_records else state.convergence_records[-1]
    )
    latest_truth = None if not truths else truths[-1]
    outcomes = state.session_outcomes
    holder_counts = {
        life_id: sum(outcome.holder_id == life_id for outcome in outcomes)
        for life_id in life_ids
    }
    candidate_count = sum(outcome.candidate_generated for outcome in outcomes)
    accepted_count = sum(outcome.candidate_accepted for outcome in outcomes)
    post_outlier_count = (
        0
        if latest_convergence is None
        else latest_convergence.post_convergence_outlier_count
    )
    post_total = (
        0
        if latest_convergence is None
        else latest_convergence.post_convergence_cluster_member_count
        + latest_convergence.post_convergence_outlier_count
    )
    return {
        "project_version": __version__,
        **dict(state.versions),
        "runner_version": state.runner_version,
        "stationary_user_type_profile": profile.to_dict(),
        "convergence_config": state.convergence_config.to_dict(),
        "seed_policy": state.seed_policy,
        "master_seed": state.master_seed,
        "maximum_sessions": state.convergence_config.maximum_sessions,
        "completed_sessions": state.completed_session_count,
        "valid_sessions": state.valid_session_count,
        "invalid_sessions": len(outcomes) - state.valid_session_count,
        "first_convergence_session_index": state.first_convergence_session_index,
        "current_convergence_state": state.current_convergence_state,
        "currently_converged": (
            False
            if latest_convergence is None
            else latest_convergence.currently_converged
        ),
        "dominant_holder_id": (
            None if latest_convergence is None else latest_convergence.holder_id
        ),
        "cluster_support": (
            0 if latest_convergence is None else latest_convergence.support_count
        ),
        "window_size": (
            0 if latest_convergence is None else latest_convergence.window_size
        ),
        "cluster_member_session_indices": (
            ()
            if latest_convergence is None
            else latest_convergence.member_session_indices
        ),
        "outlier_session_indices": (
            ()
            if latest_convergence is None
            else latest_convergence.outlier_session_indices
        ),
        "medoid_hue_degree": (
            None if latest_convergence is None else latest_convergence.medoid_hue_degree
        ),
        "medoid_blink_bpm": (
            None if latest_convergence is None else latest_convergence.medoid_blink_bpm
        ),
        "truth_classification": (
            "not_converged"
            if latest_truth is None
            else latest_truth.truth_classification
        ),
        "preference_match_at_medoid": (
            None if latest_truth is None else latest_truth.preference_match_at_medoid
        ),
        "global_maximum_match": (
            max((peak.peak_weight for peak in profile.peaks), default=0.0)
            if latest_truth is None
            else latest_truth.global_maximum_preference_match
        ),
        "response_gap": None if latest_truth is None else latest_truth.response_gap,
        "nearest_peak_id": (
            None if latest_truth is None else latest_truth.nearest_peak_id
        ),
        "convergence_loss_count": (
            0 if latest_convergence is None else latest_convergence.convergence_lost_count
        ),
        "reconvergence_count": (
            0 if latest_convergence is None else latest_convergence.reconvergence_count
        ),
        "dominant_cluster_switch_count": (
            0
            if latest_convergence is None
            else latest_convergence.dominant_cluster_switch_count
        ),
        "post_convergence_outlier_count": post_outlier_count,
        "post_convergence_outlier_rate": (
            0.0 if post_total == 0 else post_outlier_count / post_total
        ),
        "holder_count_by_life": holder_counts,
        "explore_count": sum(
            outcome.exploration_decision == "explore" for outcome in outcomes
        ),
        "hold_count": sum(
            outcome.exploration_decision == "hold" for outcome in outcomes
        ),
        "candidate_count": candidate_count,
        "accepted_count": accepted_count,
        "rejected_count": candidate_count - accepted_count,
        "initial_persistent_state": initial_values,
        "final_persistent_state": final_values,
        "session_outcomes": [outcome.to_dict() for outcome in outcomes],
        "stationary_user_type_digest": stationary_user_type_digest((profile,)),
        "session_outcome_digest": session_outcome_digest(outcomes),
        "convergence_history_digest": convergence_history_digest(
            state.convergence_records
        ),
        "final_multi_session_state_digest": final_multi_session_state_digest(state),
        "comparison_digest": (
            None if comparison is None else user_type_comparison_digest(comparison)
        ),
        "per_session_full_event_digests": {
            str(outcome.session_index): outcome.session_digest for outcome in outcomes
        },
        "stationary_preference": True,
        "moving_preference": False,
        "convergence_is_diagnostic_only": True,
        "exploration_continues_after_convergence": True,
        "v2_coefficients_modified": False,
        "multi_session": True,
        "Monte_Carlo": False,
    }


def stationary_user_type_rows(
    profiles: Sequence[StationaryUserTypeProfile] | None = None,
) -> tuple[dict[str, object], ...]:
    selected = (
        tuple(stationary_user_type_profile(value) for value in stationary_user_type_ids())
        if profiles is None
        else tuple(profiles)
    )
    rows: list[dict[str, object]] = []
    for profile in selected:
        peaks = profile.peaks or (None,)
        for peak in peaks:
            rows.append(
                {
                    "user_type_id": profile.user_type_id,
                    "display_name_ja": profile.display_name_ja,
                    "description_ja": profile.description_ja,
                    "peak_count": len(profile.peaks),
                    "peak_id": None if peak is None else peak.peak_id,
                    "preferred_hue_degree": (
                        None if peak is None else peak.preferred_hue_degree
                    ),
                    "hue_sigma_degree": None if peak is None else peak.hue_sigma_degree,
                    "preferred_blink_bpm": (
                        None if peak is None else peak.preferred_blink_bpm
                    ),
                    "blink_sigma_bpm": None if peak is None else peak.blink_sigma_bpm,
                    "peak_weight": None if peak is None else peak.peak_weight,
                    "maximum_respiratory_amplitude_gain_ms": (
                        profile.maximum_respiratory_amplitude_gain_ms
                    ),
                    "maximum_mean_rri_increase_ms": (
                        profile.maximum_mean_rri_increase_ms
                    ),
                    "onset_time_constant_seconds": profile.onset_time_constant_seconds,
                    "recovery_time_constant_seconds": (
                        profile.recovery_time_constant_seconds
                    ),
                    "landscape_version": profile.landscape_version,
                    "peak_model_version": profile.peak_model_version,
                    "multi_peak_combination_version": (
                        profile.multi_peak_combination_version
                    ),
                    "schema_version": profile.schema_version,
                }
            )
    return tuple(rows)


def session_outcome_rows(
    outcomes: Sequence[SessionOutcome],
    convergence_records: Sequence[RollingConvergenceRecord],
    truth_records: Sequence[TruthAlignmentRecord],
) -> tuple[dict[str, object], ...]:
    convergence_by_index = {
        record.evaluated_at_session_index: record for record in convergence_records
    }
    truth_by_index = {
        record.evaluated_at_session_index: record for record in truth_records
    }
    rows = []
    for outcome in outcomes:
        convergence = convergence_by_index[outcome.session_index]
        truth = truth_by_index[outcome.session_index]
        rows.append(
            {
                "session_index": outcome.session_index,
                "local_time_us": outcome.local_time_us,
                "global_time_us": outcome.global_time_us,
                "valid": outcome.valid_for_convergence,
                "invalid_reason": outcome.invalid_reason,
                "root_seed": outcome.physiology_root_seed,
                "holder": outcome.holder_id,
                "holder_role": outcome.holder_role,
                "initial_k_anchor_by_life": dict(outcome.initial_k_anchor_by_life),
                "final_k_anchor_by_life": dict(outcome.final_k_anchor_by_life),
                "initial_hue_degree": outcome.holder_initial_hue_degree,
                "initial_blink_bpm": outcome.holder_initial_blink_bpm,
                "final_hue_degree": outcome.holder_final_hue_degree,
                "final_blink_bpm": outcome.holder_final_blink_bpm,
                "holder_k_trial": outcome.holder_k_trial,
                "bundle_presentations": tuple(
                    record.to_dict() for record in outcome.bundle_presentations
                ),
                "exploration_decision": outcome.exploration_decision,
                "candidate_generated": outcome.candidate_generated,
                "adoption_result": outcome.adoption_result,
                "holder_W_anchor_session": outcome.holder_W_anchor_session,
                "holder_W_trial_1": outcome.holder_W_trial_1,
                "holder_W_trial_2": outcome.holder_W_trial_2,
                "session_count_before_by_life": dict(
                    outcome.session_count_before_by_life
                ),
                "session_count_after_by_life": dict(
                    outcome.session_count_after_by_life
                ),
                "trial_count_before_by_life": dict(
                    outcome.trial_count_before_by_life
                ),
                "trial_count_after_by_life": dict(
                    outcome.trial_count_after_by_life
                ),
                "cluster_member": outcome.session_index
                in convergence.member_session_indices,
                "outlier": outcome.session_index
                in convergence.outlier_session_indices,
                "convergence_state": convergence.convergence_state,
                "truth_classification": truth.truth_classification,
                "session_digest": outcome.session_digest,
            }
        )
    return tuple(rows)


def convergence_history_rows(
    records: Sequence[RollingConvergenceRecord],
    truth_records: Sequence[TruthAlignmentRecord],
) -> tuple[dict[str, object], ...]:
    truth_by_index = {
        record.evaluated_at_session_index: record for record in truth_records
    }
    rows = []
    for record in records:
        truth = truth_by_index[record.evaluated_at_session_index]
        values = record.to_dict()
        rows.append(
            {
                field: (
                    truth.response_gap
                    if field == "response_gap"
                    else truth.truth_classification
                    if field == "truth_classification"
                    else values[field]
                )
                for field in CONVERGENCE_HISTORY_CSV_FIELDS
            }
        )
    return tuple(rows)


def pattern_trajectory_rows(
    outcomes: Sequence[SessionOutcome],
    records: Sequence[RollingConvergenceRecord],
) -> tuple[dict[str, object], ...]:
    by_index = {record.evaluated_at_session_index: record for record in records}
    rows: list[dict[str, object]] = []
    for outcome in outcomes:
        convergence = by_index[outcome.session_index]
        common = {
            "session_index": outcome.session_index,
            "valid": outcome.valid_for_convergence,
            "holder_id": outcome.holder_id,
            "cluster_member": outcome.session_index
            in convergence.member_session_indices,
            "outlier": outcome.session_index in convergence.outlier_session_indices,
            "medoid_session_index": convergence.medoid_session_index,
            "medoid_hue_degree": convergence.medoid_hue_degree,
            "medoid_blink_bpm": convergence.medoid_blink_bpm,
        }
        for segment_index, presentation in enumerate(outcome.bundle_presentations):
            rows.append(
                {
                    **common,
                    "point_kind": "bundle_presentation",
                    "bundle_index": presentation.bundle_index,
                    "segment_index": segment_index,
                    "first_signal_index": presentation.first_signal_index,
                    "last_signal_index": presentation.last_signal_index,
                    "local_time_us": presentation.first_effective_time_us,
                    "global_time_us": presentation.first_global_time_us,
                    "last_local_time_us": presentation.last_effective_time_us,
                    "last_global_time_us": presentation.last_global_time_us,
                    "k_presented": presentation.k_presented,
                    "b_presented": presentation.b_presented,
                    "hue_degree": presentation.hue_degree,
                    "blink_bpm": presentation.blink_bpm,
                }
            )
        rows.append(
            {
                **common,
                "point_kind": "final_committed",
                "bundle_index": None,
                "segment_index": None,
                "first_signal_index": None,
                "last_signal_index": None,
                "local_time_us": outcome.local_time_us,
                "global_time_us": outcome.global_time_us,
                "last_local_time_us": outcome.local_time_us,
                "last_global_time_us": outcome.global_time_us,
                "k_presented": outcome.holder_final_k_anchor,
                "b_presented": (
                    None
                    if outcome.holder_final_b_f is None
                    else (
                        outcome.holder_final_b_f,
                        outcome.holder_final_b_a,
                        outcome.holder_final_b_t,
                        outcome.holder_final_b_d,
                    )
                ),
                "hue_degree": outcome.holder_final_hue_degree,
                "blink_bpm": outcome.holder_final_blink_bpm,
            }
        )
    return tuple(rows)


def persistent_state_trajectory_rows(
    outcomes: Sequence[SessionOutcome],
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for outcome in outcomes:
        for life_id, state in outcome.initial_persistent_state_by_life.items():
            rows.append(
                {
                    "session_index": outcome.session_index,
                    "local_time_us": 0,
                    "global_time_us": outcome.global_time_us - outcome.local_time_us,
                    "state_position": "initial",
                    "digital_life_id": life_id,
                    "k_anchor": state.k_anchor,
                    "q": state.q,
                    "e": state.e,
                    "trial_count": state.trial_count,
                    "session_count": state.session_count,
                    "profile_version": state.profile_version,
                    "algorithm_version": state.algorithm_version,
                    "state_schema_version": state.state_schema_version,
                }
            )
        for life_id, state in outcome.final_persistent_state_by_life.items():
            rows.append(
                {
                    "session_index": outcome.session_index,
                    "local_time_us": outcome.local_time_us,
                    "global_time_us": outcome.global_time_us,
                    "state_position": "final",
                    "digital_life_id": life_id,
                    "k_anchor": state.k_anchor,
                    "q": state.q,
                    "e": state.e,
                    "trial_count": state.trial_count,
                    "session_count": state.session_count,
                    "profile_version": state.profile_version,
                    "algorithm_version": state.algorithm_version,
                    "state_schema_version": state.state_schema_version,
                }
            )
    return tuple(rows)


def comparison_rows(
    comparison: StationaryUserTypeComparison | None,
) -> tuple[dict[str, object], ...]:
    return () if comparison is None else tuple(row.to_dict() for row in comparison.rows)


def export_multi_session_diagnostics(
    destination: str | Path,
    state: MultiSessionRelationState,
    truth_records: Sequence[TruthAlignmentRecord],
    *,
    comparison: StationaryUserTypeComparison | None = None,
    profiles: Sequence[StationaryUserTypeProfile] | None = None,
) -> tuple[Path, Path, Path, Path, Path, Path]:
    """Write all Stage 8A CSVs without mutating the run or its diagnostics."""

    if not isinstance(state, MultiSessionRelationState):
        raise TypeError("state must be a MultiSessionRelationState")
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    return (
        _write_rows(
            root / STATIONARY_USER_TYPES_CSV_FILENAME,
            STATIONARY_USER_TYPES_CSV_FIELDS,
            stationary_user_type_rows(profiles),
        ),
        _write_rows(
            root / SESSION_OUTCOMES_CSV_FILENAME,
            SESSION_OUTCOMES_CSV_FIELDS,
            session_outcome_rows(
                state.session_outcomes,
                state.convergence_records,
                truth_records,
            ),
        ),
        _write_rows(
            root / CONVERGENCE_HISTORY_CSV_FILENAME,
            CONVERGENCE_HISTORY_CSV_FIELDS,
            convergence_history_rows(state.convergence_records, truth_records),
        ),
        _write_rows(
            root / PATTERN_TRAJECTORY_CSV_FILENAME,
            PATTERN_TRAJECTORY_CSV_FIELDS,
            pattern_trajectory_rows(state.session_outcomes, state.convergence_records),
        ),
        _write_rows(
            root / PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME,
            PERSISTENT_STATE_TRAJECTORY_CSV_FIELDS,
            persistent_state_trajectory_rows(state.session_outcomes),
        ),
        _write_rows(
            root / USER_TYPE_COMPARISON_CSV_FILENAME,
            USER_TYPE_COMPARISON_CSV_FIELDS,
            comparison_rows(comparison),
        ),
    )


def _csv_cell(value: object) -> object:
    if isinstance(value, (tuple, list, dict, Mapping)):
        return json.dumps(
            dict(value) if isinstance(value, Mapping) else value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return value


def _write_rows(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(
            {field: _csv_cell(row[field]) for field in fieldnames} for row in rows
        )
    return path


__all__ = [
    "CONVERGENCE_HISTORY_CSV_FILENAME",
    "PATTERN_TRAJECTORY_CSV_FILENAME",
    "PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME",
    "SESSION_OUTCOMES_CSV_FILENAME",
    "STATIONARY_USER_TYPES_CSV_FILENAME",
    "USER_TYPE_COMPARISON_CSV_FILENAME",
    "comparison_rows",
    "convergence_history_digest",
    "convergence_history_rows",
    "export_multi_session_diagnostics",
    "final_multi_session_state_digest",
    "multi_session_persistent_state_digest",
    "multi_session_summary",
    "pattern_trajectory_rows",
    "persistent_state_trajectory_rows",
    "session_outcome_digest",
    "session_outcome_rows",
    "stationary_user_type_digest",
    "stationary_user_type_rows",
    "user_type_comparison_digest",
]
