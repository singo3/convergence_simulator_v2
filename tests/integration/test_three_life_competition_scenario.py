"""End-to-end Stage 5B three-life competition and closing-round tests."""

from __future__ import annotations

from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.garden.output_layer.events import (
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
    GARDEN_HOLDER_RELEASE_EVENT_TYPE,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
)
from symbiotic_sim_v2.runtime.multi_life.config import MultiLifeRuntimeConfig
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    ThreeDigitalLifeCompetitionSimulation,
    create_three_digital_life_competition_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig


def stage5b_digests(
    simulation: ThreeDigitalLifeCompetitionSimulation,
) -> tuple[object, ...]:
    return (
        simulation.garden_output_component.touch_digest(),
        simulation.garden_output_component.qualification_digest(),
        simulation.garden_output_component.qualified_b_digest(),
        simulation.garden_output_component.feedback_digest(),
        tuple(
            component.second_round_digest()
            for component in simulation.digital_life_components.values()
        ),
        simulation.engine.deterministic_digest(),
    )


def test_standard_three_life_scenario_uses_actual_first_arrival_and_completes() -> None:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()

    runtime = simulation.runtime_coordinator.snapshot()
    garden = simulation.garden_output_component.snapshot()
    assert simulation.engine.snapshot().current_time_us == 240_000_000
    assert runtime.completed_round_count == 241
    assert runtime.scheduled_touch_count == 540
    assert runtime.routed_feedback_count == 723
    assert runtime.release_count == 1
    assert not runtime.round_pending

    assert garden.total_touch_count == 540
    assert garden.feedback_count == 723
    assert garden.active_output_count == 180
    assert garden.inactive_output_count == 61
    assert garden.assignment_count == 1
    assert garden.release_count == 1
    assert garden.last_assigned_holder_id == "life-green"
    assert garden.qualification_holder_id is None
    assert garden.incomplete_round_count == 0

    first_round_touches = simulation.garden_output_component.touch_records()[:3]
    assert tuple(record.digital_life_id for record in first_round_touches) == (
        "life-green",
        "life-blue",
        "life-red",
    )
    assert first_round_touches[0].assigned_holder_on_this_touch
    assert all(not record.exact_time_tie for record in first_round_touches)


def test_all_life_states_are_independent_and_only_holder_updates_q() -> None:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()

    components = simulation.digital_life_components
    assert len({id(component) for component in components.values()}) == 3
    assert len({id(component._state) for component in components.values()}) == 3  # noqa: SLF001
    snapshots = {
        life_id: component.connected_snapshot()
        for life_id, component in components.items()
    }
    assert all(snapshot.first_round_count == 241 for snapshot in snapshots.values())
    assert all(snapshot.second_round_count == 241 for snapshot in snapshots.values())
    assert all(snapshot.current_g == 0 for snapshot in snapshots.values())
    assert all(snapshot.k_current == (0.5, 0.5, 0.5, 0.5) for snapshot in snapshots.values())
    assert snapshots["life-green"].e > 0.14
    assert snapshots["life-blue"].e == 0.0
    assert snapshots["life-red"].e == 0.0
    assert snapshots["life-green"].q_update_count == 3
    assert snapshots["life-green"].q != 0.5
    assert snapshots["life-blue"].q == 0.5
    assert snapshots["life-red"].q == 0.5

    closing = {
        life_id: component.second_round_records()[-1]
        for life_id, component in components.items()
    }
    assert closing["life-green"].g == 1
    assert closing["life-green"].q_update_applied
    assert closing["life-green"].closing_evaluation_attribution
    assert closing["life-blue"].g == 0
    assert closing["life-red"].g == 0


def test_closing_event_order_attributes_bundle_before_holder_release() -> None:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()
    formal_closing_types = {
        GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
        GARDEN_INPUT_SIGNAL_EVENT_TYPE,
        GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
        GARDEN_HOLDER_RELEASE_EVENT_TYPE,
        SIMULATION_COMPLETE_EVENT_TYPE,
    }
    relevant = [
        (event.priority, event.event_type)
        for event in simulation.engine.executed_events()
        if event.scheduled_time_us == 240_000_000
        and event.event_type in formal_closing_types
    ]
    assert relevant == [
        (25, GARDEN_EVALUATION_FINALIZED_EVENT_TYPE),
        (30, GARDEN_INPUT_SIGNAL_EVENT_TYPE),
        (31, GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE),
        (75, GARDEN_QUALIFIED_B_EVENT_TYPE),
        (80, GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE),
        (80, GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE),
        (80, GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE),
        (90, GARDEN_HOLDER_RELEASE_EVENT_TYPE),
        (100, SIMULATION_COMPLETE_EVENT_TYPE),
    ]

    closing_qualification = simulation.garden_output_component.qualification_records()[-1]
    assert closing_qualification.holder_before == "life-green"
    assert closing_qualification.holder_after is None
    assert closing_qualification.released_after_second_round
    assert not closing_qualification.active_output


