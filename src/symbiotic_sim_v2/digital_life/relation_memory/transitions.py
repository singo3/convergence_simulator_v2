"""Pure confirmed-candidate relation-memory state machine for one life."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from symbiotic_sim_v2.digital_life.hash01 import hash01

from .candidate import generate_candidate
from .direction import RelationMemorySearchDirection, derive_search_direction
from .intrinsic import (
    RelationMemoryIntrinsicProfile,
    derive_relation_memory_intrinsic_profile,
    exploration_decision,
    exploration_probability,
    exploration_sigma,
)
from .persistent_state import RelationMemoryPersistentState
from .records import KVector, RelationMemoryTransitionRecord
from .session_state import RelationMemorySessionState


def _counter(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def _experimental_sigma_multiplier(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("sigma_multiplier must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("sigma_multiplier must be finite")
    if not 0.25 <= converted <= 1.50:
        raise ValueError("sigma_multiplier must be between 0.25 and 1.50")
    return converted


def _optional_non_empty(name: str, value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string or null")
    return value


@dataclass(frozen=True, slots=True)
class RelationMemoryTransitionInput:
    """Formal-boundary projection; it intentionally imports no Garden type."""

    transition_index: int
    signal_index: int
    signal_time_us: int
    digital_life_id: str
    g: int
    bundle_index: int | None
    evaluation_id: str | None
    evaluation_kind: str | None
    evaluation_quality: str | None
    evaluation_is_valid: bool | None
    is_new_valid_evaluation: bool
    w: float
    closing: bool

    def __post_init__(self) -> None:
        for name in ("transition_index", "signal_index", "signal_time_us"):
            object.__setattr__(self, name, _counter(name, getattr(self, name)))
        if not isinstance(self.digital_life_id, str) or not self.digital_life_id.strip():
            raise ValueError("digital_life_id must be a non-empty string")
        if isinstance(self.g, bool) or not isinstance(self.g, int):
            raise TypeError("g must be an integer")
        if self.g not in (0, 1):
            raise ValueError("g must be 0 or 1")
        if self.bundle_index is not None:
            object.__setattr__(
                self,
                "bundle_index",
                _counter("bundle_index", self.bundle_index),
            )
            if self.bundle_index > 2:
                raise ValueError("bundle_index must be null or between 0 and 2")
        for name in ("evaluation_id", "evaluation_kind", "evaluation_quality"):
            object.__setattr__(
                self,
                name,
                _optional_non_empty(name, getattr(self, name)),
            )
        if self.evaluation_is_valid is not None and not isinstance(
            self.evaluation_is_valid, bool
        ):
            raise TypeError("evaluation_is_valid must be boolean or null")
        if not isinstance(self.is_new_valid_evaluation, bool):
            raise TypeError("is_new_valid_evaluation must be boolean")
        object.__setattr__(self, "w", _unit("w", self.w))
        if not isinstance(self.closing, bool):
            raise TypeError("closing must be boolean")
        self._validate_evaluation_metadata()

    @property
    def evaluation_present(self) -> bool:
        return self.evaluation_id is not None

    def _validate_evaluation_metadata(self) -> None:
        fields = (
            self.evaluation_id,
            self.evaluation_kind,
            self.evaluation_quality,
            self.evaluation_is_valid,
        )
        if self.evaluation_id is None:
            if any(value is not None for value in fields[1:]):
                raise ValueError("absent evaluation cannot carry metadata")
            if self.bundle_index is not None:
                raise ValueError("absent evaluation cannot carry bundle_index")
            if self.is_new_valid_evaluation:
                raise ValueError("absent evaluation cannot be a new valid evaluation")
            return
        if any(value is None for value in fields[1:]):
            raise ValueError("present evaluation requires complete metadata")
        if self.evaluation_kind not in {"baseline", "bundle"}:
            raise ValueError("evaluation_kind must be baseline or bundle")
        if self.evaluation_quality not in {"valid", "low_confidence", "rejected"}:
            raise ValueError("evaluation_quality is not recognized")
        if self.evaluation_kind == "baseline" and self.bundle_index is not None:
            raise ValueError("baseline evaluation cannot have bundle_index")
        if self.evaluation_kind == "bundle" and self.bundle_index is None:
            raise ValueError("bundle evaluation requires bundle_index")
        expected_valid = self.evaluation_quality != "rejected"
        if self.evaluation_is_valid != expected_valid:
            raise ValueError("evaluation quality and validity are inconsistent")
        if self.is_new_valid_evaluation != expected_valid:
            raise ValueError("new-valid flag and evaluation validity are inconsistent")


@dataclass(frozen=True, slots=True)
class RelationMemoryTransitionResult:
    persistent_state: RelationMemoryPersistentState
    session_state: RelationMemorySessionState
    k_current_before: KVector
    k_current_after: KVector
    record: RelationMemoryTransitionRecord | None
    candidate_generated: bool
    k_anchor_updated: bool
    session_finalized: bool


def current_relation_k(
    persistent_state: RelationMemoryPersistentState,
    session_state: RelationMemorySessionState,
) -> KVector:
    """Derive the presentation position without introducing a second mutable state."""

    if session_state.adaptation_phase in {
        "trial",
        "confirmation",
        "trial_unconfirmed",
    }:
        if session_state.k_trial is None:
            raise RuntimeError("trial phase has no k_trial")
        return session_state.k_trial
    return persistent_state.k_anchor


def apply_relation_memory_transition(
    persistent_state: RelationMemoryPersistentState,
    session_state: RelationMemorySessionState,
    transition_input: RelationMemoryTransitionInput,
) -> RelationMemoryTransitionResult:
    """Apply the unchanged v2.0 reference transition with sigma multiplier 1.0."""

    return _apply_relation_memory_transition(
        persistent_state,
        session_state,
        transition_input,
        sigma_multiplier=1.0,
    )


def apply_relation_memory_transition_with_sigma_multiplier(
    persistent_state: RelationMemoryPersistentState,
    session_state: RelationMemorySessionState,
    transition_input: RelationMemoryTransitionInput,
    *,
    sigma_multiplier: object,
) -> RelationMemoryTransitionResult:
    """Apply the Stage 8A.1 experimental scale only to reference sigma."""

    return _apply_relation_memory_transition(
        persistent_state,
        session_state,
        transition_input,
        sigma_multiplier=_experimental_sigma_multiplier(sigma_multiplier),
    )


def _apply_relation_memory_transition(
    persistent_state: RelationMemoryPersistentState,
    session_state: RelationMemorySessionState,
    transition_input: RelationMemoryTransitionInput,
    *,
    sigma_multiplier: float,
) -> RelationMemoryTransitionResult:
    """Return new immutable states; mutate neither input nor any external component."""

    _validate_state_identity(persistent_state, session_state, transition_input)
    if session_state.session_finalized:
        raise RuntimeError("relation-memory session was already finalized")

    k_current_before = current_relation_k(persistent_state, session_state)
    if not transition_input.evaluation_present and not transition_input.closing:
        return RelationMemoryTransitionResult(
            persistent_state=persistent_state,
            session_state=session_state,
            k_current_before=k_current_before,
            k_current_after=k_current_before,
            record=None,
            candidate_generated=False,
            k_anchor_updated=False,
            session_finalized=False,
        )

    profile = derive_relation_memory_intrinsic_profile(
        persistent_state.digital_life_id
    )
    persistent_after = persistent_state
    session_after = session_state
    candidate_generated = False
    provisional_condition: bool | None = None
    confirmation_condition_1: bool | None = None
    confirmation_condition_2: bool | None = None
    candidate_mean_w: float | None = None

    if (
        transition_input.evaluation_present
        and transition_input.evaluation_kind == "bundle"
    ):
        assert transition_input.bundle_index is not None
        if transition_input.bundle_index == 0:
            (
                persistent_after,
                session_after,
                candidate_generated,
            ) = _apply_bundle_zero(
                persistent_after,
                session_after,
                transition_input,
                profile,
                sigma_multiplier,
            )
        elif transition_input.bundle_index == 1:
            (
                persistent_after,
                session_after,
                provisional_condition,
            ) = _apply_bundle_one(
                persistent_after,
                session_after,
                transition_input,
            )
        else:
            (
                persistent_after,
                session_after,
                confirmation_condition_1,
                confirmation_condition_2,
                candidate_mean_w,
            ) = _apply_bundle_two(
                persistent_after,
                session_after,
                transition_input,
            )
        # A baseline evaluation is deliberately audit-only: W=0.5 is not anchor W.

    k_trial_for_audit = session_after.k_trial
    if transition_input.closing:
        persistent_after, session_after = _finalize_session(
            persistent_after,
            session_after,
        )

    k_current_after = current_relation_k(persistent_after, session_after)
    direction = _session_direction(session_after)
    record = RelationMemoryTransitionRecord(
        transition_index=transition_input.transition_index,
        signal_index=transition_input.signal_index,
        signal_time_us=transition_input.signal_time_us,
        digital_life_id=transition_input.digital_life_id,
        g=transition_input.g,
        bundle_index=transition_input.bundle_index,
        evaluation_id=transition_input.evaluation_id,
        evaluation_quality=transition_input.evaluation_quality,
        evaluation_is_valid=transition_input.evaluation_is_valid,
        w=(transition_input.w if transition_input.evaluation_is_valid is True else None),
        phase_before=session_state.adaptation_phase,
        phase_after=session_after.adaptation_phase,
        exploration_decision=session_after.exploration_decision,
        curiosity=profile.curiosity,
        sigma_min=profile.sigma_min,
        sigma_max=profile.sigma_max,
        sigma=session_after.sigma,
        epsilon_accept=profile.epsilon_accept,
        p_explore_min=profile.p_explore_min,
        p_explore=session_after.p_explore,
        u_explore=session_after.u_explore,
        direction_trial_index=(
            None if direction is None else direction.trial_index_used
        ),
        direction_u_f=None if direction is None else direction.u_f,
        direction_u_t=None if direction is None else direction.u_t,
        direction_norm=None if direction is None else direction.norm,
        direction_xi=None if direction is None else direction.xi,
        k_anchor_before=persistent_state.k_anchor,
        k_current_before=k_current_before,
        k_trial=k_trial_for_audit,
        k_current_after=k_current_after,
        k_anchor_after=persistent_after.k_anchor,
        w_anchor_session_before=session_state.w_anchor_session,
        w_anchor_session_after=session_after.w_anchor_session,
        w_trial_1_before=session_state.w_trial_1,
        w_trial_1_after=session_after.w_trial_1,
        w_trial_2_before=session_state.w_trial_2,
        w_trial_2_after=session_after.w_trial_2,
        provisional_condition=provisional_condition,
        confirmation_condition_1=confirmation_condition_1,
        confirmation_condition_2=confirmation_condition_2,
        candidate_mean_w=candidate_mean_w,
        trial_count_before=persistent_state.trial_count,
        trial_count_after=persistent_after.trial_count,
        session_count_used=session_state.session_count_used,
        session_count_after=persistent_after.session_count,
        adoption_result=session_after.adoption_result,
        rollback_reason=session_after.rollback_reason,
        candidate_effective_signal_index=(
            session_after.candidate_effective_signal_index
        ),
    )
    return RelationMemoryTransitionResult(
        persistent_state=persistent_after,
        session_state=session_after,
        k_current_before=k_current_before,
        k_current_after=k_current_after,
        record=record,
        candidate_generated=candidate_generated,
        k_anchor_updated=persistent_after.k_anchor != persistent_state.k_anchor,
        session_finalized=(
            session_after.session_finalized and not session_state.session_finalized
        ),
    )


def _apply_bundle_zero(
    persistent: RelationMemoryPersistentState,
    session: RelationMemorySessionState,
    item: RelationMemoryTransitionInput,
    profile: RelationMemoryIntrinsicProfile,
    sigma_multiplier: float,
) -> tuple[RelationMemoryPersistentState, RelationMemorySessionState, bool]:
    if session.adaptation_phase != "anchor_evaluation":
        raise RuntimeError(
            "Bundle 0 evaluation arrived after the one-candidate decision boundary"
        )
    if item.g == 0:
        return (
            persistent,
            replace(
                session,
                adaptation_phase="completed_non_holder",
                adoption_result="non_holder_no_adaptation",
            ),
            False,
        )
    if item.evaluation_is_valid is not True:
        return (
            persistent,
            replace(
                session,
                adaptation_phase="hold",
                exploration_decision="hold",
                adoption_result="bundle0_evaluation_rejected",
            ),
            False,
        )

    sigma_reference = exploration_sigma(item.w, profile.sigma_min, profile.sigma_max)
    sigma = sigma_multiplier * sigma_reference
    probability = exploration_probability(item.w, profile.p_explore_min)
    u_explore = hash01(
        item.digital_life_id,
        "C",
        "explore",
        session.session_count_used,
    )
    decision = exploration_decision(u_explore, probability)
    base_changes = {
        "w_anchor_session": item.w,
        "anchor_evaluated": True,
        "sigma": sigma,
        "p_explore": probability,
        "u_explore": u_explore,
        "exploration_decision": decision,
    }
    if decision == "hold":
        return (
            persistent,
            replace(
                session,
                **base_changes,
                adaptation_phase="hold",
                adoption_result="hold",
            ),
            False,
        )

    trial_index = persistent.trial_count
    direction = derive_search_direction(item.digital_life_id, trial_index)
    candidate = generate_candidate(persistent.k_anchor, sigma, direction)
    persistent_after = replace(persistent, trial_count=trial_index + 1)
    session_after = replace(
        session,
        **base_changes,
        adaptation_phase="trial",
        k_trial=candidate,
        direction_xi=direction.xi,
        candidate_generated=True,
        candidate_generation_trial_index=trial_index,
        candidate_effective_signal_index=item.signal_index + 1,
    )
    return persistent_after, session_after, True


def _apply_bundle_one(
    persistent: RelationMemoryPersistentState,
    session: RelationMemorySessionState,
    item: RelationMemoryTransitionInput,
) -> tuple[RelationMemoryPersistentState, RelationMemorySessionState, bool | None]:
    if item.g == 0 or session.adaptation_phase in {
        "hold",
        "completed_non_holder",
        "completed_bundle0_rejected",
    }:
        return persistent, session, None
    if session.adaptation_phase != "trial":
        raise RuntimeError("Bundle 1 evaluation arrived outside trial/hold state")
    if item.evaluation_is_valid is not True:
        return (
            persistent,
            replace(
                session,
                adaptation_phase="trial_unconfirmed",
                adoption_result="unconfirmed_evaluation_reject",
                rollback_reason=None,
            ),
            None,
        )
    if session.w_anchor_session is None or session.k_trial is None:
        raise RuntimeError("trial evaluation requires anchor W and k_trial")
    provisional = item.w > session.w_anchor_session + session.epsilon_accept
    if provisional:
        return (
            persistent,
            replace(
                session,
                w_trial_1=item.w,
                valid_trial_evaluation_count=1,
                adaptation_phase="confirmation",
                rollback_reason=None,
            ),
            True,
        )
    return (
        persistent,
        replace(
            session,
            w_trial_1=item.w,
            valid_trial_evaluation_count=1,
            adaptation_phase="return_anchor",
            adoption_result="rejected_bundle1_threshold",
            rollback_reason=None,
        ),
        False,
    )


def _apply_bundle_two(
    persistent: RelationMemoryPersistentState,
    session: RelationMemorySessionState,
    item: RelationMemoryTransitionInput,
) -> tuple[
    RelationMemoryPersistentState,
    RelationMemorySessionState,
    bool | None,
    bool | None,
    float | None,
]:
    if item.g == 0 or session.adaptation_phase in {
        "hold",
        "completed_non_holder",
        "completed_bundle0_rejected",
    }:
        return persistent, session, None, None, None
    if session.adaptation_phase == "return_anchor":
        if item.evaluation_is_valid is True:
            session = replace(
                session,
                anchor_return_w=item.w,
                w_anchor_session=item.w,
                anchor_evaluated=True,
            )
        return persistent, session, None, None, None
    if session.adaptation_phase == "trial_unconfirmed":
        session = replace(
            session,
            w_trial_2=(item.w if item.evaluation_is_valid is True else None),
            valid_trial_evaluation_count=(
                1 if item.evaluation_is_valid is True else 0
            ),
            adaptation_phase="rejected",
            adoption_result="unconfirmed_evaluation_reject",
            rollback_reason="fewer_than_two_valid_trial_evaluations",
        )
        return persistent, session, None, None, None
    if session.adaptation_phase != "confirmation":
        raise RuntimeError("Bundle 2 evaluation arrived outside a valid final phase")
    if item.evaluation_is_valid is not True:
        return (
            persistent,
            replace(
                session,
                adaptation_phase="rejected",
                adoption_result="unconfirmed_evaluation_reject",
                rollback_reason="bundle2_evaluation_rejected",
            ),
            None,
            None,
            None,
        )
    if (
        session.w_anchor_session is None
        or session.w_trial_1 is None
        or session.k_trial is None
    ):
        raise RuntimeError("confirmation requires anchor, first trial W, and k_trial")
    candidate_mean = (session.w_trial_1 + item.w) / 2.0
    condition_one = item.w > session.w_anchor_session
    condition_two = (
        candidate_mean > session.w_anchor_session + session.epsilon_accept
    )
    if condition_one and condition_two:
        return (
            replace(persistent, k_anchor=session.k_trial),
            replace(
                session,
                w_trial_2=item.w,
                valid_trial_evaluation_count=2,
                adaptation_phase="accepted",
                adoption_result="accepted",
                rollback_reason=None,
            ),
            condition_one,
            condition_two,
            candidate_mean,
        )
    return (
        persistent,
        replace(
            session,
            w_trial_2=item.w,
            valid_trial_evaluation_count=2,
            adaptation_phase="rejected",
            adoption_result="rejected_after_confirmation",
            rollback_reason="confirmation_conditions_not_met",
        ),
        condition_one,
        condition_two,
        candidate_mean,
    )


def _finalize_session(
    persistent: RelationMemoryPersistentState,
    session: RelationMemorySessionState,
) -> tuple[RelationMemoryPersistentState, RelationMemorySessionState]:
    phase = session.adaptation_phase
    adoption = session.adoption_result
    rollback = session.rollback_reason
    if phase in {"trial", "confirmation"}:
        phase = "rejected"
        adoption = "rolled_back_at_session_end"
        rollback = "unresolved_candidate_at_session_end"
    elif phase == "trial_unconfirmed":
        phase = "rejected"
        adoption = "unconfirmed_evaluation_reject"
        rollback = "fewer_than_two_valid_trial_evaluations"
    elif adoption == "bundle0_evaluation_rejected":
        phase = "completed_bundle0_rejected"
    elif phase == "anchor_evaluation":
        phase = "hold"
        adoption = "no_candidate"
    persistent_after = replace(
        persistent,
        session_count=persistent.session_count + 1,
    )
    session_after = replace(
        session,
        k_trial=None,
        adaptation_phase=phase,
        adoption_result=adoption,
        rollback_reason=rollback,
        session_finalized=True,
    )
    return persistent_after, session_after


def _session_direction(
    session: RelationMemorySessionState,
) -> RelationMemorySearchDirection | None:
    if session.candidate_generation_trial_index is None:
        return None
    return derive_search_direction(
        session.digital_life_id,
        session.candidate_generation_trial_index,
    )


def _validate_state_identity(
    persistent: RelationMemoryPersistentState,
    session: RelationMemorySessionState,
    item: RelationMemoryTransitionInput,
) -> None:
    if not isinstance(persistent, RelationMemoryPersistentState):
        raise TypeError("persistent_state must be a RelationMemoryPersistentState")
    if not isinstance(session, RelationMemorySessionState):
        raise TypeError("session_state must be a RelationMemorySessionState")
    if not isinstance(item, RelationMemoryTransitionInput):
        raise TypeError("transition_input must be a RelationMemoryTransitionInput")
    if not (
        persistent.digital_life_id
        == session.digital_life_id
        == item.digital_life_id
    ):
        raise ValueError("Digital Life IDs differ across transition inputs")
    if persistent.session_count != session.session_count_used:
        raise ValueError("persistent session_count changed during the active session")
    if persistent.k_anchor != session.initial_k_anchor and not session.candidate_generated:
        raise ValueError("k_anchor changed without a generated candidate")
    expected_epsilon = derive_relation_memory_intrinsic_profile(
        persistent.digital_life_id
    ).epsilon_accept
    if session.epsilon_accept != expected_epsilon:
        raise ValueError("session epsilon_accept differs from the intrinsic profile")


__all__ = [
    "RelationMemoryTransitionInput",
    "RelationMemoryTransitionResult",
    "apply_relation_memory_transition",
    "apply_relation_memory_transition_with_sigma_multiplier",
    "current_relation_k",
]
