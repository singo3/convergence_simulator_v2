"""Stage 5C connected Digital Life with private confirmed relation memory."""

from __future__ import annotations

from dataclasses import dataclass, replace

from symbiotic_sim_v2.digital_life.connected_component import (
    ConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.math import intrinsic_b_mapping
from symbiotic_sim_v2.digital_life.second_round import calculate_g
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.events import (
    parse_garden_interoceptive_feedback_event,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine

from .config import ADAPTIVE_DIGITAL_LIFE_MODEL_VERSION
from .intrinsic import (
    RelationMemoryIntrinsicProfile,
    derive_relation_memory_intrinsic_profile,
)
from .persistent_state import RelationMemoryPersistentState
from .records import (
    AdaptiveDigitalLifeSecondRoundRecord,
    AdaptiveDigitalLifeSignalRecord,
    RelationMemoryPersistentStateRecord,
    RelationMemorySessionStateRecord,
    RelationMemoryTransitionRecord,
    canonical_digest,
)
from .session_state import RelationMemorySessionState
from .transitions import (
    RelationMemoryTransitionInput,
    RelationMemoryTransitionResult,
    apply_relation_memory_transition,
    current_relation_k,
)

K_UPDATE_STATUS_UNCHANGED = "relation_anchor_unchanged"
K_UPDATE_STATUS_CURRENT_CHANGED = "relation_current_changed_next_signal"
K_UPDATE_STATUS_ANCHOR_ACCEPTED = "relation_anchor_accepted"


@dataclass(frozen=True, slots=True)
class _PendingAdaptiveSignal:
    k_anchor_before: tuple[float, float, float, float]
    k_current_before: tuple[float, float, float, float]
    relation_phase_before: str
    q_before: float
    e_before: float


class AdaptiveConnectedDigitalLifeComponent(ConnectedDigitalLifeComponent):
    """Extend the existing connected round without central candidate selection."""

    def __init__(
        self,
        config,
        initial_persistent_state: RelationMemoryPersistentState | None = None,
    ) -> None:
        selected = initial_persistent_state or RelationMemoryPersistentState.fresh(
            config.digital_life_id
        )
        self._injected_initial_persistent_state = self._validate_injected_state(
            config.digital_life_id,
            selected,
        )
        super().__init__(config)

    def reset(self) -> None:
        """Return to the constructor-injected state and clear only this session."""

        super().reset()
        self._initialize_relation_session(self._injected_initial_persistent_state)

    def reset_session(
        self,
        persistent_state: RelationMemoryPersistentState,
    ) -> None:
        """Install an explicit Stage 8 handoff state, then start one fresh session."""

        self._injected_initial_persistent_state = self._validate_injected_state(
            self.config.digital_life_id,
            persistent_state,
        )
        self.reset()

    def begin_signal(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ):
        """Present the pre-transition k and defer any relation update to feedback."""

        if self._pending_adaptive_signal is not None:
            raise RuntimeError("previous adaptive signal record is incomplete")
        expected_current = current_relation_k(
            self._working_persistent_state,
            self._relation_session_state,
        )
        if expected_current != self._state.k_current:
            raise RuntimeError("relation-memory k differs from Digital Life state")
        context = _PendingAdaptiveSignal(
            k_anchor_before=self._working_persistent_state.k_anchor,
            k_current_before=expected_current,
            relation_phase_before=self._relation_session_state.adaptation_phase,
            q_before=self._state.q,
            e_before=self._state.e,
        )
        intent = super().begin_signal(event, engine)
        pending = self._pending_second_round
        if pending is None:
            raise RuntimeError("adaptive first round did not create pending feedback")
        if pending.first_round.k_current != expected_current:
            raise RuntimeError("first-round B did not use the pre-transition k")
        self._pending_adaptive_signal = context
        return intent

    handle_garden_input_signal = begin_signal

    def handle_interoceptive_feedback(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Compute E, q, and relation memory from one common before-state."""

        feedback = parse_garden_interoceptive_feedback_event(event)
        pending = self._require_pending(feedback.signal_index)
        context = self._pending_adaptive_signal
        if context is None:
            raise RuntimeError("feedback has no pending adaptive signal context")
        metadata = pending.evaluation
        g = calculate_g(
            self.config.digital_life_id,
            feedback.qualification_holder_id,
        )
        transition_input = RelationMemoryTransitionInput(
            transition_index=len(self._relation_transition_records),
            signal_index=pending.signal.signal_index,
            signal_time_us=pending.signal.signal_time_us,
            digital_life_id=self.config.digital_life_id,
            g=g,
            bundle_index=None if metadata is None else metadata.bundle_index,
            evaluation_id=None if metadata is None else metadata.evaluation_id,
            evaluation_kind=None if metadata is None else metadata.evaluation_kind,
            evaluation_quality=None if metadata is None else metadata.quality,
            evaluation_is_valid=None if metadata is None else metadata.is_valid,
            is_new_valid_evaluation=pending.first_round.is_new_valid_evaluation,
            w=pending.first_round.w,
            closing=feedback.closing_evaluation_attribution,
        )
        relation_result = self._transition_relation_memory(
            self._working_persistent_state,
            self._relation_session_state,
            transition_input,
        )

        # The inherited handler validates B attribution and computes E/q.  No
        # observer can interleave inside this synchronous event handler, so the
        # subsequent k assignment is one atomic second-round boundary.
        super().handle_interoceptive_feedback(event, engine)
        base_record = self._second_round_records[-1]
        working_after = replace(
            relation_result.persistent_state,
            q=self._state.q,
            e=self._state.e,
        )
        k_current_after = relation_result.k_current_after
        k_anchor_after = working_after.k_anchor
        current_changed = k_current_after != context.k_current_before
        anchor_changed = k_anchor_after != context.k_anchor_before
        if current_changed:
            self._k_current_transition_count += 1
        if anchor_changed:
            self._k_anchor_update_count += 1
            self._k_update_count += 1
        if relation_result.candidate_generated:
            self._candidate_count += 1

        self._working_persistent_state = working_after
        self._relation_session_state = relation_result.session_state
        self._state.k_anchor = k_anchor_after
        self._state.k_current = k_current_after
        # Intentionally retain self._state.b from the first round.  The new k is
        # mapped to B only by the next GardenInputSignalEvent.

        if anchor_changed:
            k_status = K_UPDATE_STATUS_ANCHOR_ACCEPTED
        elif current_changed:
            k_status = K_UPDATE_STATUS_CURRENT_CHANGED
        else:
            k_status = K_UPDATE_STATUS_UNCHANGED
        self._second_round_records[-1] = replace(
            base_record,
            k_after=k_current_after,
            k_update_status=k_status,
        )

        transition_record = relation_result.record
        transition_index = None
        if transition_record is not None:
            transition_index = transition_record.transition_index
            self._relation_transition_records.append(transition_record)
            self._relation_session_state_records.append(
                self._session_state_record(
                    transition_record.signal_index,
                    transition_record.signal_time_us,
                )
            )

        first_round = pending.first_round
        adaptive_second_round = AdaptiveDigitalLifeSecondRoundRecord(
            signal_index=first_round.signal_index,
            signal_time_us=first_round.signal_time_us,
            digital_life_id=self.config.digital_life_id,
            g=g,
            evaluation_id=None if metadata is None else metadata.evaluation_id,
            evaluation_quality=None if metadata is None else metadata.quality,
            is_new_valid_evaluation=first_round.is_new_valid_evaluation,
            w=first_round.w,
            q_before=context.q_before,
            q_after=self._state.q,
            e_before=context.e_before,
            e_after=self._state.e,
            k_anchor_before=context.k_anchor_before,
            k_current_before=context.k_current_before,
            k_current_after=k_current_after,
            k_anchor_after=k_anchor_after,
            relation_phase_before=context.relation_phase_before,
            relation_phase_after=self._relation_session_state.adaptation_phase,
            relation_transition_index=transition_index,
            closing_evaluation_attribution=feedback.closing_evaluation_attribution,
        )
        self._adaptive_second_round_records.append(adaptive_second_round)
        self._adaptive_signal_records.append(
            AdaptiveDigitalLifeSignalRecord(
                signal_index=first_round.signal_index,
                signal_time_us=first_round.signal_time_us,
                digital_life_id=self.config.digital_life_id,
                role=self.config.role,
                s=first_round.s,
                bundle_index=first_round.bundle_index,
                phase=first_round.phase,
                evaluation_id=None if metadata is None else metadata.evaluation_id,
                evaluation_quality=None if metadata is None else metadata.quality,
                is_new_valid_evaluation=first_round.is_new_valid_evaluation,
                g=g,
                w=first_round.w,
                k_anchor_before=context.k_anchor_before,
                k_current_before=context.k_current_before,
                k_presented=first_round.k_current,
                b_presented=(
                    first_round.b_f,
                    first_round.b_a,
                    first_round.b_t,
                    first_round.b_d,
                ),
                relation_phase_before=context.relation_phase_before,
                relation_phase_after=self._relation_session_state.adaptation_phase,
                k_current_after=k_current_after,
                k_anchor_after=k_anchor_after,
                candidate_effective_next_signal=(
                    relation_result.candidate_generated
                ),
                q_before=context.q_before,
                q_after=self._state.q,
                e_before=context.e_before,
                e_after=self._state.e,
            )
        )
        self._pending_adaptive_signal = None

        if relation_result.session_finalized:
            if not feedback.closing_evaluation_attribution:
                raise RuntimeError("relation session finalized outside closing feedback")
            self._handle_finalized_relation_state(working_after)

    def _transition_relation_memory(
        self,
        persistent_state: RelationMemoryPersistentState,
        session_state: RelationMemorySessionState,
        transition_input: RelationMemoryTransitionInput,
    ) -> RelationMemoryTransitionResult:
        """Use the exact reference transition unless an experimental life overrides it."""

        return apply_relation_memory_transition(
            persistent_state,
            session_state,
            transition_input,
        )

    def _handle_finalized_relation_state(
        self,
        state: RelationMemoryPersistentState,
    ) -> None:
        """Commit the reference final state immediately at its closing feedback."""

        self._commit_final_persistent_state(state)

    def _commit_final_persistent_state(
        self,
        state: RelationMemoryPersistentState,
    ) -> None:
        """Publish one validated final state and exactly one final audit record."""

        if self._final_persistent_state is not None:
            raise RuntimeError("relation-memory final state was already committed")
        if not self._relation_session_state.session_finalized:
            raise RuntimeError("cannot commit state before relation session finalization")
        if state != self._working_persistent_state:
            raise RuntimeError("final state must equal the component working state")
        self._final_persistent_state = state
        self._persistent_state_records.append(
            self._persistent_state_record("final", state)
        )

    def relation_memory_intrinsic_profile(self) -> RelationMemoryIntrinsicProfile:
        return self._relation_intrinsic_profile

    def relation_memory_session_state(self) -> RelationMemorySessionState:
        return self._relation_session_state

    def relation_memory_transition_records(
        self,
    ) -> tuple[RelationMemoryTransitionRecord, ...]:
        return tuple(self._relation_transition_records)

    def adaptive_signal_records(self) -> tuple[AdaptiveDigitalLifeSignalRecord, ...]:
        return tuple(self._adaptive_signal_records)

    def adaptive_second_round_records(
        self,
    ) -> tuple[AdaptiveDigitalLifeSecondRoundRecord, ...]:
        return tuple(self._adaptive_second_round_records)

    def persistent_state_records(
        self,
    ) -> tuple[RelationMemoryPersistentStateRecord, ...]:
        return tuple(self._persistent_state_records)

    def session_state_records(
        self,
    ) -> tuple[RelationMemorySessionStateRecord, ...]:
        return tuple(self._relation_session_state_records)

    def initial_persistent_state(self) -> RelationMemoryPersistentState:
        return self._initial_persistent_state

    def current_persistent_state(self) -> RelationMemoryPersistentState:
        return self._working_persistent_state

    def final_persistent_state(self) -> RelationMemoryPersistentState | None:
        return self._final_persistent_state

    def candidate_count(self) -> int:
        return self._candidate_count

    def k_current_transition_count(self) -> int:
        return self._k_current_transition_count

    def k_anchor_update_count(self) -> int:
        return self._k_anchor_update_count

    def relation_memory_transition_digest(self) -> str:
        return canonical_digest(self._relation_transition_records)

    def adaptive_signal_digest(self) -> str:
        return canonical_digest(self._adaptive_signal_records)

    def persistent_state_digest(self) -> str:
        state = self._final_persistent_state or self._working_persistent_state
        return canonical_digest(state)

    def snapshot(self):
        return replace(
            super().connected_snapshot(),
            model_version=ADAPTIVE_DIGITAL_LIFE_MODEL_VERSION,
            k_update_count=self._k_anchor_update_count,
        )

    def _initialize_relation_session(
        self,
        initial_state: RelationMemoryPersistentState,
    ) -> None:
        self._initial_persistent_state = initial_state
        self._working_persistent_state = initial_state
        self._final_persistent_state: RelationMemoryPersistentState | None = None
        self._relation_intrinsic_profile = (
            derive_relation_memory_intrinsic_profile(initial_state.digital_life_id)
        )
        self._relation_session_state = RelationMemorySessionState.fresh(initial_state)
        self._relation_transition_records: list[RelationMemoryTransitionRecord] = []
        self._adaptive_signal_records: list[AdaptiveDigitalLifeSignalRecord] = []
        self._adaptive_second_round_records: list[
            AdaptiveDigitalLifeSecondRoundRecord
        ] = []
        self._relation_session_state_records: list[
            RelationMemorySessionStateRecord
        ] = []
        self._persistent_state_records = [
            self._persistent_state_record("initial", initial_state)
        ]
        self._pending_adaptive_signal: _PendingAdaptiveSignal | None = None
        self._candidate_count = 0
        self._k_current_transition_count = 0
        self._k_anchor_update_count = 0
        self._state.q = initial_state.q
        self._state.e = initial_state.e
        self._state.k_anchor = initial_state.k_anchor
        self._state.k_current = initial_state.k_anchor
        self._state.b = intrinsic_b_mapping(
            initial_state.k_anchor,
            f_min=self.config.f_min,
            f_max=self.config.f_max,
            a_fixed=self.config.a_fixed,
            t_min=self.config.t_min,
            t_max=self.config.t_max,
            d_fixed=self.config.d_fixed,
        )

    def _persistent_state_record(
        self,
        position: str,
        state: RelationMemoryPersistentState,
    ) -> RelationMemoryPersistentStateRecord:
        return RelationMemoryPersistentStateRecord(
            record_index=len(self._persistent_state_records)
            if hasattr(self, "_persistent_state_records")
            else 0,
            state_position=position,
            digital_life_id=state.digital_life_id,
            k_anchor=state.k_anchor,
            q=state.q,
            e=state.e,
            trial_count=state.trial_count,
            session_count=state.session_count,
        )

    def _session_state_record(
        self,
        signal_index: int,
        signal_time_us: int,
    ) -> RelationMemorySessionStateRecord:
        state = self._relation_session_state
        return RelationMemorySessionStateRecord(
            record_index=len(self._relation_session_state_records),
            signal_index=signal_index,
            signal_time_us=signal_time_us,
            **state.to_dict(),
        )

    @staticmethod
    def _validate_injected_state(
        digital_life_id: str,
        state: RelationMemoryPersistentState,
    ) -> RelationMemoryPersistentState:
        if not isinstance(state, RelationMemoryPersistentState):
            raise TypeError(
                "initial_persistent_state must be a RelationMemoryPersistentState"
            )
        if state.digital_life_id != digital_life_id:
            raise ValueError("persistent state ID does not match Digital Life config")
        return state


__all__ = [
    "AdaptiveConnectedDigitalLifeComponent",
    "K_UPDATE_STATUS_ANCHOR_ACCEPTED",
    "K_UPDATE_STATUS_CURRENT_CHANGED",
    "K_UPDATE_STATUS_UNCHANGED",
]