def test_config_input_order_does_not_change_normal_arrival_or_digests() -> None:
    baseline = create_three_digital_life_competition_simulation()
    reordered = create_three_digital_life_competition_simulation(
        digital_life_configs=tuple(reversed(baseline.digital_life_configs))
    )
    baseline.engine.run_until_end()
    reordered.engine.run_until_end()

    baseline_garden = baseline.garden_output_component
    reordered_garden = reordered.garden_output_component
    assert baseline_garden.touch_digest() == reordered_garden.touch_digest()
    assert baseline_garden.qualification_digest() == reordered_garden.qualification_digest()
    assert baseline_garden.qualified_b_digest() == reordered_garden.qualified_b_digest()
    assert baseline_garden.feedback_digest() == reordered_garden.feedback_digest()
    assert {
        life_id: component.second_round_digest()
        for life_id, component in baseline.digital_life_components.items()
    } == {
        life_id: component.second_round_digest()
        for life_id, component in reordered.digital_life_components.items()
    }


def test_reset_reproduces_all_stage5b_digests_and_counts() -> None:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()
    first = stage5b_digests(simulation)

    simulation.engine.reset()
    simulation.engine.run_until_end()
    second = stage5b_digests(simulation)
    assert second == first
    assert len(
        [
            event
            for event in simulation.engine.executed_events()
            if event.event_type == DIGITAL_LIFE_TOUCH_EVENT_TYPE
        ]
    ) == 540


def test_run_until_end_one_second_and_one_event_modes_have_identical_digests() -> None:
    fastest = create_three_digital_life_competition_simulation()
    fastest.engine.run_until_end()

    one_second = create_three_digital_life_competition_simulation()
    while one_second.engine.snapshot().state is not ClockState.COMPLETED:
        one_second.engine.step_one_second()

    one_event = create_three_digital_life_competition_simulation()
    while one_event.engine.snapshot().state is not ClockState.COMPLETED:
        assert one_event.engine.step_one_event() is not None

    assert stage5b_digests(one_second) == stage5b_digests(fastest)
    assert stage5b_digests(one_event) == stage5b_digests(fastest)


def run_in_virtual_time_chunks(
    chunk_us: int,
    snapshot_reads: int,
) -> ThreeDigitalLifeCompetitionSimulation:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        for _ in range(snapshot_reads):
            simulation.engine.snapshot()
            simulation.runtime_coordinator.snapshot()
            simulation.garden_output_component.snapshot()
            simulation.garden_output_component.touch_records()
            simulation.garden_output_component.qualification_records()
            for component in simulation.digital_life_components.values():
                component.snapshot()
                component.first_round_records()
                component.second_round_records()
        simulation.engine.advance_by_us(chunk_us)
    return simulation


def run_in_maximum_batches() -> ThreeDigitalLifeCompetitionSimulation:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.start()
    while simulation.engine.clock.state is ClockState.RUNNING:
        simulation.engine.run_max_batch(max_events=7, wall_time_budget_ms=None)
    return simulation


def test_speed_batch_and_snapshot_patterns_preserve_all_stage5b_digests() -> None:
    fastest = create_three_digital_life_competition_simulation()
    fastest.engine.run_until_end()
    expected = stage5b_digests(fastest)

    simulations = (
        run_in_virtual_time_chunks(17_000, 0),
        run_in_virtual_time_chunks(170_000, 0),
        run_in_virtual_time_chunks(170_000, 17),
        run_in_virtual_time_chunks(1_700_000, 13),
        run_in_maximum_batches(),
    )
    assert all(stage5b_digests(simulation) == expected for simulation in simulations)


def test_all_stage5b_config_json_round_trips_preserve_full_results() -> None:
    original = create_three_digital_life_competition_simulation()
    round_tripped = create_three_digital_life_competition_simulation(
        virtual_user_config=VirtualUserConfig.from_json(
            original.virtual_user_config.to_json()
        ),
        polar_h10_config=PolarH10Config.from_json(original.polar_h10_config.to_json()),
        garden_input_config=GardenInputConfig.from_json(
            original.garden_input_config.to_json()
        ),
        digital_life_configs=tuple(
            DigitalLifeConfig.from_json(config.to_json())
            for config in original.digital_life_configs
        ),
        runtime_config=MultiLifeRuntimeConfig.from_json(original.runtime_config.to_json()),
        garden_output_config=GardenOutputConfig.from_json(
            original.garden_output_config.to_json()
        ),
    )
    original.engine.run_until_end()
    round_tripped.engine.run_until_end()

    assert stage5b_digests(round_tripped) == stage5b_digests(original)
    assert round_tripped.digital_life_configs == original.digital_life_configs
    assert round_tripped.runtime_config == original.runtime_config
    assert round_tripped.garden_output_config == original.garden_output_config
