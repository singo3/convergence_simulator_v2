"""GUI-independent integration of clock, scheduler, handlers, and history."""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from symbiotic_sim_v2.domain.events import SimulationEvent, thaw_json
from symbiotic_sim_v2.simulation.clock import ClockState, SimulationClock
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.simulation.time_utils import MICROSECONDS_PER_SECOND


class Scenario(Protocol):
    """Minimal scenario contract accepted by :class:`SimulationEngine`."""

    start_time_us: int
    end_time_us: int

    def schedule(self, scheduler: EventScheduler) -> None:
        """Populate a freshly reset scheduler."""


EventHandler = Callable[[SimulationEvent, "SimulationEngine"], None]


@dataclass(frozen=True, slots=True)
class EngineSnapshot:
    """Read-only state sent to non-core consumers such as the GUI controller."""

    current_time_us: int
    start_time_us: int
    end_time_us: int
    state: ClockState
    pending_event_count: int
    executed_event_count: int
    next_event: SimulationEvent | None
    last_executed_event: SimulationEvent | None

    @property
    def virtual_elapsed_us(self) -> int:
        """Return elapsed virtual time since the scenario start."""

        return self.current_time_us - self.start_time_us


class SimulationEngine:
    """Execute scheduled events on one deterministic integer virtual clock."""

    def __init__(self, scenario: Scenario | None = None) -> None:
        self._scenario: Scenario | None = None
        self._clock = SimulationClock(start_time_us=0, end_time_us=1)
        self._scheduler = EventScheduler(
            lambda: self._clock.current_time_us,
            lambda: self._clock.end_time_us,
        )
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[SimulationEvent] = []
        self._planned_events: tuple[SimulationEvent, ...] = ()
        self._executing_event: SimulationEvent | None = None
        if scenario is not None:
            self.load_scenario(scenario)

    @property
    def clock(self) -> SimulationClock:
        """Return the core virtual clock (never a GUI or wall clock)."""

        return self._clock

    @property
    def scheduler(self) -> EventScheduler:
        """Return the scheduler for diagnostic inspection and advanced composition."""

        return self._scheduler

    def load_scenario(self, scenario: Scenario) -> None:
        """Load a scenario into a clean clock, queue, and history."""

        if not hasattr(scenario, "schedule"):
            raise TypeError("scenario must implement schedule(scheduler)")
        self._scenario = scenario
        self._clock = SimulationClock(
            start_time_us=scenario.start_time_us,
            end_time_us=scenario.end_time_us,
        )
        self._scheduler = EventScheduler(
            lambda: self._clock.current_time_us,
            lambda: self._clock.end_time_us,
        )
        self._history.clear()
        self._executing_event = None
        scenario.schedule(self._scheduler)
        self._planned_events = self._scheduler.pending_events()

    def start(self) -> None:
        """Start a freshly loaded or reset scenario."""

        self._require_scenario()
        self._clock.start()

    def pause(self) -> None:
        """Pause automatic virtual-time advancement."""

        self._clock.pause()

    def resume(self) -> None:
        """Resume a paused scenario."""

        self._clock.resume()

    def reset(self) -> None:
        """Rebuild clock, queue, IDs, sequences, and history deterministically."""

        scenario = self._require_scenario()
        self._clock.reset()
        self._scheduler.reset()
        self._history.clear()
        self._executing_event = None
        scenario.schedule(self._scheduler)
        self._planned_events = self._scheduler.pending_events()

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for an event type; ``*`` receives every event."""

        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type must be a non-empty string")
        if not callable(handler):
            raise TypeError("handler must be callable")
        self._handlers[event_type].append(handler)

    def schedule_at(
        self,
        scheduled_time_us: int,
        event_type: str,
        *,
        source: str = "handler",
        priority: int = 100,
        payload: Any = None,
        event_id: str | None = None,
    ) -> SimulationEvent:
        """Schedule through the engine while preserving same-time ordering floors."""

        current = self._executing_event
        if (
            current is not None
            and scheduled_time_us == self._clock.current_time_us
            and priority < current.priority
        ):
            raise ValueError(
                "a handler cannot insert a same-time event ahead of the event being executed"
            )
        return self._scheduler.schedule_at(
            scheduled_time_us,
            event_type,
            source=source,
            priority=priority,
            payload=payload,
            event_id=event_id,
        )

    def schedule_after(
        self,
        delay_us: int,
        event_type: str,
        *,
        source: str = "handler",
        priority: int = 100,
        payload: Any = None,
        event_id: str | None = None,
    ) -> SimulationEvent:
        """Schedule relative to the current virtual clock through the engine."""

        if isinstance(delay_us, bool) or not isinstance(delay_us, int):
            raise TypeError("delay_us must be an integer")
        if delay_us < 0:
            raise ValueError("delay_us must be non-negative")
        return self.schedule_at(
            self._clock.current_time_us + delay_us,
            event_type,
            source=source,
            priority=priority,
            payload=payload,
            event_id=event_id,
        )

    def advance_by_us(self, delta_us: int) -> int:
        """Advance a running engine and execute every event reached, inclusively.

        Calls while stopped, paused, or completed are safe no-ops. This is the
        controller-facing automatic-advance API; explicit stepping has separate
        methods and is permitted while stopped or paused.
        """

        if isinstance(delta_us, bool) or not isinstance(delta_us, int):
            raise TypeError("delta_us must be an integer")
        if delta_us < 0:
            raise ValueError("delta_us must be non-negative")
        if self._clock.state is not ClockState.RUNNING:
            return 0
        target_us = min(self._clock.current_time_us + delta_us, self._clock.end_time_us)
        return self._advance_running_to(target_us)

    def step_one_second(self) -> int:
        """Advance exactly one virtual second (end-clamped), including due events."""

        if self._clock.state is ClockState.COMPLETED:
            return 0
        restore_pause = self._begin_manual_step()
        if self._clock.state is ClockState.COMPLETED:
            return 0
        target_us = min(
            self._clock.current_time_us + MICROSECONDS_PER_SECOND,
            self._clock.end_time_us,
        )
        executed_count = self._advance_running_to(target_us)
        self._finish_manual_step(restore_pause)
        return executed_count

    def step_one_event(self) -> SimulationEvent | None:
        """Execute exactly the next queued event and no same-time neighbour."""

        if self._clock.state is ClockState.COMPLETED:
            return None
        next_event = self._scheduler.peek_next()
        if next_event is None:
            return None
        restore_pause = self._begin_manual_step()
        self._clock.advance_to_us(next_event.scheduled_time_us)
        event = self._scheduler.pop_next()
        if event is None:  # pragma: no cover - protected by the preceding peek
            self._finish_manual_step(restore_pause)
            return None
        self._execute_event(event)
        self._maybe_complete()
        self._finish_manual_step(restore_pause)
        return event

    def run_until_end(self, *, safety_event_limit: int = 1_000_000) -> int:
        """Process the full queue without real-time waiting, with a runaway guard."""

        if isinstance(safety_event_limit, bool) or safety_event_limit <= 0:
            raise ValueError("safety_event_limit must be a positive integer")
        if self._clock.state is ClockState.COMPLETED:
            return 0
        if self._clock.state is ClockState.STOPPED:
            self._clock.start()
        elif self._clock.state is ClockState.PAUSED:
            self._clock.resume()

        total = 0
        while self._clock.state is not ClockState.COMPLETED:
            remaining = safety_event_limit - total
            if remaining <= 0:
                raise RuntimeError("run_until_end exceeded the safety event limit")
            processed = self.run_max_batch(max_events=min(10_000, remaining))
            total += processed
            if processed == 0 and self._clock.state is not ClockState.COMPLETED:
                raise RuntimeError("engine made no progress while running to completion")
        return total

    def run_max_batch(
        self,
        max_events: int = 500,
        wall_time_budget_ms: float | None = 8.0,
    ) -> int:
        """Run a bounded maximum-speed batch and yield before monopolizing the GUI."""

        if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events <= 0:
            raise ValueError("max_events must be a positive integer")
        if wall_time_budget_ms is not None and wall_time_budget_ms <= 0:
            raise ValueError("wall_time_budget_ms must be positive or None")
        if self._clock.state is not ClockState.RUNNING:
            return 0

        deadline_ns = (
            None
            if wall_time_budget_ms is None
            else time.perf_counter_ns() + int(wall_time_budget_ms * 1_000_000)
        )
        processed = 0
        while processed < max_events:
            if processed and deadline_ns is not None and time.perf_counter_ns() >= deadline_ns:
                break
            next_event = self._scheduler.peek_next()
            if next_event is None:
                self._clock.advance_to_us(self._clock.end_time_us)
                self._maybe_complete()
                break
            self._clock.advance_to_us(next_event.scheduled_time_us)
            event = self._scheduler.pop_next()
            if event is None:  # pragma: no cover - protected by the preceding peek
                continue
            self._execute_event(event)
            processed += 1
            self._maybe_complete()
            if self._clock.state is ClockState.COMPLETED:
                break
        return processed

    def snapshot(self) -> EngineSnapshot:
        """Return an immutable state snapshot without exposing queue internals."""

        return EngineSnapshot(
            current_time_us=self._clock.current_time_us,
            start_time_us=self._clock.start_time_us,
            end_time_us=self._clock.end_time_us,
            state=self._clock.state,
            pending_event_count=self._scheduler.pending_count,
            executed_event_count=len(self._history),
            next_event=self._scheduler.peek_next(),
            last_executed_event=self._history[-1] if self._history else None,
        )

    def executed_events(self) -> tuple[SimulationEvent, ...]:
        """Return the execution history in exact execution order."""

        return tuple(self._history)

    def planned_events(self) -> tuple[SimulationEvent, ...]:
        """Return the scenario's initially scheduled events for diagnostics/plots."""

        return self._planned_events

    def deterministic_digest(self) -> str:
        """Return SHA-256 over the canonical required execution fields."""

        return execution_digest(self._history)

    def _advance_running_to(self, target_us: int) -> int:
        if target_us < self._clock.current_time_us:
            raise ValueError("virtual time cannot move backward")
        processed = 0
        while (event := self._scheduler.peek_next()) is not None:
            if event.scheduled_time_us > target_us:
                break
            self._clock.advance_to_us(event.scheduled_time_us)
            popped = self._scheduler.pop_next()
            if popped is None:  # pragma: no cover - protected by peek
                continue
            self._execute_event(popped)
            processed += 1
        if self._clock.state is ClockState.RUNNING:
            self._clock.advance_to_us(target_us)
            self._maybe_complete()
        return processed

    def _execute_event(self, event: SimulationEvent) -> None:
        if event.scheduled_time_us != self._clock.current_time_us:
            raise RuntimeError("event execution time does not match the virtual clock")
        if self._history and event.ordering_key < self._history[-1].ordering_key:
            raise RuntimeError("event ordering invariant was violated")

        self._history.append(event)
        self._executing_event = event
        try:
            handlers = (
                *self._handlers.get(event.event_type, ()),
                *self._handlers.get("*", ()),
            )
            for handler in handlers:
                handler(event, self)
        finally:
            self._executing_event = None

    def _maybe_complete(self) -> None:
        if (
            self._clock.state is ClockState.RUNNING
            and self._clock.current_time_us >= self._clock.end_time_us
            and not self._scheduler.has_pending_events
        ):
            self._clock.complete()

    def _begin_manual_step(self) -> bool:
        if self._clock.state is ClockState.STOPPED:
            self._clock.start()
            return self._clock.state is ClockState.RUNNING
        if self._clock.state is ClockState.PAUSED:
            self._clock.resume()
            return True
        return False

    def _finish_manual_step(self, restore_pause: bool) -> None:
        if restore_pause and self._clock.state is ClockState.RUNNING:
            self._clock.pause()

    def _require_scenario(self) -> Scenario:
        if self._scenario is None:
            raise RuntimeError("no scenario is loaded")
        return self._scenario


def execution_digest(events: list[SimulationEvent] | tuple[SimulationEvent, ...]) -> str:
    """Hash canonical execution order/type/time/priority/sequence/payload records."""

    records = [
        {
            "execution_order": index,
            "event_type": event.event_type,
            "scheduled_time_us": event.scheduled_time_us,
            "priority": event.priority,
            "sequence": event.sequence,
            "payload": thaw_json(event.payload),
        }
        for index, event in enumerate(events, start=1)
    ]
    canonical = json.dumps(
        records,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
