"""Focused synchronization, tie-break, and recipient-routing runtime tests."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from symbiotic_sim_v2.digital_life.touch_intent import DigitalLifeTouchIntent
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.runtime.multi_life.config import MultiLifeRuntimeConfig
from symbiotic_sim_v2.runtime.multi_life.coordinator import MultiLifeRuntimeCoordinator
from symbiotic_sim_v2.runtime.multi_life.feedback_router import FeedbackRouter
from symbiotic_sim_v2.runtime.multi_life.touch_delivery import (
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler


@dataclass(frozen=True, slots=True)
class EmptyScenario:
    start_time_us: int = 0
    end_time_us: int = 1_000_000

    def schedule(self, _scheduler: EventScheduler) -> None:
        return None


class FakeLife:
    def __init__(self, life_id: str, role: str) -> None:
        self.config = SimpleNamespace(digital_life_id=life_id)
        self.role = role
        self.received_feedback: list[SimulationEvent] = []
        self.dispatched: list[tuple[int, int]] = []
        self.pending = False

    def reset(self) -> None:
        self.received_feedback.clear()
        self.dispatched.clear()
        self.pending = False

    def handle_evaluation_finalized(
        self, _event: SimulationEvent, _engine: SimulationEngine
    ) -> None:
        return None

    def begin_signal(
        self, event: SimulationEvent, _engine: SimulationEngine
    ) -> DigitalLifeTouchIntent:
        self.pending = True
        return DigitalLifeTouchIntent(
            signal_index=event.payload["signal_index"],
            signal_time_us=event.payload["signal_time_us"],
            digital_life_id=self.config.digital_life_id,
            role=self.role,
            b=(0.5, 0.5, 0.5, 0.5),
            tau=0.25,
            touch_enabled=True,
        )

    def mark_touch_dispatched(self, signal_index: int, arrival_time_us: int) -> None:
        self.dispatched.append((signal_index, arrival_time_us))

    def handle_interoceptive_feedback(
        self, event: SimulationEvent, _engine: SimulationEngine
    ) -> None:
        self.received_feedback.append(event)
        self.pending = False

    def has_pending_second_round(self) -> bool:
        return self.pending

    def mark_holder_released(self) -> None:
        return None


class FakeGarden:
    config = SimpleNamespace(
        expected_digital_life_ids=("life-blue", "life-green", "life-red")
    )

    def reset(self) -> None:
        return None

    def begin_round(self, **_values: object) -> None:
        return None

    def handle_round_finalize(
        self, _event: SimulationEvent, _engine: SimulationEngine
    ) -> None:
        return None

    def release_holder(self, _event: SimulationEvent, _engine: SimulationEngine) -> None:
        return None


def active_signal_event() -> SimulationEvent:
    return SimulationEvent(
        event_id="signal",
        event_type="garden_input_signal",
        source="garden_input",
        scheduled_time_us=0,
        priority=30,
        sequence=0,
        payload={
            "signal_index": 0,
            "signal_time_us": 0,
            "s": 1,
            "phase": "bundle_0_discard",
            "bundle_index": 0,
            "window_role": "discard",
            "n_current": 0.2,
            "n_available": True,
            "n_baseline_session": 0.2,
            "baseline_available": True,
            "latest_valid_evaluation_id": "baseline",
            "valid_evaluation_revision": 1,
            "session_status": "active",
            "schema_version": "garden_input_signal_event_v1",
        },
    )


def feedback_event(recipient: str) -> SimulationEvent:
    return SimulationEvent(
        event_id=f"feedback-{recipient}",
        event_type="garden_interoceptive_feedback",
        source="garden_output",
        scheduled_time_us=999_999,
        priority=80,
        sequence=0,
        payload={
            "garden_id": "relax-with-light",
            "recipient_digital_life_id": recipient,
            "signal_index": 0,
            "signal_time_us": 0,
            "s": 1,
            "qualification_holder_id": "life-green",
            "returned_b_f": 0.5,
            "returned_b_a": 0.5,
            "returned_b_t": 0.5,
            "returned_b_d": 0.5,
            "attribution_source": "current_signal_touch",
            "closing_evaluation_attribution": False,
            "schema_version": "garden_interoceptive_feedback_event_v1",
        },
    )


def fake_lives_reversed() -> dict[str, FakeLife]:
    return {
        "life-red": FakeLife("life-red", "red"),
        "life-green": FakeLife("life-green", "green"),
        "life-blue": FakeLife("life-blue", "blue"),
    }


def test_equal_arrival_registration_uses_lexical_id_only_as_sequence_tie_break() -> None:
    engine = SimulationEngine(EmptyScenario())
    lives = fake_lives_reversed()
    coordinator = MultiLifeRuntimeCoordinator(MultiLifeRuntimeConfig(), lives, FakeGarden())
    coordinator.handle_garden_input_signal(active_signal_event(), engine)

    touches = [
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == DIGITAL_LIFE_TOUCH_EVENT_TYPE
    ]
    assert len({event.scheduled_time_us for event in touches}) == 1
    assert tuple(event.payload["digital_life_id"] for event in touches) == (
        "life-blue",
        "life-green",
        "life-red",
    )
    assert [event.sequence for event in touches] == sorted(event.sequence for event in touches)


def test_next_signal_is_rejected_while_previous_second_round_is_pending() -> None:
    engine = SimulationEngine(EmptyScenario())
    coordinator = MultiLifeRuntimeCoordinator(
        MultiLifeRuntimeConfig(), fake_lives_reversed(), FakeGarden()
    )
    signal = active_signal_event()
    coordinator.handle_garden_input_signal(signal, engine)
    with pytest.raises(RuntimeError, match="previous signal"):
        coordinator.handle_garden_input_signal(signal, engine)


def test_feedback_router_delivers_to_exactly_one_recipient() -> None:
    engine = SimulationEngine(EmptyScenario())
    lives = fake_lives_reversed()
    router = FeedbackRouter(lives)
    recipient = router.route(feedback_event("life-green"), engine)

    assert recipient == "life-green"
    assert len(lives["life-green"].received_feedback) == 1
    assert not lives["life-blue"].received_feedback
    assert not lives["life-red"].received_feedback


def test_feedback_router_rejects_an_unknown_recipient_without_broadcasting() -> None:
    engine = SimulationEngine(EmptyScenario())
    lives = fake_lives_reversed()
    router = FeedbackRouter(lives)
    with pytest.raises(ValueError, match="not a configured"):
        router.route(feedback_event("life-unknown"), engine)
    assert all(not life.received_feedback for life in lives.values())


def test_coordinator_rejects_a_garden_with_a_different_session_roster() -> None:
    garden = FakeGarden()
    garden.config = SimpleNamespace(
        expected_digital_life_ids=("alpha", "middle", "zeta")
    )

    with pytest.raises(ValueError, match="Garden output roster"):
        MultiLifeRuntimeCoordinator(
            MultiLifeRuntimeConfig(),
            fake_lives_reversed(),
            garden,
        )
