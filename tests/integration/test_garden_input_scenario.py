"""Stage 4 full scenario, reset, execution-mode, and fixed-digest tests."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

import pytest

from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
    GARDEN_PHASE_CHANGED_EVENT_TYPE,
    HEARTBEAT_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.scenario import (
    GardenInputSimulation,
    create_garden_input_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState

ARTIFACT_DIGEST = "4bea74309fcc62922325bd94a6a6a8561daf63740a4fe1b853c9a26f3b6838f1"
EVALUATION_DIGEST = "371f7d7618b8dbc1259f17765409fed1167eaa8fd4bdf62bef743891b726dd1e"
SIGNAL_DIGEST = "0f68cde436e712e7dad5608ad6347af216cee80945ca951404cf511825785add"
FULL_EVENT_DIGEST = "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72"


def run_standard() -> GardenInputSimulation:
    simulation = create_garden_input_simulation()
    simulation.engine.run_until_end()
    return simulation


def assert_fixed_digests(simulation: GardenInputSimulation) -> None:
    component = simulation.garden_input_component
    assert component.artifact_digest() == ARTIFACT_DIGEST
    assert component.evaluation_digest() == EVALUATION_DIGEST
    assert component.signal_digest() == SIGNAL_DIGEST
    assert simulation.engine.deterministic_digest() == FULL_EVENT_DIGEST


def test_standard_240_second_scenario_has_exact_counts_and_completed_state() -> None:
    simulation = run_standard()
    component = simulation.garden_input_component
    snapshot = component.snapshot()
    event_counts = Counter(event.event_type for event in simulation.engine.executed_events())

    assert simulation.engine.clock.current_time_us == 240_000_000
    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert len(simulation.virtual_user_component.heartbeat_records()) == 280
    assert len(simulation.polar_h10_component.measurement_records()) == 279
    assert len(component.rri_records()) == 279
    assert len(component.signal_records()) == 241
    assert len(component.evaluation_records()) == 4
    assert len(simulation.engine.executed_events()) == 1_059
    assert event_counts == {
        HEARTBEAT_EVENT_TYPE: 280,
        RRI_MEASUREMENT_EVENT_TYPE: 279,
        GARDEN_PHASE_CHANGED_EVENT_TYPE: 9,
        GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE: 4,
        GARDEN_EVALUATION_FINALIZED_EVENT_TYPE: 4,
        GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE: 241,
        GARDEN_INPUT_SIGNAL_EVENT_TYPE: 241,
        SIMULATION_COMPLETE_EVENT_TYPE: 1,
    }
    assert snapshot.session_status == "completed"
    assert snapshot.current_phase == "outside"
    assert snapshot.current_s == 0
    assert snapshot.received_rri_count == 279
    assert snapshot.valid_rri_count == 279
    assert snapshot.artifact_rri_count == 0
    assert snapshot.recent_valid_history_count == 15
    assert snapshot.baseline_available
    assert snapshot.valid_evaluation_revision == 4
    assert_fixed_digests(simulation)


def test_standard_scenario_has_four_exact_valid_evaluations() -> None:
    records = run_standard().garden_input_component.evaluation_records()

    assert [record.evaluation_id for record in records] == [
        "session-001-baseline",
        "session-001-bundle-0",
        "session-001-bundle-1",
        "session-001-bundle-2",
    ]
    assert [record.total_rri_count for record in records] == [35, 35, 35, 35]
    assert [record.artifact_rri_count for record in records] == [0, 0, 0, 0]
    assert [record.valid_rri_count for record in records] == [35, 35, 35, 35]
    assert [record.quality for record in records] == ["valid"] * 4
    assert [record.is_valid for record in records] == [True] * 4
    assert [record.n_revision for record in records] == [1, 2, 3, 4]
    assert [record.rmssd_ms for record in records] == pytest.approx(
        [
            25.66777218385641,
            26.55920724587637,
            25.62292729465271,
            26.169925725354823,
        ]
    )
    assert [record.n for record in records] == pytest.approx(
        [
            0.1641195720593294,
            0.17783395762886722,
            0.16342965068696474,
            0.17184501115930495,
        ]
    )
    assert records[0].baseline_id == "session-001-baseline"
    assert {record.baseline_id for record in records[1:]} == {"session-001-baseline"}


def test_reset_rebuilds_all_stage4_state_without_duplicate_handlers_or_records() -> None:
    simulation = run_standard()
    component = simulation.garden_input_component
    first_records = (
        component.rri_records(),
        component.evaluation_records(),
        component.signal_records(),
    )
    first_digests = (
        component.artifact_digest(),
        component.evaluation_digest(),
        component.signal_digest(),
        simulation.engine.deterministic_digest(),
    )

    for _ in range(2):
        simulation.engine.reset()
        assert component.rri_records() == ()
        assert component.evaluation_records() == ()
        assert component.signal_records() == ()
        simulation.engine.run_until_end()
        assert (
            component.rri_records(),
            component.evaluation_records(),
            component.signal_records(),
        ) == first_records
        assert (
            component.artifact_digest(),
            component.evaluation_digest(),
            component.signal_digest(),
            simulation.engine.deterministic_digest(),
        ) == first_digests
        assert len(simulation.engine.executed_events()) == 1_059


def test_standard_records_have_no_duplicate_formal_identity() -> None:
    simulation = run_standard()
    component = simulation.garden_input_component
    rri_records = component.rri_records()
    signals = component.signal_records()
    evaluations = component.evaluation_records()

    assert len({record.input_event_id for record in rri_records}) == 279
    assert {record.input_measurement_index for record in rri_records} == set(range(279))
    assert [record.signal_index for record in signals] == list(range(241))
    assert len({record.evaluation_id for record in evaluations}) == 4
    executed_ids = [event.event_id for event in simulation.engine.executed_events()]
    assert len(executed_ids) == len(set(executed_ids))


def run_until_end() -> GardenInputSimulation:
    return run_standard()


def run_by_one_second_steps() -> GardenInputSimulation:
    simulation = create_garden_input_simulation()
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        simulation.engine.step_one_second()
    return simulation


def run_by_one_event_steps() -> GardenInputSimulation:
    simulation = create_garden_input_simulation()
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        assert simulation.engine.step_one_event() is not None
    return simulation


def run_by_chunks(chunk_us: int, snapshot_reads: int) -> GardenInputSimulation:
    simulation = create_garden_input_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        for _ in range(snapshot_reads):
            simulation.engine.snapshot()
            simulation.garden_input_component.snapshot()
            simulation.garden_input_component.rri_records()
            simulation.garden_input_component.evaluation_records()
            simulation.garden_input_component.signal_records()
        simulation.engine.advance_by_us(chunk_us)
    return simulation


def run_by_max_batches() -> GardenInputSimulation:
    simulation = create_garden_input_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.run_max_batch(max_events=7, wall_time_budget_ms=None)
    return simulation


ExecutionPattern = Callable[[], GardenInputSimulation]


@pytest.mark.parametrize(
    "run_pattern",
    (
        pytest.param(run_until_end, id="run-until-end"),
        pytest.param(run_by_one_second_steps, id="one-second-steps"),
        pytest.param(run_by_one_event_steps, id="one-event-steps"),
        pytest.param(lambda: run_by_chunks(17_000, 0), id="realtime-equivalent"),
        pytest.param(lambda: run_by_chunks(170_000, 2), id="x10-equivalent"),
        pytest.param(lambda: run_by_chunks(1_700_000, 13), id="x100-many-snapshots"),
        pytest.param(run_by_max_batches, id="maximum-batches"),
    ),
)
def test_all_execution_and_snapshot_patterns_have_identical_fixed_digests(
    run_pattern: ExecutionPattern,
) -> None:
    simulation = run_pattern()

    assert_fixed_digests(simulation)
    assert len(simulation.garden_input_component.rri_records()) == 279
    assert len(simulation.garden_input_component.signal_records()) == 241
    assert len(simulation.garden_input_component.evaluation_records()) == 4


def test_config_json_round_trip_does_not_change_scenario_records_or_digests() -> None:
    original = GardenInputConfig()
    round_tripped = GardenInputConfig.from_json(original.to_json())
    first = create_garden_input_simulation(garden_input_config=original)
    second = create_garden_input_simulation(garden_input_config=round_tripped)
    first.engine.run_until_end()
    second.engine.run_until_end()

    assert first.garden_input_component.rri_records() == second.garden_input_component.rri_records()
    assert first.garden_input_component.evaluation_records() == (
        second.garden_input_component.evaluation_records()
    )
    assert first.garden_input_component.signal_records() == (
        second.garden_input_component.signal_records()
    )
    assert_fixed_digests(first)
    assert_fixed_digests(second)
