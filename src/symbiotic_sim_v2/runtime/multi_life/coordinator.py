"""GUI-independent Stage 5B orchestration without central winner logic."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from symbiotic_sim_v2.digital_life.component import (
    GardenInputSignalInput,
    parse_garden_input_signal_event,
)
from symbiotic_sim_v2.domain.event_priorities import SIMULATION_COMPLETE_EVENT_PRIORITY
from symbiotic_sim_v2.domain.event_types import SIMULATION_COMPLETE_EVENT_TYPE
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.events import (
    GARDEN_HOLDER_RELEASE_EVENT_PRIORITY,
    GARDEN_HOLDER_RELEASE_EVENT_TYPE,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine

from .config import MultiLifeRuntimeConfig
from .feedback_router import FeedbackRouter
from .touch_delivery import TouchIntentLike, schedule_touch_intent

RUNTIME_EVENT_SOURCE = GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE


class ConnectedLife(Protocol):
    config: object

    def reset(self) -> None: ...

    def handle_evaluation_finalized(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None: ...

    def begin_signal(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> TouchIntentLike | None: ...

    def mark_touch_dispatched(self, signal_index: int, arrival_time_us: int) -> None: ...

    def handle_interoceptive_feedback(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None: ...

    def has_pending_second_round(self) -> bool: ...

    def mark_holder_released(self) -> None: ...


class GardenOutput(Protocol):
    config: object

    def reset(self) -> None: ...

    def begin_round(
        self,
        *,
        signal_index: int,
        signal_time_us: int,
        s: int,
        session_status: str,
        closing_signal: bool,
        round_finalize_time_us: int,
    ) -> None: ...

    def handle_round_finalize(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None: ...

    def release_holder(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class MultiLifeRuntimeSnapshot:
    runtime_model_version: str
    current_signal_index: int | None
    current_signal_time_us: int | None
    round_pending: bool
    garden_finalized: bool
    pending_feedback_ids: tuple[str, ...]
    completed_round_count: int
    scheduled_touch_count: int
    routed_feedback_count: int
    release_count: int


@dataclass(slots=True)
class _PendingRuntimeRound:
    signal_index: int
    signal_time_us: int
    s: int
    closing_signal: bool
    finalize_time_us: int
    expected_feedback_ids: frozenset[str]
    delivered_feedback_ids: set[str]
    garden_finalized: bool = False


class MultiLifeRuntimeCoordinator:
    """Coordinate three independent lives through scheduler-delivered events.

    The coordinator intentionally has no API for comparing P, V, B, or tau. Each
    enabled intent is independently mapped to a scheduled event; queue ordering
    and Garden's actual receipt order establish qualification.
    """

    def __init__(
        self,
        config: MultiLifeRuntimeConfig,
        digital_life_components: Mapping[str, ConnectedLife],
        garden_output_component: GardenOutput,
    ) -> None:
        if not isinstance(config, MultiLifeRuntimeConfig):
            raise TypeError("config must be a MultiLifeRuntimeConfig")
        if not isinstance(digital_life_components, Mapping):
            raise TypeError("digital_life_components must be a mapping")
        components = dict(digital_life_components)
        expected_ids = config.expected_digital_life_ids
        if set(components) != set(expected_ids):
            raise ValueError("Digital Life component IDs must match the runtime config")
        if len({id(component) for component in components.values()}) != len(components):
            raise ValueError("each Digital Life ID must have an independent component")
        for life_id, component in components.items():
            component_config = getattr(component, "config", None)
            if getattr(component_config, "digital_life_id", None) != life_id:
                raise ValueError("component mapping key and configured Digital Life ID differ")
            for method_name in (
                "reset",
                "handle_evaluation_finalized",
                "begin_signal",
                "mark_touch_dispatched",
                "handle_interoceptive_feedback",
                "has_pending_second_round",
                "mark_holder_released",
            ):
                if not callable(getattr(component, method_name, None)):
                    raise TypeError(f"Digital Life component must provide {method_name}()")
        for method_name in (
            "reset",
            "begin_round",
            "handle_round_finalize",
            "release_holder",
        ):
            if not callable(getattr(garden_output_component, method_name, None)):
                raise TypeError(f"Garden output component must provide {method_name}()")
        garden_config = getattr(garden_output_component, "config", None)
        if (
            getattr(garden_config, "expected_digital_life_ids", None)
            != expected_ids
        ):
            raise ValueError("Garden output roster must match the runtime config")

        self.config = config
        self._life_ids = expected_ids
        self._components = MappingProxyType(components)
        self._garden_output = garden_output_component
        self._feedback_router = FeedbackRouter(components)
        self.reset()

    @property
    def digital_life_components(self) -> Mapping[str, ConnectedLife]:
        return self._components

    def reset(self) -> None:
        """Clear orchestration state; scenario composition resets components once."""

        self._pending_round: _PendingRuntimeRound | None = None
        self._last_signal_index: int | None = None
        self._last_signal_time_us: int | None = None
        self._completed_round_count = 0
        self._scheduled_touch_count = 0
        self._routed_feedback_count = 0
        self._release_count = 0
        self._release_pending_for: tuple[int, int] | None = None

    def handle_evaluation_finalized(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Deliver the same formal evaluation event independently in ID order."""

        if self._pending_round is not None:
            raise RuntimeError("evaluation arrived before the previous round completed")
        for life_id in self._life_ids:
            self._components[life_id].handle_evaluation_finalized(event, engine)

    def handle_garden_input_signal(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Run three first rounds and schedule every enabled intent independently."""

        signal = parse_garden_input_signal_event(event)
        self._validate_next_signal(signal)
        closing_signal = signal.session_status == "completed"
        finalize_time_us = (
            signal.signal_time_us + self.config.round_finalize_offset_us
            if signal.s == 1
            else signal.signal_time_us
        )
        pending = _PendingRuntimeRound(
            signal_index=signal.signal_index,
            signal_time_us=signal.signal_time_us,
            s=signal.s,
            closing_signal=closing_signal,
            finalize_time_us=finalize_time_us,
            expected_feedback_ids=frozenset(self._life_ids),
            delivered_feedback_ids=set(),
        )
        self._pending_round = pending

        intents: dict[str, TouchIntentLike] = {}
        for life_id in self._life_ids:
            intent = self._components[life_id].begin_signal(event, engine)
            if intent is None:
                continue
            self._validate_intent(life_id, signal, intent)
            if intent.touch_enabled:
                intents[life_id] = intent
            elif signal.s == 1:
                raise RuntimeError("an active signal produced a disabled touch intent")

        if signal.s == 1 and set(intents) != set(self._life_ids):
            raise RuntimeError("an active round requires one enabled intent from every life")
        if signal.s == 0 and intents:
            raise RuntimeError("an inactive round cannot schedule a formal touch")

        self._garden_output.begin_round(
            signal_index=signal.signal_index,
            signal_time_us=signal.signal_time_us,
            s=signal.s,
            session_status=signal.session_status,
            closing_signal=closing_signal,
            round_finalize_time_us=finalize_time_us,
        )

        for life_id in self._life_ids:
            intent = intents.get(life_id)
            if intent is None:
                continue
            touch_event = schedule_touch_intent(engine, intent)
            self._components[life_id].mark_touch_dispatched(
                signal.signal_index,
                touch_event.scheduled_time_us,
            )
            self._scheduled_touch_count += 1

        finalize_type = (
            GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE
            if signal.s == 1
            else GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE
        )
        finalize_priority = (
            GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY
            if signal.s == 1
            else GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY
        )
        engine.schedule_at(
            finalize_time_us,
            finalize_type,
            source=RUNTIME_EVENT_SOURCE,
            priority=finalize_priority,
            payload={
                "signal_index": signal.signal_index,
                "signal_time_us": signal.signal_time_us,
            },
        )
        self._last_signal_index = signal.signal_index
        self._last_signal_time_us = signal.signal_time_us

    def handle_round_finalize(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Validate the control trigger, then let Garden produce its own outputs."""

        pending = self._require_pending_round()
        expected_type = (
            GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE
            if pending.s == 1
            else GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE
        )
        expected_priority = (
            GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY
            if pending.s == 1
            else GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY
        )
        if event.event_type != expected_type:
            raise ValueError("round finalize trigger type does not match S")
        if event.source != RUNTIME_EVENT_SOURCE:
            raise ValueError("round finalize trigger source must be runtime")
        if event.priority != expected_priority:
            raise ValueError("round finalize trigger priority does not match S")
        self._validate_round_control_payload(event, pending)
        if event.scheduled_time_us != pending.finalize_time_us:
            raise ValueError("round finalize trigger time does not match the round")
        if pending.garden_finalized:
            raise RuntimeError("round finalize trigger was delivered more than once")
        self._garden_output.handle_round_finalize(event, engine)
        pending.garden_finalized = True

    def handle_interoceptive_feedback(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Route one feedback event and close the round after all three recipients."""

        pending = self._require_pending_round()
        if not pending.garden_finalized:
            raise RuntimeError("feedback arrived before Garden round finalization")
        recipient_id = self._feedback_router.recipient_id(event)
        if event.payload["signal_index"] != pending.signal_index:
            raise ValueError("feedback signal_index does not match the pending round")
        if event.payload["signal_time_us"] != pending.signal_time_us:
            raise ValueError("feedback signal_time_us does not match the pending round")
        if recipient_id in pending.delivered_feedback_ids:
            raise RuntimeError("duplicate feedback recipient in one round")
        self._feedback_router.route(event, engine)
        pending.delivered_feedback_ids.add(recipient_id)
        self._routed_feedback_count += 1

        if pending.delivered_feedback_ids == set(pending.expected_feedback_ids):
            for life_id in self._life_ids:
                if self._components[life_id].has_pending_second_round():
                    raise RuntimeError("a Digital Life did not finish its second round")
            closing = pending.closing_signal
            closing_identity = (pending.signal_index, pending.signal_time_us)
            if closing:
                # This is the sole cross-life closing barrier: every second round
                # has returned, while holder release has not yet been scheduled.
                # The Runtime invokes component-owned policy but never reads or
                # rewrites E, q, k, counters, or candidate state itself.
                for life_id in self._life_ids:
                    hook = getattr(
                        self._components[life_id],
                        "finalize_session_end_state_policy",
                        None,
                    )
                    if hook is not None:
                        if not callable(hook):
                            raise TypeError(
                                "Digital Life session-end state policy hook must be callable"
                            )
                        hook()
            self._completed_round_count += 1
            self._pending_round = None
            if closing:
                self._release_pending_for = closing_identity
                engine.schedule_at(
                    event.scheduled_time_us,
                    GARDEN_HOLDER_RELEASE_EVENT_TYPE,
                    source=RUNTIME_EVENT_SOURCE,
                    priority=GARDEN_HOLDER_RELEASE_EVENT_PRIORITY,
                    payload={
                        "signal_index": closing_identity[0],
                        "signal_time_us": closing_identity[1],
                    },
                )

    def handle_holder_release(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Release only after all closing feedback handlers have returned."""

        if self._pending_round is not None:
            raise RuntimeError("holder release cannot precede second-round completion")
        if event.event_type != GARDEN_HOLDER_RELEASE_EVENT_TYPE:
            raise ValueError("holder release handler received the wrong event type")
        if event.source != RUNTIME_EVENT_SOURCE:
            raise ValueError("holder release source must be runtime")
        if event.priority != GARDEN_HOLDER_RELEASE_EVENT_PRIORITY:
            raise ValueError("holder release priority does not match Stage 5B")
        if self._release_pending_for is None:
            raise RuntimeError("no closing holder release is pending")
        signal_index, signal_time_us = self._release_pending_for
        if not isinstance(event.payload, dict) or set(event.payload) != {
            "signal_index",
            "signal_time_us",
        }:
            raise ValueError("holder release payload fields are invalid")
        if (
            event.payload["signal_index"] != signal_index
            or event.payload["signal_time_us"] != signal_time_us
        ):
            raise ValueError("holder release payload does not match the closing round")
        self._garden_output.release_holder(event, engine)
        for life_id in self._life_ids:
            self._components[life_id].mark_holder_released()
        self._release_pending_for = None
        self._release_count += 1

    def snapshot(self) -> MultiLifeRuntimeSnapshot:
        pending = self._pending_round
        return MultiLifeRuntimeSnapshot(
            runtime_model_version=self.config.runtime_model_version,
            current_signal_index=self._last_signal_index,
            current_signal_time_us=self._last_signal_time_us,
            round_pending=pending is not None,
            garden_finalized=False if pending is None else pending.garden_finalized,
            pending_feedback_ids=(
                ()
                if pending is None
                else tuple(sorted(pending.expected_feedback_ids - pending.delivered_feedback_ids))
            ),
            completed_round_count=self._completed_round_count,
            scheduled_touch_count=self._scheduled_touch_count,
            routed_feedback_count=self._routed_feedback_count,
            release_count=self._release_count,
        )

    def handle_simulation_complete(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Reject completion until every round and the closing release are complete."""

        if event.event_type != SIMULATION_COMPLETE_EVENT_TYPE:
            raise ValueError("completion handler received the wrong event type")
        if event.priority != SIMULATION_COMPLETE_EVENT_PRIORITY:
            raise ValueError("completion priority does not match the stable boundary")
        if self._pending_round is not None:
            raise RuntimeError("simulation completed with a pending runtime round")
        if self._release_pending_for is not None:
            raise RuntimeError("simulation completed before holder release")
        expected_round_count = 0 if self._last_signal_index is None else self._last_signal_index + 1
        if self._completed_round_count != expected_round_count:
            raise RuntimeError("simulation completed with a missing second round")

    def _validate_next_signal(self, signal: GardenInputSignalInput) -> None:
        if self._pending_round is not None:
            raise RuntimeError("the previous signal's second round is incomplete")
        if self._release_pending_for is not None:
            raise RuntimeError("the closing holder release is incomplete")
        if (
            self._last_signal_index is not None
            and signal.signal_index != self._last_signal_index + 1
        ):
            raise ValueError("runtime signal_index must increase by exactly one")
        if (
            self._last_signal_time_us is not None
            and signal.signal_time_us <= self._last_signal_time_us
        ):
            raise ValueError("runtime signal time must strictly increase")
        if signal.session_status == "completed" and signal.s != 0:
            raise ValueError("the closing completed signal must have S=0")

    @staticmethod
    def _validate_intent(
        life_id: str,
        signal: GardenInputSignalInput,
        intent: TouchIntentLike,
    ) -> None:
        if intent.digital_life_id != life_id:
            raise ValueError("TouchIntent was returned under the wrong Digital Life ID")
        if intent.signal_index != signal.signal_index:
            raise ValueError("TouchIntent signal_index does not match the formal signal")
        if intent.signal_time_us != signal.signal_time_us:
            raise ValueError("TouchIntent signal_time_us does not match the formal signal")
        if not isinstance(intent.touch_enabled, bool):
            raise TypeError("TouchIntent touch_enabled must be boolean")

    @staticmethod
    def _validate_round_control_payload(
        event: SimulationEvent,
        pending: _PendingRuntimeRound,
    ) -> None:
        if not isinstance(event.payload, dict) or set(event.payload) != {
            "signal_index",
            "signal_time_us",
        }:
            raise ValueError("round finalize payload fields are invalid")
        if event.payload["signal_index"] != pending.signal_index:
            raise ValueError("round finalize signal_index does not match the round")
        if event.payload["signal_time_us"] != pending.signal_time_us:
            raise ValueError("round finalize signal_time_us does not match the round")

    def _require_pending_round(self) -> _PendingRuntimeRound:
        if self._pending_round is None:
            raise RuntimeError("no runtime round is pending")
        return self._pending_round
