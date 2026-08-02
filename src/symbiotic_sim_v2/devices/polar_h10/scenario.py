"""Stage 3 integration factory for the virtual user and ideal Polar H10."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.devices.polar_h10.component import PolarH10Component
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.domain.event_priorities import SIMULATION_COMPLETE_EVENT_PRIORITY
from symbiotic_sim_v2.domain.event_types import (
    HEARTBEAT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.simulation.time_utils import seconds_to_us
from symbiotic_sim_v2.virtual_user.component import VirtualUserComponent
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig

POLAR_H10_SCENARIO_SOURCE = "polar_h10_scenario"


@dataclass(slots=True)
class PolarH10Scenario:
    """Reset and schedule both Stage 2 producer and Stage 3 input device."""

    virtual_user_config: VirtualUserConfig
    polar_h10_config: PolarH10Config
    virtual_user_component: VirtualUserComponent
    polar_h10_component: PolarH10Component

    @property
    def start_time_us(self) -> int:
        return 0

    @property
    def end_time_us(self) -> int:
        return seconds_to_us(self.virtual_user_config.duration_seconds)

    def schedule(self, scheduler: EventScheduler) -> None:
        """Recreate a clean producer/device run without registering handlers again."""

        if self.virtual_user_component.config != self.virtual_user_config:
            raise RuntimeError("virtual-user scenario and component configurations differ")
        if self.polar_h10_component.config != self.polar_h10_config:
            raise RuntimeError("H10 scenario and component configurations differ")
        if self.polar_h10_config.expected_user_id != self.virtual_user_config.user_id:
            raise ValueError("H10 expected_user_id must match virtual-user user_id")
        self.virtual_user_component.reset()
        self.polar_h10_component.reset()
        self.virtual_user_component.schedule_initial(scheduler)
        scheduler.schedule_at(
            self.end_time_us,
            SIMULATION_COMPLETE_EVENT_TYPE,
            source=POLAR_H10_SCENARIO_SOURCE,
            priority=SIMULATION_COMPLETE_EVENT_PRIORITY,
            payload={"scenario": "stage_03_virtual_polar_h10"},
        )


@dataclass(frozen=True, slots=True)
class PolarH10Simulation:
    """Fully wired Stage 3 bundle shared by GUI and headless execution."""

    engine: SimulationEngine
    scenario: PolarH10Scenario
    virtual_user_component: VirtualUserComponent
    polar_h10_component: PolarH10Component
    virtual_user_config: VirtualUserConfig
    polar_h10_config: PolarH10Config

    @property
    def component(self) -> VirtualUserComponent:
        """Expose the Stage 2 producer for the reused virtual-user GUI panel."""

        return self.virtual_user_component

    @property
    def config(self) -> VirtualUserConfig:
        """Expose the Stage 2 config for the reused virtual-user GUI panel."""

        return self.virtual_user_config


def create_polar_h10_simulation(
    virtual_user_config: VirtualUserConfig | None = None,
    polar_h10_config: PolarH10Config | None = None,
) -> PolarH10Simulation:
    """Create one engine with exactly one producer and one H10 heartbeat handler."""

    selected_user_config = virtual_user_config or VirtualUserConfig()
    selected_h10_config = polar_h10_config or PolarH10Config(
        expected_user_id=selected_user_config.user_id
    )
    if selected_h10_config.expected_user_id != selected_user_config.user_id:
        raise ValueError("H10 expected_user_id must match virtual-user user_id")
    virtual_user = VirtualUserComponent(selected_user_config)
    polar_h10 = PolarH10Component(selected_h10_config)
    scenario = PolarH10Scenario(
        virtual_user_config=selected_user_config,
        polar_h10_config=selected_h10_config,
        virtual_user_component=virtual_user,
        polar_h10_component=polar_h10,
    )
    engine = SimulationEngine()
    engine.register_handler(HEARTBEAT_EVENT_TYPE, virtual_user.handle_heartbeat)
    engine.register_handler(HEARTBEAT_EVENT_TYPE, polar_h10.handle_heartbeat)
    engine.register_handler(
        SIMULATION_COMPLETE_EVENT_TYPE,
        polar_h10.handle_simulation_complete,
    )
    engine.load_scenario(scenario)
    return PolarH10Simulation(
        engine=engine,
        scenario=scenario,
        virtual_user_component=virtual_user,
        polar_h10_component=polar_h10,
        virtual_user_config=selected_user_config,
        polar_h10_config=selected_h10_config,
    )
