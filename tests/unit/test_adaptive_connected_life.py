"""Formal-boundary tests for the Stage 5C adaptive connected component."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.math import (
    calculate_e_next,
    intrinsic_b_mapping,
)
from symbiotic_sim_v2.digital_life.relation_memory.adaptive_component import (
    AdaptiveConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.domain.event_priorities import (
    GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
    GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import GARDEN_INPUT_EVENT_SOURCE
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.events import (
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    GARDEN_OUTPUT_EVENT_SOURCE,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler

BASELINE_ID = "adaptive-component-baseline"
BASELINE_N = 0.2


@dataclass(frozen=True, slots=True)
class EmptyScenario:
    start_time_us: int = 0
    end_time_us: int = 240_000_000

    def schedule(self, _scheduler: EventScheduler) -> None:
        return None


def evaluation_event(
    *,
    evaluation_id: str,
    time_us: int,
    evaluation_kind: str,
    bundle_index: int | None,
    n: float,
    revision: int,
) -> SimulationEvent:
    return SimulationEvent(
        event_id=f"evaluation-{evaluation_id}",
        event_type=GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
        source=GARDEN_INPUT_EVENT_SOURCE,
        scheduled_time_us=time_us,
        priority=GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
        sequence=revision,
        payload={
            "evaluation_id": evaluation_id,
            "evaluation_kind": evaluation_kind,
            "bundle_index": bundle_index,
            "quality": "valid",
            "is_valid": True,
            "n": n,
            "n_revision": revision,
            "baseline_id": BASELINE_ID,
            "schema_version": "garden_evaluation_finalized_event_v1",
        },
    )


def signal_event(
    *,
    signal_index: int,
    n_current: float,
    revision: int,
    latest_evaluation_id: str,
    phase: str,
    bundle_index: int | None,
    window_role: str,
) -> SimulationEvent:
    time_us = signal_index * 1_000_000
    return SimulationEvent(
        event_id=f"signal-{signal_index}",
        event_type=GARDEN_INPUT_SIGNAL_EVENT_TYPE,
        source=GARDEN_INPUT_EVENT_SOURCE,
        scheduled_time_us=time_us,
        priority=GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
        sequence=10_000 + signal_index,
        payload={
            "signal_index": signal_index,
            "signal_time_us": time_us,
            "s": 1,
            "phase": phase,
            "bundle_index": bundle_index,
            "window_role": window_role,
            "n_current": n_current,
            "n_available": True,
            "n_baseline_session": BASELINE_N,
            "baseline_available": True,
            "latest_valid_evaluation_id": latest_evaluation_id,
            "valid_evaluation_revision": revision,
            "session_status": "active",
            "schema_version": "garden_input_signal_event_v1",
        },
    )


def feedback_event(
    *,
    signal_index: int,
    returned_b: tuple[float, float, float, float],
    holder: str = "life-green",
) -> SimulationEvent:
    signal_time_us = signal_index * 1_000_000
    return SimulationEvent(
        event_id=f"feedback-{signal_index}-life-green",
        event_type=GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
        source=GARDEN_OUTPUT_EVENT_SOURCE,
        scheduled_time_us=signal_time_us + 999_999,
        priority=GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
        sequence=20_000 + signal_index,
        payload={
            "garden_id": "relax-with-light",
            "recipient_digital_life_id": "life-green",
            "signal_index": signal_index,
            "signal_time_us": signal_time_us,
            "s": 1,
            "qualification_holder_id": holder,
            "returned_b_f": returned_b[0],
            "returned_b_a": returned_b[1],
            "returned_b_t": returned_b[2],
            "returned_b_d": returned_b[3],
            "attribution_source": "current_signal_touch",
            "closing_evaluation_attribution": False,
            "schema_version": "garden_interoceptive_feedback_event_v1",
        },
    )


def complete_round(
    component: AdaptiveConnectedDigitalLifeComponent,
    engine: SimulationEngine,
    signal: SimulationEvent,
) -> tuple[float, float, float, float]:
    intent = component.begin_signal(signal, engine)
    assert intent is not None
    component.mark_touch_dispatched(
        signal.payload["signal_index"],  # type: ignore[index]
        signal.scheduled_time_us + 500_000,
    )
    component.handle_interoceptive_feedback(
        feedback_event(
            signal_index=signal.payload["signal_index"],  # type: ignore[index]
            returned_b=intent.b,
        ),
        engine,
    )
    return intent.b


def test_injected_persistent_state_is_owned_and_reset_as_one_fresh_session() -> None:
    config = digital_life_config_for_role("green")
    injected = replace(
        RelationMemoryPersistentState.fresh(config.digital_life_id),
        k_anchor=(0.2, 0.3, 0.4, 0.7),
        q=0.65,
        e=0.25,
        trial_count=4,
        session_count=9,
    )
    component = AdaptiveConnectedDigitalLifeComponent(config, injected)

    assert component.initial_persistent_state() is injected
    assert component.current_persistent_state() is injected
    assert component.final_persistent_state() is None
    assert component.snapshot().k_current == injected.k_anchor
    assert component.snapshot().q == injected.q
    assert component.snapshot().e == injected.e
    session = component.relation_memory_session_state()
    assert session.session_count_used == 9
    assert session.initial_k_anchor == injected.k_anchor
    assert session.w_anchor_session is None
    assert session.k_trial is None

    replacement = replace(injected, session_count=12, trial_count=6)
    component.reset_session(replacement)
    assert component.initial_persistent_state() is replacement
    assert component.current_persistent_state() is replacement
    assert component.relation_memory_session_state().session_count_used == 12
    assert component.adaptive_signal_records() == ()
    assert component.relation_memory_transition_records() == ()
    assert component.final_persistent_state() is None

    wrong_id = replace(replacement, digital_life_id="life-red")
    with pytest.raises(ValueError, match="does not match"):
        component.reset_session(wrong_id)


def test_formal_feedback_commits_q_e_and_candidate_atomically_for_next_signal() -> None:
    config = digital_life_config_for_role("green")
    component = AdaptiveConnectedDigitalLifeComponent(config)
    engine = SimulationEngine(EmptyScenario())

    component.handle_evaluation_finalized(
        evaluation_event(
            evaluation_id=BASELINE_ID,
            time_us=60_000_000,
            evaluation_kind="baseline",
            bundle_index=None,
            n=BASELINE_N,
            revision=1,
        ),
        engine,
    )
    complete_round(
        component,
        engine,
        signal_event(
            signal_index=60,
            n_current=BASELINE_N,
            revision=1,
            latest_evaluation_id=BASELINE_ID,
            phase="baseline_evaluation",
            bundle_index=None,
            window_role="evaluation",
        ),
    )
    assert component.relation_memory_session_state().w_anchor_session is None

    component.handle_evaluation_finalized(
        evaluation_event(
            evaluation_id="adaptive-bundle-0",
            time_us=120_000_000,
            evaluation_kind="bundle",
            bundle_index=0,
            n=0.0,
            revision=2,
        ),
        engine,
    )
    signal_120 = signal_event(
        signal_index=120,
        n_current=0.0,
        revision=2,
        latest_evaluation_id="adaptive-bundle-0",
        phase="bundle_0_evaluation",
        bundle_index=0,
        window_role="evaluation",
    )
    intent_120 = component.begin_signal(signal_120, engine)
    assert intent_120 is not None
    component.mark_touch_dispatched(120, 120_500_000)
    before = component.snapshot()
    first_120 = component.first_round_records()[-1]
    component.handle_interoceptive_feedback(
        feedback_event(signal_index=120, returned_b=intent_120.b),
        engine,
    )

    after = component.snapshot()
    transition = component.relation_memory_transition_records()[-1]
    adaptive = component.adaptive_signal_records()[-1]
    inherited = component.second_round_records()[-1]
    session = component.relation_memory_session_state()
    candidate = session.k_trial
    assert candidate is not None
    assert transition.signal_index == 120
    assert transition.k_current_before == first_120.k_current == before.k_current
    assert transition.k_current_after == candidate == after.k_current
    assert transition.k_anchor_before == transition.k_anchor_after == before.k_anchor
    assert candidate[1] == before.k_anchor[1]
    assert candidate[3] == before.k_anchor[3]
    assert component.current_persistent_state().trial_count == 1
    assert component.candidate_count() == 1

    # E, q, and relation memory all use the exact same pre-feedback state.
    assert adaptive.q_before == inherited.q_before == before.q
    assert adaptive.e_before == inherited.e_before == before.e
    assert adaptive.k_current_before == inherited.k_before == before.k_current
    assert adaptive.q_after == inherited.q_after == after.q
    assert adaptive.e_after == inherited.e_after == after.e
    assert after.e == pytest.approx(calculate_e_next(before.e, 1, 1))

    # The update is synchronous, but B for signal 120 remains the first-round B.
    assert adaptive.k_presented == before.k_current
    assert adaptive.k_current_after == candidate
    assert adaptive.candidate_effective_next_signal
    assert adaptive.b_presented == intent_120.b
    assert inherited.first_round_b == inherited.returned_b == intent_120.b
    assert after.b == intent_120.b

    signal_121 = signal_event(
        signal_index=121,
        n_current=0.0,
        revision=2,
        latest_evaluation_id="adaptive-bundle-0",
        phase="bundle_1_discard",
        bundle_index=1,
        window_role="discard",
    )
    intent_121 = component.begin_signal(signal_121, engine)
    assert intent_121 is not None
    first_121 = component.first_round_records()[-1]
    expected_candidate_b = intrinsic_b_mapping(
        candidate,
        f_min=config.f_min,
        f_max=config.f_max,
        a_fixed=config.a_fixed,
        t_min=config.t_min,
        t_max=config.t_max,
        d_fixed=config.d_fixed,
    )
    assert first_121.k_current == candidate
    assert intent_121.b == expected_candidate_b
    assert intent_121.b != intent_120.b
    assert first_121.q == after.q
    assert first_121.e == after.e
    component.mark_touch_dispatched(121, 121_500_000)
    component.handle_interoceptive_feedback(
        feedback_event(signal_index=121, returned_b=intent_121.b),
        engine,
    )
    assert component.candidate_count() == 1
    assert component.current_persistent_state().trial_count == 1
