"""Open-loop physiology sessions composed from existing Stage 3/4/6/7 parts."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.devices.virtual_light.component import VirtualLightDeviceComponent
from symbiotic_sim_v2.devices.virtual_light.config import VirtualLightDeviceConfig
from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.event_types import SIMULATION_COMPLETE_EVENT_TYPE
from symbiotic_sim_v2.garden.input_layer.scenario import (
    GardenInputSimulation,
    _create_garden_input_simulation,
)
from symbiotic_sim_v2.garden.light_mapper.component import GardenLightMapperComponent
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.events import LIGHT_COMMAND_EVENT_TYPE
from symbiotic_sim_v2.garden.output_layer.config import (
    GARDEN_QUALIFIED_B_SCHEMA_VERSION,
    QUALIFIED_B_EMISSION_POLICY_VERSION,
)
from symbiotic_sim_v2.garden.output_layer.events import (
    GARDEN_OUTPUT_EVENT_SOURCE,
    GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.component import (
    LightResponsiveVirtualUserComponent,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    StationaryUserTypeProfileV2,
    stationary_light_response_config_v2,
)

from .output_policy import RandomBundleOutput
from .records import ReplayLightState

SESSION_END_US = 240_000_000
RANDOM_ACTIVE_OFFSET_US = 500_000


@dataclass(frozen=True, slots=True)
class OpenLoopSessionSimulation:
    garden_simulation: GardenInputSimulation
    responsive_user: LightResponsiveVirtualUserComponent
    mapper: GardenLightMapperComponent | None
    device: VirtualLightDeviceComponent | None

    @property
    def engine(self):
        return self.garden_simulation.engine

    @property
    def garden_input_component(self):
        return self.garden_simulation.garden_input_component


def _base_open_loop(
    *,
    physiology_root_seed: int,
    profile: StationaryUserTypeProfileV2,
) -> tuple[GardenInputSimulation, LightResponsiveVirtualUserComponent]:
    light_config = stationary_light_response_config_v2(profile)

    def responsive_factory(config: VirtualUserConfig) -> LightResponsiveVirtualUserComponent:
        return LightResponsiveVirtualUserComponent(config, light_config)

    garden = _create_garden_input_simulation(
        virtual_user_config=VirtualUserConfig(
            duration_seconds=SESSION_END_US // 1_000_000,
            root_seed=physiology_root_seed,
        ),
        heartbeat_source_factory=responsive_factory,
    )
    user = garden.virtual_user_component
    if not isinstance(user, LightResponsiveVirtualUserComponent):
        raise RuntimeError("open-loop heartbeat-source injection produced the wrong component")
    garden.engine.register_handler(
        LIGHT_STIMULUS_STATE_EVENT_TYPE,
        user.handle_light_stimulus_state,
    )
    garden.engine.register_handler(
        SIMULATION_COMPLETE_EVENT_TYPE,
        user.handle_simulation_complete,
    )
    return garden, user


def create_yoked_replay_session(
    *,
    physiology_root_seed: int,
    profile: StationaryUserTypeProfileV2,
    replay_states: tuple[ReplayLightState, ...],
) -> OpenLoopSessionSimulation:
    garden, user = _base_open_loop(
        physiology_root_seed=physiology_root_seed,
        profile=profile,
    )
    if not replay_states:
        raise ValueError("yoked replay requires a non-empty donor state sequence")
    previous_time = -1
    for state in replay_states:
        if state.scheduled_time_us <= previous_time:
            raise ValueError("replay light states must have strictly increasing times")
        garden.engine.schedule_at(
            state.scheduled_time_us,
            LIGHT_STIMULUS_STATE_EVENT_TYPE,
            source=LIGHT_STIMULUS_STATE_EVENT_SOURCE,
            priority=LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
            payload=dict(state.payload),
        )
        previous_time = state.scheduled_time_us
    return OpenLoopSessionSimulation(garden, user, None, None)


def _qualified_payload(
    *,
    signal_index: int,
    signal_time_us: int,
    effective_time_us: int,
    active: bool,
    holder_id: str | None,
    b: tuple[float, float, float, float] | None,
) -> dict[str, object]:
    return {
        "garden_id": "relax-with-light",
        "signal_index": signal_index,
        "signal_time_us": signal_time_us,
        "effective_time_us": effective_time_us,
        "s": int(active),
        "active": active,
        "qualification_holder_id": holder_id,
        "b_f": None if b is None else b[0],
        "b_a": None if b is None else b[1],
        "b_t": None if b is None else b[2],
        "b_d": None if b is None else b[3],
        "emission_policy_version": QUALIFIED_B_EMISSION_POLICY_VERSION,
        "schema_version": GARDEN_QUALIFIED_B_SCHEMA_VERSION,
    }


def create_random_open_loop_session(
    *,
    physiology_root_seed: int,
    profile: StationaryUserTypeProfileV2,
    outputs: tuple[RandomBundleOutput, RandomBundleOutput, RandomBundleOutput],
) -> OpenLoopSessionSimulation:
    garden, user = _base_open_loop(
        physiology_root_seed=physiology_root_seed,
        profile=profile,
    )
    if tuple(item.bundle_index for item in outputs) != (0, 1, 2):
        raise ValueError("random output sequence must contain Bundle 0/1/2")
    if len({item.displayed_life_id for item in outputs}) != 1:
        raise ValueError("random holder must remain fixed for all three Bundles")
    mapper = GardenLightMapperComponent(GardenLightMapperConfig())
    device = VirtualLightDeviceComponent(VirtualLightDeviceConfig())
    engine = garden.engine
    engine.register_handler(
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        mapper.handle_garden_qualified_b,
    )
    engine.register_handler(LIGHT_COMMAND_EVENT_TYPE, device.handle_light_command)
    engine.register_handler(SIMULATION_COMPLETE_EVENT_TYPE, device.handle_simulation_complete)
    for signal_index in range(241):
        signal_time_us = signal_index * 1_000_000
        active = 60 <= signal_index < 240
        if active:
            selected = outputs[(signal_index - 60) // 60]
            holder_id = selected.displayed_life_id
            b = selected.b
            effective_time_us = signal_time_us + RANDOM_ACTIVE_OFFSET_US
        else:
            holder_id = None
            b = None
            effective_time_us = signal_time_us
        engine.schedule_at(
            effective_time_us,
            GARDEN_QUALIFIED_B_EVENT_TYPE,
            source=GARDEN_OUTPUT_EVENT_SOURCE,
            priority=GARDEN_QUALIFIED_B_EVENT_PRIORITY,
            payload=_qualified_payload(
                signal_index=signal_index,
                signal_time_us=signal_time_us,
                effective_time_us=effective_time_us,
                active=active,
                holder_id=holder_id,
                b=b,
            ),
        )
    return OpenLoopSessionSimulation(garden, user, mapper, device)


__all__ = [
    "OpenLoopSessionSimulation",
    "create_random_open_loop_session",
    "create_yoked_replay_session",
]
