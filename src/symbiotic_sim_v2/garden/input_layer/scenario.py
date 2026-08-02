"""Stage 4 integration factory for VirtualUser, Polar H10, and Garden input."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from symbiotic_sim_v2.devices.polar_h10.component import PolarH10Component
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.domain.event_priorities import (
    GARDEN_EVALUATION_FINALIZE_TRIGGER_PRIORITY,
    GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
    GARDEN_PHASE_EVENT_PRIORITY,
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import GARDEN_INPUT_EVENT_SOURCE
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
    GARDEN_PHASE_CHANGED_EVENT_TYPE,
    HEARTBEAT_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.input_layer.component import (
    GARDEN_INPUT_SCENARIO_SOURCE,
    GardenInputComponent,
)
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.timing import (
    evaluation_windows,
    phase_at,
    phase_change_times_us,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.simulation.time_utils import seconds_to_us
from symbiotic_sim_v2.virtual_user.component import VirtualUserComponent
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig


class HeartbeatSourceComponent(Protocol):
    """Internal injection seam for a formal-heartbeat-only virtual user."""

    config: VirtualUserConfig

    def reset(self) -> None: ...

    def schedule_initial(self, scheduler: EventScheduler) -> SimulationEvent: ...

    def handle_heartbeat(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None: ...


HeartbeatSourceFactory = Callable[[VirtualUserConfig], HeartbeatSourceComponent]


@dataclass(slots=True)
class GardenInputScenario:
    """Reset and schedule exactly one deterministic 240-second Stage 4 session."""

    virtual_user_config: VirtualUserConfig
    polar_h10_config: PolarH10Config
    garden_input_config: GardenInputConfig
    virtual_user_component: HeartbeatSourceComponent
    polar_h10_component: PolarH10Component
    garden_input_component: GardenInputComponent

    @property
    def start_time_us(self) -> int:
        return 0

    @property
    def end_time_us(self) -> int:
        return seconds_to_us(self.garden_input_config.total_duration_seconds)

    def schedule(self, scheduler: EventScheduler) -> None:
        """Rebuild all component state and the fixed Stage 4 boundary schedule."""

        if self.virtual_user_component.config != self.virtual_user_config:
            raise RuntimeError("virtual-user scenario and component configurations differ")
        if self.polar_h10_component.config != self.polar_h10_config:
            raise RuntimeError("H10 scenario and component configurations differ")
        if self.garden_input_component.config != self.garden_input_config:
            raise RuntimeError("Garden scenario and component configurations differ")
        if (
            self.virtual_user_config.duration_seconds
            != self.garden_input_config.total_duration_seconds
        ):
            raise ValueError("virtual-user duration must equal the 240-second Garden session")
        if self.polar_h10_config.expected_user_id != self.virtual_user_config.user_id:
            raise ValueError("H10 expected_user_id must match virtual-user user_id")

        self.virtual_user_component.reset()
        self.polar_h10_component.reset()
        self.garden_input_component.reset()

        for phase_time_us in phase_change_times_us(self.garden_input_config):
            descriptor = phase_at(phase_time_us, self.garden_input_config)
            scheduler.schedule_at(
                phase_time_us,
                GARDEN_PHASE_CHANGED_EVENT_TYPE,
                source=GARDEN_INPUT_EVENT_SOURCE,
                priority=GARDEN_PHASE_EVENT_PRIORITY,
                payload={
                    "garden_id": self.garden_input_config.garden_id,
                    "session_id": self.garden_input_component.session_id,
                    "phase_time_us": phase_time_us,
                    "phase": descriptor.phase.value,
                    "bundle_index": descriptor.bundle_index,
                    "window_role": descriptor.window_role.value,
                    "schema_version": self.garden_input_config.phase_schema_version,
                },
            )

        for window in evaluation_windows(self.garden_input_config):
            scheduler.schedule_at(
                window.window_end_us,
                GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
                source=GARDEN_INPUT_SCENARIO_SOURCE,
                priority=GARDEN_EVALUATION_FINALIZE_TRIGGER_PRIORITY,
                payload={"evaluation_id": window.evaluation_id},
            )

        signal_count = self.end_time_us // self.garden_input_config.signal_interval_us + 1
        for signal_index in range(signal_count):
            scheduler.schedule_at(
                signal_index * self.garden_input_config.signal_interval_us,
                GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
                source=GARDEN_INPUT_SCENARIO_SOURCE,
                priority=GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
                payload={"signal_index": signal_index},
            )

        self.virtual_user_component.schedule_initial(scheduler)
        scheduler.schedule_at(
            self.end_time_us,
            SIMULATION_COMPLETE_EVENT_TYPE,
            source=GARDEN_INPUT_SCENARIO_SOURCE,
            priority=SIMULATION_COMPLETE_EVENT_PRIORITY,
            payload={"scenario": "stage_04_garden_input_layer"},
        )


@dataclass(frozen=True, slots=True)
class GardenInputSimulation:
    """Fully wired Stage 4 bundle shared by GUI and headless execution."""

    engine: SimulationEngine
    scenario: GardenInputScenario
    virtual_user_component: HeartbeatSourceComponent
    polar_h10_component: PolarH10Component
    garden_input_component: GardenInputComponent
    virtual_user_config: VirtualUserConfig
    polar_h10_config: PolarH10Config
    garden_input_config: GardenInputConfig

    @property
    def component(self) -> HeartbeatSourceComponent:
        """Stage 2-compatible alias used by the retained virtual-user panel."""

        return self.virtual_user_component

    @property
    def config(self) -> VirtualUserConfig:
        """Stage 2-compatible alias used by the retained virtual-user panel."""

        return self.virtual_user_config


def create_garden_input_simulation(
    virtual_user_config: VirtualUserConfig | None = None,
    polar_h10_config: PolarH10Config | None = None,
    garden_input_config: GardenInputConfig | None = None,
) -> GardenInputSimulation:
    """Create one engine with exactly one handler at each formal boundary."""

    return _create_garden_input_simulation(
        virtual_user_config=virtual_user_config,
        polar_h10_config=polar_h10_config,
        garden_input_config=garden_input_config,
        heartbeat_source_factory=VirtualUserComponent,
    )


def _create_garden_input_simulation(
    *,
    virtual_user_config: VirtualUserConfig | None = None,
    polar_h10_config: PolarH10Config | None = None,
    garden_input_config: GardenInputConfig | None = None,
    heartbeat_source_factory: HeartbeatSourceFactory,
) -> GardenInputSimulation:
    """Build Stage 4 with an injected formal-heartbeat source.

    The public Stage 4 factory always supplies :class:`VirtualUserComponent`.
    Later stages may use this private seam to replace only that component while
    preserving every formal handler and scheduled boundary.
    """

    if not callable(heartbeat_source_factory):
        raise TypeError("heartbeat_source_factory must be callable")

    selected_garden_config = garden_input_config or GardenInputConfig()
    selected_user_config = virtual_user_config or replace(
        VirtualUserConfig(),
        duration_seconds=selected_garden_config.total_duration_seconds,
    )
    if selected_user_config.duration_seconds != selected_garden_config.total_duration_seconds:
        raise ValueError("Stage 4 virtual-user duration must be 240 seconds")
    selected_h10_config = polar_h10_config or PolarH10Config(
        expected_user_id=selected_user_config.user_id
    )
    if selected_h10_config.expected_user_id != selected_user_config.user_id:
        raise ValueError("H10 expected_user_id must match virtual-user user_id")

    virtual_user = heartbeat_source_factory(selected_user_config)
    if getattr(virtual_user, "config", None) != selected_user_config:
        raise ValueError("injected heartbeat source config differs from selected config")
    for method_name in ("reset", "schedule_initial", "handle_heartbeat"):
        if not callable(getattr(virtual_user, method_name, None)):
            raise TypeError(f"injected heartbeat source must provide {method_name}()")
    polar_h10 = PolarH10Component(selected_h10_config)
    garden_input = GardenInputComponent(selected_garden_config)
    scenario = GardenInputScenario(
        virtual_user_config=selected_user_config,
        polar_h10_config=selected_h10_config,
        garden_input_config=selected_garden_config,
        virtual_user_component=virtual_user,
        polar_h10_component=polar_h10,
        garden_input_component=garden_input,
    )
    engine = SimulationEngine()
    engine.register_handler(HEARTBEAT_EVENT_TYPE, virtual_user.handle_heartbeat)
    engine.register_handler(HEARTBEAT_EVENT_TYPE, polar_h10.handle_heartbeat)
    engine.register_handler(RRI_MEASUREMENT_EVENT_TYPE, garden_input.handle_rri_measurement)
    engine.register_handler(GARDEN_PHASE_CHANGED_EVENT_TYPE, garden_input.handle_phase_change)
    engine.register_handler(
        GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
        garden_input.handle_evaluation_finalize_trigger,
    )
    engine.register_handler(
        GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
        garden_input.handle_signal_trigger,
    )
    engine.register_handler(
        SIMULATION_COMPLETE_EVENT_TYPE,
        polar_h10.handle_simulation_complete,
    )
    engine.register_handler(
        SIMULATION_COMPLETE_EVENT_TYPE,
        garden_input.handle_simulation_complete,
    )
    engine.load_scenario(scenario)
    return GardenInputSimulation(
        engine=engine,
        scenario=scenario,
        virtual_user_component=virtual_user,
        polar_h10_component=polar_h10,
        garden_input_component=garden_input,
        virtual_user_config=selected_user_config,
        polar_h10_config=selected_h10_config,
        garden_input_config=selected_garden_config,
    )
