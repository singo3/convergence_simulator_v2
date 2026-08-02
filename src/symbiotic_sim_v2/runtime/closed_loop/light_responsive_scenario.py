"""Stage 7 closed-loop composition with an injected responsive virtual user."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from symbiotic_sim_v2.devices.polar_h10.component import PolarH10Component
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.virtual_light.component import VirtualLightDeviceComponent
from symbiotic_sim_v2.devices.virtual_light.config import VirtualLightDeviceConfig
from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
)
from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.digital_life.connected_component import (
    ConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.domain.event_types import SIMULATION_COMPLETE_EVENT_TYPE
from symbiotic_sim_v2.garden.input_layer.component import GardenInputComponent
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.light_mapper.component import GardenLightMapperComponent
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.output_layer.component import GardenOutputComponent
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    LightFeedbackScenario,
    LightFeedbackSimulation,
    _create_light_feedback_simulation,
)
from symbiotic_sim_v2.runtime.multi_life.config import MultiLifeRuntimeConfig
from symbiotic_sim_v2.runtime.multi_life.coordinator import (
    MultiLifeRuntimeCoordinator,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.component import (
    LightResponsiveVirtualUserComponent,
)
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.presets import aligned_green_center


@dataclass(slots=True)
class LightResponsiveClosedLoopScenario:
    """Validate Stage 7 ownership and delegate the unchanged Stage 6 schedule."""

    upstream_scenario: LightFeedbackScenario
    virtual_user_config: VirtualUserConfig
    light_response_config: LightResponseConfig
    light_responsive_virtual_user_component: LightResponsiveVirtualUserComponent

    @property
    def start_time_us(self) -> int:
        return self.upstream_scenario.start_time_us

    @property
    def end_time_us(self) -> int:
        return self.upstream_scenario.end_time_us

    def schedule(self, scheduler: EventScheduler) -> None:
        """Rebuild through Stage 6, which resets the injected user exactly once."""

        component = self.light_responsive_virtual_user_component
        if component.config != self.virtual_user_config:
            raise RuntimeError("scenario and responsive-user base configs differ")
        if component.light_response_config != self.light_response_config:
            raise RuntimeError("scenario and responsive-user light configs differ")
        if self.light_response_config.simulation_end_time_us != self.end_time_us:
            raise RuntimeError("light-response end time differs from the scenario")
        garden_scenario = (
            self.upstream_scenario.upstream_scenario.upstream_scenario
        )
        if garden_scenario.virtual_user_component is not component:
            raise RuntimeError("Stage 7 responsive user is not the injected heartbeat source")
        self.upstream_scenario.schedule(scheduler)


@dataclass(frozen=True, slots=True)
class LightResponsiveClosedLoopSimulation:
    """Complete Stage 7 bundle shared by headless and GUI execution."""

    engine: SimulationEngine
    scenario: LightResponsiveClosedLoopScenario
    upstream_simulation: LightFeedbackSimulation
    light_responsive_virtual_user_component: LightResponsiveVirtualUserComponent
    light_response_config: LightResponseConfig

    @property
    def upstream(self) -> LightFeedbackSimulation:
        return self.upstream_simulation

    @property
    def component(self) -> LightResponsiveVirtualUserComponent:
        return self.light_responsive_virtual_user_component

    @property
    def virtual_user_component(self) -> LightResponsiveVirtualUserComponent:
        return self.light_responsive_virtual_user_component

    @property
    def config(self) -> VirtualUserConfig:
        return self.virtual_user_config

    @property
    def virtual_user_config(self) -> VirtualUserConfig:
        return self.upstream_simulation.upstream_simulation.virtual_user_config

    @property
    def polar_h10_component(self) -> PolarH10Component:
        return self.upstream_simulation.upstream_simulation.polar_h10_component

    @property
    def garden_input_component(self) -> GardenInputComponent:
        return self.upstream_simulation.upstream_simulation.garden_input_component

    @property
    def digital_life_components(self) -> Mapping[str, ConnectedDigitalLifeComponent]:
        return self.upstream_simulation.upstream_simulation.digital_life_components

    @property
    def life_components(self) -> Mapping[str, ConnectedDigitalLifeComponent]:
        return self.digital_life_components

    @property
    def runtime_coordinator(self) -> MultiLifeRuntimeCoordinator:
        return self.upstream_simulation.upstream_simulation.runtime_coordinator

    @property
    def coordinator(self) -> MultiLifeRuntimeCoordinator:
        return self.runtime_coordinator

    @property
    def garden_output_component(self) -> GardenOutputComponent:
        return self.upstream_simulation.upstream_simulation.garden_output_component

    @property
    def garden_output(self) -> GardenOutputComponent:
        return self.garden_output_component

    @property
    def garden_light_mapper_component(self) -> GardenLightMapperComponent:
        return self.upstream_simulation.garden_light_mapper_component

    @property
    def virtual_light_device_component(self) -> VirtualLightDeviceComponent:
        return self.upstream_simulation.virtual_light_device_component

    @property
    def mapper(self) -> GardenLightMapperComponent:
        return self.garden_light_mapper_component

    @property
    def device(self) -> VirtualLightDeviceComponent:
        return self.virtual_light_device_component

    @property
    def polar_h10_config(self) -> PolarH10Config:
        return self.upstream_simulation.upstream_simulation.polar_h10_config

    @property
    def garden_input_config(self) -> GardenInputConfig:
        return self.upstream_simulation.upstream_simulation.garden_input_config

    @property
    def digital_life_configs(
        self,
    ) -> tuple[DigitalLifeConfig, DigitalLifeConfig, DigitalLifeConfig]:
        return self.upstream_simulation.upstream_simulation.digital_life_configs

    @property
    def runtime_config(self) -> MultiLifeRuntimeConfig:
        return self.upstream_simulation.upstream_simulation.runtime_config

    @property
    def garden_output_config(self) -> GardenOutputConfig:
        return self.upstream_simulation.upstream_simulation.garden_output_config

    @property
    def garden_light_mapper_config(self) -> GardenLightMapperConfig:
        return self.upstream_simulation.garden_light_mapper_config

    @property
    def virtual_light_device_config(self) -> VirtualLightDeviceConfig:
        return self.upstream_simulation.virtual_light_device_config


def create_light_responsive_closed_loop_simulation(
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
) -> LightResponsiveClosedLoopSimulation:
    """Wire only the Stage 6 formal light state back to the injected user."""

    selected_light_response_config = light_response_config or aligned_green_center()
    if not isinstance(selected_light_response_config, LightResponseConfig):
        raise TypeError("light_response_config must be a LightResponseConfig")

    def create_responsive_user(
        selected_virtual_user_config: VirtualUserConfig,
    ) -> LightResponsiveVirtualUserComponent:
        return LightResponsiveVirtualUserComponent(
            selected_virtual_user_config,
            selected_light_response_config,
        )

    upstream = _create_light_feedback_simulation(
        virtual_user_config=virtual_user_config,
        polar_h10_config=polar_h10_config,
        garden_input_config=garden_input_config,
        digital_life_configs=digital_life_configs,
        runtime_config=runtime_config,
        garden_output_config=garden_output_config,
        garden_light_mapper_config=garden_light_mapper_config,
        virtual_light_device_config=virtual_light_device_config,
        heartbeat_source_factory=create_responsive_user,
    )
    responsive_user = upstream.upstream_simulation.virtual_user_component
    if not isinstance(responsive_user, LightResponsiveVirtualUserComponent):
        raise RuntimeError("Stage 7 heartbeat-source injection produced the wrong component")
    scenario = LightResponsiveClosedLoopScenario(
        upstream_scenario=upstream.scenario,
        virtual_user_config=upstream.upstream_simulation.virtual_user_config,
        light_response_config=selected_light_response_config,
        light_responsive_virtual_user_component=responsive_user,
    )
    engine = upstream.engine
    engine.register_handler(
        LIGHT_STIMULUS_STATE_EVENT_TYPE,
        responsive_user.handle_light_stimulus_state,
    )
    engine.register_handler(
        SIMULATION_COMPLETE_EVENT_TYPE,
        responsive_user.handle_simulation_complete,
    )
    engine.load_scenario(scenario)
    return LightResponsiveClosedLoopSimulation(
        engine=engine,
        scenario=scenario,
        upstream_simulation=upstream,
        light_responsive_virtual_user_component=responsive_user,
        light_response_config=selected_light_response_config,
    )
