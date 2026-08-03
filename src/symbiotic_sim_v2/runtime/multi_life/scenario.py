"""Stage 5B factory over the unchanged Stage 4 formal signal pipeline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from symbiotic_sim_v2.devices.polar_h10.component import PolarH10Component
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.digital_life.config import (
    DigitalLifeConfig,
    digital_life_config_for_role,
)
from symbiotic_sim_v2.digital_life.connected_component import (
    ConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.garden.input_layer.component import GardenInputComponent
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.scenario import (
    GardenInputScenario,
    HeartbeatSourceComponent,
    HeartbeatSourceFactory,
    _create_garden_input_simulation,
)
from symbiotic_sim_v2.garden.output_layer.component import GardenOutputComponent
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.garden.output_layer.events import (
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
    GARDEN_HOLDER_RELEASE_EVENT_TYPE,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
)
from symbiotic_sim_v2.runtime.multi_life.config import MultiLifeRuntimeConfig
from symbiotic_sim_v2.runtime.multi_life.coordinator import (
    MultiLifeRuntimeCoordinator,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.virtual_user.component import VirtualUserComponent
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig


class DigitalLifeComponentFactory(Protocol):
    """Private construction seam for one roster-owned connected component."""

    def __call__(
        self,
        config: DigitalLifeConfig,
        initial_persistent_state: object | None,
        /,
    ) -> ConnectedDigitalLifeComponent: ...


def _create_legacy_connected_life(
    config: DigitalLifeConfig,
    initial_persistent_state: object | None,
) -> ConnectedDigitalLifeComponent:
    """Keep every public Stage 5B-7.1 factory on the original component."""

    if initial_persistent_state is not None:
        raise ValueError(
            "initial persistent state requires an injected Digital Life component factory"
        )
    return ConnectedDigitalLifeComponent(config)


@dataclass(slots=True)
class ThreeDigitalLifeCompetitionScenario:
    """Reset Stage 5B state and delegate the unchanged upstream event schedule."""

    upstream_scenario: GardenInputScenario
    digital_life_configs: tuple[DigitalLifeConfig, DigitalLifeConfig, DigitalLifeConfig]
    digital_life_components: Mapping[str, ConnectedDigitalLifeComponent]
    runtime_config: MultiLifeRuntimeConfig
    runtime_coordinator: MultiLifeRuntimeCoordinator
    garden_output_config: GardenOutputConfig
    garden_output_component: GardenOutputComponent

    @property
    def start_time_us(self) -> int:
        return self.upstream_scenario.start_time_us

    @property
    def end_time_us(self) -> int:
        return self.upstream_scenario.end_time_us

    def schedule(self, scheduler: EventScheduler) -> None:
        """Reset each component exactly once and rebuild the Stage 4 base schedule."""

        configs_by_id = {config.digital_life_id: config for config in self.digital_life_configs}
        if set(configs_by_id) != set(self.runtime_config.expected_digital_life_ids):
            raise RuntimeError("scenario Digital Life configs differ from runtime config")
        if set(self.digital_life_components) != set(configs_by_id):
            raise RuntimeError("scenario Digital Life components differ from configs")
        for life_id in self.runtime_config.expected_digital_life_ids:
            component = self.digital_life_components[life_id]
            if component.config != configs_by_id[life_id]:
                raise RuntimeError("scenario and component Digital Life configs differ")
            component.reset()
        if self.garden_output_component.config != self.garden_output_config:
            raise RuntimeError("scenario and Garden output configs differ")
        self.garden_output_component.reset()
        self.runtime_coordinator.reset()
        self.upstream_scenario.schedule(scheduler)


@dataclass(frozen=True, slots=True)
class ThreeDigitalLifeCompetitionSimulation:
    """Complete Stage 5B bundle shared by headless and GUI execution."""

    engine: SimulationEngine
    scenario: ThreeDigitalLifeCompetitionScenario
    virtual_user_component: HeartbeatSourceComponent
    polar_h10_component: PolarH10Component
    garden_input_component: GardenInputComponent
    digital_life_components: Mapping[str, ConnectedDigitalLifeComponent]
    runtime_coordinator: MultiLifeRuntimeCoordinator
    garden_output_component: GardenOutputComponent
    virtual_user_config: VirtualUserConfig
    polar_h10_config: PolarH10Config
    garden_input_config: GardenInputConfig
    digital_life_configs: tuple[DigitalLifeConfig, DigitalLifeConfig, DigitalLifeConfig]
    runtime_config: MultiLifeRuntimeConfig
    garden_output_config: GardenOutputConfig

    @property
    def component(self) -> HeartbeatSourceComponent:
        """Stage 2-compatible alias retained by the upstream GUI panel."""

        return self.virtual_user_component

    @property
    def config(self) -> VirtualUserConfig:
        """Stage 2-compatible alias retained by the upstream GUI panel."""

        return self.virtual_user_config

    @property
    def life_components(self) -> Mapping[str, ConnectedDigitalLifeComponent]:
        """Concise read-only alias for Stage 5B callers."""

        return self.digital_life_components

    @property
    def coordinator(self) -> MultiLifeRuntimeCoordinator:
        return self.runtime_coordinator

    @property
    def garden_output(self) -> GardenOutputComponent:
        return self.garden_output_component

    @property
    def red_life_component(self) -> ConnectedDigitalLifeComponent:
        return self.digital_life_components["life-red"]

    @property
    def green_life_component(self) -> ConnectedDigitalLifeComponent:
        return self.digital_life_components["life-green"]

    @property
    def blue_life_component(self) -> ConnectedDigitalLifeComponent:
        return self.digital_life_components["life-blue"]


def create_three_digital_life_competition_simulation(
    *,
    virtual_user_config: VirtualUserConfig | None = None,
    polar_h10_config: PolarH10Config | None = None,
    garden_input_config: GardenInputConfig | None = None,
    digital_life_configs: Sequence[DigitalLifeConfig] | None = None,
    runtime_config: MultiLifeRuntimeConfig | None = None,
    garden_output_config: GardenOutputConfig | None = None,
) -> ThreeDigitalLifeCompetitionSimulation:
    """Wire three independent first/second rounds without central tau comparison."""

    return _create_three_digital_life_competition_simulation(
        virtual_user_config=virtual_user_config,
        polar_h10_config=polar_h10_config,
        garden_input_config=garden_input_config,
        digital_life_configs=digital_life_configs,
        runtime_config=runtime_config,
        garden_output_config=garden_output_config,
        heartbeat_source_factory=VirtualUserComponent,
    )


def _create_three_digital_life_competition_simulation(
    *,
    virtual_user_config: VirtualUserConfig | None = None,
    polar_h10_config: PolarH10Config | None = None,
    garden_input_config: GardenInputConfig | None = None,
    digital_life_configs: Sequence[DigitalLifeConfig] | None = None,
    runtime_config: MultiLifeRuntimeConfig | None = None,
    garden_output_config: GardenOutputConfig | None = None,
    heartbeat_source_factory: HeartbeatSourceFactory,
    digital_life_component_factory: DigitalLifeComponentFactory = (
        _create_legacy_connected_life
    ),
    initial_persistent_states_by_life_id: Mapping[str, object] | None = None,
) -> ThreeDigitalLifeCompetitionSimulation:
    """Build Stage 5B over private heartbeat and Digital Life injection seams."""

    supplied_configs = (
        tuple(digital_life_configs)
        if digital_life_configs is not None
        else tuple(digital_life_config_for_role(role) for role in ("red", "green", "blue"))
    )
    if len(supplied_configs) != 3:
        raise ValueError("Stage 5B requires exactly three Digital Life configs")
    if any(not isinstance(config, DigitalLifeConfig) for config in supplied_configs):
        raise TypeError("digital_life_configs must contain only DigitalLifeConfig values")
    configs_by_id = {config.digital_life_id: config for config in supplied_configs}
    if len(configs_by_id) != 3:
        raise ValueError("Digital Life config IDs must be unique")
    selected_runtime_config = runtime_config or MultiLifeRuntimeConfig(
        expected_digital_life_ids=tuple(configs_by_id)
    )
    if set(configs_by_id) != set(selected_runtime_config.expected_digital_life_ids):
        raise ValueError("Digital Life config IDs must match the runtime roster")
    selected_garden_output_config = garden_output_config or GardenOutputConfig(
        expected_digital_life_ids=(
            selected_runtime_config.expected_digital_life_ids
        )
    )
    if (
        selected_garden_output_config.expected_digital_life_ids
        != selected_runtime_config.expected_digital_life_ids
    ):
        raise ValueError("Garden output and runtime expected Digital Life IDs differ")
    if (
        selected_garden_output_config.round_finalize_offset_us
        != selected_runtime_config.round_finalize_offset_us
    ):
        raise ValueError("Garden output and runtime finalize offsets differ")
    selected_life_configs = tuple(
        configs_by_id[life_id] for life_id in selected_runtime_config.expected_digital_life_ids
    )
    if not callable(digital_life_component_factory):
        raise TypeError("digital_life_component_factory must be callable")
    if initial_persistent_states_by_life_id is None:
        initial_states_by_id = {
            life_id: None for life_id in selected_runtime_config.expected_digital_life_ids
        }
    else:
        if not isinstance(initial_persistent_states_by_life_id, Mapping):
            raise TypeError("initial_persistent_states_by_life_id must be a mapping")
        initial_states_by_id = dict(initial_persistent_states_by_life_id)
        if set(initial_states_by_id) != set(
            selected_runtime_config.expected_digital_life_ids
        ):
            raise ValueError(
                "initial persistent state IDs must match the runtime roster"
            )

    upstream = _create_garden_input_simulation(
        virtual_user_config=virtual_user_config,
        polar_h10_config=polar_h10_config,
        garden_input_config=garden_input_config,
        heartbeat_source_factory=heartbeat_source_factory,
    )
    life_components = {
        config.digital_life_id: digital_life_component_factory(
            config,
            initial_states_by_id[config.digital_life_id],
        )
        for config in selected_life_configs
    }
    immutable_life_components = MappingProxyType(life_components)
    garden_output = GardenOutputComponent(selected_garden_output_config)
    coordinator = MultiLifeRuntimeCoordinator(
        selected_runtime_config,
        immutable_life_components,
        garden_output,
    )
    scenario = ThreeDigitalLifeCompetitionScenario(
        upstream_scenario=upstream.scenario,
        digital_life_configs=selected_life_configs,
        digital_life_components=immutable_life_components,
        runtime_config=selected_runtime_config,
        runtime_coordinator=coordinator,
        garden_output_config=selected_garden_output_config,
        garden_output_component=garden_output,
    )

    engine = upstream.engine
    engine.register_handler(
        GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
        coordinator.handle_evaluation_finalized,
    )
    engine.register_handler(
        GARDEN_INPUT_SIGNAL_EVENT_TYPE,
        coordinator.handle_garden_input_signal,
    )
    engine.register_handler(DIGITAL_LIFE_TOUCH_EVENT_TYPE, garden_output.handle_touch)
    engine.register_handler(
        GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
        coordinator.handle_round_finalize,
    )
    engine.register_handler(
        GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
        coordinator.handle_round_finalize,
    )
    engine.register_handler(
        GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
        coordinator.handle_interoceptive_feedback,
    )
    engine.register_handler(
        GARDEN_HOLDER_RELEASE_EVENT_TYPE,
        coordinator.handle_holder_release,
    )
    engine.register_handler(
        SIMULATION_COMPLETE_EVENT_TYPE,
        coordinator.handle_simulation_complete,
    )
    engine.load_scenario(scenario)

    return ThreeDigitalLifeCompetitionSimulation(
        engine=engine,
        scenario=scenario,
        virtual_user_component=upstream.virtual_user_component,
        polar_h10_component=upstream.polar_h10_component,
        garden_input_component=upstream.garden_input_component,
        digital_life_components=immutable_life_components,
        runtime_coordinator=coordinator,
        garden_output_component=garden_output,
        virtual_user_config=upstream.virtual_user_config,
        polar_h10_config=upstream.polar_h10_config,
        garden_input_config=upstream.garden_input_config,
        digital_life_configs=selected_life_configs,
        runtime_config=selected_runtime_config,
        garden_output_config=selected_garden_output_config,
    )
