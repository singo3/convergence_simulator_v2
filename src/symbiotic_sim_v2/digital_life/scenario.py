"""Stage 5A integration over the unchanged Stage 4 input pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.devices.polar_h10.component import PolarH10Component
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.digital_life.component import SingleDigitalLifeComponent
from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
)
from symbiotic_sim_v2.garden.input_layer.component import GardenInputComponent
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.scenario import (
    GardenInputScenario,
    create_garden_input_simulation,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.virtual_user.component import VirtualUserComponent
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig


@dataclass(slots=True)
class SingleDigitalLifeScenario:
    """Reset one life and delegate the complete event schedule to Stage 4."""

    upstream_scenario: GardenInputScenario
    digital_life_config: DigitalLifeConfig
    digital_life_component: SingleDigitalLifeComponent

    @property
    def start_time_us(self) -> int:
        """Use the unchanged Stage 4 scenario start time."""

        return self.upstream_scenario.start_time_us

    @property
    def end_time_us(self) -> int:
        """Use the unchanged 240-second Stage 4 scenario end time."""

        return self.upstream_scenario.end_time_us

    def schedule(self, scheduler: EventScheduler) -> None:
        """Reset all four components and recreate only the Stage 4 event stream."""

        if self.digital_life_component.config != self.digital_life_config:
            raise RuntimeError("digital-life scenario and component configurations differ")
        self.digital_life_component.reset()
        self.upstream_scenario.schedule(scheduler)


@dataclass(frozen=True, slots=True)
class SingleDigitalLifeSimulation:
    """Fully wired Stage 5A bundle shared by GUI and headless execution."""

    engine: SimulationEngine
    scenario: SingleDigitalLifeScenario
    virtual_user_component: VirtualUserComponent
    polar_h10_component: PolarH10Component
    garden_input_component: GardenInputComponent
    digital_life_component: SingleDigitalLifeComponent
    virtual_user_config: VirtualUserConfig
    polar_h10_config: PolarH10Config
    garden_input_config: GardenInputConfig
    digital_life_config: DigitalLifeConfig

    @property
    def component(self) -> VirtualUserComponent:
        """Stage 2-compatible alias used by the retained virtual-user panel."""

        return self.virtual_user_component

    @property
    def config(self) -> VirtualUserConfig:
        """Stage 2-compatible alias used by the retained virtual-user panel."""

        return self.virtual_user_config

    @property
    def life_component(self) -> SingleDigitalLifeComponent:
        """Concise alias for Stage 5A-specific callers."""

        return self.digital_life_component

    @property
    def life_config(self) -> DigitalLifeConfig:
        """Concise alias for Stage 5A-specific callers."""

        return self.digital_life_config


def create_single_digital_life_simulation(
    *,
    virtual_user_config: VirtualUserConfig | None = None,
    polar_h10_config: PolarH10Config | None = None,
    garden_input_config: GardenInputConfig | None = None,
    digital_life_config: DigitalLifeConfig | None = None,
) -> SingleDigitalLifeSimulation:
    """Add one formal Garden-event consumer without changing Stage 4 scheduling."""

    upstream = create_garden_input_simulation(
        virtual_user_config=virtual_user_config,
        polar_h10_config=polar_h10_config,
        garden_input_config=garden_input_config,
    )
    selected_life_config = digital_life_config or DigitalLifeConfig()
    digital_life = SingleDigitalLifeComponent(selected_life_config)
    scenario = SingleDigitalLifeScenario(
        upstream_scenario=upstream.scenario,
        digital_life_config=selected_life_config,
        digital_life_component=digital_life,
    )

    engine = upstream.engine
    engine.register_handler(
        GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
        digital_life.handle_evaluation_finalized,
    )
    engine.register_handler(
        GARDEN_INPUT_SIGNAL_EVENT_TYPE,
        digital_life.handle_garden_input_signal,
    )
    engine.load_scenario(scenario)

    return SingleDigitalLifeSimulation(
        engine=engine,
        scenario=scenario,
        virtual_user_component=upstream.virtual_user_component,
        polar_h10_component=upstream.polar_h10_component,
        garden_input_component=upstream.garden_input_component,
        digital_life_component=digital_life,
        virtual_user_config=upstream.virtual_user_config,
        polar_h10_config=upstream.polar_h10_config,
        garden_input_config=upstream.garden_input_config,
        digital_life_config=selected_life_config,
    )
