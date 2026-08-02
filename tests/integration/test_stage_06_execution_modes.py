"""Stage 6 execution-mode, reset, observation, and config determinism."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from symbiotic_sim_v2.devices.virtual_light.config import VirtualLightDeviceConfig
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    LightFeedbackSimulation,
    create_light_feedback_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState

EXPECTED_DIGESTS = (
    "306648650d4b286a48b3f9188f7fd640764b05fb135c581c4b9d00b487d06020",
    "1dbf214e1448802a665031f73fb798cdbf04471210aeddf438c68b72b616265e",
    "9dabc1b018b52f9be603ba164655f3c5fa79ff4f6579ae8a6bfd48047d8fd763",
    "a075f488a588d7d2f78548e4ae339e7cac59c88f8e4508b2a89f0ca6e36cc0c0",
    "f2ef166cd2bbea252d2c848b7f67d80cad1840534fe736d792087639b5b2a833",
)


def result_digests(simulation: LightFeedbackSimulation) -> tuple[str, ...]:
    return (
        simulation.mapper.command_digest(),
        simulation.device.stimulus_state_digest(),
        simulation.device.segment_digest(),
        simulation.device.waveform_sample_digest(),
        simulation.engine.deterministic_digest(),
    )


def run_until_end(simulation: LightFeedbackSimulation) -> None:
    simulation.engine.run_until_end()


def run_one_second_steps(simulation: LightFeedbackSimulation) -> None:
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        simulation.engine.step_one_second()


def run_one_event_steps(simulation: LightFeedbackSimulation) -> None:
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        assert simulation.engine.step_one_event() is not None


def run_virtual_chunks(simulation: LightFeedbackSimulation, chunk_us: int) -> None:
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.advance_by_us(chunk_us)


def run_max_batches(simulation: LightFeedbackSimulation) -> None:
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.run_max_batch(max_events=37, wall_time_budget_ms=None)


RUNNERS: tuple[tuple[str, Callable[[LightFeedbackSimulation], None]], ...] = (
    ("run_until_end", run_until_end),
    ("one_second", run_one_second_steps),
    ("one_event", run_one_event_steps),
    ("realtime_equivalent", lambda simulation: run_virtual_chunks(simulation, 17_000)),
    ("x10_equivalent", lambda simulation: run_virtual_chunks(simulation, 170_000)),
    ("x100_equivalent", lambda simulation: run_virtual_chunks(simulation, 1_700_000)),
    ("max_batch", run_max_batches),
)


@pytest.mark.parametrize(("_name", "runner"), RUNNERS, ids=[name for name, _ in RUNNERS])
def test_all_execution_modes_produce_exactly_the_same_stage6_result(
    _name: str,
    runner: Callable[[LightFeedbackSimulation], None],
) -> None:
    simulation = create_light_feedback_simulation()
    runner(simulation)
    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert simulation.engine.clock.current_time_us == 240_000_000
    assert result_digests(simulation) == EXPECTED_DIGESTS


def test_reset_rebuilds_commands_states_segments_samples_and_full_history() -> None:
    simulation = create_light_feedback_simulation()
    simulation.engine.run_until_end()
    first = result_digests(simulation)
    assert first == EXPECTED_DIGESTS

    simulation.engine.reset()
    assert simulation.engine.clock.state is ClockState.STOPPED
    assert simulation.engine.executed_events() == ()
    assert simulation.mapper.command_records() == ()
    assert simulation.device.command_records() == ()
    assert simulation.device.stimulus_state_records() == ()
    assert simulation.device.stimulus_segments() == ()
    simulation.engine.run_until_end()
    assert result_digests(simulation) == first


def test_snapshot_and_state_query_frequency_do_not_mutate_the_formal_result() -> None:
    simulation = create_light_feedback_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.advance_by_us(137_000)
        time_us = simulation.engine.clock.current_time_us
        for _ in range(7):
            simulation.engine.snapshot()
            simulation.mapper.snapshot()
            simulation.device.snapshot(time_us)
            simulation.device.state_at(time_us)
    assert result_digests(simulation) == EXPECTED_DIGESTS


def test_mapper_and_device_config_json_round_trip_preserves_all_digests() -> None:
    mapper_config = GardenLightMapperConfig.from_json(
        GardenLightMapperConfig().to_json()
    )
    device_config = VirtualLightDeviceConfig.from_json(
        VirtualLightDeviceConfig().to_json()
    )
    simulation = create_light_feedback_simulation(
        garden_light_mapper_config=mapper_config,
        virtual_light_device_config=device_config,
    )
    simulation.engine.run_until_end()
    assert result_digests(simulation) == EXPECTED_DIGESTS
