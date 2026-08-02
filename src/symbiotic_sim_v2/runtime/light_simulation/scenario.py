"""Stage 6 factory layered over the unchanged Stage 5B.1 simulation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.virtual_light.component import VirtualLightDeviceComponent
from symbiotic_sim_v2.devices.virtual_light.config import VirtualLightDeviceConfig
from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.domain.event_types import SIMULATION_COMPLETE_EVENT_TYPE
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.light_mapper.component import GardenLightMapperComponent
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.events import LIGHT_COMMAND_EVENT_TYPE
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.garden.output_layer.events import GARDEN_QUALIFIED_B_EVENT_TYPE
from symbiotic_sim_v2.runtime.multi_life.config import MultiLifeRuntimeConfig
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    ThreeDigitalLifeCompetitionScenario,
    ThreeDigitalLifeCompetitionSimulation,
    create_three_digital_life_competition_simulation,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig


@dataclass(slots=True)
class LightFeedbackScenario:
    """Reset Stage 6 components and delegate the unchanged upstream schedule."""

    upstream_scenario: ThreeDigitalLifeCompetitionScenario
    garden_light_mapper_config: GardenLightMapperConfig
    garden_light_mapper_component: GardenLightMapperComponent
    virtual_light_device_config: VirtualLightDeviceConfig
    virtual_light_device_component: VirtualLightDeviceComponent

    @property
    def start_time_us(self) -> int:
        return self.upstream_scenario.start_time_us

    @property
    def end_time_us(self) -> int:
        return self.upstream_scenario.end_time_us

    def schedule(self, scheduler: EventScheduler) -> None:
        """Reset light state exactly once before rebuilding upstream events."""

        if self.garden_light_mapper_component.config != self.garden_light_mapper_config:
            raise RuntimeError("scenario and Garden Light Mapper configs differ")
        if self.virtual_light_device_component.config != self.virtual_light_device_config:
            raise RuntimeError("scenario and Virtual Light Device configs differ")
        if self.virtual_light_device_config.simulation_end_time_us != self.end_time_us:
            raise RuntimeError("Virtual Light Device end time differs from the scenario")
        self.garden_light_mapper_component.reset()
        self.virtual_light_device_component.reset()
        self.upstream_scenario.schedule(scheduler)


@dataclass(frozen=True, slots=True)
class LightFeedbackSimulation:
    """Complete Stage 6 bundle shared by headless and GUI execution."""

    engine: SimulationEngine
    scenario: LightFeedbackScenario
    upstream_simulation: ThreeDigitalLifeCompetitionSimulation
    garden_light_mapper_component: GardenLightMapperComponent
    virtual_light_device_component: VirtualLightDeviceComponent
    garden_light_mapper_config: GardenLightMapperConfig
    virtual_light_device_config: VirtualLightDeviceConfig

    @property
    def upstream(self) -> ThreeDigitalLifeCompetitionSimulation:
        return self.upstream_simulation

    @property
    def mapper(self) -> GardenLightMapperComponent:
        return self.garden_light_mapper_component

    @property
    def device(self) -> VirtualLightDeviceComponent:
        return self.virtual_light_device_component


def create_light_feedback_simulation(
    *,
    virtual_user_config: VirtualUserConfig | None = None,
    polar_h10_config: PolarH10Config | None = None,
    garden_input_config: GardenInputConfig | None = None,
    digital_life_configs: Sequence[DigitalLifeConfig] | None = None,
    runtime_config: MultiLifeRuntimeConfig | None = None,
    garden_output_config: GardenOutputConfig | None = None,
    garden_light_mapper_config: GardenLightMapperConfig | None = None,
    virtual_light_device_config: VirtualLightDeviceConfig | None = None,
) -> LightFeedbackSimulation:
    """Wrap Stage 5B.1 without changing its factory, handlers, or event digest."""

    upstream = create_three_digital_life_competition_simulation(
        virtual_user_config=virtual_user_config,
        polar_h10_config=polar_h10_config,
        garden_input_config=garden_input_config,
        digital_life_configs=digital_life_configs,
        runtime_config=runtime_config,
        garden_output_config=garden_output_config,
    )
    mapper_config = garden_light_mapper_config or GardenLightMapperConfig(
        garden_id=upstream.garden_output_config.garden_id
    )
    if mapper_config.garden_id != upstream.garden_output_config.garden_id:
        raise ValueError("Garden Light Mapper and Garden output IDs differ")
    device_config = virtual_light_device_config or VirtualLightDeviceConfig(
        simulation_end_time_us=upstream.scenario.end_time_us
    )
    if device_config.simulation_end_time_us != upstream.scenario.end_time_us:
        raise ValueError("Virtual Light Device end time must match the scenario")

    mapper = GardenLightMapperComponent(mapper_config)
    device = VirtualLightDeviceComponent(device_config)
    scenario = LightFeedbackScenario(
        upstream_scenario=upstream.scenario,
        garden_light_mapper_config=mapper_config,
        garden_light_mapper_component=mapper,
        virtual_light_device_config=device_config,
        virtual_light_device_component=device,
    )

    engine = upstream.engine
    engine.register_handler(
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        mapper.handle_garden_qualified_b,
    )
    engine.register_handler(LIGHT_COMMAND_EVENT_TYPE, device.handle_light_command)
    engine.register_handler(
        SIMULATION_COMPLETE_EVENT_TYPE,
        device.handle_simulation_complete,
    )
    engine.load_scenario(scenario)

    return LightFeedbackSimulation(
        engine=engine,
        scenario=scenario,
        upstream_simulation=upstream,
        garden_light_mapper_component=mapper,
        virtual_light_device_component=device,
        garden_light_mapper_config=mapper_config,
        virtual_light_device_config=device_config,
    )
