"""GUI-independent Stage 5B Garden output qualification component."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.garden.output_layer.events import (
    GARDEN_HOLDER_RELEASE_EVENT_PRIORITY,
    GARDEN_HOLDER_RELEASE_EVENT_TYPE,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    GARDEN_OUTPUT_EVENT_SOURCE,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE,
    GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
    DigitalLifeTouchInput,
    parse_digital_life_touch_event,
)
from symbiotic_sim_v2.garden.output_layer.records import (
    BVector,
    GardenFeedbackRecord,
    GardenOutputSnapshot,
    GardenQualificationRecord,
    GardenQualifiedBRecord,
    GardenTouchRecord,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine

_ROLE_BY_ID = {
    "life-blue": "blue",
    "life-green": "green",
    "life-red": "red",
}
_KNOWN_SESSION_STATUSES = {"baseline", "active", "baseline_invalid", "completed"}
_FINALIZE_PAYLOAD_FIELDS = {"signal_index", "signal_time_us"}


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _binary_s(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("s must be an integer")
    if value not in (0, 1):
        raise ValueError("s must be 0 or 1")
    return value


@dataclass(frozen=True, slots=True)
class _PendingTouch:
    input: DigitalLifeTouchInput
    holder_before: str | None
    holder_after: str | None
    assigned: bool


@dataclass(slots=True)
class _RoundContext:
    signal_index: int
    signal_time_us: int
    s: int
    session_status: str
    closing_signal: bool
    round_finalize_time_us: int
    holder_before: str | None
    touches: list[_PendingTouch]


@dataclass(frozen=True, slots=True)
class _PendingClosingQualification:
    signal_index: int
    signal_time_us: int
    holder_before: str
    held_from_previous_signal: bool


class GardenOutputComponent:
    """Qualify solely from actual ID/B touch arrivals and emit formal feedback."""

    def __init__(self, config: GardenOutputConfig | None = None) -> None:
        self.config = config or GardenOutputConfig()
        if not isinstance(self.config, GardenOutputConfig):
            raise TypeError("config must be a GardenOutputConfig")
        self.reset()

    def reset(self) -> None:
        """Restore an empty Garden qualification session."""

        self._qualification_holder_id: str | None = None
        self._last_assigned_holder_id: str | None = None
        self._qualification_assigned_signal_index: int | None = None
        self._qualification_assignment_time_us: int | None = None
        self._current_round: _RoundContext | None = None
        self._pending_closing: _PendingClosingQualification | None = None
        self._latest_active_b_by_life: dict[str, BVector] = {}
        self._touch_records: list[GardenTouchRecord] = []
        self._qualification_records: list[GardenQualificationRecord] = []
        self._qualified_b_records: list[GardenQualifiedBRecord] = []
        self._feedback_records: list[GardenFeedbackRecord] = []
        self._current_signal_index: int | None = None
        self._current_signal_time_us: int | None = None
        self._current_s: int | None = None
        self._last_started_signal_index: int | None = None
        self._last_started_signal_time_us: int | None = None
        self._latest_qualified_b: BVector | None = None
        self._latest_touch_order: tuple[str, ...] = ()
        self._active_output_count = 0
        self._inactive_output_count = 0
        self._assignment_count = 0
        self._release_count = 0
        self._incomplete_round_count = 0

    def begin_round(
        self,
        *,
        signal_index: int,
        signal_time_us: int,
        s: int,
        session_status: str,
        closing_signal: bool,
        round_finalize_time_us: int,
    ) -> None:
        """Open exactly one round using only the permitted Runtime metadata."""

        index = _non_negative_int("signal_index", signal_index)
        time_us = _non_negative_int("signal_time_us", signal_time_us)
        binary_s = _binary_s(s)
        finalize_time_us = _non_negative_int(
            "round_finalize_time_us", round_finalize_time_us
        )
        if not isinstance(session_status, str) or session_status not in _KNOWN_SESSION_STATUSES:
            raise ValueError("session_status is not recognized")
        if not isinstance(closing_signal, bool):
            raise TypeError("closing_signal must be boolean")
        if closing_signal and binary_s != 0:
            raise ValueError("the closing signal must have s=0")
        expected_finalize = (
            time_us + self.config.round_finalize_offset_us if binary_s == 1 else time_us
        )
        if finalize_time_us != expected_finalize:
            raise ValueError("round_finalize_time_us does not match the Stage 5B policy")
        if self._current_round is not None:
            raise RuntimeError("the previous Garden round is not finalized")
        if self._pending_closing is not None:
            raise RuntimeError("closing holder release is still pending")
        if (
            self._last_started_signal_index is not None
            and index <= self._last_started_signal_index
        ):
            raise ValueError("signal_index must be strictly increasing")
        if (
            self._last_started_signal_time_us is not None
            and time_us <= self._last_started_signal_time_us
        ):
            raise ValueError("signal_time_us must be strictly increasing")
        if binary_s == 0 and self._qualification_holder_id is not None and not closing_signal:
            raise RuntimeError("an inactive non-closing round cannot retain a holder")
        if closing_signal and self._qualification_holder_id is None:
            raise RuntimeError("closing evaluation attribution requires an existing holder")

        self._current_round = _RoundContext(
            signal_index=index,
            signal_time_us=time_us,
            s=binary_s,
            session_status=session_status,
            closing_signal=closing_signal,
            round_finalize_time_us=finalize_time_us,
            holder_before=self._qualification_holder_id,
            touches=[],
        )
        self._current_signal_index = index
        self._current_signal_time_us = time_us
        self._current_s = binary_s
        self._last_started_signal_index = index
        self._last_started_signal_time_us = time_us

    def handle_touch(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Accept one actual active-round arrival without seeing hidden life values."""

        touch = parse_digital_life_touch_event(event)
        context = self._require_open_round()
        if context.s != 1:
            raise RuntimeError("Garden cannot accept a touch while s=0")
        if touch.signal_index != context.signal_index:
            raise ValueError("touch signal_index does not match the open round")
        if touch.signal_time_us != context.signal_time_us:
            raise ValueError("touch signal_time_us does not match the open round")
        if touch.digital_life_id not in self.config.expected_digital_life_ids:
            raise ValueError("touch has an unexpected Digital Life ID")
        if touch.role != _ROLE_BY_ID[touch.digital_life_id]:
            raise ValueError("touch role does not match its Digital Life ID")
        if any(
            item.input.digital_life_id == touch.digital_life_id
            for item in context.touches
        ):
            raise ValueError("duplicate touch for one Digital Life and signal")
        if not context.signal_time_us < touch.arrival_time_us < context.round_finalize_time_us:
            raise ValueError("touch arrival must be after the signal and before finalize")
        if context.touches:
            previous = context.touches[-1].input
            if touch.arrival_time_us < previous.arrival_time_us:
                raise ValueError("touch arrival time moved backwards")
            if (
                touch.arrival_time_us == previous.arrival_time_us
                and touch.digital_life_id <= previous.digital_life_id
            ):
                raise ValueError("equal-time touches must arrive in lexical ID order")

        holder_before = self._qualification_holder_id
        assigned = holder_before is None
        if assigned:
            self._qualification_holder_id = touch.digital_life_id
            self._last_assigned_holder_id = touch.digital_life_id
            self._qualification_assigned_signal_index = context.signal_index
            self._qualification_assignment_time_us = touch.arrival_time_us
            self._assignment_count += 1
        context.touches.append(
            _PendingTouch(
                input=touch,
                holder_before=holder_before,
                holder_after=self._qualification_holder_id,
                assigned=assigned,
            )
        )

    def handle_round_finalize(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Validate round completeness, then emit one output and three feedback events."""

        context = self._require_open_round()
        self._validate_finalize_event(event, context)
        expected_ids = set(self.config.expected_digital_life_ids)
        actual_ids = {item.input.digital_life_id for item in context.touches}

        if context.s == 1:
            if len(context.touches) != len(expected_ids) or actual_ids != expected_ids:
                self._incomplete_round_count += 1
                raise RuntimeError("active Garden output round is incomplete")
            holder = self._qualification_holder_id
            if holder is None:
                self._incomplete_round_count += 1
                raise RuntimeError("active Garden output round has no holder")
            touch_by_id = {
                item.input.digital_life_id: item.input for item in context.touches
            }
            if holder not in touch_by_id:
                self._incomplete_round_count += 1
                raise RuntimeError("the holder did not touch in the current round")
            qualified_b = touch_by_id[holder].b
            returned_by_id = {
                life_id: touch_by_id[life_id].b
                for life_id in self.config.expected_digital_life_ids
            }
            output_holder = holder
            active = True
            attribution_source = "current_signal_touch"
            closing_attribution = False
        else:
            if context.touches:
                raise RuntimeError("inactive Garden output round unexpectedly contains touches")
            qualified_b = None
            output_holder = None
            active = False
            if context.closing_signal:
                holder = self._qualification_holder_id
                assert holder is not None
                if set(self._latest_active_b_by_life) != expected_ids:
                    self._incomplete_round_count += 1
                    raise RuntimeError("closing round lacks the last active B for all lives")
                returned_by_id = dict(self._latest_active_b_by_life)
                attribution_source = "last_active_touch"
                closing_attribution = True
            else:
                holder = None
                returned_by_id = {
                    life_id: None for life_id in self.config.expected_digital_life_ids
                }
                attribution_source = "none"
                closing_attribution = False

        output_record = GardenQualifiedBRecord(
            garden_id=self.config.garden_id,
            signal_index=context.signal_index,
            signal_time_us=context.signal_time_us,
            s=context.s,
            active=active,
            qualification_holder_id=output_holder,
            b=qualified_b,
            schema_version=self.config.qualified_b_schema_version,
        )
        engine.schedule_at(
            event.scheduled_time_us,
            GARDEN_QUALIFIED_B_EVENT_TYPE,
            source=GARDEN_OUTPUT_EVENT_SOURCE,
            priority=GARDEN_QUALIFIED_B_EVENT_PRIORITY,
            payload=self._qualified_b_payload(output_record),
        )

        feedback_batch: list[GardenFeedbackRecord] = []
        for life_id in self.config.expected_digital_life_ids:
            feedback = GardenFeedbackRecord(
                garden_id=self.config.garden_id,
                recipient_digital_life_id=life_id,
                signal_index=context.signal_index,
                signal_time_us=context.signal_time_us,
                s=context.s,
                qualification_holder_id=holder,
                returned_b=returned_by_id[life_id],
                attribution_source=attribution_source,
                closing_evaluation_attribution=closing_attribution,
                schema_version=self.config.feedback_schema_version,
            )
            engine.schedule_at(
                event.scheduled_time_us,
                GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
                source=GARDEN_OUTPUT_EVENT_SOURCE,
                priority=GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
                payload=self._feedback_payload(feedback),
            )
            feedback_batch.append(feedback)

        touch_records = self._materialize_touch_records(context)
        touch_order = tuple(
            item.input.digital_life_id for item in context.touches
        )
        if context.s == 1:
            self._latest_active_b_by_life = {
                item.input.digital_life_id: item.input.b for item in context.touches
            }
        self._touch_records.extend(touch_records)
        self._qualified_b_records.append(output_record)
        self._feedback_records.extend(feedback_batch)
        self._latest_qualified_b = qualified_b
        self._latest_touch_order = touch_order
        if active:
            self._active_output_count += 1
        else:
            self._inactive_output_count += 1

        assigned = any(item.assigned for item in context.touches)
        assignment_touch = next(
            (item.input for item in context.touches if item.assigned), None
        )
        if context.closing_signal:
            assert context.holder_before is not None
            self._pending_closing = _PendingClosingQualification(
                signal_index=context.signal_index,
                signal_time_us=context.signal_time_us,
                holder_before=context.holder_before,
                held_from_previous_signal=True,
            )
        else:
            self._qualification_records.append(
                GardenQualificationRecord(
                    signal_index=context.signal_index,
                    signal_time_us=context.signal_time_us,
                    s=context.s,
                    holder_before=context.holder_before,
                    holder_after=self._qualification_holder_id,
                    assigned_this_signal=assigned,
                    assignment_touch_time_us=(
                        None if assignment_touch is None else assignment_touch.arrival_time_us
                    ),
                    assignment_touch_id=(
                        None if assignment_touch is None else assignment_touch.digital_life_id
                    ),
                    held_from_previous_signal=context.holder_before is not None,
                    released_after_second_round=False,
                    touch_order=touch_order,
                    qualified_b=qualified_b,
                    active_output=active,
                )
            )
        self._current_round = None

    def release_holder(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Release the closing holder only after all second rounds have completed."""

        pending = self._pending_closing
        if pending is None:
            raise RuntimeError("no closing holder release is pending")
        self._validate_runtime_control_event(
            event,
            event_type=GARDEN_HOLDER_RELEASE_EVENT_TYPE,
            priority=GARDEN_HOLDER_RELEASE_EVENT_PRIORITY,
            signal_index=pending.signal_index,
            signal_time_us=pending.signal_time_us,
            scheduled_time_us=pending.signal_time_us,
        )
        if self._qualification_holder_id != pending.holder_before:
            raise RuntimeError("closing holder changed before release")

        self._qualification_holder_id = None
        self._release_count += 1
        self._qualification_records.append(
            GardenQualificationRecord(
                signal_index=pending.signal_index,
                signal_time_us=pending.signal_time_us,
                s=0,
                holder_before=pending.holder_before,
                holder_after=None,
                assigned_this_signal=False,
                assignment_touch_time_us=None,
                assignment_touch_id=None,
                held_from_previous_signal=pending.held_from_previous_signal,
                released_after_second_round=True,
                touch_order=(),
                qualified_b=None,
                active_output=False,
            )
        )
        self._latest_touch_order = ()
        self._pending_closing = None

    def snapshot(self) -> GardenOutputSnapshot:
        context = self._current_round
        return GardenOutputSnapshot(
            garden_id=self.config.garden_id,
            model_version=self.config.model_version,
            qualification_state_schema_version=(
                self.config.qualification_state_schema_version
            ),
            current_signal_index=self._current_signal_index,
            current_s=self._current_s,
            qualification_holder_id=self._qualification_holder_id,
            last_assigned_holder_id=self._last_assigned_holder_id,
            qualification_assigned_signal_index=(
                self._qualification_assigned_signal_index
            ),
            qualification_assignment_time_us=self._qualification_assignment_time_us,
            holder_active=self._qualification_holder_id is not None,
            round_open=context is not None,
            closing_release_pending=self._pending_closing is not None,
            touch_count_current_round=0 if context is None else len(context.touches),
            total_touch_count=len(self._touch_records) + (
                0 if context is None else len(context.touches)
            ),
            active_output_count=self._active_output_count,
            inactive_output_count=self._inactive_output_count,
            feedback_count=len(self._feedback_records),
            assignment_count=self._assignment_count,
            release_count=self._release_count,
            incomplete_round_count=self._incomplete_round_count,
            qualification_record_count=len(self._qualification_records),
            latest_qualified_b=self._latest_qualified_b,
            latest_touch_order=self._latest_touch_order,
        )

    def touch_records(self) -> tuple[GardenTouchRecord, ...]:
        return tuple(self._touch_records)

    def qualification_records(self) -> tuple[GardenQualificationRecord, ...]:
        return tuple(self._qualification_records)

    def qualified_b_records(self) -> tuple[GardenQualifiedBRecord, ...]:
        return tuple(self._qualified_b_records)

    def feedback_records(self) -> tuple[GardenFeedbackRecord, ...]:
        return tuple(self._feedback_records)

    def touch_digest(self) -> str:
        return self._digest(
            [
                {
                    "signal_index": record.signal_index,
                    "arrival_order": record.arrival_order,
                    "arrival_time_us": record.arrival_time_us,
                    "digital_life_id": record.digital_life_id,
                    "b": record.b,
                    "holder_before": record.holder_before,
                    "holder_after": record.holder_after,
                    "assigned": record.assigned_holder_on_this_touch,
                    "exact_time_tie": record.exact_time_tie,
                }
                for record in self._touch_records
            ]
        )

    def qualification_digest(self) -> str:
        return self._digest(
            [
                {
                    "signal_index": record.signal_index,
                    "s": record.s,
                    "holder_before": record.holder_before,
                    "holder_after": record.holder_after,
                    "assigned": record.assigned_this_signal,
                    "released": record.released_after_second_round,
                    "touch_order": record.touch_order,
                    "qualified_b": record.qualified_b,
                }
                for record in self._qualification_records
            ]
        )

    def qualified_b_digest(self) -> str:
        return self._digest(
            [
                {
                    "signal_index": record.signal_index,
                    "s": record.s,
                    "active": record.active,
                    "holder": record.qualification_holder_id,
                    "b": record.b,
                }
                for record in self._qualified_b_records
            ]
        )

    def feedback_digest(self) -> str:
        return self._digest(
            [
                {
                    "recipient": record.recipient_digital_life_id,
                    "signal_index": record.signal_index,
                    "s": record.s,
                    "holder": record.qualification_holder_id,
                    "returned_b": record.returned_b,
                    "attribution_source": record.attribution_source,
                    "closing_evaluation_attribution": (
                        record.closing_evaluation_attribution
                    ),
                }
                for record in self._feedback_records
            ]
        )

    def _require_open_round(self) -> _RoundContext:
        if self._current_round is None:
            raise RuntimeError("no Garden output round is open")
        return self._current_round

    def _validate_finalize_event(
        self,
        event: SimulationEvent,
        context: _RoundContext,
    ) -> None:
        if context.s == 1:
            event_type = GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE
            priority = GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY
        else:
            event_type = GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE
            priority = GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY
        self._validate_runtime_control_event(
            event,
            event_type=event_type,
            priority=priority,
            signal_index=context.signal_index,
            signal_time_us=context.signal_time_us,
            scheduled_time_us=context.round_finalize_time_us,
        )

    @staticmethod
    def _validate_runtime_control_event(
        event: SimulationEvent,
        *,
        event_type: str,
        priority: int,
        signal_index: int,
        signal_time_us: int,
        scheduled_time_us: int,
    ) -> None:
        if event.event_type != event_type:
            raise ValueError("Runtime control event type does not match the open round")
        if event.source != GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE:
            raise ValueError("Garden Runtime control source must be runtime")
        if event.priority != priority:
            raise ValueError("Garden Runtime control priority is incorrect")
        if event.scheduled_time_us != scheduled_time_us:
            raise ValueError("Garden Runtime control time is incorrect")
        if (
            not isinstance(event.payload, dict)
            or set(event.payload) != _FINALIZE_PAYLOAD_FIELDS
        ):
            raise ValueError("Garden Runtime control payload fields are incorrect")
        if event.payload["signal_index"] != signal_index:
            raise ValueError("Garden Runtime control signal_index is incorrect")
        if event.payload["signal_time_us"] != signal_time_us:
            raise ValueError("Garden Runtime control signal_time_us is incorrect")

    def _materialize_touch_records(
        self,
        context: _RoundContext,
    ) -> tuple[GardenTouchRecord, ...]:
        arrival_counts = Counter(item.input.arrival_time_us for item in context.touches)
        return tuple(
            GardenTouchRecord(
                signal_index=context.signal_index,
                signal_time_us=context.signal_time_us,
                arrival_order=index,
                arrival_time_us=item.input.arrival_time_us,
                digital_life_id=item.input.digital_life_id,
                role=item.input.role,
                b=item.input.b,
                holder_before=item.holder_before,
                holder_after=item.holder_after,
                assigned_holder_on_this_touch=item.assigned,
                exact_time_tie=arrival_counts[item.input.arrival_time_us] > 1,
                tie_break_policy=self.config.tie_break_rule,
                schema_version=self.config.touch_schema_version,
            )
            for index, item in enumerate(context.touches, start=1)
        )

    @staticmethod
    def _qualified_b_payload(record: GardenQualifiedBRecord) -> dict[str, object]:
        b = record.b
        return {
            "garden_id": record.garden_id,
            "signal_index": record.signal_index,
            "signal_time_us": record.signal_time_us,
            "s": record.s,
            "active": record.active,
            "qualification_holder_id": record.qualification_holder_id,
            "b_f": None if b is None else b[0],
            "b_a": None if b is None else b[1],
            "b_t": None if b is None else b[2],
            "b_d": None if b is None else b[3],
            "schema_version": record.schema_version,
        }

    @staticmethod
    def _feedback_payload(record: GardenFeedbackRecord) -> dict[str, object]:
        b = record.returned_b
        return {
            "garden_id": record.garden_id,
            "recipient_digital_life_id": record.recipient_digital_life_id,
            "signal_index": record.signal_index,
            "signal_time_us": record.signal_time_us,
            "s": record.s,
            "qualification_holder_id": record.qualification_holder_id,
            "returned_b_f": None if b is None else b[0],
            "returned_b_a": None if b is None else b[1],
            "returned_b_t": None if b is None else b[2],
            "returned_b_d": None if b is None else b[3],
            "attribution_source": record.attribution_source,
            "closing_evaluation_attribution": (
                record.closing_evaluation_attribution
            ),
            "schema_version": record.schema_version,
        }

    @staticmethod
    def _digest(records: list[dict[str, object]]) -> str:
        encoded = json.dumps(
            records,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
