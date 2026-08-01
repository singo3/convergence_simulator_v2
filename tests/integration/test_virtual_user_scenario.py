"""Engine, event-boundary, and determinism tests for Stage 2 virtual users."""

from __future__ import annotations

import json
import statistics
import subprocess
import sys

import pytest

from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine
from symbiotic_sim_v2.virtual_user.component import (
    HEARTBEAT_EVENT_PRIORITY,
    HEARTBEAT_EVENT_SOURCE,
    HEARTBEAT_EVENT_TYPE,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.diagnostics import (
    export_heartbeat_diagnostics_csv,
    full_run_rmssd_ms,
)
from symbiotic_sim_v2.virtual_user.scenario import create_virtual_user_simulation

STANDARD_HEARTBEAT_DIGEST = "4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765"
STAGE_1_DIGEST = "1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d"


def run_standard():
    simulation = create_virtual_user_simulation()
    simulation.engine.run_until_end()
    return simulation


def zero_variability_config(**overrides) -> VirtualUserConfig:
    values = {
        "duration_seconds": 10,
        "mean_heart_rate_bpm": 60.0,
        "respiratory_amplitude_ms": 0.0,
        "slow_wave_amplitude_ms": 0.0,
        "correlated_variability_sd_ms": 0.0,
        "beat_jitter_sd_ms": 0.0,
    }
    values.update(overrides)
    return VirtualUserConfig(**values)


def heartbeat_events(simulation):
    return tuple(
        event
        for event in simulation.engine.executed_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )


def test_standard_180_second_scenario_completes_with_sane_statistics() -> None:
    simulation = run_standard()
    records = simulation.component.heartbeat_records()
    rri_values = [record.true_rri_ms for record in records if record.true_rri_ms is not None]
    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert simulation.engine.clock.current_time_us == 180_000_000
    assert 190 <= len(records) <= 230
    assert all(
        simulation.config.min_rri_ms <= value <= simulation.config.max_rri_ms
        for value in rri_values
    )
    actual_hr = 60_000.0 / statistics.fmean(rri_values)
    assert actual_hr == pytest.approx(simulation.config.mean_heart_rate_bpm, abs=2.0)
    assert full_run_rmssd_ms(records) is not None


def test_standard_digest_and_timestamp_series_are_fixed() -> None:
    simulation = run_standard()
    records = simulation.component.heartbeat_records()
    assert len(records) == 211
    assert records[0].heartbeat_time_us == 0
    assert records[-1].heartbeat_time_us == 179_810_668
    assert simulation.component.heartbeat_digest() == STANDARD_HEARTBEAT_DIGEST


def test_first_heartbeat_has_no_rri_and_second_has_true_rri() -> None:
    simulation = create_virtual_user_simulation(zero_variability_config())
    first_event = simulation.engine.step_one_event()
    first_record = simulation.component.heartbeat_records()[0]
    assert first_event is not None and first_event.scheduled_time_us == 0
    assert first_record.true_rri_us is None
    assert first_record.instantaneous_hr_bpm is None
    simulation.engine.step_one_event()
    second_record = simulation.component.heartbeat_records()[1]
    assert second_record.true_rri_us == 1_000_000
    assert second_record.true_rri_ms == 1000.0


def test_heartbeat_payload_is_minimal_formal_boundary() -> None:
    simulation = run_standard()
    for event in heartbeat_events(simulation):
        assert set(event.payload) == {"user_id", "beat_index"}
        assert "rri_ms" not in event.payload
        assert "rmssd_ms" not in event.payload
        assert "n" not in event.payload
        assert "nd" not in event.payload
        assert "w" not in event.payload
        assert event.source == HEARTBEAT_EVENT_SOURCE
        assert event.priority == HEARTBEAT_EVENT_PRIORITY


def test_heartbeat_times_are_strictly_increasing_and_within_end() -> None:
    simulation = run_standard()
    times = [record.heartbeat_time_us for record in simulation.component.heartbeat_records()]
    assert all(current > previous for previous, current in zip(times, times[1:], strict=False))
    assert times[-1] <= simulation.engine.clock.end_time_us


def test_no_heartbeat_after_end_and_exact_end_is_allowed() -> None:
    simulation = create_virtual_user_simulation(zero_variability_config())
    simulation.engine.run_until_end()
    times = [record.heartbeat_time_us for record in simulation.component.heartbeat_records()]
    assert times == list(range(0, 10_000_001, 1_000_000))
    assert max(times) == simulation.engine.clock.end_time_us


def test_heartbeat_precedes_completion_at_exact_end() -> None:
    simulation = create_virtual_user_simulation(zero_variability_config())
    simulation.engine.run_until_end()
    at_end = [
        event.event_type
        for event in simulation.engine.executed_events()
        if event.scheduled_time_us == simulation.engine.clock.end_time_us
    ]
    assert at_end == ["heartbeat", "simulation_complete"]


def test_reset_clears_records_and_reproduces_digest() -> None:
    simulation = run_standard()
    first_digest = simulation.component.heartbeat_digest()
    first_records = simulation.component.heartbeat_records()
    simulation.engine.reset()
    assert simulation.component.heartbeat_records() == ()
    simulation.engine.run_until_end()
    assert simulation.component.heartbeat_records() == first_records
    assert simulation.component.heartbeat_digest() == first_digest


def _digest_by_one_second_steps() -> str:
    simulation = create_virtual_user_simulation()
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        simulation.engine.step_one_second()
    return simulation.component.heartbeat_digest()


def _digest_by_event_steps() -> str:
    simulation = create_virtual_user_simulation()
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        assert simulation.engine.step_one_event() is not None
    return simulation.component.heartbeat_digest()


def _digest_by_chunks(chunk_us: int, snapshot_reads: int) -> str:
    simulation = create_virtual_user_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        for _ in range(snapshot_reads):
            simulation.engine.snapshot()
            simulation.component.snapshot()
        simulation.engine.advance_by_us(chunk_us)
    return simulation.component.heartbeat_digest()


def _digest_by_max_batches() -> str:
    simulation = create_virtual_user_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.run_max_batch(max_events=7, wall_time_budget_ms=None)
    return simulation.component.heartbeat_digest()


def test_all_step_speed_batch_and_snapshot_patterns_have_same_digest() -> None:
    run_until = run_standard().component.heartbeat_digest()
    assert _digest_by_one_second_steps() == run_until
    assert _digest_by_event_steps() == run_until
    assert _digest_by_chunks(17_000, 0) == run_until
    assert _digest_by_chunks(170_000, 2) == run_until
    assert _digest_by_chunks(1_700_000, 13) == run_until
    assert _digest_by_max_batches() == run_until


def test_config_json_roundtrip_keeps_digest() -> None:
    config = VirtualUserConfig()
    round_tripped = VirtualUserConfig.from_json(config.to_json())
    first = create_virtual_user_simulation(config)
    second = create_virtual_user_simulation(round_tripped)
    first.engine.run_until_end()
    second.engine.run_until_end()
    assert first.component.heartbeat_digest() == second.component.heartbeat_digest()


def test_different_seed_changes_stochastic_heartbeat_series() -> None:
    first = create_virtual_user_simulation(VirtualUserConfig(root_seed=1))
    second = create_virtual_user_simulation(VirtualUserConfig(root_seed=2))
    first.engine.run_until_end()
    second.engine.run_until_end()
    assert first.component.heartbeat_digest() != second.component.heartbeat_digest()


def test_seed_has_no_effect_when_both_random_amplitudes_are_zero() -> None:
    base_values = {
        "correlated_variability_sd_ms": 0.0,
        "beat_jitter_sd_ms": 0.0,
    }
    first = create_virtual_user_simulation(VirtualUserConfig(root_seed=1, **base_values))
    second = create_virtual_user_simulation(VirtualUserConfig(root_seed=2, **base_values))
    first.engine.run_until_end()
    second.engine.run_until_end()
    assert first.component.heartbeat_digest() == second.component.heartbeat_digest()


def test_all_variability_zero_has_constant_rri_and_zero_rmssd() -> None:
    simulation = create_virtual_user_simulation(zero_variability_config())
    simulation.engine.run_until_end()
    records = simulation.component.heartbeat_records()
    assert {record.true_rri_us for record in records[1:]} == {1_000_000}
    assert full_run_rmssd_ms(records) == 0.0


def test_respiratory_amplitude_increases_rri_variation() -> None:
    common = {
        "duration_seconds": 60,
        "slow_wave_amplitude_ms": 0.0,
        "correlated_variability_sd_ms": 0.0,
        "beat_jitter_sd_ms": 0.0,
    }
    no_respiration = create_virtual_user_simulation(
        VirtualUserConfig(respiratory_amplitude_ms=0.0, **common)
    )
    respiration = create_virtual_user_simulation(
        VirtualUserConfig(respiratory_amplitude_ms=40.0, **common)
    )
    no_respiration.engine.run_until_end()
    respiration.engine.run_until_end()
    flat_values = [
        record.true_rri_ms for record in no_respiration.component.heartbeat_records()[1:]
    ]
    varied_values = [record.true_rri_ms for record in respiration.component.heartbeat_records()[1:]]
    assert statistics.pstdev(varied_values) > statistics.pstdev(flat_values) + 20.0


def test_one_handler_execution_per_heartbeat_and_no_reset_duplicates() -> None:
    simulation = run_standard()
    assert len(heartbeat_events(simulation)) == len(simulation.component.heartbeat_records())
    simulation.engine.reset()
    simulation.engine.run_until_end()
    assert len(heartbeat_events(simulation)) == len(simulation.component.heartbeat_records())
    assert len(simulation.component.heartbeat_records()) == 211


def test_csv_export_does_not_change_digest(tmp_path) -> None:
    simulation = run_standard()
    before = simulation.component.heartbeat_digest()
    output = export_heartbeat_diagnostics_csv(tmp_path, simulation.component.heartbeat_records())
    assert output.exists()
    assert simulation.component.heartbeat_digest() == before


def test_stage_1_time_demo_digest_is_unchanged() -> None:
    engine = create_demo_engine()
    engine.run_until_end()
    assert engine.deterministic_digest() == STAGE_1_DIGEST


def test_headless_virtual_user_json_matches_factory() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "symbiotic_sim_v2", "--headless-virtual-user-demo"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)
    assert output["heartbeat_count"] == 211
    assert output["heartbeat_digest"] == STANDARD_HEARTBEAT_DIGEST
    assert output["final_virtual_time_us"] == 180_000_000
    assert output["final_state"] == "completed"


def test_headless_csv_option_writes_diagnostics(tmp_path) -> None:
    output_path = tmp_path / "virtual_user_true_heartbeat_diagnostics.csv"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "symbiotic_sim_v2",
            "--headless-virtual-user-demo",
            "--export-virtual-user-csv",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)
    assert output_path.exists()
    assert output["diagnostic_csv"] == str(output_path)
