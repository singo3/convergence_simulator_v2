"""Component-level continuity, causality, record, digest, and CSV tests."""

from __future__ import annotations

import csv
from dataclasses import dataclass

import pytest

from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.event_priorities import SIMULATION_COMPLETE_EVENT_PRIORITY
from symbiotic_sim_v2.domain.event_types import (
    HEARTBEAT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.light_mapper.config import (
    COMMAND_HOLD_POLICY_VERSION,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_MAPPING_VERSION,
    PHASE_POLICY_VERSION,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.component import (
    LightResponsiveVirtualUserComponent,
)
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.diagnostics import (
    LIGHT_RESPONSE_SAMPLES_CSV_FIELDS,
    LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS,
    LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS,
    LIGHT_STIMULUS_RECEIPTS_CSV_FIELDS,
    export_light_response_diagnostics,
)

END_TIME_US = 240_000_000


def light_event(
    time_us: int,
    source_signal_index: int,
    *,
    active: bool,
) -> SimulationEvent:
    payload = {
        "device_id": "virtual-pc-light-001",
        "source_signal_index": source_signal_index,
        "source_signal_time_us": time_us,
        "effective_time_us": time_us,
        "active": active,
        "qualification_holder_id": "life-green" if active else None,
        "source_b_f": 125 / 360 if active else None,
        "source_b_a": 0.5 if active else None,
        "source_b_t": 0.5 if active else None,
        "source_b_d": 0.5 if active else None,
        "hue_degree": 125.0 if active else None,
        "render_hue_degree": 125.0 if active else None,
        "saturation": 1.0 if active else 0.0,
        "value_center": 0.425 if active else 0.0,
        "value_amplitude": 0.075 if active else 0.0,
        "value_min": 0.35 if active else 0.0,
        "value_max": 0.5 if active else 0.0,
        "blink_bpm": 87.5 if active else None,
        "waveform": "sine" if active else "off",
        "phase_cycles_at_start": 0.0 if active else None,
        "value_at_start": 0.425 if active else 0.0,
        "phase_reset": active,
        "physical_parameters_changed": True,
        "command_equivalent_to_previous": False,
        "mapping_version": LIGHT_MAPPING_VERSION,
        "phase_policy_version": PHASE_POLICY_VERSION,
        "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
        "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
        "schema_version": "light_stimulus_state_event_v1",
    }
    return SimulationEvent(
        event_id=f"light-{source_signal_index}",
        event_type=LIGHT_STIMULUS_STATE_EVENT_TYPE,
        source=LIGHT_STIMULUS_STATE_EVENT_SOURCE,
        scheduled_time_us=time_us,
        priority=LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
        sequence=source_signal_index,
        payload=payload,
    )


def completion_event() -> SimulationEvent:
    return SimulationEvent(
        event_id="complete",
        event_type=SIMULATION_COMPLETE_EVENT_TYPE,
        source="test-scenario",
        scheduled_time_us=END_TIME_US,
        priority=SIMULATION_COMPLETE_EVENT_PRIORITY,
        sequence=10_000,
        payload={"scenario": "test"},
    )


@dataclass(slots=True)
class ResponsiveScenario:
    component: LightResponsiveVirtualUserComponent
    active_time_us: int = 500_000
    start_time_us: int = 0
    end_time_us: int = END_TIME_US

    def schedule(self, scheduler: EventScheduler) -> None:
        self.component.reset()
        self.component.schedule_initial(scheduler)
        for event in (
            light_event(0, 0, active=False),
            light_event(self.active_time_us, 1, active=True),
            light_event(self.end_time_us, 2, active=False),
            completion_event(),
        ):
            scheduler.schedule_at(
                event.scheduled_time_us,
                event.event_type,
                source=event.source,
                priority=event.priority,
                payload=dict(event.payload),
            )


def simulation() -> tuple[SimulationEngine, LightResponsiveVirtualUserComponent]:
    component = LightResponsiveVirtualUserComponent(
        VirtualUserConfig(duration_seconds=240),
        LightResponseConfig(),
    )
    engine = SimulationEngine()
    engine.register_handler(HEARTBEAT_EVENT_TYPE, component.handle_heartbeat)
    engine.register_handler(
        LIGHT_STIMULUS_STATE_EVENT_TYPE,
        component.handle_light_stimulus_state,
    )
    engine.register_handler(
        SIMULATION_COMPLETE_EVENT_TYPE,
        component.handle_simulation_complete,
    )
    engine.load_scenario(ResponsiveScenario(component))
    return engine, component


def test_pending_heartbeat_is_not_rescheduled_and_later_interval_changes() -> None:
    engine, component = simulation()
    engine.step_one_event()  # heartbeat 0 schedules its next beat from response 0
    [pending_before] = tuple(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    engine.step_one_event()  # inactive state at 0
    engine.step_one_event()  # active state at 500 ms
    [pending_after] = tuple(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    assert pending_after == pending_before
    assert component.response_at(500_000) == 0.0
    engine.step_one_event()  # the already-reserved first post-light heartbeat
    heartbeat_times = tuple(
        event.scheduled_time_us
        for event in engine.executed_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    assert heartbeat_times == (0, pending_before.scheduled_time_us)
    next_pending = next(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    assert next_pending.scheduled_time_us > pending_before.scheduled_time_us
    assert component.responsive_heartbeat_records()[-1].response_sample_time_us == 0


def test_light_receipts_target_segments_continuity_completion_and_samples() -> None:
    engine, component = simulation()
    engine.run_until_end()
    receipts = component.light_receipt_records()
    segments = component.response_segments()
    assert len(receipts) == 3
    assert receipts[1].target_changed
    assert receipts[1].response_before == receipts[1].response_after_at_same_time == 0.0
    assert not receipts[1].provenance_used_by_physiology
    assert segments[0].start_time_us == 0
    assert segments[-1].end_time_us == END_TIME_US
    assert all(
        left.end_time_us == right.start_time_us
        and left.response_at_end == right.response_at_start
        for left, right in zip(segments, segments[1:], strict=False)
    )
    assert component.response_at(90_000_000) > 0.99
    samples = component.response_samples()
    assert len(samples) == 2_401
    assert samples[0].time_us == 0
    assert samples[-1].time_us == END_TIME_US
    snapshot = component.snapshot()
    assert snapshot.completed
    assert not snapshot.current_light_active
    assert snapshot.current_response_target == 0.0
    assert snapshot.current_response_level > 0.99


def test_same_target_receipt_does_not_split_or_reset_response() -> None:
    component = LightResponsiveVirtualUserComponent(
        VirtualUserConfig(duration_seconds=240),
        LightResponseConfig(),
    )
    engine = SimulationEngine(ResponsiveScenario(component))
    component.handle_light_stimulus_state(light_event(10, 1, active=True), engine)
    before = component.response_at(20)
    segments_before = component.response_segments()
    component.handle_light_stimulus_state(light_event(20, 2, active=True), engine)
    assert not component.light_receipt_records()[-1].target_changed
    assert component.response_segments() == segments_before
    assert component.response_at(20) == before


def test_duplicate_index_reverse_time_and_duplicate_completion_are_rejected() -> None:
    component = LightResponsiveVirtualUserComponent(
        VirtualUserConfig(duration_seconds=240),
        LightResponseConfig(),
    )
    engine = SimulationEngine(ResponsiveScenario(component))
    component.handle_light_stimulus_state(light_event(10, 1, active=True), engine)
    with pytest.raises(ValueError, match="duplicate"):
        component.handle_light_stimulus_state(light_event(20, 1, active=True), engine)
    with pytest.raises(ValueError, match="strictly increasing"):
        component.handle_light_stimulus_state(light_event(5, 2, active=False), engine)
    component.handle_simulation_complete(completion_event(), engine)
    with pytest.raises(RuntimeError, match="already completed"):
        component.handle_simulation_complete(completion_event(), engine)


def test_formal_heartbeat_schema_and_digests_are_stable_across_reset() -> None:
    engine, component = simulation()
    engine.run_until_end()
    digests = (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_sample_digest(),
    )
    for event in engine.executed_events():
        if event.event_type == HEARTBEAT_EVENT_TYPE:
            assert event.priority == 40
            assert event.source == "virtual_user"
            assert set(event.payload) == {"user_id", "beat_index"}
    assert len(component.heartbeat_records()) == len(
        component.responsive_heartbeat_records()
    )
    engine.reset()
    assert component.heartbeat_records() == ()
    assert component.responsive_heartbeat_records() == ()
    engine.run_until_end()
    assert (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_sample_digest(),
    ) == digests


def test_csv_schemas_and_export_do_not_mutate_digests(tmp_path) -> None:
    engine, component = simulation()
    engine.run_until_end()
    before = (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_sample_digest(),
    )
    paths = export_light_response_diagnostics(tmp_path, component)
    expected_headers = (
        LIGHT_STIMULUS_RECEIPTS_CSV_FIELDS,
        LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS,
        LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS,
        LIGHT_RESPONSE_SAMPLES_CSV_FIELDS,
    )
    for path, expected in zip(paths, expected_headers, strict=True):
        with path.open(encoding="utf-8", newline="") as csv_file:
            assert tuple(next(csv.reader(csv_file))) == expected
    assert (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_sample_digest(),
    ) == before
