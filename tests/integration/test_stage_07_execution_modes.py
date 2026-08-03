"""Stage 7 execution-mode, observation, reset, and config determinism."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from symbiotic_sim_v2.runtime.closed_loop import (
    LightResponsiveClosedLoopSimulation,
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig

EXPECTED_DIGESTS = (
    "3392698943c200a9ab08964644ca72d56f50dfc1944c225b8c3e7933c5a229ae",
    "f8240cabbc882ceef81b537c29f907b60c23bad3bc207dac3c4a51b52aaca3cd",
    "8d46a403067232d1d4532ba878d22881ddc2e5f5b7e429394b5d26b02a03e706",
    "b09c15e82e25ee42eaaea0d374ac7ba041494f59c742fb953ec178a31f5ffe85",
    "d1be764aa7ffa60a8545e03e7f1fc853a4a95291a95dad09b873d1b9e2a31916",
    "b230c3d38ca3d1f85ba910c5970f667970c8d6e66533c84b3ecca7abe7c30bb7",
    "db9948271c0a664cd990c9954b131ebefc855a553005225241a6f94ac00625bf",
)


def result_digests(
    simulation: LightResponsiveClosedLoopSimulation,
) -> tuple[str, ...]:
    component = simulation.component
    return (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_dynamics_epoch_digest(),
        component.response_sample_digest(),
        simulation.engine.deterministic_digest(),
    )


def run_until_end(simulation: LightResponsiveClosedLoopSimulation) -> None:
    simulation.engine.run_until_end()


def run_one_second_steps(simulation: LightResponsiveClosedLoopSimulation) -> None:
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        simulation.engine.step_one_second()


def run_one_event_steps(simulation: LightResponsiveClosedLoopSimulation) -> None:
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        assert simulation.engine.step_one_event() is not None


def run_virtual_chunks(
    simulation: LightResponsiveClosedLoopSimulation,
    chunk_us: int,
) -> None:
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.advance_by_us(chunk_us)


def run_max_batches(simulation: LightResponsiveClosedLoopSimulation) -> None:
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.run_max_batch(max_events=37, wall_time_budget_ms=None)


RUNNERS: tuple[
    tuple[str, Callable[[LightResponsiveClosedLoopSimulation], None]], ...
] = (
    ("run_until_end", run_until_end),
    ("one_second", run_one_second_steps),
    ("one_event", run_one_event_steps),
    ("realtime_equivalent", lambda simulation: run_virtual_chunks(simulation, 17_000)),
    ("x10_equivalent", lambda simulation: run_virtual_chunks(simulation, 170_000)),
    ("x100_equivalent", lambda simulation: run_virtual_chunks(simulation, 1_700_000)),
    ("max_batch", run_max_batches),
)


@pytest.mark.parametrize(("_name", "runner"), RUNNERS, ids=[name for name, _ in RUNNERS])
def test_all_execution_modes_produce_the_exact_stage7_result(
    _name: str,
    runner: Callable[[LightResponsiveClosedLoopSimulation], None],
) -> None:
    simulation = create_light_responsive_closed_loop_simulation()
    runner(simulation)
    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert simulation.engine.clock.current_time_us == 240_000_000
    assert result_digests(simulation) == EXPECTED_DIGESTS


def test_reset_rebuilds_all_response_histories_and_digests() -> None:
    simulation = create_light_responsive_closed_loop_simulation()
    simulation.engine.run_until_end()
    first = result_digests(simulation)
    assert first == EXPECTED_DIGESTS

    simulation.engine.reset()
    component = simulation.component
    assert simulation.engine.clock.state is ClockState.STOPPED
    assert simulation.engine.executed_events() == ()
    assert component.heartbeat_records() == ()
    assert component.responsive_heartbeat_records() == ()
    assert component.light_receipt_records() == ()
    assert component.response_segments() == ()
    assert component.response_dynamics_epoch_records() == ()
    simulation.engine.run_until_end()
    assert result_digests(simulation) == first


def test_snapshot_and_response_query_frequency_do_not_mutate_results() -> None:
    simulation = create_light_responsive_closed_loop_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.advance_by_us(137_000)
        time_us = simulation.engine.clock.current_time_us
        for _ in range(7):
            simulation.engine.snapshot()
            simulation.component.snapshot()
            simulation.component.response_at(time_us)
            simulation.mapper.snapshot()
            simulation.device.snapshot(time_us)
            simulation.device.state_at(time_us)
    assert result_digests(simulation) == EXPECTED_DIGESTS


def test_light_response_config_json_round_trip_preserves_all_digests() -> None:
    config = LightResponseConfig.from_json(LightResponseConfig().to_json())
    simulation = create_light_responsive_closed_loop_simulation(
        light_response_config=config
    )
    simulation.engine.run_until_end()
    assert result_digests(simulation) == EXPECTED_DIGESTS
