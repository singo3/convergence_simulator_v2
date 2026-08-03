"""Stage 5C execution-mode, observation, and reset determinism."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from symbiotic_sim_v2.digital_life.connected_component import (
    ConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.relation_memory.adaptive_component import (
    AdaptiveConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.relation_memory.diagnostics import (
    adaptive_signal_digest,
    final_persistent_state_digest,
    intrinsic_profile_digest,
    relation_memory_transition_digest,
    session_summary_digest,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.closed_loop import (
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState

EXPECTED_STAGE5C_DIGESTS = (
    "97289a7bd4672edb5ffc7ecb56543a7602638c1a9b76a0859b81bbef332c67d2",
    "90751d6ce46cd810ade11db5bfcc7a26642c264cbd18426e4b4476cc099811cf",
    "534b24088f5d39d51a11640e659813da322f54f3056ad2ef900cc4aa530873f6",
    "a0166bf6c27b9b42629a7bcbf86c5b8ecf0a62f458f1e7ea4b1a98c921e8a999",
    "7d5b885d843e251171ad18c29e753355ddddf1646a2f7f18b692537d55d0070c",
    "edd74c6da4136319f46f7ade2c56baf9b887330dd19e634cdce266e42e3669e4",
    "d841f8243bcb839ab7e26f00fcaeedcf307b12c51af26667d313aa57b2e2b7f7",
    "ca77c5bd92050c42aedd8896cfc8c4e49f252f395fadba862594b1fe8834680f",
    "45167f62c4cd6723f953a63d8e25de1f60215770571dcd4d54928f01f39e17f4",
    "2afb235b6b41b98fd6a34dd1dcc3b1e2365ed93d26e27ee76e71f0cb71689de1",
)


def stage5c_digests(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> tuple[str, ...]:
    components = adaptive_digital_life_components(simulation)
    return (
        simulation.engine.deterministic_digest(),
        intrinsic_profile_digest(components),
        adaptive_signal_digest(components),
        relation_memory_transition_digest(components),
        final_persistent_state_digest(components),
        session_summary_digest(components),
        simulation.component.heartbeat_digest(),
        simulation.component.responsive_diagnostic_digest(),
        simulation.component.light_receipt_digest(),
        simulation.component.response_dynamics_epoch_digest(),
    )


def run_until_end(simulation: AdaptiveRelationMemoryClosedLoopSimulation) -> None:
    simulation.engine.run_until_end()


def run_one_second_steps(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> None:
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        simulation.engine.step_one_second()


def run_one_event_steps(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> None:
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        assert simulation.engine.step_one_event() is not None


def run_maximum_batches(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> None:
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.run_max_batch(max_events=37, wall_time_budget_ms=None)
        # Observation frequency is deliberately unrelated to the batch size.
        simulation.engine.snapshot()
        simulation.component.snapshot()
        simulation.mapper.snapshot()
        for component in adaptive_digital_life_components(simulation).values():
            component.snapshot()
            component.relation_memory_session_state()
            component.adaptive_signal_records()


RUNNERS: tuple[
    tuple[
        str,
        Callable[[AdaptiveRelationMemoryClosedLoopSimulation], None],
    ],
    ...,
] = (
    ("run_until_end", run_until_end),
    ("one_second", run_one_second_steps),
    ("one_event", run_one_event_steps),
    ("max_batch", run_maximum_batches),
)


@pytest.mark.parametrize(("_name", "runner"), RUNNERS, ids=[name for name, _ in RUNNERS])
def test_execution_modes_produce_identical_stage5c_and_physical_digests(
    _name: str,
    runner: Callable[[AdaptiveRelationMemoryClosedLoopSimulation], None],
) -> None:
    simulation = create_adaptive_relation_memory_closed_loop_simulation()
    runner(simulation)

    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert simulation.engine.clock.current_time_us == 240_000_000
    assert stage5c_digests(simulation) == EXPECTED_STAGE5C_DIGESTS


def test_reset_clears_transient_and_final_state_then_reproduces_every_digest() -> None:
    simulation = create_adaptive_relation_memory_closed_loop_simulation()
    simulation.engine.run_until_end()
    expected = stage5c_digests(simulation)
    assert expected == EXPECTED_STAGE5C_DIGESTS

    simulation.engine.reset()
    assert simulation.engine.clock.state is ClockState.STOPPED
    assert simulation.engine.executed_events() == ()
    for component in adaptive_digital_life_components(simulation).values():
        assert component.final_persistent_state() is None
        assert component.current_persistent_state() == component.initial_persistent_state()
        assert component.adaptive_signal_records() == ()
        assert component.relation_memory_transition_records() == ()
        assert component.candidate_count() == 0
        session = component.relation_memory_session_state()
        assert session.w_anchor_session is None
        assert session.k_trial is None
        assert not session.session_finalized

    simulation.engine.run_until_end()
    assert stage5c_digests(simulation) == expected


def test_existing_public_stage7_factory_remains_legacy_and_byte_deterministic() -> None:
    simulation = create_light_responsive_closed_loop_simulation()
    assert all(
        type(component) is ConnectedDigitalLifeComponent
        for component in simulation.digital_life_components.values()
    )
    assert not any(
        isinstance(component, AdaptiveConnectedDigitalLifeComponent)
        for component in simulation.digital_life_components.values()
    )

    simulation.engine.run_until_end()
    assert simulation.component.heartbeat_digest() == (
        "3392698943c200a9ab08964644ca72d56f50dfc1944c225b8c3e7933c5a229ae"
    )
    assert simulation.engine.deterministic_digest() == (
        "db9948271c0a664cd990c9954b131ebefc855a553005225241a6f94ac00625bf"
    )
