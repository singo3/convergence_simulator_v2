"""Unit tests for clock/scheduler integration and deterministic execution."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.demo_scenario import DemoScenario, create_demo_engine
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler


def test_step_one_second_is_exact_and_executes_all_reached_events() -> None:
    engine = create_demo_engine()
    executed = engine.step_one_second()
    assert executed == 2
    assert engine.clock.current_time_us == 1_000_000
    assert engine.clock.state is ClockState.PAUSED
    assert [event.scheduled_time_us for event in engine.executed_events()] == [0, 1_000_000]


def test_step_one_event_executes_exactly_one() -> None:
    engine = create_demo_engine()
    event = engine.step_one_event()
    assert event is not None
    assert event.event_type == "clock_tick"
    assert event.scheduled_time_us == 0
    assert engine.clock.current_time_us == 0
    assert engine.clock.state is ClockState.PAUSED
    assert len(engine.executed_events()) == 1


def test_run_until_end_completes_without_waiting() -> None:
    engine = create_demo_engine()
    count = engine.run_until_end()
    assert count == 26
    assert engine.clock.current_time_us == 20_000_000
    assert engine.clock.state is ClockState.COMPLETED
    assert engine.snapshot().pending_event_count == 0


def test_run_max_batch_respects_event_limit() -> None:
    engine = create_demo_engine()
    engine.start()
    assert engine.run_max_batch(max_events=1, wall_time_budget_ms=None) == 1
    assert len(engine.executed_events()) == 1
    assert engine.clock.current_time_us == 0


def test_paused_and_completed_engines_do_not_auto_advance() -> None:
    engine = create_demo_engine()
    engine.start()
    engine.pause()
    assert engine.advance_by_us(10_000_000) == 0
    assert engine.clock.current_time_us == 0
    engine.run_until_end()
    digest = engine.deterministic_digest()
    assert engine.advance_by_us(1_000_000) == 0
    assert engine.step_one_second() == 0
    assert engine.step_one_event() is None
    assert engine.deterministic_digest() == digest


def test_reset_rebuilds_queue_history_ids_and_digest() -> None:
    engine = create_demo_engine()
    initial_plan = [event.to_dict() for event in engine.planned_events()]
    engine.run_until_end()
    first_digest = engine.deterministic_digest()
    engine.reset()
    assert engine.clock.state is ClockState.STOPPED
    assert engine.clock.current_time_us == 0
    assert engine.executed_events() == ()
    assert [event.to_dict() for event in engine.planned_events()] == initial_plan
    engine.run_until_end()
    assert engine.deterministic_digest() == first_digest


def test_snapshot_and_history_are_read_only_views() -> None:
    engine = create_demo_engine()
    engine.step_one_event()
    snapshot = engine.snapshot()
    assert snapshot.executed_event_count == 1
    assert snapshot.pending_event_count == 25
    assert snapshot.last_executed_event is engine.executed_events()[0]
    assert snapshot.next_event is not None


@dataclass(frozen=True)
class HandlerScenario:
    start_time_us: int = 0
    end_time_us: int = 3_000_000

    def schedule(self, scheduler: EventScheduler) -> None:
        scheduler.schedule_at(1_000_000, "seed", payload={"generation": 0})


def test_handler_can_schedule_a_future_event() -> None:
    engine = SimulationEngine(HandlerScenario())

    def handler(event, context: SimulationEngine) -> None:
        context.schedule_after(
            1_000_000,
            "child",
            payload={"parent": event.event_id},
        )

    engine.register_handler("seed", handler)
    engine.run_until_end()
    assert [event.event_type for event in engine.executed_events()] == ["seed", "child"]
    assert [event.scheduled_time_us for event in engine.executed_events()] == [
        1_000_000,
        2_000_000,
    ]


def test_handler_cannot_schedule_into_past_or_break_same_time_priority() -> None:
    engine = SimulationEngine(HandlerScenario())

    def invalid_handler(_event, context: SimulationEngine) -> None:
        with pytest.raises(ValueError, match="past"):
            context.schedule_at(999_999, "past")
        with pytest.raises(ValueError, match="ahead"):
            context.schedule_at(1_000_000, "priority_retrograde", priority=99)

    # The seed's default priority is 100, so 99 would retroactively precede it.
    engine.register_handler("seed", invalid_handler)
    engine.run_until_end()


def _digest_for_chunk(chunk_us: int, *, snapshot_reads: int = 0) -> str:
    engine = create_demo_engine()
    engine.start()
    while engine.clock.state is ClockState.RUNNING:
        for _ in range(snapshot_reads):
            engine.snapshot()
        engine.advance_by_us(chunk_us)
    return engine.deterministic_digest()


def test_realtime_x10_x100_and_different_gui_refresh_counts_match_maximum() -> None:
    realtime = _digest_for_chunk(17_000, snapshot_reads=1)
    x10 = _digest_for_chunk(170_000, snapshot_reads=3)
    x100 = _digest_for_chunk(1_700_000, snapshot_reads=11)
    maximum_engine = create_demo_engine()
    maximum_engine.run_until_end()
    assert realtime == x10 == x100 == maximum_engine.deterministic_digest()


def test_load_scenario_replaces_previous_state() -> None:
    engine = SimulationEngine(DemoScenario())
    engine.step_one_event()
    engine.load_scenario(DemoScenario())
    assert engine.executed_events() == ()
    assert engine.snapshot().pending_event_count == 26
