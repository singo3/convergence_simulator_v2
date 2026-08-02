"""Stage 5B connected Digital Life with an independent live second round."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace

from symbiotic_sim_v2.digital_life.component import (
    GardenEvaluationMetadata,
    GardenInputSignalInput,
    SingleDigitalLifeComponent,
    parse_garden_evaluation_finalized_event,
    parse_garden_input_signal_event,
)
from symbiotic_sim_v2.digital_life.config import (
    DIGITAL_LIFE_MODEL_VERSION,
    DigitalLifeConfig,
)
from symbiotic_sim_v2.digital_life.math import calculate_e_next
from symbiotic_sim_v2.digital_life.records import DigitalLifeFirstRoundRecord
from symbiotic_sim_v2.digital_life.second_round import calculate_g, decide_q_update
from symbiotic_sim_v2.digital_life.second_round_records import (
    DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION,
    K_UPDATE_STATUS_DEFERRED,
    ConnectedDigitalLifeSnapshot,
    DigitalLifeSecondRoundRecord,
)
from symbiotic_sim_v2.digital_life.touch_intent import DigitalLifeTouchIntent
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.events import (
    parse_garden_interoceptive_feedback_event,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine

G_STATUS_CONNECTED = "connected"


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class _PendingSecondRound:
    signal: GardenInputSignalInput
    first_round: DigitalLifeFirstRoundRecord
    evaluation: GardenEvaluationMetadata | None
    touch_intent: DigitalLifeTouchIntent | None
    touch_dispatched: bool = False


class ConnectedDigitalLifeComponent(SingleDigitalLifeComponent):
    """Reuse Stage 5A's first round and connect only this life's own feedback."""

    def __init__(self, config: DigitalLifeConfig) -> None:
        super().__init__(config)

    def reset(self) -> None:
        """Restore one independent connected state and clear pending round data."""

        super().reset()
        # Ensure each life owns distinct tuple objects even though k is immutable.
        self._state.k_anchor = tuple([*self._state.k_anchor])
        self._state.k_current = tuple([*self._state.k_current])
        self._state.second_round_connected = True
        self._state.g_status = G_STATUS_CONNECTED
        self._pending_second_round: _PendingSecondRound | None = None
        self._second_round_records: list[DigitalLifeSecondRoundRecord] = []
        self._latest_seen_evaluation: GardenEvaluationMetadata | None = None
        self._qualification_holder_id: str | None = None
        self._current_g = 0
        self._latest_touch_time_us: int | None = None
        self._latest_returned_b: tuple[float, float, float, float] | None = None
        self._latest_attribution_source: str | None = None
        self._last_active_b: tuple[float, float, float, float] | None = None
        self._q_update_count = 0
        self._k_update_count = 0

    def handle_evaluation_finalized(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        metadata = parse_garden_evaluation_finalized_event(event)
        super().handle_evaluation_finalized(event, engine)
        self._latest_seen_evaluation = metadata

    def begin_signal(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> DigitalLifeTouchIntent | None:
        """Complete this life's first round and expose only its own touch intent."""

        if self._pending_second_round is not None:
            raise RuntimeError("previous Digital Life second round is incomplete")
        signal = parse_garden_input_signal_event(event)
        super().handle_garden_input_signal(event, engine)
        first_round = replace(
            self._first_round_records[-1],
            second_round_connected=True,
            g_status=G_STATUS_CONNECTED,
        )
        self._first_round_records[-1] = first_round
        evaluation = self._evaluation_for_signal(signal, first_round)
        intent = None
        if first_round.touch_enabled:
            if first_round.tau is None or first_round.v is None or signal.s != 1:
                raise RuntimeError("enabled touch has inconsistent first-round values")
            intent = DigitalLifeTouchIntent(
                signal_index=signal.signal_index,
                signal_time_us=signal.signal_time_us,
                digital_life_id=self.config.digital_life_id,
                role=self.config.role,
                b=(
                    first_round.b_f,
                    first_round.b_a,
                    first_round.b_t,
                    first_round.b_d,
                ),
                tau=first_round.tau,
                touch_enabled=True,
            )
        self._pending_second_round = _PendingSecondRound(
            signal=signal,
            first_round=first_round,
            evaluation=evaluation,
            touch_intent=intent,
        )
        return intent

    # Handler-shaped alias used by focused tests and alternative coordinators.
    handle_garden_input_signal = begin_signal

    def pending_touch_intent(self) -> DigitalLifeTouchIntent | None:
        pending = self._pending_second_round
        return None if pending is None else pending.touch_intent

    def mark_touch_dispatched(self, signal_index: int, arrival_time_us: int) -> None:
        """Record that Runtime scheduled this intent without exposing queue internals."""

        pending = self._require_pending(signal_index)
        if pending.touch_intent is None:
            raise ValueError("this signal has no enabled touch")
        if pending.touch_dispatched:
            raise ValueError("touch was already dispatched")
        arrival = _non_negative_int("arrival_time_us", arrival_time_us)
        if not pending.signal.signal_time_us < arrival < pending.signal.signal_time_us + 1_000_000:
            raise ValueError("touch arrival must remain inside its signal interval")
        first_round = replace(pending.first_round, touch_dispatched=True)
        self._first_round_records[-1] = first_round
        self._pending_second_round = replace(
            pending,
            first_round=first_round,
            touch_dispatched=True,
        )
        self._state.touch_dispatched_count += 1
        self._latest_touch_time_us = arrival
        self._last_active_b = pending.touch_intent.b

    def handle_interoceptive_feedback(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Calculate G locally, then update E and eligible q exactly once."""

        feedback = parse_garden_interoceptive_feedback_event(event)
        if feedback.recipient_digital_life_id != self.config.digital_life_id:
            raise ValueError("feedback recipient does not match this Digital Life")
        pending = self._require_pending(feedback.signal_index)
        if feedback.signal_time_us != pending.signal.signal_time_us:
            raise ValueError("feedback signal time does not match the pending round")
        if feedback.s != pending.signal.s:
            raise ValueError("feedback S does not match the pending round")

        expected_b: tuple[float, float, float, float] | None
        if feedback.s == 1:
            expected_b = (
                pending.first_round.b_f,
                pending.first_round.b_a,
                pending.first_round.b_t,
                pending.first_round.b_d,
            )
        elif feedback.closing_evaluation_attribution:
            expected_b = self._last_active_b
            if expected_b is None:
                raise RuntimeError("closing attribution has no last active touch B")
        else:
            expected_b = None
        if feedback.returned_b != expected_b:
            raise ValueError("returned B does not match this life's Garden touch B")

        g = calculate_g(
            self.config.digital_life_id,
            feedback.qualification_holder_id,
        )
        e_before = self._state.e
        q_before = self._state.q
        k_before = self._state.k_current
        e_after = calculate_e_next(e_before, feedback.s, g)
        q_after, q_applied, q_reason = self._calculate_q_update(pending, q_before, g)
        record = DigitalLifeSecondRoundRecord(
            signal_index=pending.signal.signal_index,
            signal_time_us=pending.signal.signal_time_us,
            digital_life_id=self.config.digital_life_id,
            role=self.config.role,
            s=feedback.s,
            qualification_holder_id=feedback.qualification_holder_id,
            g=g,
            first_round_b=(
                pending.first_round.b_f,
                pending.first_round.b_a,
                pending.first_round.b_t,
                pending.first_round.b_d,
            ),
            returned_b=feedback.returned_b,
            b_match=True,
            attribution_source=feedback.attribution_source,
            is_new_valid_evaluation=pending.first_round.is_new_valid_evaluation,
            evaluation_id=(
                None if pending.evaluation is None else pending.evaluation.evaluation_id
            ),
            evaluation_kind=(
                None if pending.evaluation is None else pending.evaluation.evaluation_kind
            ),
            evaluation_quality=(
                None if pending.evaluation is None else pending.evaluation.quality
            ),
            w=pending.first_round.w,
            e_before=e_before,
            e_after=e_after,
            e_updated=True,
            q_before=q_before,
            q_after=q_after,
            q_update_applied=q_applied,
            q_skip_reason=q_reason,
            k_before=k_before,
            k_after=k_before,
            k_update_status=K_UPDATE_STATUS_DEFERRED,
            closing_evaluation_attribution=feedback.closing_evaluation_attribution,
            holder_release_pending=feedback.closing_evaluation_attribution,
            first_round_completed=True,
        )
        self._state.e = e_after
        self._state.q = q_after
        self._state.g_status = G_STATUS_CONNECTED
        self._qualification_holder_id = feedback.qualification_holder_id
        self._current_g = g
        self._latest_returned_b = feedback.returned_b
        self._latest_attribution_source = feedback.attribution_source
        if q_applied:
            self._q_update_count += 1
        self._second_round_records.append(record)
        self._pending_second_round = None

    def mark_holder_released(self) -> None:
        """Reflect the post-closing state after the priority-90 release event."""

        if self._pending_second_round is not None:
            raise RuntimeError("cannot release holder before this life's second round")
        if not self._second_round_records:
            raise RuntimeError("cannot release holder before any second round")
        if not self._second_round_records[-1].closing_evaluation_attribution:
            raise RuntimeError("holder release is only valid after closing attribution")
        self._qualification_holder_id = None
        self._current_g = 0

    def has_pending_second_round(self) -> bool:
        return self._pending_second_round is not None

    def second_round_records(self) -> tuple[DigitalLifeSecondRoundRecord, ...]:
        return tuple(self._second_round_records)

    def connected_snapshot(self) -> ConnectedDigitalLifeSnapshot:
        base = super().snapshot()
        pending = self._pending_second_round
        return ConnectedDigitalLifeSnapshot(
            digital_life_id=base.digital_life_id,
            role=base.role,
            model_version=DIGITAL_LIFE_MODEL_VERSION,
            n_current=base.n_current,
            n_baseline_session=base.n_baseline_session,
            baseline_initialized=base.baseline_initialized,
            nd=base.nd,
            w=base.w,
            p=base.p,
            p_intrinsic=base.p_intrinsic,
            e=base.e,
            q=base.q,
            v=base.v,
            k_anchor=base.k_anchor,
            k_current=base.k_current,
            b=base.b,
            tau=base.tau,
            birth_phase=base.birth_phase,
            last_signal_index=base.last_signal_index,
            last_revision=base.last_revision,
            latest_s=base.latest_s,
            latest_evaluation_id=base.latest_evaluation_id,
            qualification_holder_id=self._qualification_holder_id,
            current_g=self._current_g,
            holder_matches=self._current_g == 1,
            latest_touch_time_us=self._latest_touch_time_us,
            latest_returned_b=self._latest_returned_b,
            latest_attribution_source=self._latest_attribution_source,
            first_round_count=base.first_round_count,
            second_round_count=len(self._second_round_records),
            evaluation_update_count=base.evaluation_update_count,
            new_valid_evaluation_count=base.new_valid_evaluation_count,
            q_update_count=self._q_update_count,
            k_update_count=self._k_update_count,
            touch_dispatched_count=self._state.touch_dispatched_count,
            first_round_completed=base.first_round_count > 0,
            second_round_completed=(
                pending is None
                and len(self._second_round_records) == base.first_round_count
            ),
            pending_signal_index=(
                None if pending is None else pending.signal.signal_index
            ),
        )

    # Stage 5B callers use snapshot() naturally; Stage 5A keeps its original class.
    snapshot = connected_snapshot

    def second_round_digest(self) -> str:
        records = [
            {
                "signal": record.signal_index,
                "S": record.s,
                "holder": record.qualification_holder_id,
                "G": record.g,
                "W": record.w,
                "E_before": record.e_before,
                "E_after": record.e_after,
                "q_before": record.q_before,
                "q_after": record.q_after,
                "q_applied": record.q_update_applied,
                "q_reason": record.q_skip_reason,
                "B_match": record.b_match,
                "k_status": record.k_update_status,
            }
            for record in self._second_round_records
        ]
        canonical = json.dumps(
            records,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _evaluation_for_signal(
        self,
        signal: GardenInputSignalInput,
        first_round: DigitalLifeFirstRoundRecord,
    ) -> GardenEvaluationMetadata | None:
        metadata = self._latest_seen_evaluation
        if metadata is not None and metadata.event_time_us == signal.signal_time_us:
            if first_round.is_new_valid_evaluation:
                if not metadata.is_valid:
                    raise RuntimeError("new valid revision cannot use rejected metadata")
                if metadata.evaluation_id != first_round.source_evaluation_id:
                    raise RuntimeError("first-round evaluation metadata is inconsistent")
            return metadata
        if first_round.is_new_valid_evaluation:
            raise RuntimeError("new valid revision has no same-time evaluation metadata")
        return None

    def _calculate_q_update(
        self,
        pending: _PendingSecondRound,
        q_before: float,
        g: int,
    ) -> tuple[float, bool, str]:
        metadata = pending.evaluation
        decision = decide_q_update(
            q=q_before,
            w=pending.first_round.w,
            g=g,
            evaluation_present=metadata is not None,
            is_new_valid_evaluation=pending.first_round.is_new_valid_evaluation,
            evaluation_kind=None if metadata is None else metadata.evaluation_kind,
            evaluation_is_valid=None if metadata is None else metadata.is_valid,
        )
        return decision.q_after, decision.applied, decision.skip_reason

    def _require_pending(self, signal_index: int) -> _PendingSecondRound:
        index = _non_negative_int("signal_index", signal_index)
        pending = self._pending_second_round
        if pending is None:
            raise ValueError("feedback or touch has no pending Digital Life round")
        if pending.signal.signal_index != index:
            raise ValueError("signal index does not match the pending Digital Life round")
        return pending


def second_round_schema_version() -> str:
    """Small explicit accessor used by headless schema reporting."""

    return DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION
