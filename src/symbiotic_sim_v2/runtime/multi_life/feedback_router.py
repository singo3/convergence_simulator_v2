"""Recipient-only routing for formal Garden interoceptive feedback."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.events import (
    GARDEN_OUTPUT_EVENT_SOURCE,
    parse_garden_interoceptive_feedback_event,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine

GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_SOURCE = GARDEN_OUTPUT_EVENT_SOURCE


class FeedbackRecipient(Protocol):
    def handle_interoceptive_feedback(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None: ...


class FeedbackRouter:
    """Route each event to exactly one configured component, never broadcast it."""

    def __init__(self, recipients: Mapping[str, FeedbackRecipient]) -> None:
        if not isinstance(recipients, Mapping):
            raise TypeError("recipients must be a mapping")
        copied = dict(recipients)
        if not copied:
            raise ValueError("at least one feedback recipient is required")
        for life_id, component in copied.items():
            if not isinstance(life_id, str) or not life_id.strip():
                raise ValueError("feedback recipient IDs must be non-empty strings")
            if not callable(getattr(component, "handle_interoceptive_feedback", None)):
                raise TypeError("each recipient must handle interoceptive feedback")
        self._recipients = MappingProxyType(copied)

    @property
    def recipient_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._recipients))

    def recipient_id(self, event: SimulationEvent) -> str:
        """Validate the formal routing envelope and return its sole recipient."""

        parsed = parse_garden_interoceptive_feedback_event(event)
        recipient_id = parsed.recipient_digital_life_id
        if recipient_id not in self._recipients:
            raise ValueError("feedback recipient is not a configured Digital Life")
        return recipient_id

    def route(self, event: SimulationEvent, engine: SimulationEngine) -> str:
        """Deliver the event only to its recipient and return that recipient ID."""

        recipient_id = self.recipient_id(event)
        self._recipients[recipient_id].handle_interoceptive_feedback(event, engine)
        return recipient_id
