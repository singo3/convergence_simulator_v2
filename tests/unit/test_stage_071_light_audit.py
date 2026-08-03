"""Stage 7.1 physical-audit and response-epoch separation checks."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import fields

import pytest

from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.event_priorities import (
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
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
from symbiotic_sim_v2.virtual_user.light_response import component as component_module
from symbiotic_sim_v2.virtual_user.light_response.component import (
    LightResponsiveVirtualUserComponent,
)
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.dynamics import (
    first_order_response_at,
)
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
    physical_light_parameter_signature,
)
from symbiotic_sim_v2.virtual_user.light_response.records import (
    LightResponseDynamicsEpochRecord,
)

END_TIME_US = 240_000_000


def _light_event(
    time_us: int,
    source_signal_index: int,
    *,
    active: bool,
    render_hue_degree: float = 125.0,
    blink_bpm: float = 87.5,
    saturation: float = 1.0,
    value_center: float = 0.425,
    value_amplitude: float = 0.075,
    phase_cycles_at_start: float = 0.0,
    qualification_holder_id: str = "life-green",
    source_b: tuple[float, float, float, float] | None = None,
    upstream_reported_physical_change: bool = False,
) -> SimulationEvent:
    if active:
        b = source_b or (render_hue_degree / 360.0, 0.5, 0.5, 0.5)
        hue: float | None = render_hue_degree
        render_hue: float | None = render_hue_degree
        bpm: float | None = blink_bpm
        holder: str | None = qualification_holder_id
        phase: float | None = phase_cycles_at_start
        waveform = "sine"
        value_min = value_center - value_amplitude
        value_max = value_center + value_amplitude
        value_at_start = value_center + value_amplitude * math.sin(
            math.tau * phase_cycles_at_start
        )
        phase_reset = phase_cycles_at_start == 0.0
    else:
        b = None
        hue = render_hue = bpm = holder = phase = None
        saturation = value_center = value_amplitude = 0.0
        value_min = value_max = value_at_start = 0.0
        waveform = "off"
        phase_reset = False
    payload = {
        "device_id": "virtual-pc-light-001",
        "source_signal_index": source_signal_index,
        "source_signal_time_us": time_us,
        "effective_time_us": time_us,
        "active": active,
        "qualification_holder_id": holder,
        "source_b_f": None if b is None else b[0],
        "source_b_a": None if b is None else b[1],
        "source_b_t": None if b is None else b[2],
        "source_b_d": None if b is None else b[3],
        "hue_degree": hue,
        "render_hue_degree": render_hue,
        "saturation": saturation,
        "value_center": value_center,
        "value_amplitude": value_amplitude,
        "value_min": value_min,
        "value_max": value_max,
        "blink_bpm": bpm,
        "waveform": waveform,
        "phase_cycles_at_start": phase,
        "value_at_start": value_at_start,
        "phase_reset": phase_reset,
        "physical_parameters_changed": upstream_reported_physical_change,
        "command_equivalent_to_previous": not upstream_reported_physical_change,
        "mapping_version": LIGHT_MAPPING_VERSION,
        "phase_policy_version": PHASE_POLICY_VERSION,
        "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
        "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
        "schema_version": "light_stimulus_state_event_v1",
    }
    return SimulationEvent(
        event_id=f"stage-071-light-{source_signal_index}",
        event_type=LIGHT_STIMULUS_STATE_EVENT_TYPE,
        source=LIGHT_STIMULUS_STATE_EVENT_SOURCE,
        scheduled_time_us=time_us,
        priority=LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
        sequence=source_signal_index,
        payload=payload,
    )


def _completion_event() -> SimulationEvent:
    return SimulationEvent(
        event_id="stage-071-complete",
        event_type=SIMULATION_COMPLETE_EVENT_TYPE,
        source="stage-071-test",
        scheduled_time_us=END_TIME_US,
        priority=SIMULATION_COMPLETE_EVENT_PRIORITY,
        sequence=10_000,
        payload={"scenario": "stage-071-test"},
    )


def _component() -> LightResponsiveVirtualUserComponent:
    return LightResponsiveVirtualUserComponent(
        VirtualUserConfig(duration_seconds=240),
        LightResponseConfig(),
    )


def _handle(
    component: LightResponsiveVirtualUserComponent,
    event: SimulationEvent,
) -> None:
    component.handle_light_stimulus_state(event, SimulationEngine())


def _completed_split_matrix_component() -> LightResponsiveVirtualUserComponent:
    component = _component()
    events = (
        _light_event(0, 0, active=False),
        _light_event(1_000_000, 1, active=True, render_hue_degree=123.0),
        _light_event(
            5_000_000,
            2,
            active=True,
            render_hue_degree=127.0,
            phase_cycles_at_start=0.25,
            qualification_holder_id="life-red",
            source_b=(127.0 / 360.0, 0.2, 0.8, 0.1),
        ),
        _light_event(10_000_000, 3, active=True, render_hue_degree=140.0),
        _light_event(
            15_000_000,
            4,
            active=True,
            render_hue_degree=140.0,
            phase_cycles_at_start=0.5,
            qualification_holder_id="life-blue",
            source_b=(140.0 / 360.0, 0.9, 0.1, 0.9),
            upstream_reported_physical_change=True,
        ),
    )
    for event in events:
        _handle(component, event)
    component.handle_simulation_complete(_completion_event(), SimulationEngine())
    return component


def test_physical_signature_has_exact_included_and_excluded_fields() -> None:
    stimulus = PhysicalLightStimulus(
        effective_time_us=1_000_000,
        active=True,
        render_hue_degree=123.0,
        saturation=1.0,
        value_center=0.425,
        value_amplitude=0.075,
        value_min=0.35,
        value_max=0.5,
        blink_bpm=87.5,
        waveform="sine",
        phase_cycles_at_start=0.125,
    )
    signature = physical_light_parameter_signature(stimulus)
    assert signature == (
        True,
        123.0,
        1.0,
        0.425,
        0.075,
        0.35,
        0.5,
        87.5,
        "sine",
    )
    assert physical_light_parameter_signature(
        dataclasses.replace(
            stimulus,
            effective_time_us=99_000_000,
            phase_cycles_at_start=0.875,
        )
    ) == signature

    changed_values: tuple[dict[str, object], ...] = (
        {"active": False},
        {"render_hue_degree": math.nextafter(123.0, math.inf)},
        {"saturation": 0.9},
        {"value_center": 0.4},
        {"value_amplitude": 0.05},
        {"value_min": 0.3},
        {"value_max": 0.6},
        {"blink_bpm": 87.50000000000001},
        {"waveform": "square"},
    )
    for changes in changed_values:
        changed = dataclasses.replace(stimulus, **changes)
        assert physical_light_parameter_signature(changed) != signature


def test_split_matrix_linkage_and_same_target_continuity() -> None:
    component = _completed_split_matrix_component()
    receipts = component.light_receipt_records()
    assert tuple(
        (record.physical_parameters_changed, record.target_changed)
        for record in receipts
    ) == (
        (False, False),
        (True, True),
        (True, False),
        (True, True),
        (False, False),
    )
    assert tuple(
        (record.audit_segment_index, record.response_dynamics_epoch_index)
        for record in receipts
    ) == ((0, 0), (1, 1), (2, 1), (3, 2), (3, 2))
    assert receipts[0].audit_split_reason is None
    assert receipts[1].audit_split_reason
    assert receipts[2].audit_split_reason
    assert receipts[3].audit_split_reason
    assert receipts[4].audit_split_reason is None

    symmetric_boundary = receipts[2]
    assert symmetric_boundary.response_target == receipts[1].response_target
    assert symmetric_boundary.response_before == (
        symmetric_boundary.response_after_at_same_time
    )
    expected_before_target_change = first_order_response_at(
        10_000_000,
        start_time_us=1_000_000,
        response_at_start=0.0,
        target=receipts[1].response_target,
        time_constant_seconds=8.0,
    )
    assert receipts[3].response_before == pytest.approx(expected_before_target_change)
    assert receipts[3].response_after_at_same_time == pytest.approx(
        expected_before_target_change
    )

    audits = component.physical_audit_segments()
    epochs = component.response_dynamics_epoch_records()
    assert component.response_segments() == component.physical_stimulus_segments() == audits
    assert len(audits) == 4
    assert len(epochs) == 3
    assert tuple(segment.response_dynamics_epoch_index for segment in audits) == (
        0,
        1,
        1,
        2,
    )
    assert tuple(segment.render_hue_degree for segment in audits) == (
        None,
        123.0,
        127.0,
        140.0,
    )
    assert epochs[1].response_at_end == pytest.approx(expected_before_target_change)
    assert epochs[2].response_at_start == pytest.approx(expected_before_target_change)
    assert epochs[2].target_changed_at_start


def test_unexpected_target_only_split_has_an_explicit_diagnostic_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    component = _component()
    first = _light_event(1_000_000, 1, active=True, render_hue_degree=123.0)
    _handle(component, first)
    first_target = component.light_receipt_records()[-1].response_target
    with monkeypatch.context() as patch:
        patch.setattr(
            component_module,
            "response_target_for",
            lambda *_args: first_target / 2.0,
        )
        _handle(
            component,
            _light_event(
                2_000_000,
                2,
                active=True,
                render_hue_degree=123.0,
                phase_cycles_at_start=0.25,
                qualification_holder_id="life-red",
                source_b=(123.0 / 360.0, 0.1, 0.9, 0.2),
            ),
        )

    receipt = component.light_receipt_records()[-1]
    assert not receipt.physical_parameters_changed
    assert receipt.target_changed
    assert receipt.audit_segment_index == 2
    assert receipt.response_dynamics_epoch_index == 2
    assert receipt.audit_split_reason is not None
    reason = receipt.audit_split_reason.lower()
    assert "target" in reason and "physical" in reason
    assert receipt.response_before == receipt.response_after_at_same_time


def test_epoch_schema_is_exact_immutable_and_free_of_stimulus_or_provenance() -> None:
    expected_fields = (
        "epoch_index",
        "start_time_us",
        "end_time_us",
        "duration_us",
        "response_target",
        "response_at_start",
        "response_at_end",
        "time_constant_seconds",
        "target_changed_at_start",
        "response_dynamics_version",
        "schema_version",
    )
    assert tuple(field.name for field in fields(LightResponseDynamicsEpochRecord)) == (
        expected_fields
    )
    forbidden = {
        "hue",
        "render_hue_degree",
        "bpm",
        "blink_bpm",
        "holder",
        "qualification_holder_id",
        "source_b",
        "source_signal_index",
        "receipt_index",
        "digital_life_id",
        "k",
        "q",
        "w",
        "n",
    }
    assert forbidden.isdisjoint(LightResponseDynamicsEpochRecord.__dataclass_fields__)
    record = _completed_split_matrix_component().response_dynamics_epoch_records()[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.response_target = 0.5  # type: ignore[misc]


def test_completion_closes_only_positive_contiguous_audits_and_epochs() -> None:
    component = _completed_split_matrix_component()
    for records in (
        component.physical_audit_segments(),
        component.response_dynamics_epoch_records(),
    ):
        assert records[0].start_time_us == 0
        assert records[-1].end_time_us == END_TIME_US
        assert all(record.duration_us > 0 for record in records)
        assert all(
            left.end_time_us == right.start_time_us
            for left, right in zip(records, records[1:], strict=False)
        )
        assert all(
            record.duration_us == record.end_time_us - record.start_time_us
            for record in records
        )


def test_active_light_at_zero_omits_only_zero_duration_initial_states() -> None:
    component = _component()
    _handle(
        component,
        _light_event(0, 0, active=True, render_hue_degree=125.0),
    )
    component.handle_simulation_complete(_completion_event(), SimulationEngine())

    [audit] = component.physical_audit_segments()
    [epoch] = component.response_dynamics_epoch_records()
    assert (audit.segment_index, audit.start_time_us, audit.end_time_us) == (
        0,
        0,
        END_TIME_US,
    )
    assert (epoch.epoch_index, epoch.start_time_us, epoch.end_time_us) == (
        0,
        0,
        END_TIME_US,
    )
    assert audit.duration_us == epoch.duration_us == END_TIME_US
    assert audit.response_dynamics_epoch_index == epoch.epoch_index


def test_same_target_physical_change_never_reschedules_pending_heartbeat() -> None:
    component = _component()
    events = (
        _light_event(100_000, 1, active=True, render_hue_degree=123.0),
        _light_event(
            200_000,
            2,
            active=True,
            render_hue_degree=127.0,
            phase_cycles_at_start=0.25,
        ),
    )

    class PendingHeartbeatScenario:
        start_time_us = 0
        end_time_us = 3_000_000

        def schedule(self, scheduler: EventScheduler) -> None:
            component.reset()
            component.schedule_initial(scheduler)
            for event in events:
                scheduler.schedule_at(
                    event.scheduled_time_us,
                    event.event_type,
                    source=event.source,
                    priority=event.priority,
                    payload=dict(event.payload),
                )

    engine = SimulationEngine(PendingHeartbeatScenario())
    engine.register_handler(HEARTBEAT_EVENT_TYPE, component.handle_heartbeat)
    engine.register_handler(
        LIGHT_STIMULUS_STATE_EVENT_TYPE,
        component.handle_light_stimulus_state,
    )
    first = engine.step_one_event()
    assert first is not None and first.event_type == HEARTBEAT_EVENT_TYPE
    [pending_before] = tuple(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    first_light = engine.step_one_event()
    assert first_light is not None and first_light.event_type == (
        LIGHT_STIMULUS_STATE_EVENT_TYPE
    )
    [pending_after_target_change] = tuple(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    second_light = engine.step_one_event()
    assert second_light is not None and second_light.event_type == (
        LIGHT_STIMULUS_STATE_EVENT_TYPE
    )
    [pending_after_same_target_physical_change] = tuple(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == HEARTBEAT_EVENT_TYPE
    )
    assert pending_after_target_change == pending_before
    assert pending_after_same_target_physical_change == pending_before
    first_receipt, second_receipt = component.light_receipt_records()
    assert first_receipt.target_changed
    assert second_receipt.physical_parameters_changed
    assert not second_receipt.target_changed
