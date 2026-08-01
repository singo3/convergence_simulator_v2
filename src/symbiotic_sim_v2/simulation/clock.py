"""Deterministic integer-microsecond virtual clock."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ClockState(StrEnum):
    """Lifecycle state of a :class:`SimulationClock`."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class InvalidClockTransition(RuntimeError):
    """Raised when an operation is not valid in the current clock state."""


def _validate_time(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer number of microseconds")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass(slots=True)
class SimulationClock:
    """A monotonic virtual clock bounded by an inclusive start and end time."""

    start_time_us: int
    end_time_us: int
    current_time_us: int = field(init=False)
    state: ClockState = field(init=False, default=ClockState.STOPPED)

    def __post_init__(self) -> None:
        _validate_time("start_time_us", self.start_time_us)
        _validate_time("end_time_us", self.end_time_us)
        if self.end_time_us < self.start_time_us:
            raise ValueError("end_time_us must not precede start_time_us")
        self.current_time_us = self.start_time_us

    def start(self) -> None:
        """Start a stopped clock at its current (initial) virtual time."""

        if self.state is not ClockState.STOPPED:
            raise InvalidClockTransition(f"cannot start a {self.state.value} clock")
        if self.current_time_us >= self.end_time_us:
            self.state = ClockState.COMPLETED
            return
        self.state = ClockState.RUNNING

    def pause(self) -> None:
        """Pause a running clock without changing virtual time."""

        if self.state is not ClockState.RUNNING:
            raise InvalidClockTransition(f"cannot pause a {self.state.value} clock")
        self.state = ClockState.PAUSED

    def resume(self) -> None:
        """Resume a paused clock."""

        if self.state is not ClockState.PAUSED:
            raise InvalidClockTransition(f"cannot resume a {self.state.value} clock")
        self.state = ClockState.RUNNING

    def reset(self) -> None:
        """Restore the exact initial time and stopped state."""

        self.current_time_us = self.start_time_us
        self.state = ClockState.STOPPED

    def advance_by_us(self, delta_us: int) -> int:
        """Advance a running clock by a non-negative integer duration."""

        _validate_time("delta_us", delta_us)
        return self.advance_to_us(self.current_time_us + delta_us)

    def advance_to_us(self, target_time_us: int) -> int:
        """Advance to a target, clamping at ``end_time_us`` and never moving back."""

        _validate_time("target_time_us", target_time_us)
        if self.state is not ClockState.RUNNING:
            raise InvalidClockTransition(f"cannot advance a {self.state.value} clock")
        if target_time_us < self.current_time_us:
            raise ValueError("virtual time cannot move backward")
        self.current_time_us = min(target_time_us, self.end_time_us)
        return self.current_time_us

    def complete(self) -> None:
        """Move to the configured end time and enter the completed state."""

        if self.state is ClockState.COMPLETED:
            raise InvalidClockTransition("clock is already completed")
        self.current_time_us = self.end_time_us
        self.state = ClockState.COMPLETED
