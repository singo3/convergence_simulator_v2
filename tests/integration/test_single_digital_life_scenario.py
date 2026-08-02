"""Stage 5A factory, reset, role, and Stage 4 event-stream regression tests."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from symbiotic_sim_v2.digital_life.config import (
    DigitalLifeConfig,
    digital_life_config_for_role,
)
from symbiotic_sim_v2.digital_life.scenario import (
    SingleDigitalLifeSimulation,
    create_single_digital_life_simulation,
)
from symbiotic_sim_v2.garden.input_layer.scenario import create_garden_input_simulation
from symbiotic_sim_v2.simulation.clock import ClockState

STAGE_4_FULL_EVENT_DIGEST = (
    "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72"
)
GREEN_FIRST_ROUND_DIGEST = (
    "661c2c74942d6b217a635fb4f2cb142bee8cff2e0e842cd21ccdd511682028b8"
)
EVALUATION_UPDATE_DIGEST = (
    "f7bf973cc20a2af77ccd7b38fa0e2407801353890a23cc1b3e30e9d7feeba4c3"
)


def run_stage5(role: str = "green") -> SingleDigitalLifeSimulation:
    simulation = create_single_digital_life_simulation(
        digital_life_config=digital_life_config_for_role(role)
    )
    simulation.engine.run_until_end()
    return simulation


def test_factory_preserves_exact_stage4_event_stream_and_applies_closing_revision() -> None:
    stage4 = create_garden_input_simulation()
    stage5 = create_single_digital_life_simulation()

    stage4.engine.run_until_end()
    stage5.engine.run_until_end()

    assert stage5.component is stage5.virtual_user_component
    assert stage5.config is stage5.virtual_user_config
    assert stage5.life_component is stage5.digital_life_component
    assert stage5.life_config is stage5.digital_life_config
    assert stage5.engine.executed_events() == stage4.engine.executed_events()
    assert stage5.engine.deterministic_digest() == STAGE_4_FULL_EVENT_DIGEST

    records = stage5.digital_life_component.first_round_records()
    updates = stage5.digital_life_component.evaluation_update_records()
    assert len(records) == 241
    assert len(updates) == 4
    assert [records[index].valid_evaluation_revision for index in (60, 120, 180, 240)] == [
        1,
        2,
        3,
        4,
    ]
    closing = records[240]
    assert closing.s == 0
    assert closing.is_new_valid_evaluation is True
    assert closing.source_evaluation_id == "session-001-bundle-2"
    assert closing.nd == updates[-1].new_nd
    assert closing.w == updates[-1].new_w
    assert closing.p == 1.0
    assert closing.tau is None
    assert closing.touch_dispatched is False


def test_reset_replays_once_without_duplicate_handlers_or_changed_digests() -> None:
    simulation = run_stage5()
    component = simulation.digital_life_component
    first_result = (
        simulation.engine.deterministic_digest(),
        component.first_round_digest(),
        component.evaluation_update_digest(),
        component.first_round_records(),
        component.evaluation_update_records(),
    )

    simulation.engine.reset()
    assert component.first_round_records() == ()
    assert component.evaluation_update_records() == ()
    simulation.engine.run_until_end()

    second_result = (
        simulation.engine.deterministic_digest(),
        component.first_round_digest(),
        component.evaluation_update_digest(),
        component.first_round_records(),
        component.evaluation_update_records(),
    )
    assert second_result == first_result
    assert len(component.first_round_records()) == 241
    assert len(component.evaluation_update_records()) == 4


def test_role_changes_only_life_specific_results() -> None:
    simulations = tuple(run_stage5(role) for role in ("red", "green", "blue"))

    upstream_results = {
        (
            simulation.engine.deterministic_digest(),
            simulation.garden_input_component.artifact_digest(),
            simulation.garden_input_component.evaluation_digest(),
            simulation.garden_input_component.signal_digest(),
        )
        for simulation in simulations
    }
    assert upstream_results == {
        (
            STAGE_4_FULL_EVENT_DIGEST,
            "4bea74309fcc62922325bd94a6a6a8561daf63740a4fe1b853c9a26f3b6838f1",
            "371f7d7618b8dbc1259f17765409fed1167eaa8fd4bdf62bef743891b726dd1e",
            "0f68cde436e712e7dad5608ad6347af216cee80945ca951404cf511825785add",
        )
    }
    assert len(
        {
            simulation.digital_life_component.first_round_digest()
            for simulation in simulations
        }
    ) == 3
    assert len(
        {
            simulation.digital_life_component.evaluation_update_digest()
            for simulation in simulations
        }
    ) == 1


def run_one_second_steps() -> SingleDigitalLifeSimulation:
    simulation = create_single_digital_life_simulation()
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        simulation.engine.step_one_second()
    return simulation


def run_one_event_steps() -> SingleDigitalLifeSimulation:
    simulation = create_single_digital_life_simulation()
    while simulation.engine.clock.state is not ClockState.COMPLETED:
        assert simulation.engine.step_one_event() is not None
    return simulation


def run_chunks(chunk_us: int, snapshot_reads: int) -> SingleDigitalLifeSimulation:
    simulation = create_single_digital_life_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        for _ in range(snapshot_reads):
            simulation.engine.snapshot()
            simulation.digital_life_component.snapshot()
            simulation.digital_life_component.first_round_records()
            simulation.digital_life_component.evaluation_update_records()
        simulation.engine.advance_by_us(chunk_us)
    return simulation


def run_max_batches() -> SingleDigitalLifeSimulation:
    simulation = create_single_digital_life_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.run_max_batch(max_events=7, wall_time_budget_ms=None)
    return simulation


ExecutionPattern = Callable[[], SingleDigitalLifeSimulation]


@pytest.mark.parametrize(
    "run_pattern",
    (
        pytest.param(lambda: run_stage5(), id="run-until-end"),
        pytest.param(run_one_second_steps, id="one-second-steps"),
        pytest.param(run_one_event_steps, id="one-event-steps"),
        pytest.param(lambda: run_chunks(17_000, 0), id="realtime-equivalent"),
        pytest.param(lambda: run_chunks(170_000, 2), id="x10-equivalent"),
        pytest.param(lambda: run_chunks(1_700_000, 13), id="x100-many-snapshots"),
        pytest.param(run_max_batches, id="maximum-batches"),
    ),
)
def test_execution_and_snapshot_patterns_preserve_life_digests(
    run_pattern: ExecutionPattern,
) -> None:
    simulation = run_pattern()
    component = simulation.digital_life_component
    assert component.first_round_digest() == GREEN_FIRST_ROUND_DIGEST
    assert component.evaluation_update_digest() == EVALUATION_UPDATE_DIGEST
    assert simulation.engine.deterministic_digest() == STAGE_4_FULL_EVENT_DIGEST
    assert len(component.first_round_records()) == 241
    assert len(component.evaluation_update_records()) == 4


def test_config_json_round_trip_preserves_all_life_results() -> None:
    original = DigitalLifeConfig()
    round_tripped = DigitalLifeConfig.from_json(original.to_json())
    first = create_single_digital_life_simulation(digital_life_config=original)
    second = create_single_digital_life_simulation(digital_life_config=round_tripped)
    first.engine.run_until_end()
    second.engine.run_until_end()
    assert first.digital_life_component.first_round_records() == (
        second.digital_life_component.first_round_records()
    )
    assert first.digital_life_component.evaluation_update_records() == (
        second.digital_life_component.evaluation_update_records()
    )
    assert first.digital_life_component.first_round_digest() == GREEN_FIRST_ROUND_DIGEST
    assert second.digital_life_component.first_round_digest() == GREEN_FIRST_ROUND_DIGEST
