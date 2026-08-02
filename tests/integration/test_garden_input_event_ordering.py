"""Deterministic same-time ordering at every formal Garden boundary."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.domain.event_priorities import (
    GARDEN_EVALUATION_FINALIZE_TRIGGER_PRIORITY,
    GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
    GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
    GARDEN_PHASE_EVENT_PRIORITY,
    HEARTBEAT_EVENT_PRIORITY,
    RRI_MEASUREMENT_EVENT_PRIORITY,
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
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
from symbiotic_sim_v2.garden.input_layer.scenario import create_garden_input_simulation
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig


def zero_variability_user_config() -> VirtualUserConfig:
    return VirtualUserConfig(
        duration_seconds=240,
        mean_heart_rate_bpm=60.0,
        respiratory_amplitude_ms=0.0,
        slow_wave_amplitude_ms=0.0,
        correlated_variability_sd_ms=0.0,
        beat_jitter_sd_ms=0.0,
    )


def run_exact_second_fixture():
    simulation = create_garden_input_simulation(zero_variability_user_config())
    simulation.engine.run_until_end()
    return simulation


def event_types_at(simulation, time_us: int) -> list[str]:
    return [
        event.event_type
        for event in simulation.engine.executed_events()
        if event.scheduled_time_us == time_us
    ]


@pytest.mark.parametrize(
    ("time_us", "expected_types"),
    (
        (
            60_000_000,
            [
                GARDEN_PHASE_CHANGED_EVENT_TYPE,
                GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
                GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
                GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
                GARDEN_INPUT_SIGNAL_EVENT_TYPE,
                HEARTBEAT_EVENT_TYPE,
                RRI_MEASUREMENT_EVENT_TYPE,
            ],
        ),
        (
            120_000_000,
            [
                GARDEN_PHASE_CHANGED_EVENT_TYPE,
                GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
                GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
                GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
                GARDEN_INPUT_SIGNAL_EVENT_TYPE,
                HEARTBEAT_EVENT_TYPE,
                RRI_MEASUREMENT_EVENT_TYPE,
            ],
        ),
        (
            240_000_000,
            [
                GARDEN_PHASE_CHANGED_EVENT_TYPE,
                GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
                GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
                GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
                GARDEN_INPUT_SIGNAL_EVENT_TYPE,
                HEARTBEAT_EVENT_TYPE,
                RRI_MEASUREMENT_EVENT_TYPE,
                SIMULATION_COMPLETE_EVENT_TYPE,
            ],
        ),
    ),
)
def test_exact_boundary_execution_order(time_us: int, expected_types: list[str]) -> None:
    simulation = run_exact_second_fixture()

    assert event_types_at(simulation, time_us) == expected_types


def test_priority_constants_encode_the_required_cross_component_order() -> None:
    assert (
        GARDEN_PHASE_EVENT_PRIORITY
        < GARDEN_EVALUATION_FINALIZE_TRIGGER_PRIORITY
        < GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY
        < GARDEN_INPUT_SIGNAL_EVENT_PRIORITY
        < HEARTBEAT_EVENT_PRIORITY
        < RRI_MEASUREMENT_EVENT_PRIORITY
        < SIMULATION_COMPLETE_EVENT_PRIORITY
    )


def test_formal_finalize_output_is_inserted_before_the_existing_signal_trigger() -> None:
    simulation = run_exact_second_fixture()
    events = simulation.engine.executed_events()

    for time_us in (60_000_000, 120_000_000, 180_000_000, 240_000_000):
        at_boundary = [event for event in events if event.scheduled_time_us == time_us]
        types = [event.event_type for event in at_boundary]
        trigger_index = types.index(GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE)
        output_index = types.index(GARDEN_EVALUATION_FINALIZED_EVENT_TYPE)
        signal_index = types.index(GARDEN_INPUT_SIGNAL_EVENT_TYPE)
        assert trigger_index < output_index < signal_index
        assert at_boundary[output_index].priority == GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY


def test_signal_trigger_precedes_its_same_priority_formal_signal_by_sequence() -> None:
    simulation = run_exact_second_fixture()

    for time_us in (0, 60_000_000, 120_000_000, 240_000_000):
        at_boundary = [
            event
            for event in simulation.engine.executed_events()
            if event.scheduled_time_us == time_us
            and event.event_type
            in {GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE, GARDEN_INPUT_SIGNAL_EVENT_TYPE}
        ]
        assert [event.event_type for event in at_boundary] == [
            GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
            GARDEN_INPUT_SIGNAL_EVENT_TYPE,
        ]
        assert at_boundary[0].priority == at_boundary[1].priority
        assert at_boundary[0].sequence < at_boundary[1].sequence


def test_every_executed_event_obeys_time_priority_sequence_order() -> None:
    simulation = run_exact_second_fixture()
    keys = [event.ordering_key for event in simulation.engine.executed_events()]

    assert keys == sorted(keys)
