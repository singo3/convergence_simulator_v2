"""Stage 3 factory, ordering, reset, determinism, and regression tests."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from symbiotic_sim_v2.devices.polar_h10.component import PolarH10State
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.polar_h10.diagnostics import (
    compare_rri_measurements,
    export_rri_measurement_diagnostics_csv,
)
from symbiotic_sim_v2.devices.polar_h10.scenario import (
    PolarH10Simulation,
    create_polar_h10_simulation,
)
from symbiotic_sim_v2.domain.event_priorities import (
    HEARTBEAT_EVENT_PRIORITY,
    RRI_MEASUREMENT_EVENT_PRIORITY,
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_types import (
    HEARTBEAT_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.scenario import create_virtual_user_simulation

STAGE_1_DIGEST = "1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d"
STAGE_2_HEARTBEAT_DIGEST = (
    "4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765"
)
STAGE_2_DIAGNOSTIC_DIGEST = (
    "ef0bc8c644e8b5f6fc2c3b58ef825491e49e005bc0c6c22a9f0c62c66168cd8f"
)
STAGE_2_FULL_EVENT_DIGEST = (
    "761a2dc6b2b03c4d538a85d95160f2ecc731e301a1362006ee97ea575872bddb"
)
STAGE_3_MEASUREMENT_DIGEST = (
    "69d645f9e742f8cb9dbb16d9deb65ff10ce77b31c66c35e8fd01cfc5c97272b3"
)
STAGE_3_FULL_EVENT_DIGEST = (
    "d5a174f007a160a1442569b017fe404806db61cc18e0b6a0cda99cd2995b6572"
)


def run_standard() -> PolarH10Simulation:
    simulation = create_polar_h10_simulation()
    simulation.engine.run_until_end()
    return simulation


def typed_events(simulation: PolarH10Simulation, event_type: str):
    return tuple(
        event
        for event in simulation.engine.executed_events()
        if event.event_type == event_type
    )


def zero_variability_config() -> VirtualUserConfig:
    return VirtualUserConfig(
        duration_seconds=10,
        mean_heart_rate_bpm=60.0,
        respiratory_amplitude_ms=0.0,
        slow_wave_amplitude_ms=0.0,
        correlated_variability_sd_ms=0.0,
        beat_jitter_sd_ms=0.0,
    )


def test_standard_180_second_stage3_run_has_exact_counts_state_and_fixed_digests() -> None:
    simulation = run_standard()
    heartbeat_records = simulation.virtual_user_component.heartbeat_records()
    measurements = simulation.polar_h10_component.measurement_records()
    snapshot = simulation.polar_h10_component.snapshot()

    assert simulation.engine.clock.current_time_us == 180_000_000
    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert snapshot.state is PolarH10State.COMPLETED
    assert len(heartbeat_records) == 211
    assert snapshot.observed_heartbeat_count == len(heartbeat_records)
    assert len(measurements) == len(heartbeat_records) - 1 == 210
    assert len(simulation.engine.executed_events()) == 422
    assert measurements[0].event_time_us == 855_679
    assert measurements[-1].event_time_us == 179_810_668
    assert measurements[0].rri_us == 855_679
    assert measurements[-1].rri_us == 844_384
    assert simulation.virtual_user_component.heartbeat_digest() == STAGE_2_HEARTBEAT_DIGEST
    assert simulation.polar_h10_component.measurement_digest() == STAGE_3_MEASUREMENT_DIGEST
    assert simulation.engine.deterministic_digest() == STAGE_3_FULL_EVENT_DIGEST


def test_every_measurement_matches_adjacent_heartbeat_timestamps_and_internal_truth() -> None:
    simulation = run_standard()
    heartbeat_records = simulation.virtual_user_component.heartbeat_records()
    measurements = simulation.polar_h10_component.measurement_records()
    truth_by_index = {record.beat_index: record for record in heartbeat_records}
    for measurement in measurements:
        previous = truth_by_index[measurement.previous_beat_index]
        current = truth_by_index[measurement.current_beat_index]
        assert measurement.previous_heartbeat_time_us == previous.heartbeat_time_us
        assert measurement.current_heartbeat_time_us == current.heartbeat_time_us
        assert measurement.rri_us == current.heartbeat_time_us - previous.heartbeat_time_us
        assert measurement.rri_us == current.true_rri_us
        assert measurement.rri_ms == current.true_rri_ms

    diagnostics = compare_rri_measurements(measurements, heartbeat_records)
    assert len(diagnostics) == len(measurements)
    assert sum(record.match for record in diagnostics) == len(measurements)
    assert sum(not record.match for record in diagnostics) == 0
    assert max(record.absolute_error_us for record in diagnostics) == 0


def test_each_rri_event_executes_after_its_heartbeat_at_the_same_virtual_time() -> None:
    simulation = run_standard()
    events = simulation.engine.executed_events()
    positions = {event.event_id: index for index, event in enumerate(events)}
    heartbeats_by_index = {
        event.payload["beat_index"]: event
        for event in events
        if event.event_type == HEARTBEAT_EVENT_TYPE
    }
    for rri_event in typed_events(simulation, RRI_MEASUREMENT_EVENT_TYPE):
        heartbeat = heartbeats_by_index[rri_event.payload["current_beat_index"]]
        assert heartbeat.scheduled_time_us == rri_event.scheduled_time_us
        assert heartbeat.priority == HEARTBEAT_EVENT_PRIORITY
        assert rri_event.priority == RRI_MEASUREMENT_EVENT_PRIORITY
        assert positions[heartbeat.event_id] < positions[rri_event.event_id]
    assert [event.ordering_key for event in events] == sorted(
        event.ordering_key for event in events
    )


def test_exact_end_heartbeat_orders_before_rri_and_completion() -> None:
    simulation = create_polar_h10_simulation(zero_variability_config())
    simulation.engine.run_until_end()
    at_end = tuple(
        event
        for event in simulation.engine.executed_events()
        if event.scheduled_time_us == simulation.engine.clock.end_time_us
    )
    assert [event.event_type for event in at_end] == [
        HEARTBEAT_EVENT_TYPE,
        RRI_MEASUREMENT_EVENT_TYPE,
        SIMULATION_COMPLETE_EVENT_TYPE,
    ]
    assert [event.priority for event in at_end] == [
        HEARTBEAT_EVENT_PRIORITY,
        RRI_MEASUREMENT_EVENT_PRIORITY,
        SIMULATION_COMPLETE_EVENT_PRIORITY,
    ]
    assert len(simulation.virtual_user_component.heartbeat_records()) == 11
    assert len(simulation.polar_h10_component.measurement_records()) == 10
    assert simulation.polar_h10_component.snapshot().state is PolarH10State.COMPLETED


def test_reset_rebuilds_both_components_without_duplicate_handlers_or_records() -> None:
    simulation = run_standard()
    first_records = simulation.polar_h10_component.measurement_records()
    first_measurement_digest = simulation.polar_h10_component.measurement_digest()
    first_event_digest = simulation.engine.deterministic_digest()

    for _ in range(2):
        simulation.engine.reset()
        assert simulation.virtual_user_component.heartbeat_records() == ()
        assert simulation.polar_h10_component.measurement_records() == ()
        assert simulation.polar_h10_component.snapshot().state is PolarH10State.READY
        simulation.engine.run_until_end()
        assert simulation.polar_h10_component.measurement_records() == first_records
        assert simulation.polar_h10_component.measurement_digest() == first_measurement_digest
        assert simulation.engine.deterministic_digest() == first_event_digest
        assert len(typed_events(simulation, HEARTBEAT_EVENT_TYPE)) == 211
        assert len(typed_events(simulation, RRI_MEASUREMENT_EVENT_TYPE)) == 210
        assert len(typed_events(simulation, SIMULATION_COMPLETE_EVENT_TYPE)) == 1


def _run_until_end() -> PolarH10Simulation:
    return run_standard()


def _run_by_one_second_steps() -> PolarH10Simulation:
    simulation = create_polar_h10_simulation()
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        simulation.engine.step_one_second()
    return simulation


def _run_by_one_event_steps() -> PolarH10Simulation:
    simulation = create_polar_h10_simulation()
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        assert simulation.engine.step_one_event() is not None
    return simulation


def _run_by_chunks(chunk_us: int, snapshot_reads: int) -> PolarH10Simulation:
    simulation = create_polar_h10_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        for _ in range(snapshot_reads):
            simulation.engine.snapshot()
            simulation.virtual_user_component.snapshot()
            simulation.polar_h10_component.snapshot()
            simulation.polar_h10_component.measurement_records()
        simulation.engine.advance_by_us(chunk_us)
    return simulation


def _run_by_max_batches() -> PolarH10Simulation:
    simulation = create_polar_h10_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.run_max_batch(max_events=7, wall_time_budget_ms=None)
    return simulation


ExecutionPattern = Callable[[], PolarH10Simulation]


@pytest.mark.parametrize(
    "run_pattern",
    (
        pytest.param(_run_until_end, id="run-until-end"),
        pytest.param(_run_by_one_second_steps, id="one-second-steps"),
        pytest.param(_run_by_one_event_steps, id="one-event-steps"),
        pytest.param(lambda: _run_by_chunks(17_000, 0), id="realtime-equivalent"),
        pytest.param(lambda: _run_by_chunks(170_000, 2), id="x10-equivalent"),
        pytest.param(lambda: _run_by_chunks(1_700_000, 13), id="x100-many-snapshots"),
        pytest.param(_run_by_max_batches, id="maximum-batches"),
    ),
)
def test_all_execution_and_snapshot_patterns_have_identical_fixed_digests(
    run_pattern: ExecutionPattern,
) -> None:
    simulation = run_pattern()
    assert simulation.polar_h10_component.measurement_digest() == STAGE_3_MEASUREMENT_DIGEST
    assert simulation.engine.deterministic_digest() == STAGE_3_FULL_EVENT_DIGEST
    assert len(simulation.polar_h10_component.measurement_records()) == 210


def test_h10_config_json_roundtrip_does_not_change_the_measurement_series() -> None:
    original = PolarH10Config()
    round_tripped = PolarH10Config.from_json(original.to_json())
    first = create_polar_h10_simulation(polar_h10_config=original)
    second = create_polar_h10_simulation(polar_h10_config=round_tripped)
    first.engine.run_until_end()
    second.engine.run_until_end()
    assert first.polar_h10_component.measurement_records() == (
        second.polar_h10_component.measurement_records()
    )
    assert first.polar_h10_component.measurement_digest() == STAGE_3_MEASUREMENT_DIGEST
    assert second.polar_h10_component.measurement_digest() == STAGE_3_MEASUREMENT_DIGEST


def test_csv_export_is_observational_and_does_not_change_any_digest(tmp_path) -> None:
    simulation = run_standard()
    before_measurement = simulation.polar_h10_component.measurement_digest()
    before_full = simulation.engine.deterministic_digest()
    before_records = simulation.polar_h10_component.measurement_records()
    output = export_rri_measurement_diagnostics_csv(
        tmp_path,
        before_records,
        simulation.virtual_user_component.heartbeat_records(),
    )
    assert output.exists()
    assert simulation.polar_h10_component.measurement_records() == before_records
    assert simulation.polar_h10_component.measurement_digest() == before_measurement
    assert simulation.engine.deterministic_digest() == before_full


def test_stage3_heartbeat_series_is_exactly_the_unchanged_stage2_series() -> None:
    stage_2 = create_virtual_user_simulation()
    stage_3 = create_polar_h10_simulation()
    stage_2.engine.run_until_end()
    stage_3.engine.run_until_end()
    assert stage_3.virtual_user_component.heartbeat_records() == (
        stage_2.component.heartbeat_records()
    )
    assert stage_3.virtual_user_component.heartbeat_digest() == (
        stage_2.component.heartbeat_digest()
    )
    assert stage_3.virtual_user_component.diagnostic_digest() == (
        stage_2.component.diagnostic_digest()
    )


def test_stage1_and_stage2_golden_digests_remain_unchanged() -> None:
    stage_1 = create_demo_engine()
    stage_1.run_until_end()
    stage_2 = create_virtual_user_simulation()
    stage_2.engine.run_until_end()
    assert stage_1.deterministic_digest() == STAGE_1_DIGEST
    assert stage_2.component.heartbeat_digest() == STAGE_2_HEARTBEAT_DIGEST
    assert stage_2.component.diagnostic_digest() == STAGE_2_DIAGNOSTIC_DIGEST
    assert stage_2.engine.deterministic_digest() == STAGE_2_FULL_EVENT_DIGEST


def test_factory_rejects_a_device_configured_for_another_user() -> None:
    with pytest.raises(ValueError, match="expected_user_id"):
        create_polar_h10_simulation(
            VirtualUserConfig(user_id="expected-user"),
            PolarH10Config(expected_user_id="different-user"),
        )
