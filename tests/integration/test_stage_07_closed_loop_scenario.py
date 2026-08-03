"""Stage 7 injected closed-loop assembly, causality, and control checks."""

from __future__ import annotations

import inspect
from bisect import bisect_right

import pytest

from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.event_types import HEARTBEAT_EVENT_TYPE
from symbiotic_sim_v2.garden.input_layer.scenario import (
    _create_garden_input_simulation,
    create_garden_input_simulation,
)
from symbiotic_sim_v2.runtime.closed_loop import (
    LightResponsiveClosedLoopSimulation,
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.closed_loop.light_responsive_scenario import (
    _create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.light_simulation import (
    LightFeedbackSimulation,
    create_light_feedback_simulation,
)
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    _create_light_feedback_simulation,
)
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    _create_three_digital_life_competition_simulation,
    create_three_digital_life_competition_simulation,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.virtual_user.component import VirtualUserComponent
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.component import (
    LightResponsiveVirtualUserComponent,
)
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.presets import (
    light_insensitive_control,
)


@pytest.fixture(scope="module")
def responsive_simulation() -> LightResponsiveClosedLoopSimulation:
    simulation = create_light_responsive_closed_loop_simulation()
    simulation.engine.run_until_end()
    return simulation


@pytest.fixture(scope="module")
def control_pair() -> tuple[
    LightResponsiveClosedLoopSimulation,
    LightFeedbackSimulation,
]:
    control = create_light_responsive_closed_loop_simulation(
        light_response_config=light_insensitive_control()
    )
    stage6 = create_light_feedback_simulation()
    control.engine.run_until_end()
    stage6.engine.run_until_end()
    return control, stage6


def heartbeat_times(
    simulation: LightResponsiveClosedLoopSimulation | LightFeedbackSimulation,
) -> tuple[int, ...]:
    engine = simulation.engine
    return tuple(
        event.scheduled_time_us
        for event in engine.executed_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )


def test_private_injection_seam_preserves_every_existing_public_signature() -> None:
    pairs = (
        (create_garden_input_simulation, _create_garden_input_simulation),
        (
            create_three_digital_life_competition_simulation,
            _create_three_digital_life_competition_simulation,
        ),
        (create_light_feedback_simulation, _create_light_feedback_simulation),
    )
    for public_factory, internal_builder in pairs:
        assert "heartbeat_source_factory" not in inspect.signature(public_factory).parameters
        assert "heartbeat_source_factory" in inspect.signature(internal_builder).parameters
        assert (
            "digital_life_component_factory"
            not in inspect.signature(public_factory).parameters
        )
        assert (
            "initial_persistent_states_by_life_id"
            not in inspect.signature(public_factory).parameters
        )

    for internal_builder in (
        _create_three_digital_life_competition_simulation,
        _create_light_feedback_simulation,
        _create_light_responsive_closed_loop_simulation,
    ):
        parameters = inspect.signature(internal_builder).parameters
        assert "digital_life_component_factory" in parameters
        assert "initial_persistent_states_by_life_id" in parameters

    stage7_public_parameters = inspect.signature(
        create_light_responsive_closed_loop_simulation
    ).parameters
    assert "digital_life_component_factory" not in stage7_public_parameters
    assert "initial_persistent_states_by_life_id" not in stage7_public_parameters

    stage7_public_source = inspect.getsource(
        create_light_responsive_closed_loop_simulation
    )
    assert "_create_light_responsive_closed_loop_simulation" in stage7_public_source
    stage7_source = inspect.getsource(_create_light_responsive_closed_loop_simulation)
    assert "_create_light_feedback_simulation" in stage7_source
    assert "SimulationEngine(" not in stage7_source
    assert "GardenInputComponent(" not in stage7_source
    assert "ConnectedDigitalLifeComponent(" not in stage7_source
    assert "GardenOutputComponent(" not in stage7_source
    assert "GardenLightMapperComponent(" not in stage7_source
    assert "VirtualLightDeviceComponent(" not in stage7_source


def test_factory_injects_one_responsive_user_through_the_existing_assembly() -> None:
    simulation = create_light_responsive_closed_loop_simulation()
    component = simulation.light_responsive_virtual_user_component
    stage6 = simulation.upstream_simulation
    stage5b = stage6.upstream_simulation
    garden_scenario = stage5b.scenario.upstream_scenario

    assert isinstance(component, LightResponsiveVirtualUserComponent)
    assert simulation.component is simulation.virtual_user_component is component
    assert stage5b.virtual_user_component is component
    assert garden_scenario.virtual_user_component is component
    assert simulation.scenario.upstream_scenario is stage6.scenario
    assert simulation.engine is stage6.engine
    assert simulation.config is stage5b.virtual_user_config

    unchanged_stage6 = create_light_feedback_simulation()
    assert isinstance(
        unchanged_stage6.upstream_simulation.virtual_user_component,
        VirtualUserComponent,
    )


def test_standard_run_closes_the_physical_feedback_loop_only_via_formal_state(
    responsive_simulation: LightResponsiveClosedLoopSimulation,
) -> None:
    simulation = responsive_simulation
    component = simulation.component
    states = simulation.device.stimulus_state_records()
    receipts = component.light_receipt_records()

    assert len(states) == len(receipts) == 241
    assert tuple(record.event_time_us for record in receipts) == tuple(
        record.effective_time_us for record in states
    )
    assert all(not record.provenance_used_by_physiology for record in receipts)
    first_active = next(record for record in receipts if record.active)
    assert first_active.event_time_us == 60_551_540
    assert first_active.qualification_holder_id == "life-green"
    assert first_active.preference_match == pytest.approx(1.0)
    assert first_active.response_target == pytest.approx(1.0)
    assert first_active.response_before == pytest.approx(0.0)
    assert first_active.response_after_at_same_time == pytest.approx(0.0)

    light_events = tuple(
        event
        for event in simulation.engine.executed_events()
        if event.event_type == LIGHT_STIMULUS_STATE_EVENT_TYPE
    )
    assert len(light_events) == len(receipts)
    assert all(event.priority == 67 for event in light_events)


def test_first_post_light_heartbeat_was_already_scheduled_and_is_unchanged(
    responsive_simulation: LightResponsiveClosedLoopSimulation,
    control_pair: tuple[LightResponsiveClosedLoopSimulation, LightFeedbackSimulation],
) -> None:
    responsive_times = heartbeat_times(responsive_simulation)
    control_times = heartbeat_times(control_pair[0])
    first_light_time_us = 60_551_540
    first_post_light_index = bisect_right(responsive_times, first_light_time_us)

    assert responsive_times[: first_post_light_index + 1] == (
        control_times[: first_post_light_index + 1]
    )
    assert responsive_times[first_post_light_index + 1] != (
        control_times[first_post_light_index + 1]
    )


def test_exact_same_time_heartbeat_precedes_light_and_keeps_the_pending_interval(
    responsive_simulation: LightResponsiveClosedLoopSimulation,
) -> None:
    source_event = next(
        event
        for event in responsive_simulation.engine.executed_events()
        if event.event_type == LIGHT_STIMULUS_STATE_EVENT_TYPE
        and event.payload["active"] is True
    )
    light_payload = dict(source_event.payload)
    light_payload["source_signal_index"] = 0
    light_payload["source_signal_time_us"] = 0
    light_payload["effective_time_us"] = 0
    component = LightResponsiveVirtualUserComponent(
        VirtualUserConfig(duration_seconds=240),
        LightResponseConfig(),
    )

    class SameTimeScenario:
        start_time_us = 0
        end_time_us = 3_000_000

        def schedule(self, scheduler) -> None:
            component.reset()
            component.schedule_initial(scheduler)
            scheduler.schedule_at(
                0,
                LIGHT_STIMULUS_STATE_EVENT_TYPE,
                source=source_event.source,
                priority=source_event.priority,
                payload=light_payload,
            )

    engine = SimulationEngine(SameTimeScenario())
    engine.register_handler(HEARTBEAT_EVENT_TYPE, component.handle_heartbeat)
    engine.register_handler(
        LIGHT_STIMULUS_STATE_EVENT_TYPE,
        component.handle_light_stimulus_state,
    )

    first = engine.step_one_event()
    assert first is not None and first.event_type == HEARTBEAT_EVENT_TYPE
    pending_before_light = next(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    second = engine.step_one_event()
    assert second is not None and second.event_type == LIGHT_STIMULUS_STATE_EVENT_TYPE
    pending_after_light = next(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    assert pending_after_light == pending_before_light

    third = engine.step_one_event()
    assert third is not None and third.event_type == HEARTBEAT_EVENT_TYPE
    assert [event.event_type for event in engine.executed_events()[:3]] == [
        HEARTBEAT_EVENT_TYPE,
        LIGHT_STIMULUS_STATE_EVENT_TYPE,
        HEARTBEAT_EVENT_TYPE,
    ]
    first_record, arriving_record = component.responsive_heartbeat_records()[:2]
    assert not first_record.light_active_at_heartbeat
    assert first_record.response_level == 0.0
    assert not arriving_record.light_active_at_heartbeat
    assert arriving_record.response_level == 0.0
    receipt = component.light_receipt_records()[0]
    assert receipt.active
    assert receipt.response_before == receipt.response_after_at_same_time == 0.0


def test_standard_response_checkpoints_and_effective_physiology(
    responsive_simulation: LightResponsiveClosedLoopSimulation,
) -> None:
    component = responsive_simulation.component
    assert [
        component.response_at(time_us)
        for time_us in (90_000_000, 120_000_000, 180_000_000, 239_999_999)
    ] == pytest.approx(
        [
            0.974803684362126,
            0.9994074394523207,
            0.9999996722640228,
            0.9999999998187343,
        ]
    )
    closing = component.snapshot()
    assert not closing.current_light_active
    assert closing.current_response_target == 0.0
    assert closing.current_response_level == pytest.approx(0.9999999998187343)
    assert closing.effective_respiratory_amplitude_ms == pytest.approx(65.0)
    assert closing.effective_mean_rri_ms == pytest.approx(872.1428571428571)


def test_insensitive_control_is_the_exact_stage6_formal_stream(
    control_pair: tuple[LightResponsiveClosedLoopSimulation, LightFeedbackSimulation],
) -> None:
    control, stage6 = control_pair

    assert heartbeat_times(control) == heartbeat_times(stage6)
    assert control.component.heartbeat_digest() == (
        stage6.upstream_simulation.virtual_user_component.heartbeat_digest()
    )
    assert control.polar_h10_component.measurement_digest() == (
        stage6.upstream_simulation.polar_h10_component.measurement_digest()
    )
    assert control.garden_input_component.evaluation_digest() == (
        stage6.upstream_simulation.garden_input_component.evaluation_digest()
    )
    assert control.mapper.command_digest() == stage6.mapper.command_digest()
    assert control.device.stimulus_state_digest() == stage6.device.stimulus_state_digest()
    assert control.engine.deterministic_digest() == stage6.engine.deterministic_digest()


def test_response_changes_only_post_light_bundle_evaluations(
    responsive_simulation: LightResponsiveClosedLoopSimulation,
    control_pair: tuple[LightResponsiveClosedLoopSimulation, LightFeedbackSimulation],
) -> None:
    responsive = responsive_simulation.garden_input_component.evaluation_records()
    control = control_pair[0].garden_input_component.evaluation_records()

    assert responsive[0].evaluation_kind == control[0].evaluation_kind == "baseline"
    assert responsive[0].rmssd_ms == control[0].rmssd_ms
    assert responsive[0].n == control[0].n
    for responsive_record, control_record in zip(
        responsive[1:], control[1:], strict=True
    ):
        assert responsive_record.evaluation_kind == "bundle"
        assert responsive_record.rmssd_ms is not None
        assert control_record.rmssd_ms is not None
        assert responsive_record.n is not None
        assert control_record.n is not None
        assert responsive_record.rmssd_ms > control_record.rmssd_ms
        assert responsive_record.n > control_record.n


def test_response_completion_samples_and_reset_are_deterministic(
    responsive_simulation: LightResponsiveClosedLoopSimulation,
) -> None:
    simulation = responsive_simulation
    component = simulation.component
    first_digests = (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_sample_digest(),
        simulation.engine.deterministic_digest(),
    )
    samples = component.response_samples()
    segments = component.response_segments()

    assert len(samples) == 2_401
    assert samples[0].time_us == 0
    assert samples[-1].time_us == 240_000_000
    assert segments[0].start_time_us == 0
    assert segments[-1].end_time_us == 240_000_000
    assert component.snapshot().completed
    assert "light_response_sample" not in {
        event.event_type for event in simulation.engine.executed_events()
    }

    simulation.engine.reset()
    assert component.heartbeat_records() == ()
    assert component.light_receipt_records() == ()
    assert component.response_segments() == ()
    simulation.engine.run_until_end()
    assert (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_sample_digest(),
        simulation.engine.deterministic_digest(),
    ) == first_digests
