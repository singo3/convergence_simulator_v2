"""Garden actual-arrival qualification, hold, completeness, and release tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.component import GardenOutputComponent
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.garden.output_layer.events import (
    DIGITAL_LIFE_TOUCH_EVENT_PRIORITY,
    DIGITAL_LIFE_TOUCH_EVENT_SOURCE,
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
    GARDEN_HOLDER_RELEASE_EVENT_PRIORITY,
    GARDEN_HOLDER_RELEASE_EVENT_TYPE,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE,
    GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler

GREEN_B = (125 / 360, 0.5, 0.5, 0.5)
BLUE_B = (250 / 360, 0.5, 0.5, 0.5)
RED_B = (5 / 360, 0.5, 0.5, 0.5)
B_BY_ID = {"life-blue": BLUE_B, "life-green": GREEN_B, "life-red": RED_B}
ROSTER = ("life-blue", "life-green", "life-red")


@dataclass(frozen=True, slots=True)
class Scenario:
    start_time_us: int = 0
    end_time_us: int = 300_000_000

    def schedule(self, _scheduler: EventScheduler) -> None:
        pass


def engine() -> SimulationEngine:
    return SimulationEngine(Scenario())


def garden_output() -> GardenOutputComponent:
    return GardenOutputComponent(GardenOutputConfig(expected_digital_life_ids=ROSTER))


def touch_event(
    life_id: str,
    signal_index: int,
    signal_time_us: int,
    arrival_time_us: int,
    *,
    sequence: int = 0,
    payload_updates: dict[str, object] | None = None,
) -> SimulationEvent:
    b = B_BY_ID[life_id]
    payload: dict[str, object] = {
        "digital_life_id": life_id,
        "signal_index": signal_index,
        "signal_time_us": signal_time_us,
        "b_f": b[0],
        "b_a": b[1],
        "b_t": b[2],
        "b_d": b[3],
        "schema_version": "digital_life_touch_event_v2",
    }
    payload.update(payload_updates or {})
    return SimulationEvent(
        event_id=f"touch-{signal_index}-{life_id}-{sequence}",
        event_type=DIGITAL_LIFE_TOUCH_EVENT_TYPE,
        source=DIGITAL_LIFE_TOUCH_EVENT_SOURCE,
        scheduled_time_us=arrival_time_us,
        priority=DIGITAL_LIFE_TOUCH_EVENT_PRIORITY,
        sequence=sequence,
        payload=payload,
    )


def finalize_event(
    signal_index: int,
    signal_time_us: int,
    *,
    active: bool,
    sequence: int = 100,
) -> SimulationEvent:
    return SimulationEvent(
        event_id=f"finalize-{signal_index}",
        event_type=(
            GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE
            if active
            else GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE
        ),
        source=GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE,
        scheduled_time_us=signal_time_us + (999_999 if active else 0),
        priority=(
            GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY
            if active
            else GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY
        ),
        sequence=sequence,
        payload={"signal_index": signal_index, "signal_time_us": signal_time_us},
    )


def release_event(signal_index: int, signal_time_us: int) -> SimulationEvent:
    return SimulationEvent(
        event_id=f"release-{signal_index}",
        event_type=GARDEN_HOLDER_RELEASE_EVENT_TYPE,
        source=GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE,
        scheduled_time_us=signal_time_us,
        priority=GARDEN_HOLDER_RELEASE_EVENT_PRIORITY,
        sequence=200,
        payload={"signal_index": signal_index, "signal_time_us": signal_time_us},
    )


def begin(
    component: GardenOutputComponent,
    index: int,
    *,
    s: int,
    closing: bool = False,
) -> int:
    time_us = index * 1_000_000
    component.begin_round(
        signal_index=index,
        signal_time_us=time_us,
        s=s,
        session_status="completed" if closing else ("active" if s else "baseline"),
        closing_signal=closing,
        round_finalize_time_us=time_us + (999_999 if s else 0),
    )
    return time_us


def deliver_active_round(
    component: GardenOutputComponent,
    runtime: SimulationEngine,
    index: int,
    order: tuple[str, str, str] = ("life-green", "life-blue", "life-red"),
) -> None:
    time_us = begin(component, index, s=1)
    for offset, life_id in enumerate(order, start=100_000):
        component.handle_touch(
            touch_event(life_id, index, time_us, time_us + offset, sequence=offset),
            runtime,
        )
    component.handle_round_finalize(finalize_event(index, time_us, active=True), runtime)


def test_first_actual_touch_assigns_holder_and_later_signals_hold_it() -> None:
    component = garden_output()
    runtime = engine()

    deliver_active_round(component, runtime, 60)
    first = component.qualification_records()[0]
    assert first.holder_before is None
    assert first.holder_after == "life-green"
    assert first.assigned_this_signal
    assert first.touch_order == ("life-green", "life-blue", "life-red")
    assert first.qualified_b == GREEN_B
    first_output = component.qualified_b_records()[0]
    assert first_output.effective_time_us == 60_100_000
    assert first_output.qualification_holder_id == "life-green"
    assert first_output.b == GREEN_B

    deliver_active_round(
        component,
        runtime,
        61,
        order=("life-red", "life-blue", "life-green"),
    )
    second = component.qualification_records()[1]
    assert second.holder_before == second.holder_after == "life-green"
    assert second.held_from_previous_signal
    assert not second.assigned_this_signal
    assert second.touch_order == ("life-red", "life-blue", "life-green")
    assert second.qualified_b == GREEN_B
    second_output = component.qualified_b_records()[1]
    assert second_output.effective_time_us == 61_100_002
    assert second_output.qualification_holder_id == "life-green"

    snapshot = component.snapshot()
    assert snapshot.assignment_count == 1
    assert snapshot.total_touch_count == 6
    assert snapshot.active_output_count == 2
    assert snapshot.feedback_count == 6
    assert snapshot.latest_active_holder_touch_time_us == 61_100_002
    assert snapshot.latest_active_qualified_b_effective_time_us == 61_100_002
    assert snapshot.latest_active_qualified_b_delay_us == 0


def test_equal_time_tie_uses_actual_lexical_scheduler_order_and_flags_every_tie() -> None:
    component = garden_output()
    runtime = engine()
    time_us = begin(component, 60, s=1)

    for sequence, life_id in enumerate(("life-blue", "life-green", "life-red")):
        component.handle_touch(
            touch_event(
                life_id,
                60,
                time_us,
                time_us + 500_000,
                sequence=sequence,
            ),
            runtime,
        )
    component.handle_round_finalize(finalize_event(60, time_us, active=True), runtime)

    records = component.touch_records()
    assert [record.digital_life_id for record in records] == [
        "life-blue",
        "life-green",
        "life-red",
    ]
    assert {record.exact_time_tie for record in records} == {True}
    assert component.snapshot().qualification_holder_id == "life-blue"
    output = component.qualified_b_records()[0]
    assert output.effective_time_us == time_us + 500_000
    assert output.qualification_holder_id == "life-blue"
    queued_outputs = [
        event
        for event in runtime.scheduler.pending_events()
        if event.event_type == GARDEN_QUALIFIED_B_EVENT_TYPE
    ]
    assert len(queued_outputs) == 1
    assert queued_outputs[0].priority == GARDEN_QUALIFIED_B_EVENT_PRIORITY == 65


def test_incomplete_round_errors_without_fallback_and_can_be_completed() -> None:
    component = garden_output()
    runtime = engine()
    time_us = begin(component, 60, s=1)
    for offset, life_id in enumerate(("life-green", "life-blue"), start=100_000):
        component.handle_touch(
            touch_event(life_id, 60, time_us, time_us + offset, sequence=offset),
            runtime,
        )

    with pytest.raises(RuntimeError, match="incomplete"):
        component.handle_round_finalize(finalize_event(60, time_us, active=True), runtime)
    assert component.snapshot().round_open
    assert component.snapshot().incomplete_round_count == 1
    assert len(component.qualified_b_records()) == 1

    component.handle_touch(
        touch_event("life-red", 60, time_us, time_us + 300_000, sequence=3),
        runtime,
    )
    component.handle_round_finalize(finalize_event(60, time_us, active=True), runtime)
    assert len(component.touch_records()) == 3


def test_closing_feedback_is_attributed_before_holder_release() -> None:
    component = garden_output()
    runtime = engine()
    deliver_active_round(component, runtime, 239)
    time_us = begin(component, 240, s=0, closing=True)

    component.handle_round_finalize(finalize_event(240, time_us, active=False), runtime)
    before_release = component.snapshot()
    assert before_release.qualification_holder_id == "life-green"
    assert before_release.closing_release_pending
    output = component.qualified_b_records()[-1]
    assert not output.active
    assert output.effective_time_us == time_us
    assert output.qualification_holder_id is None
    assert output.b is None
    closing_feedback = component.feedback_records()[-3:]
    assert {item.qualification_holder_id for item in closing_feedback} == {"life-green"}
    assert {item.attribution_source for item in closing_feedback} == {"last_active_touch"}
    assert all(item.closing_evaluation_attribution for item in closing_feedback)
    assert {item.recipient_digital_life_id: item.returned_b for item in closing_feedback} == (
        B_BY_ID
    )

    component.release_holder(release_event(240, time_us), runtime)
    after_release = component.snapshot()
    assert after_release.qualification_holder_id is None
    assert after_release.release_count == 1
    assert not after_release.closing_release_pending
    closing = component.qualification_records()[-1]
    assert closing.holder_before == "life-green"
    assert closing.holder_after is None
    assert closing.released_after_second_round


@pytest.mark.parametrize(
    "failure",
    ("s-zero", "duplicate", "unknown", "mixed-signal", "extra", "legacy-role"),
)
def test_invalid_touch_is_rejected(failure: str) -> None:
    component = garden_output()
    runtime = engine()
    time_us = begin(component, 0 if failure == "s-zero" else 60, s=0 if failure == "s-zero" else 1)
    event = touch_event("life-green", 60, 60_000_000, 60_100_000)

    if failure == "duplicate":
        component.handle_touch(event, runtime)
    elif failure == "unknown":
        event = touch_event(
            "life-green",
            60,
            60_000_000,
            60_100_000,
            payload_updates={"digital_life_id": "life-violet"},
        )
    elif failure == "mixed-signal":
        event = touch_event("life-green", 61, 60_000_000, 60_100_000)
    elif failure == "extra":
        event = touch_event(
            "life-green",
            60,
            60_000_000,
            60_100_000,
            payload_updates={"tau": 0.1},
        )
    elif failure == "legacy-role":
        event = touch_event(
            "life-green",
            60,
            60_000_000,
            60_100_000,
            payload_updates={"role": "green"},
        )

    with pytest.raises((RuntimeError, ValueError)):
        component.handle_touch(event, runtime)
    assert component.snapshot().touch_count_current_round == (1 if failure == "duplicate" else 0)
    assert time_us >= 0
