"""Deterministic heap-based event scheduler."""

from __future__ import annotations

import heapq
from collections.abc import Callable
from typing import Any

from symbiotic_sim_v2.domain.events import SimulationEvent

TimeProvider = Callable[[], int]


class EventScheduler:
    """Schedule immutable events with stable time/priority/sequence ordering."""

    def __init__(
        self,
        current_time_provider: TimeProvider | None = None,
        end_time_provider: TimeProvider | None = None,
    ) -> None:
        self._current_time_provider = current_time_provider or (lambda: 0)
        self._end_time_provider = end_time_provider
        self._heap: list[tuple[int, int, int, SimulationEvent]] = []
        self._events_by_id: dict[str, SimulationEvent] = {}
        self._issued_ids: set[str] = set()
        self._next_sequence = 0

    @property
    def pending_count(self) -> int:
        """Return the number of non-cancelled queued events."""

        return len(self._events_by_id)

    @property
    def has_pending_events(self) -> bool:
        """Return whether at least one executable event remains."""

        return bool(self._events_by_id)

    def schedule_at(
        self,
        scheduled_time_us: int,
        event_type: str,
        *,
        source: str = "simulation",
        priority: int = 100,
        payload: Any = None,
        event_id: str | None = None,
    ) -> SimulationEvent:
        """Schedule an event at an absolute virtual time."""

        now_us = self._current_time_provider()
        if scheduled_time_us < now_us:
            raise ValueError("cannot schedule an event in the virtual past")
        if self._end_time_provider is not None and scheduled_time_us > self._end_time_provider():
            raise ValueError("cannot schedule an event beyond the simulation end")

        sequence = self._next_sequence
        assigned_id = event_id or f"evt-{sequence:06d}"
        if assigned_id in self._issued_ids:
            raise ValueError(f"duplicate event_id: {assigned_id}")

        event = SimulationEvent(
            event_id=assigned_id,
            event_type=event_type,
            source=source,
            scheduled_time_us=scheduled_time_us,
            priority=priority,
            sequence=sequence,
            payload={} if payload is None else payload,
        )
        self._next_sequence += 1
        self._issued_ids.add(assigned_id)
        self._events_by_id[event.event_id] = event
        heapq.heappush(self._heap, (*event.ordering_key, event))
        return event

    def schedule_after(
        self,
        delay_us: int,
        event_type: str,
        *,
        source: str = "simulation",
        priority: int = 100,
        payload: Any = None,
        event_id: str | None = None,
    ) -> SimulationEvent:
        """Schedule relative to the current virtual time."""

        if isinstance(delay_us, bool) or not isinstance(delay_us, int):
            raise TypeError("delay_us must be an integer")
        if delay_us < 0:
            raise ValueError("delay_us must be non-negative")
        return self.schedule_at(
            self._current_time_provider() + delay_us,
            event_type,
            source=source,
            priority=priority,
            payload=payload,
            event_id=event_id,
        )

    def peek_next(self) -> SimulationEvent | None:
        """Return the next event without removing it."""

        self._discard_cancelled_head()
        return self._heap[0][3] if self._heap else None

    def pop_next(self) -> SimulationEvent | None:
        """Remove and return the next non-cancelled event."""

        self._discard_cancelled_head()
        if not self._heap:
            return None
        event = heapq.heappop(self._heap)[3]
        self._events_by_id.pop(event.event_id)
        return event

    def pop_due(self, target_time_us: int) -> tuple[SimulationEvent, ...]:
        """Pop the events currently queued at or before an inclusive target time."""

        if target_time_us < self._current_time_provider():
            raise ValueError("target_time_us cannot precede current virtual time")
        due: list[SimulationEvent] = []
        while (event := self.peek_next()) is not None:
            if event.scheduled_time_us > target_time_us:
                break
            popped = self.pop_next()
            if popped is not None:
                due.append(popped)
        return tuple(due)

    def cancel(self, event_id: str) -> bool:
        """Cancel a pending event; return ``False`` when it is not pending."""

        return self._events_by_id.pop(event_id, None) is not None

    def clear(self) -> None:
        """Remove all pending events while preserving sequence monotonicity."""

        self._heap.clear()
        self._events_by_id.clear()

    def reset(self) -> None:
        """Clear the queue and restart deterministic IDs and sequence numbers."""

        self.clear()
        self._issued_ids.clear()
        self._next_sequence = 0

    def pending_events(self) -> tuple[SimulationEvent, ...]:
        """Return a sorted, immutable view without exposing the internal heap."""

        return tuple(sorted(self._events_by_id.values(), key=lambda event: event.ordering_key))

    def _discard_cancelled_head(self) -> None:
        while self._heap and self._heap[0][3].event_id not in self._events_by_id:
            heapq.heappop(self._heap)
