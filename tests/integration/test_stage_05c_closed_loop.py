"""Production Stage 5C adaptive-life and formal closed-loop integration."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.digital_life.math import calculate_e_next
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.garden.output_layer.events import (
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.light_response.presets import off_center_green

LIFE_IDS = ("life-red", "life-green", "life-blue")
ANCHOR = (0.5, 0.5, 0.5, 0.5)


def state_map_with_forced_green_exploration() -> dict[
    str, RelationMemoryPersistentState
]:
    states = {life_id: RelationMemoryPersistentState.fresh(life_id) for life_id in LIFE_IDS}
    # For life-green, Hash01(..., "explore", 10) is below p_explore_min.
    # The actual W is still supplied by the formal closed loop, not by this fixture.
    states["life-green"] = replace(states["life-green"], session_count=10)
    return states


@pytest.fixture(scope="module")
def standard_simulation() -> AdaptiveRelationMemoryClosedLoopSimulation:
    simulation = create_adaptive_relation_memory_closed_loop_simulation()
    simulation.engine.run_until_end()
    return simulation


@pytest.fixture(scope="module")
def exploring_simulation() -> AdaptiveRelationMemoryClosedLoopSimulation:
    simulation = create_adaptive_relation_memory_closed_loop_simulation(
        initial_persistent_states_by_life_id=(
            state_map_with_forced_green_exploration()
        )
    )
    simulation.engine.run_until_end()
    return simulation


def record_at(records, signal_index: int):
    return next(record for record in records if record.signal_index == signal_index)


def test_standard_off_center_run_completes_one_session_without_assumed_branch(
    standard_simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> None:
    simulation = standard_simulation
    components = adaptive_digital_life_components(simulation)
    garden = simulation.garden_output_component.snapshot()

    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert simulation.engine.clock.current_time_us == 240_000_000
    assert simulation.light_response_config == off_center_green()
    assert simulation.light_response_config.preferred_hue_degree == 129.0
    assert simulation.light_response_config.preferred_blink_bpm == 125.0
    assert set(components) == set(LIFE_IDS)
    assert garden.last_assigned_holder_id == "life-green"
    assert garden.qualification_holder_id is None
    assert garden.release_count == 1

    for component in components.values():
        final = component.final_persistent_state()
        session = component.relation_memory_session_state()
        assert final is not None
        assert final.session_count == component.initial_persistent_state().session_count + 1
        assert session.session_finalized
        assert session.k_trial is None
        assert len(component.adaptive_signal_records()) == 241
        assert len(component.adaptive_second_round_records()) == 241
        assert len(component.relation_memory_transition_records()) == 4
        assert component.candidate_count() <= 1


def test_candidate_and_rollback_take_effect_only_on_121_and_181(
    exploring_simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> None:
    components = adaptive_digital_life_components(exploring_simulation)
    green = components["life-green"]
    records = green.adaptive_signal_records()
    signal_120 = record_at(records, 120)
    signal_121 = record_at(records, 121)
    signal_180 = record_at(records, 180)
    signal_181 = record_at(records, 181)
    signal_240 = record_at(records, 240)
    transitions = {
        record.signal_index: record
        for record in green.relation_memory_transition_records()
    }

    candidate = transitions[120].k_trial
    assert candidate is not None
    assert green.candidate_count() == 1
    assert green.current_persistent_state().trial_count == 1
    assert transitions[120].candidate_effective_signal_index == 121
    assert transitions[120].k_current_before == signal_120.k_presented == ANCHOR
    assert signal_120.k_current_after == candidate
    assert signal_120.candidate_effective_next_signal
    assert signal_121.k_presented == candidate
    assert signal_121.b_presented != signal_120.b_presented

    # The same single candidate is evaluated at Bundle 1. Its actual W does not
    # strictly exceed the anchor threshold, so the old anchor is selected next.
    assert transitions[180].k_trial == candidate
    assert transitions[180].k_current_before == signal_180.k_presented == candidate
    assert transitions[180].provisional_condition is False
    assert signal_180.k_current_after == ANCHOR
    # This flag identifies candidate generation specifically; the k_current
    # fields still prove that the return-to-anchor update waits for signal 181.
    assert not signal_180.candidate_effective_next_signal
    assert signal_181.k_presented == ANCHOR
    assert signal_181.b_presented == signal_120.b_presented

    final = green.final_persistent_state()
    assert final is not None
    assert transitions[240].k_trial == candidate  # audit value before clearing
    assert transitions[240].session_count_used == 10
    assert transitions[240].session_count_after == 11
    assert signal_240.k_presented == signal_240.k_current_after == ANCHOR
    assert final.k_anchor == ANCHOR
    assert final.session_count == 11
    assert green.relation_memory_session_state().k_trial is None
    assert green.relation_memory_session_state().adoption_result == (
        "rejected_bundle1_threshold"
    )

    # Candidate search changes F/T only. Non-holders do not generate, adopt, or
    # increment a trial even though all three lives finalize the session.
    assert candidate[1] == candidate[3] == 0.5
    assert candidate[0] != 0.5 or candidate[2] != 0.5
    for life_id in ("life-red", "life-blue"):
        component = components[life_id]
        nonholder_final = component.final_persistent_state()
        assert nonholder_final is not None
        assert component.candidate_count() == 0
        assert nonholder_final.k_anchor == ANCHOR
        assert nonholder_final.trial_count == 0
        assert nonholder_final.session_count == 1
        assert all(record.g == 0 for record in component.adaptive_signal_records())


def test_second_round_uses_one_parallel_before_state_and_never_recomputes_b(
    exploring_simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> None:
    green = adaptive_digital_life_components(exploring_simulation)["life-green"]
    adaptive_120 = record_at(green.adaptive_signal_records(), 120)
    inherited_120 = record_at(green.second_round_records(), 120)
    first_120 = record_at(green.first_round_records(), 120)
    first_121 = record_at(green.first_round_records(), 121)

    assert adaptive_120.q_before == inherited_120.q_before == first_120.q
    assert adaptive_120.e_before == inherited_120.e_before == first_120.e
    assert adaptive_120.k_current_before == inherited_120.k_before
    assert adaptive_120.k_presented == first_120.k_current
    assert adaptive_120.q_after == inherited_120.q_after == first_121.q
    assert adaptive_120.e_after == inherited_120.e_after == first_121.e
    assert adaptive_120.e_after == pytest.approx(
        calculate_e_next(adaptive_120.e_before, 1, 1)
    )

    first_round_b = (
        first_120.b_f,
        first_120.b_a,
        first_120.b_t,
        first_120.b_d,
    )
    assert inherited_120.first_round_b == inherited_120.returned_b == first_round_b
    assert adaptive_120.b_presented == first_round_b
    assert adaptive_120.k_current_after != adaptive_120.k_presented
    assert first_121.k_current == adaptive_120.k_current_after

    closing = record_at(green.adaptive_signal_records(), 240)
    closing_first = record_at(green.first_round_records(), 240)
    closing_second = record_at(green.second_round_records(), 240)
    final = green.final_persistent_state()
    assert final is not None
    assert closing_first.q == closing.q_before == closing_second.q_before
    assert closing_first.e == closing.e_before == closing_second.e_before
    assert final.q == closing.q_after == closing_second.q_after
    assert final.e == closing.e_after == closing_second.e_after


def test_candidate_b_reaches_light_and_user_only_through_formal_boundaries(
    exploring_simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> None:
    simulation = exploring_simulation
    green = adaptive_digital_life_components(simulation)["life-green"]
    signals = green.adaptive_signal_records()
    candidate_signal = record_at(signals, 121)
    anchor_signal = record_at(signals, 120)
    candidate_command = next(
        record
        for record in simulation.mapper.command_records()
        if record.source_signal_index == 121
    )
    candidate_receipt = next(
        record
        for record in simulation.component.light_receipt_records()
        if record.source_signal_index == 121
    )

    assert candidate_command.source_b == candidate_signal.b_presented
    assert candidate_command.hue_degree == pytest.approx(
        360.0 * candidate_signal.b_presented[0]
    )
    assert candidate_command.blink_bpm == pytest.approx(
        10.0 + 155.0 * candidate_signal.b_presented[2]
    )
    assert candidate_command.source_b != anchor_signal.b_presented
    assert candidate_receipt.source_b == candidate_command.source_b
    assert candidate_receipt.physical_parameters_changed
    assert candidate_receipt.target_changed
    assert not candidate_receipt.provenance_used_by_physiology

    touch = next(
        event
        for event in simulation.engine.executed_events()
        if event.event_type == DIGITAL_LIFE_TOUCH_EVENT_TYPE
        and event.payload["signal_index"] == 121
        and event.payload["digital_life_id"] == "life-green"
    )
    assert set(touch.payload) == {
        "digital_life_id",
        "signal_index",
        "signal_time_us",
        "b_f",
        "b_a",
        "b_t",
        "b_d",
        "schema_version",
    }
    assert not set(touch.payload) & {
        "k",
        "k_trial",
        "candidate",
        "role",
        "p",
        "v",
        "tau",
        "w",
        "e",
        "q",
        "g",
    }

    heartbeats = simulation.component.heartbeat_records()
    measurements = simulation.polar_h10_component.measurement_records()
    assert len(measurements) == len(heartbeats) - 1
    assert all(record.rri_us > 0 for record in measurements)
    for measurement in measurements[::50]:
        assert measurement.rri_us == (
            measurement.current_heartbeat_time_us
            - measurement.previous_heartbeat_time_us
        )
    garden = simulation.garden_input_component
    assert len(garden.rri_records()) == len(measurements)
    assert len(garden.evaluation_records()) == 4
    assert len(garden.signal_records()) == 241
