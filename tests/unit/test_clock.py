"""Unit tests for integer virtual-clock lifecycle and invariants."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.simulation.clock import (
    ClockState,
    InvalidClockTransition,
    SimulationClock,
)


def make_clock() -> SimulationClock:
    return SimulationClock(start_time_us=1_000_000, end_time_us=5_000_000)


def test_initial_state() -> None:
    clock = make_clock()
    assert clock.current_time_us == 1_000_000
    assert clock.state is ClockState.STOPPED


def test_start_pause_and_resume() -> None:
    clock = make_clock()
    clock.start()
    assert clock.state is ClockState.RUNNING
    clock.pause()
    assert clock.state is ClockState.PAUSED
    clock.resume()
    assert clock.state is ClockState.RUNNING


def test_invalid_state_transitions_are_explicit() -> None:
    clock = make_clock()
    with pytest.raises(InvalidClockTransition):
        clock.pause()
    clock.start()
    with pytest.raises(InvalidClockTransition):
        clock.start()


def test_advance_and_end_clamp() -> None:
    clock = make_clock()
    clock.start()
    assert clock.advance_by_us(750_000) == 1_750_000
    assert clock.advance_to_us(9_000_000) == 5_000_000
    assert clock.current_time_us == clock.end_time_us


def test_backward_time_is_rejected() -> None:
    clock = make_clock()
    clock.start()
    clock.advance_to_us(2_000_000)
    with pytest.raises(ValueError, match="backward"):
        clock.advance_to_us(1_999_999)


def test_paused_clock_cannot_advance() -> None:
    clock = make_clock()
    clock.start()
    clock.pause()
    with pytest.raises(InvalidClockTransition):
        clock.advance_by_us(1)
    assert clock.current_time_us == 1_000_000


def test_complete_blocks_progress_until_reset() -> None:
    clock = make_clock()
    clock.start()
    clock.complete()
    assert clock.state is ClockState.COMPLETED
    assert clock.current_time_us == 5_000_000
    with pytest.raises(InvalidClockTransition):
        clock.advance_by_us(1)
    with pytest.raises(InvalidClockTransition):
        clock.resume()


def test_reset_restores_initial_time_and_state() -> None:
    clock = make_clock()
    clock.start()
    clock.advance_by_us(2_000_000)
    clock.pause()
    clock.reset()
    assert clock.current_time_us == 1_000_000
    assert clock.state is ClockState.STOPPED


@pytest.mark.parametrize(
    ("start_us", "end_us", "exception"),
    [(-1, 1, ValueError), (1, 0, ValueError), (True, 2, TypeError)],
)
def test_invalid_clock_bounds(start_us, end_us, exception) -> None:
    with pytest.raises(exception):
        SimulationClock(start_time_us=start_us, end_time_us=end_us)
