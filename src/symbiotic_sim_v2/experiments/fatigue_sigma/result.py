"""Detached Stage 8A.1 result projections and canonical diagnostic digests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from symbiotic_sim_v2.convergence.structured import (
    StructuredConvergenceConfig,
    StructuredConvergenceEvaluator,
    StructuredTruthAlignmentRecord,
    WCeilingObservation,
    evaluate_e_driven_switches,
    evaluate_structured_truth_alignment,
    evaluate_w_ceiling,
)
from symbiotic_sim_v2.digital_life.config import (
    ALGORITHM_VERSION,
    DOCUMENT_VERSION,
    PROFILE_VERSION,
    STATE_SCHEMA_VERSION,
)
from symbiotic_sim_v2.digital_life.relation_memory.intrinsic import (
    derive_relation_memory_intrinsic_profile,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    relation_memory_state_map_to_dict,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.canonical import (
    canonical_digest,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.session_outcome import (
    ExperimentalSessionOutcome,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.state import (
    FatigueSigmaExperimentState,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    StationaryUserTypeProfileV2,
)

from .config import (
    FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION,
    FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
    PROJECT_VERSION,
)
from .manifest import FatigueSigmaExperimentManifest


def _fatigue_rows(
    outcomes: Sequence[ExperimentalSessionOutcome],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for outcome in outcomes:
        for life_id, record in outcome.fatigue_trajectory_by_life.items():
            rows.append(
                {
                    "session_index": outcome.session_index,
                    "physiology_root_seed": outcome.physiology_root_seed,
                    "holder_id": outcome.holder_id,
                    "selected_life": life_id == outcome.holder_id,
                    **dict(record),
                }
            )
    return tuple(rows)


def _sigma_rows(
    outcomes: Sequence[ExperimentalSessionOutcome],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for outcome in outcomes:
        for life_id, record in outcome.sigma_trajectory_by_life.items():
            row = {
                "session_index": outcome.session_index,
                "physiology_root_seed": outcome.physiology_root_seed,
                "holder_id": outcome.holder_id,
                "digital_life_id": life_id,
                **dict(record),
            }
            row["resulting_delta_hue"] = row.get("resulting_delta_hue_degree")
            row["resulting_delta_bpm"] = row.get("resulting_delta_bpm")
            rows.append(row)
    return tuple(rows)


def _pattern_rows(
    outcomes: Sequence[ExperimentalSessionOutcome],
    latest_record: object | None,
) -> tuple[dict[str, Any], ...]:
    cluster_members: set[int] = set()
    cluster_outliers: set[int] = set()
    if latest_record is not None:
        bpm = latest_record.bpm_common
        cluster_members.update(bpm.member_session_indices)
        cluster_outliers.update(bpm.outlier_session_indices)
        for attractor in latest_record.multi_attractor.life_attractors:
            if attractor.valid_attractor:
                cluster_members.update(attractor.member_session_indices)
                cluster_outliers.update(attractor.outlier_session_indices)
    rows: list[dict[str, Any]] = []
    for outcome in outcomes:
        fatigue = outcome.fatigue_trajectory_by_life.get(outcome.holder_id or "", {})
        if outcome.holder_id is not None:
            rows.append(
                {
                    "session_index": outcome.session_index,
                    "point_kind": "final",
                    "bundle_index": None,
                    "local_time_us": outcome.local_time_us,
                    "digital_life_id": outcome.holder_id,
                    "hue_degree": outcome.holder_final_hue_degree,
                    "blink_bpm": outcome.holder_final_blink_bpm,
                    "valid": outcome.valid_for_convergence,
                    "cluster_member": outcome.session_index in cluster_members,
                    "outlier": outcome.session_index in cluster_outliers,
                    "e": fatigue.get("e_after_session_end_policy"),
                    "exploration_decision": outcome.exploration_decision,
                    "adoption_result": outcome.adoption_result,
                    "candidate_accepted": outcome.candidate_accepted,
                }
            )
        if not outcome.candidate_generated:
            continue
        holder_id = outcome.holder_id
        if holder_id is None or holder_id not in outcome.initial_persistent_state_by_life:
            continue
        initial_anchor = outcome.initial_persistent_state_by_life[holder_id].k_anchor
        for presentation in outcome.bundle_presentations:
            # A candidate session can return to the anchor inside Bundle 1 or 2.
            # Only the physically presented non-anchor candidate segments are
            # trial points; anchor fallback segments remain represented by the
            # final committed point and must not pollute the trial trajectory.
            if presentation.k_presented == initial_anchor:
                continue
            rows.append(
                {
                    "session_index": outcome.session_index,
                    "point_kind": "trial",
                    "bundle_index": presentation.bundle_index,
                    "local_time_us": presentation.first_effective_time_us,
                    "digital_life_id": presentation.holder_id,
                    "k_presented": presentation.k_presented,
                    "hue_degree": presentation.hue_degree,
                    "blink_bpm": presentation.blink_bpm,
                    "valid": outcome.valid_for_convergence,
                    "cluster_member": False,
                    "outlier": False,
                    "e": fatigue.get("e_after_active"),
                    "exploration_decision": outcome.exploration_decision,
                    "adoption_result": outcome.adoption_result,
                    "candidate_accepted": outcome.candidate_accepted,
                }
            )
    return tuple(rows)


def _truth_history(
    evaluator: StructuredConvergenceEvaluator,
    profile: StationaryUserTypeProfileV2,
) -> tuple[StructuredTruthAlignmentRecord, ...]:
    observations = evaluator.observations()
    return tuple(
        evaluate_structured_truth_alignment(
            observations[: position + 1],
            record,
            profile,
            evaluator.config,
        )
        for position, record in enumerate(evaluator.records())
    )


def _w_diagnostic(outcomes: Sequence[ExperimentalSessionOutcome]):
    observations = []
    for outcome in outcomes:
        if outcome.holder_id is None:
            continue
        profile = derive_relation_memory_intrinsic_profile(outcome.holder_id)
        observation = WCeilingObservation.from_outcome(
            outcome,
            epsilon_accept=profile.epsilon_accept,
        )
        if observation is not None:
            observations.append(observation)
    return evaluate_w_ceiling(tuple(observations))


def _e_switch_diagnostic(
    outcomes: Sequence[ExperimentalSessionOutcome],
    config: StructuredConvergenceConfig,
):
    snapshots = tuple(
        {
            "holder_id": outcome.holder_id,
            "e_at_session_start_by_life": {
                life_id: state.e
                for life_id, state in outcome.initial_persistent_state_by_life.items()
            },
        }
        for outcome in outcomes
        if outcome.valid_for_convergence
    )
    return evaluate_e_driven_switches(snapshots, config)


def _state_dict(state: FatigueSigmaExperimentState) -> dict[str, Any]:
    ids = tuple(state.current_persistent_state_by_life)
    return relation_memory_state_map_to_dict(
        state.current_persistent_state_by_life,
        expected_digital_life_ids=ids,
    )


def _experimental_state_projection(
    state: FatigueSigmaExperimentState,
) -> dict[str, Any]:
    """Canonical resumable state of the experimental arm only.

    Enabling a paired reference arm must not change the identity of the
    experimental state.  Reference history has its own result projection and
    is therefore deliberately excluded from this digest payload.
    """

    encoded = state.to_dict()
    return {
        "condition": encoded["condition"],
        "initial_persistent_state_by_life": encoded[
            "initial_persistent_state_by_life"
        ],
        "current_persistent_state_by_life": encoded[
            "current_persistent_state_by_life"
        ],
        "session_outcomes": encoded["session_outcomes"],
        "next_session_index": encoded["next_session_index"],
        "stopped_on_error": encoded["stopped_on_error"],
        "lab_model_version": encoded["lab_model_version"],
        "schema_version": encoded["schema_version"],
    }


def _mechanical_classification(
    mechanical: object,
    e_switch: object,
    config: StructuredConvergenceConfig,
) -> str:
    three_window_warning = bool(
        mechanical.three_session_window_count
        >= config.mechanical_warning_minimum_windows
        and max(
            mechanical.three_distinct_life_window_rate,
            mechanical.immediate_return_rate,
        )
        >= config.mechanical_warning_rate_threshold
    )
    four_window_warning = bool(
        mechanical.four_session_window_count
        >= config.mechanical_warning_minimum_windows
        and mechanical.three_life_cycle_rate
        >= config.mechanical_warning_rate_threshold
    )
    rotation_warning = three_window_warning or four_window_warning
    if e_switch.e_driven_switch_warning:
        return "spurious_fatigue_driven_structure_warning"
    if rotation_warning:
        return "mechanical_rotation_warning"
    return "no_warning"


@dataclass(frozen=True, slots=True)
class FatigueSigmaSingleConditionResult:
    project_version: str
    normative_tuple: Mapping[str, str]
    lab_model_version: str
    experiment_profile_version: str
    experiment_manifest: Mapping[str, Any]
    user_type_profile: Mapping[str, Any]
    condition: Mapping[str, Any]
    reference_arm_metadata: Mapping[str, Any]
    sessions_completed: int
    sessions_valid: int
    stopped_on_error: bool
    persistent_state: Mapping[str, Any]
    session_outcomes: tuple[Mapping[str, Any], ...]
    fatigue_trajectory: tuple[Mapping[str, Any], ...]
    sigma_trajectory: tuple[Mapping[str, Any], ...]
    session_pattern_trajectory: tuple[Mapping[str, Any], ...]
    structured_convergence_history: tuple[Mapping[str, Any], ...]
    truth_alignment_history: tuple[Mapping[str, Any], ...]
    mechanical_rotation_diagnostics: Mapping[str, Any]
    e_driven_switch_diagnostics: Mapping[str, Any]
    w_ceiling_diagnostics: Mapping[str, Any]
    reference_arm_result: Mapping[str, Any] | None
    policy_flags: Mapping[str, bool]
    digests: Mapping[str, str]

    @property
    def completed_session_count(self) -> int:
        return self.sessions_completed

    @property
    def structured_convergence_records(self) -> tuple[Mapping[str, Any], ...]:
        return self.structured_convergence_history

    @property
    def structured_convergence(self) -> Mapping[str, Any] | None:
        return (
            None
            if not self.structured_convergence_history
            else self.structured_convergence_history[-1]
        )

    @property
    def latest_structured_convergence(self) -> Mapping[str, Any] | None:
        return self.structured_convergence

    @property
    def truth_alignment(self) -> Mapping[str, Any] | None:
        return None if not self.truth_alignment_history else self.truth_alignment_history[-1]

    @property
    def latest_truth_alignment(self) -> Mapping[str, Any] | None:
        return self.truth_alignment

    @property
    def fatigue_trajectory_digest(self) -> str:
        return self.digests["fatigue_trajectory_digest"]

    @property
    def sigma_trajectory_digest(self) -> str:
        return self.digests["sigma_trajectory_digest"]

    @property
    def structured_convergence_digest(self) -> str:
        return self.digests["structured_convergence_digest"]

    @property
    def experiment_manifest_digest(self) -> str:
        return self.digests["experiment_manifest_digest"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_version": self.project_version,
            "normative_tuple": dict(self.normative_tuple),
            "lab_model_version": self.lab_model_version,
            "experiment_profile_version": self.experiment_profile_version,
            "experiment_manifest": dict(self.experiment_manifest),
            "user_type_profile": dict(self.user_type_profile),
            "condition": dict(self.condition),
            "reference_arm_metadata": dict(self.reference_arm_metadata),
            "sessions_completed": self.sessions_completed,
            "sessions_valid": self.sessions_valid,
            "stopped_on_error": self.stopped_on_error,
            "persistent_state": dict(self.persistent_state),
            "fatigue_trajectory_summary": {
                "record_count": len(self.fatigue_trajectory),
                "full_recovery_count": sum(
                    bool(item.get("full_recovery_applied"))
                    for item in self.fatigue_trajectory
                ),
            },
            "sigma_trajectory_summary": {
                "record_count": len(self.sigma_trajectory),
                "candidate_count": sum(
                    bool(item.get("candidate_generated"))
                    for item in self.sigma_trajectory
                ),
            },
            "session_outcomes": [dict(item) for item in self.session_outcomes],
            "fatigue_trajectory": [dict(item) for item in self.fatigue_trajectory],
            "sigma_trajectory": [dict(item) for item in self.sigma_trajectory],
            "session_pattern_trajectory": [
                dict(item) for item in self.session_pattern_trajectory
            ],
            "structured_convergence_history": [
                dict(item) for item in self.structured_convergence_history
            ],
            "structured_convergence": (
                None
                if self.structured_convergence is None
                else dict(self.structured_convergence)
            ),
            "convergence_structure_flags": (
                {}
                if not self.structured_convergence_history
                else {
                    key: self.structured_convergence_history[-1][key]
                    for key in (
                        "early_single_life_pattern_signal",
                        "life_dominant_converged",
                        "bpm_common_converged",
                        "multi_attractor_converged",
                        "three_attractor_converged",
                    )
                }
            ),
            "summary_classification": (
                "insufficient_sessions"
                if not self.structured_convergence_history
                else self.structured_convergence_history[-1][
                    "summary_classification"
                ]
            ),
            "truth_alignment_history": [
                dict(item) for item in self.truth_alignment_history
            ],
            "truth_classification": (
                "not_converged"
                if not self.truth_alignment_history
                else self.truth_alignment_history[-1]["truth_classification"]
            ),
            "mechanical_rotation_diagnostics": dict(
                self.mechanical_rotation_diagnostics
            ),
            "e_driven_switch_diagnostics": dict(
                self.e_driven_switch_diagnostics
            ),
            "w_ceiling_diagnostics": dict(self.w_ceiling_diagnostics),
            "reference_arm_result": (
                None
                if self.reference_arm_result is None
                else dict(self.reference_arm_result)
            ),
            "policy_flags": dict(self.policy_flags),
            "digests": dict(self.digests),
        }


def _arm_projection(
    outcomes: tuple[ExperimentalSessionOutcome, ...],
    profile: StationaryUserTypeProfileV2,
    maximum_sessions: int,
) -> dict[str, Any]:
    config = StructuredConvergenceConfig(maximum_sessions=maximum_sessions)
    evaluator = StructuredConvergenceEvaluator(config, outcomes)
    records = tuple(item.to_dict() for item in evaluator.records())
    truths = tuple(item.to_dict() for item in _truth_history(evaluator, profile))
    latest = evaluator.latest_record()
    fatigue = _fatigue_rows(outcomes)
    sigma = _sigma_rows(outcomes)
    patterns = _pattern_rows(outcomes, latest)
    w = _w_diagnostic(outcomes)
    e_switch = _e_switch_diagnostic(outcomes, config)
    mechanical = (
        {}
        if latest is None
        else {
            **latest.mechanical_rotation.to_dict(),
            "e_driven_switch_diagnostic": e_switch.to_dict(),
            "classification": _mechanical_classification(
                latest.mechanical_rotation,
                e_switch,
                config,
            ),
        }
    )
    return {
        "outcomes": tuple(item.to_dict() for item in outcomes),
        "fatigue": fatigue,
        "sigma": sigma,
        "patterns": patterns,
        "records": records,
        "truths": truths,
        "mechanical": mechanical,
        "e_switch": e_switch.to_dict(),
        "w": w.to_dict(),
    }


def build_single_condition_result(
    state: FatigueSigmaExperimentState,
    profile: StationaryUserTypeProfileV2,
) -> FatigueSigmaSingleConditionResult:
    if not isinstance(state, FatigueSigmaExperimentState):
        raise TypeError("state must be a FatigueSigmaExperimentState")
    if not isinstance(profile, StationaryUserTypeProfileV2):
        raise TypeError("profile must be a StationaryUserTypeProfileV2")
    arm = _arm_projection(
        state.session_outcomes,
        profile,
        state.condition.maximum_sessions,
    )
    reference_arm_result = None
    if state.reference_arm_enabled:
        reference = _arm_projection(
            state.reference_session_outcomes,
            profile,
            state.condition.maximum_sessions,
        )
        reference_arm_result = {
            "arm_name": "v2_coefficient_reference_arm",
            "reference_fatigue_policy": True,
            "unselected_full_recovery": False,
            "sigma_multiplier": 1.0,
            "session_outcomes": list(reference["outcomes"]),
            "structured_convergence_history": list(reference["records"]),
            "truth_alignment_history": list(reference["truths"]),
            "w_ceiling_diagnostics": reference["w"],
            "digest": canonical_digest(reference),
        }
    manifest = FatigueSigmaExperimentManifest().to_dict()
    persistent = _state_dict(state)
    digests = {
        "experiment_condition_digest": canonical_digest(state.condition.to_dict()),
        "fatigue_trajectory_digest": canonical_digest(arm["fatigue"]),
        "sigma_trajectory_digest": canonical_digest(arm["sigma"]),
        "structured_convergence_digest": canonical_digest(arm["records"]),
        "experiment_manifest_digest": manifest["experiment_manifest_digest"],
        "final_experimental_state_digest": canonical_digest(
            _experimental_state_projection(state)
        ),
        "session_outcome_digest": canonical_digest(arm["outcomes"]),
    }
    digests["replicate_result_digest"] = canonical_digest(
        {
            "condition": state.condition.to_dict(),
            "outcomes": arm["outcomes"],
            "structured": arm["records"],
            "truth": arm["truths"],
            "w": arm["w"],
        }
    )
    flags = {
        "stationary_preference": True,
        "moving_preference": False,
        "unselected_full_recovery": True,
        "convergence_is_diagnostic_only": True,
        "exploration_continues_after_convergence": True,
        "p_explore_modified": False,
        "epsilon_accept_modified": False,
        "q_coefficients_modified": False,
        "v2_reference_arm_available": True,
        "formal_spec_adoption": False,
        "Monte_Carlo": False,
    }
    return FatigueSigmaSingleConditionResult(
        project_version=PROJECT_VERSION,
        normative_tuple={
            "document_version": DOCUMENT_VERSION,
            "profile_version": PROFILE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
        },
        lab_model_version=FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION,
        experiment_profile_version=FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
        experiment_manifest=manifest,
        user_type_profile=profile.to_dict(),
        condition=state.condition.to_dict(),
        reference_arm_metadata={
            "enabled": state.reference_arm_enabled,
            "available": True,
            "arm_name": "v2_coefficient_reference_arm",
            "new_user_type_v2_is_not_stage8a_user_type_v1": True,
        },
        sessions_completed=state.completed_session_count,
        sessions_valid=state.valid_session_count,
        stopped_on_error=state.stopped_on_error,
        persistent_state=persistent,
        session_outcomes=arm["outcomes"],
        fatigue_trajectory=arm["fatigue"],
        sigma_trajectory=arm["sigma"],
        session_pattern_trajectory=arm["patterns"],
        structured_convergence_history=arm["records"],
        truth_alignment_history=arm["truths"],
        mechanical_rotation_diagnostics=arm["mechanical"],
        e_driven_switch_diagnostics=arm["e_switch"],
        w_ceiling_diagnostics=arm["w"],
        reference_arm_result=reference_arm_result,
        policy_flags=flags,
        digests=digests,
    )


__all__ = [
    "FatigueSigmaSingleConditionResult",
    "build_single_condition_result",
]
