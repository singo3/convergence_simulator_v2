"""Scenario and shared factory wiring the Stage 2 component to the Stage 1 engine."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.virtual_user.component import (
    HEARTBEAT_EVENT_TYPE,
    VirtualUserComponent,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig

VIRTUAL_USER_COMPLETION_PRIORITY = 100
VIRTUAL_USER_SCENARIO_SOURCE = "virtual_user_scenario"


@dataclass(slots=True)
class VirtualUserScenario:
    """Reset and schedule an external-input-free user over a bounded duration."""

    config: VirtualUserConfig
    component: VirtualUserComponent

    @property
    def start_time_us(self) -> int:
        """Return the fixed scenario start at virtual time zero."""

        return 0

    @property
    def end_time_us(self) -> int:
        """Convert whole configuration seconds to exact integer microseconds."""

        return self.config.duration_seconds * 1_000_000

    def schedule(self, scheduler: EventScheduler) -> None:
        """Reset component state and recreate initial heartbeat/completion events."""

        if self.component.config != self.config:
            raise RuntimeError("scenario and component configurations differ")
        self.component.reset()
        self.component.schedule_initial(scheduler)
        scheduler.schedule_at(
            self.end_time_us,
            "simulation_complete",
            source=VIRTUAL_USER_SCENARIO_SOURCE,
            priority=VIRTUAL_USER_COMPLETION_PRIORITY,
            payload={"scenario": "stage_02_baseline_virtual_user"},
        )


@dataclass(frozen=True, slots=True)
class VirtualUserSimulation:
    """Fully wired engine/scenario/component bundle shared by GUI and headless paths."""

    engine: SimulationEngine
    scenario: VirtualUserScenario
    component: VirtualUserComponent
    config: VirtualUserConfig


def create_virtual_user_simulation(
    config: VirtualUserConfig | None = None,
) -> VirtualUserSimulation:
    """Create one loaded engine with exactly one virtual-user heartbeat handler."""

    selected_config = config or VirtualUserConfig()
    component = VirtualUserComponent(selected_config)
    scenario = VirtualUserScenario(selected_config, component)
    engine = SimulationEngine()
    engine.register_handler(HEARTBEAT_EVENT_TYPE, component.handle_heartbeat)
    engine.load_scenario(scenario)
    return VirtualUserSimulation(
        engine=engine,
        scenario=scenario,
        component=component,
        config=selected_config,
    )
