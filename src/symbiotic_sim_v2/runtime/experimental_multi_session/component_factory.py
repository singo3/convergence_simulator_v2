"""Stage 8A.1 component composition over the unchanged formal closed loop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.virtual_light.config import VirtualLightDeviceConfig
from symbiotic_sim_v2.digital_life.config import (
    DigitalLifeConfig,
    digital_life_config_for_role,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    relation_memory_state_map_to_dict,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    SelectedSessionFatiguePolicy,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.sigma_policy import (
    ScaledReferenceSigmaPolicy,
)
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
)
from symbiotic_sim_v2.runtime.closed_loop.light_responsive_scenario import (
    _create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.multi_life.config import MultiLifeRuntimeConfig
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.presets import off_center_green

from .experimental_component import (
    ExperimentalAdaptiveConnectedDigitalLifeComponent,
)


def create_experimental_adaptive_relation_memory_closed_loop_simulation(
    *,
    fatigue_policy: SelectedSessionFatiguePolicy,
    sigma_policy: ScaledReferenceSigmaPolicy,
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
    """Inject policy-owning adaptive lives without extending legacy factories."""

    if not isinstance(fatigue_policy, SelectedSessionFatiguePolicy):
        raise TypeError("fatigue_policy must be a SelectedSessionFatiguePolicy")
    if not isinstance(sigma_policy, ScaledReferenceSigmaPolicy):
        raise TypeError("sigma_policy must be a ScaledReferenceSigmaPolicy")
    selected_configs = (
        tuple(digital_life_configs)
        if digital_life_configs is not None
        else tuple(
            digital_life_config_for_role(role) for role in ("red", "green", "blue")
        )
    )
    if len(selected_configs) != 3:
        raise ValueError("Stage 8A.1 requires exactly three Digital Life configs")
    if any(not isinstance(config, DigitalLifeConfig) for config in selected_configs):
        raise TypeError("digital_life_configs must contain DigitalLifeConfig values")
    life_ids = tuple(config.digital_life_id for config in selected_configs)
    if len(set(life_ids)) != 3:
        raise ValueError("Stage 8A.1 Digital Life IDs must be unique")
    if initial_persistent_states_by_life_id is None:
        initial_states = {
            life_id: RelationMemoryPersistentState.fresh(life_id)
            for life_id in life_ids
        }
    else:
        relation_memory_state_map_to_dict(
            initial_persistent_states_by_life_id,
            expected_digital_life_ids=life_ids,
        )
        initial_states = dict(initial_persistent_states_by_life_id)

    def create_experimental_life(
        config: DigitalLifeConfig,
        initial_state: object | None,
    ) -> ExperimentalAdaptiveConnectedDigitalLifeComponent:
        if not isinstance(initial_state, RelationMemoryPersistentState):
            raise TypeError("Stage 8A.1 factory requires one persistent state per life")
        return ExperimentalAdaptiveConnectedDigitalLifeComponent(
            config,
            initial_state,
            fatigue_policy=fatigue_policy,
            sigma_policy=sigma_policy,
        )

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
        digital_life_component_factory=create_experimental_life,
        initial_persistent_states_by_life_id=initial_states,
    )
    experimental_adaptive_digital_life_components(simulation)
    return simulation


def experimental_adaptive_digital_life_components(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
) -> Mapping[str, ExperimentalAdaptiveConnectedDigitalLifeComponent]:
    """Return the fixed roster only when every life owns both experiment policies."""

    components = simulation.digital_life_components
    if any(
        not isinstance(component, ExperimentalAdaptiveConnectedDigitalLifeComponent)
        for component in components.values()
    ):
        raise TypeError("simulation does not contain Stage 8A.1 experimental lives")
    return cast(
        Mapping[str, ExperimentalAdaptiveConnectedDigitalLifeComponent],
        components,
    )


__all__ = [
    "create_experimental_adaptive_relation_memory_closed_loop_simulation",
    "experimental_adaptive_digital_life_components",
]
