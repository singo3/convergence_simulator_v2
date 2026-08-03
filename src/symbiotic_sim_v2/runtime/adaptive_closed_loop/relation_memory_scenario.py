"""Stage 5C factory over the existing Stage 7.1 formal closed loop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.virtual_light.config import VirtualLightDeviceConfig
from symbiotic_sim_v2.digital_life.config import (
    DigitalLifeConfig,
    digital_life_config_for_role,
)
from symbiotic_sim_v2.digital_life.relation_memory.adaptive_component import (
    AdaptiveConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    relation_memory_state_map_to_dict,
)
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.runtime.closed_loop.light_responsive_scenario import (
    LightResponsiveClosedLoopSimulation,
    _create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.multi_life.config import MultiLifeRuntimeConfig
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.presets import off_center_green

type AdaptiveRelationMemoryClosedLoopSimulation = LightResponsiveClosedLoopSimulation


def create_adaptive_relation_memory_closed_loop_simulation(
    *,
    virtual_user_config: VirtualUserConfig | None = None,
    polar_h10_config: PolarH10Config | None = None,
    garden_input_config: GardenInputConfig | None = None,
    digital_life_configs: Sequence[DigitalLifeConfig] | None = None,
    runtime_config: MultiLifeRuntimeConfig | None = None,
    garden_output_config: GardenOutputConfig | None = None,
    garden_light_mapper_config: GardenLightMapperConfig | None = None,
    virtual_light_device_config: VirtualLightDeviceConfig | None = None,
    light_response_config: LightResponseConfig | None = None,
    initial_persistent_states_by_life_id: Mapping[
        str, RelationMemoryPersistentState
    ]
    | None = None,
) -> AdaptiveRelationMemoryClosedLoopSimulation:
    """Inject three independent adaptive lives into the unchanged formal loop."""

    selected_configs = (
        tuple(digital_life_configs)
        if digital_life_configs is not None
        else tuple(
            digital_life_config_for_role(role) for role in ("red", "green", "blue")
        )
    )
    if len(selected_configs) != 3:
        raise ValueError("Stage 5C requires exactly three Digital Life configs")
    if any(not isinstance(config, DigitalLifeConfig) for config in selected_configs):
        raise TypeError("digital_life_configs must contain DigitalLifeConfig values")
    life_ids = tuple(config.digital_life_id for config in selected_configs)
    if len(set(life_ids)) != 3:
        raise ValueError("Stage 5C Digital Life IDs must be unique")
    if initial_persistent_states_by_life_id is None:
        initial_states = {
            life_id: RelationMemoryPersistentState.fresh(life_id)
            for life_id in life_ids
        }
    else:
        # The serializer's validation is deliberately reused even though no
        # JSON is involved, keeping the Stage 8 handoff contract exact.
        relation_memory_state_map_to_dict(
            initial_persistent_states_by_life_id,
            expected_digital_life_ids=life_ids,
        )
        initial_states = dict(initial_persistent_states_by_life_id)

    def create_adaptive_life(
        config: DigitalLifeConfig,
        initial_state: object | None,
    ) -> AdaptiveConnectedDigitalLifeComponent:
        if not isinstance(initial_state, RelationMemoryPersistentState):
            raise TypeError("Stage 5C factory requires one persistent state per life")
        return AdaptiveConnectedDigitalLifeComponent(config, initial_state)

    simulation = _create_light_responsive_closed_loop_simulation(
        virtual_user_config=virtual_user_config,
        polar_h10_config=polar_h10_config,
        garden_input_config=garden_input_config,
        digital_life_configs=selected_configs,
        runtime_config=runtime_config,
        garden_output_config=garden_output_config,
        garden_light_mapper_config=garden_light_mapper_config,
        virtual_light_device_config=virtual_light_device_config,
        light_response_config=light_response_config or off_center_green(),
        digital_life_component_factory=create_adaptive_life,
        initial_persistent_states_by_life_id=initial_states,
    )
    components = simulation.digital_life_components
    if any(
        not isinstance(component, AdaptiveConnectedDigitalLifeComponent)
        for component in components.values()
    ):
        raise RuntimeError("Stage 5C factory produced a non-adaptive life")
    return simulation


def adaptive_digital_life_components(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> Mapping[str, AdaptiveConnectedDigitalLifeComponent]:
    """Return the already immutable roster mapping with a precise Stage 5C type."""

    if not isinstance(simulation, LightResponsiveClosedLoopSimulation):
        raise TypeError("simulation must be a Stage 5C closed-loop simulation")
    components = simulation.digital_life_components
    if any(
        not isinstance(component, AdaptiveConnectedDigitalLifeComponent)
        for component in components.values()
    ):
        raise TypeError("simulation does not contain adaptive Digital Lives")
    return cast(Mapping[str, AdaptiveConnectedDigitalLifeComponent], components)


__all__ = [
    "AdaptiveRelationMemoryClosedLoopSimulation",
    "adaptive_digital_life_components",
    "create_adaptive_relation_memory_closed_loop_simulation",
]
