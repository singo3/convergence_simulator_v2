"""Private component-injection seam without changing Stage 5B-7.1 factories."""

from __future__ import annotations

import inspect

import pytest

from symbiotic_sim_v2.digital_life.connected_component import (
    ConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.runtime.closed_loop.light_responsive_scenario import (
    _create_light_responsive_closed_loop_simulation,
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    _create_light_feedback_simulation,
    create_light_feedback_simulation,
)
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    _create_three_digital_life_competition_simulation,
    create_three_digital_life_competition_simulation,
)

EXPECTED_LIFE_IDS = ("life-red", "life-green", "life-blue")


def test_existing_public_factory_signatures_expose_no_adaptive_injection() -> None:
    expected_parameters = {
        create_three_digital_life_competition_simulation: (
            "virtual_user_config",
            "polar_h10_config",
            "garden_input_config",
            "digital_life_configs",
            "runtime_config",
            "garden_output_config",
        ),
        create_light_feedback_simulation: (
            "virtual_user_config",
            "polar_h10_config",
            "garden_input_config",
            "digital_life_configs",
            "runtime_config",
            "garden_output_config",
            "garden_light_mapper_config",
            "virtual_light_device_config",
        ),
        create_light_responsive_closed_loop_simulation: (
            "virtual_user_config",
            "polar_h10_config",
            "garden_input_config",
            "digital_life_configs",
            "runtime_config",
            "garden_output_config",
            "garden_light_mapper_config",
            "virtual_light_device_config",
            "light_response_config",
        ),
    }
    for factory, expected in expected_parameters.items():
        assert tuple(inspect.signature(factory).parameters) == expected


def test_each_private_builder_exposes_both_adaptive_injection_parameters() -> None:
    for builder in (
        _create_three_digital_life_competition_simulation,
        _create_light_feedback_simulation,
        _create_light_responsive_closed_loop_simulation,
    ):
        parameters = inspect.signature(builder).parameters
        assert "digital_life_component_factory" in parameters
        assert "initial_persistent_states_by_life_id" in parameters


def test_stage7_private_builder_passes_each_roster_state_only_to_its_component() -> None:
    initial_states = {life_id: object() for life_id in EXPECTED_LIFE_IDS}
    received: dict[str, object | None] = {}

    def create_component(config, initial_state):
        received[config.digital_life_id] = initial_state
        return ConnectedDigitalLifeComponent(config)

    simulation = _create_light_responsive_closed_loop_simulation(
        digital_life_component_factory=create_component,
        initial_persistent_states_by_life_id=initial_states,
    )

    assert set(simulation.digital_life_components) == set(EXPECTED_LIFE_IDS)
    assert set(received) == set(EXPECTED_LIFE_IDS)
    assert all(received[life_id] is initial_states[life_id] for life_id in EXPECTED_LIFE_IDS)
    simulation.engine.run_until_end()
    assert simulation.engine.clock.current_time_us == 240_000_000


@pytest.mark.parametrize(
    "invalid_states",
    (
        (),
        {"life-red": object()},
        {
            "life-red": object(),
            "life-green": object(),
            "life-blue": object(),
            "life-extra": object(),
        },
    ),
)
def test_private_builder_rejects_non_mapping_or_non_roster_state_sets(
    invalid_states,
) -> None:
    expected_error = TypeError if not isinstance(invalid_states, dict) else ValueError
    with pytest.raises(expected_error):
        _create_light_responsive_closed_loop_simulation(
            initial_persistent_states_by_life_id=invalid_states,
        )


def test_legacy_component_path_refuses_non_null_persistent_state() -> None:
    with pytest.raises(ValueError, match="requires an injected"):
        _create_light_responsive_closed_loop_simulation(
            initial_persistent_states_by_life_id={
                life_id: object() for life_id in EXPECTED_LIFE_IDS
            },
        )
