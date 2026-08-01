"""Unit tests for deterministic queue operations."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.simulation.scheduler import EventScheduler


def test_schedule_at_peek_and_pop() -> None:
    scheduler = EventScheduler()
    event = scheduler.schedule_at(2_500_000, "marker", priority=40, payload={"x": 1})
    assert event.event_id == "evt-000000"
    assert event.sequence == 0
    assert scheduler.pending_count == 1
    assert scheduler.has_pending_events
    assert scheduler.peek_next() is event
    assert scheduler.pop_next() is event
    assert scheduler.pop_next() is None
    assert not scheduler.has_pending_events


def test_schedule_after_uses_current_virtual_time() -> None:
    current = [1_000_000]
    scheduler = EventScheduler(lambda: current[0])
    event = scheduler.schedule_after(250_000, "after")
    assert event.scheduled_time_us == 1_250_000


def test_order_is_time_then_priority_then_sequence() -> None:
    scheduler = EventScheduler()
    scheduler.schedule_at(2_000_000, "late")
    scheduler.schedule_at(1_000_000, "same_second", priority=20)
    scheduler.schedule_at(1_000_000, "same_first", priority=10)
    scheduler.schedule_at(1_000_000, "same_second_later", priority=20)
    assert [scheduler.pop_next().event_type for _ in range(4)] == [
        "same_first",
        "same_second",
        "same_second_later",
        "late",
    ]


def test_pop_due_is_inclusive_and_sorted() -> None:
    scheduler = EventScheduler()
    scheduler.schedule_at(10, "a")
    scheduler.schedule_at(20, "b")
    scheduler.schedule_at(30, "c")
    assert [event.event_type for event in scheduler.pop_due(20)] == ["a", "b"]
    assert scheduler.peek_next().event_type == "c"


def test_cancelled_event_never_executes() -> None:
    scheduler = EventScheduler()
    cancelled = scheduler.schedule_at(10, "cancelled")
    survivor = scheduler.schedule_at(20, "survivor")
    assert scheduler.cancel(cancelled.event_id)
    assert not scheduler.cancel("missing")
    assert scheduler.pop_next() is survivor
    assert scheduler.pop_next() is None


def test_clear_preserves_sequence_but_reset_restarts_it() -> None:
    scheduler = EventScheduler()
    scheduler.schedule_at(1, "first")
    scheduler.clear()
    after_clear = scheduler.schedule_at(2, "after_clear")
    assert after_clear.sequence == 1
    scheduler.reset()
    after_reset = scheduler.schedule_at(3, "after_reset")
    assert after_reset.sequence == 0
    assert after_reset.event_id == "evt-000000"


def test_past_and_after_end_scheduling_are_rejected() -> None:
    current = [100]
    end = [200]
    scheduler = EventScheduler(lambda: current[0], lambda: end[0])
    with pytest.raises(ValueError, match="past"):
        scheduler.schedule_at(99, "past")
    with pytest.raises(ValueError, match="beyond"):
        scheduler.schedule_at(201, "too_late")
    with pytest.raises(ValueError):
        scheduler.schedule_after(-1, "negative")


def test_custom_event_id_must_be_unique_until_reset() -> None:
    scheduler = EventScheduler()
    scheduler.schedule_at(1, "a", event_id="stable-id")
    with pytest.raises(ValueError, match="duplicate"):
        scheduler.schedule_at(2, "b", event_id="stable-id")
