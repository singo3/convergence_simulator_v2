"""Command transitions, segments, state query, grid, digest, and CSV tests."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pytest

from symbiotic_sim_v2.devices.virtual_light.component import (
    VirtualLightDeviceComponent,
)
from symbiotic_sim_v2.devices.virtual_light.config import VirtualLightDeviceConfig
from symbiotic_sim_v2.devices.virtual_light.diagnostics import (
    LIGHT_COMMAND_CSV_FIELDS,
    LIGHT_COMMANDS_CSV_FILENAME,
    LIGHT_STIMULUS_SEGMENT_CSV_FIELDS,
    LIGHT_STIMULUS_SEGMENTS_CSV_FILENAME,
    LIGHT_STIMULUS_STATE_CSV_FIELDS,
    LIGHT_STIMULUS_STATES_CSV_FILENAME,
    LIGHT_WAVEFORM_SAMPLE_CSV_FIELDS,
    LIGHT_WAVEFORM_SAMPLES_CSV_FILENAME,
    export_light_diagnostics,
)
from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
    parse_light_stimulus_state_event,
)
from symbiotic_sim_v2.domain.event_priorities import SIMULATION_COMPLETE_EVENT_PRIORITY
from symbiotic_sim_v2.domain.event_types import SIMULATION_COMPLETE_EVENT_TYPE
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.light_mapper.config import (
    B_TO_I_MAPPING_VERSION,
    COMMAND_HOLD_POLICY_VERSION,
    CONTINUOUS_PHASE_POLICY_VERSION,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_COMMAND_SCHEMA_VERSION,
)
from symbiotic_sim_v2.garden.light_mapper.events import (
    LIGHT_COMMAND_EVENT_PRIORITY,
    LIGHT_COMMAND_EVENT_SOURCE,
    LIGHT_COMMAND_EVENT_TYPE,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler

GREEN_B = (125 / 360, 0.5, 0.5, 0.5)


@dataclass(frozen=True, slots=True)
class EmptyScenario:
    end_time_us: int
    start_time_us: int = 0

    def schedule(self, _scheduler: EventScheduler) -> None:
        return None


def runtime(end_time_us: int = 240_000_000) -> SimulationEngine:
    return SimulationEngine(EmptyScenario(end_time_us=end_time_us))


def command_event(
    signal_index: int,
    effective_time_us: int,
    *,
    active: bool,
    b: tuple[float, float, float, float] = GREEN_B,
    holder: str = "life-green",
    hue_degree: float = 125.0,
    blink_bpm: float = 87.5,
    sequence: int | None = None,
) -> SimulationEvent:
    if active:
        source_b: tuple[float, float, float, float] | None = b
        selected_holder: str | None = holder
        hue: float | None = hue_degree
        render_hue: float | None = hue_degree % 360.0
        saturation = 1.0
        center = 0.425
        amplitude = 0.075
        value_min = 0.35
        value_max = 0.50
        bpm: float | None = blink_bpm
        waveform = "sine"
    else:
        source_b = None
        selected_holder = None
        hue = None
        render_hue = None
        saturation = center = amplitude = value_min = value_max = 0.0
        bpm = None
        waveform = "off"
    signal_time_us = min(signal_index * 1_000_000, effective_time_us)
    payload = {
        "garden_id": "relax-with-light",
        "source_signal_index": signal_index,
        "source_signal_time_us": signal_time_us,
        "source_effective_time_us": effective_time_us,
        "command_effective_time_us": effective_time_us,
        "active": active,
        "qualification_holder_id": selected_holder,
        "source_b_f": None if source_b is None else source_b[0],
        "source_b_a": None if source_b is None else source_b[1],
        "source_b_t": None if source_b is None else source_b[2],
        "source_b_d": None if source_b is None else source_b[3],
        "hue_degree": hue,
        "render_hue_degree": render_hue,
        "saturation": saturation,
        "value_center": center,
        "value_amplitude": amplitude,
        "value_min": value_min,
        "value_max": value_max,
        "blink_bpm": bpm,
        "waveform": waveform,
        "mapping_version": B_TO_I_MAPPING_VERSION,
        "phase_policy_version": CONTINUOUS_PHASE_POLICY_VERSION,
        "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
        "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
        "schema_version": LIGHT_COMMAND_SCHEMA_VERSION,
    }
    return SimulationEvent(
        event_id=f"command-{signal_index}-{effective_time_us}",
        event_type=LIGHT_COMMAND_EVENT_TYPE,
        source=LIGHT_COMMAND_EVENT_SOURCE,
        scheduled_time_us=effective_time_us,
        priority=LIGHT_COMMAND_EVENT_PRIORITY,
        sequence=signal_index if sequence is None else sequence,
        payload=payload,
    )


def completion_event(end_time_us: int) -> SimulationEvent:
    return SimulationEvent(
        event_id="complete",
        event_type=SIMULATION_COMPLETE_EVENT_TYPE,
        source="garden_input_scenario",
        scheduled_time_us=end_time_us,
        priority=SIMULATION_COMPLETE_EVENT_PRIORITY,
        sequence=100_000,
        payload={"scenario": "test"},
    )


def deliver(
    component: VirtualLightDeviceComponent,
    engine: SimulationEngine,
    event: SimulationEvent,
) -> None:
    component.handle_light_command(event, engine)


def build_transition_fixture() -> tuple[VirtualLightDeviceComponent, SimulationEngine]:
    end_time_us = 8_000_000
    component = VirtualLightDeviceComponent(
        VirtualLightDeviceConfig(simulation_end_time_us=end_time_us)
    )
    engine = runtime(end_time_us)
    events = (
        command_event(0, 0, active=False),
        command_event(1, 1_000_000, active=False),
        command_event(2, 2_000_000, active=True),
        command_event(
            3,
            3_000_000,
            active=True,
            b=(GREEN_B[0], 0.1, GREEN_B[2], 0.9),
            holder="metadata-only-change",
        ),
        command_event(4, 4_000_000, active=True, blink_bpm=120.0),
        command_event(5, 5_000_000, active=True, hue_degree=180.0),
        command_event(6, 6_000_000, active=False),
        command_event(7, 7_000_000, active=True),
    )
    for event in events:
        deliver(component, engine, event)
    component.handle_simulation_complete(completion_event(end_time_us), engine)
    return component, engine


def build_standard_count_fixture() -> tuple[VirtualLightDeviceComponent, SimulationEngine]:
    component = VirtualLightDeviceComponent(VirtualLightDeviceConfig())
    engine = runtime()
    for signal_index in range(241):
        deliver(
            component,
            engine,
            command_event(
                signal_index,
                signal_index * 1_000_000,
                active=60 <= signal_index < 240,
            ),
        )
    component.handle_simulation_complete(completion_event(240_000_000), engine)
    return component, engine


def test_transitions_preserve_phase_and_use_only_physical_command_equivalence() -> None:
    component, _engine = build_transition_fixture()
    states = component.stimulus_state_records()
    segments = component.stimulus_segments()

    assert len(states) == 8
    assert not states[0].command_equivalent_to_previous
    assert states[0].physical_parameters_changed
    assert states[1].command_equivalent_to_previous
    assert not states[1].physical_parameters_changed
    assert states[2].phase_reset
    assert states[2].phase_cycles_at_start == 0.0
    assert states[2].value_at_start == pytest.approx(0.425)
    assert states[3].command_equivalent_to_previous
    assert not states[3].physical_parameters_changed
    assert not states[3].phase_reset
    assert states[3].phase_cycles_at_start == segments[2].phase_cycles_at_end
    assert not states[4].command_equivalent_to_previous
    assert not states[4].phase_reset
    assert states[4].phase_cycles_at_start == segments[3].phase_cycles_at_end
    assert not states[5].command_equivalent_to_previous
    assert not states[5].phase_reset
    assert states[5].phase_cycles_at_start == segments[4].phase_cycles_at_end
    assert not states[6].active
    assert states[6].phase_cycles_at_start is None
    assert states[6].value_at_start == 0.0
    assert states[7].phase_reset
    assert states[7].phase_cycles_at_start == 0.0

    snapshot = component.snapshot()
    assert snapshot.completed
    assert snapshot.command_count == 8
    assert snapshot.state_event_count == 8
    assert snapshot.closed_segment_count == 8
    assert snapshot.active_command_count == 5
    assert snapshot.inactive_command_count == 3
    assert snapshot.phase_reset_count == 2
    assert snapshot.phase_continuation_count == 3
    assert snapshot.equivalent_command_count == 2
    assert snapshot.physical_parameter_change_count == 6


def test_each_command_emits_one_exact_immutable_stage7_state_event() -> None:
    component, engine = build_transition_fixture()
    state_events = tuple(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == LIGHT_STIMULUS_STATE_EVENT_TYPE
    )
    assert len(state_events) == len(component.command_records()) == 8
    assert all(event.source == LIGHT_STIMULUS_STATE_EVENT_SOURCE for event in state_events)
    assert all(event.priority == LIGHT_STIMULUS_STATE_EVENT_PRIORITY for event in state_events)

    parsed = tuple(parse_light_stimulus_state_event(event) for event in state_events)
    assert parsed[2].active
    assert parsed[2].phase_reset
    assert parsed[2].phase_cycles_at_start == 0.0
    assert parsed[2].schema_version == "light_stimulus_state_event_v1"
    assert parsed[2].phase_policy_version == CONTINUOUS_PHASE_POLICY_VERSION
    assert not parsed[6].active
    forbidden = {
        "rgb",
        "qcolor",
        "rri",
        "rmssd",
        "n",
        "nd",
        "w",
        "p",
        "v",
        "tau",
        "e",
        "q",
        "k",
        "g",
    }
    assert forbidden.isdisjoint({key.casefold() for key in state_events[0].payload})
    with pytest.raises(TypeError):
        state_events[0].payload["active"] = True  # type: ignore[index]
    with pytest.raises((AttributeError, TypeError)):
        component.stimulus_state_records()[0].active = True  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("source_signal_time_us", 2_000_001),
        ("hue_degree", -1.0),
        ("render_hue_degree", 361.0),
        ("saturation", 1.1),
        ("value_amplitude", -0.1),
        ("value_min", 0.34),
        ("blink_bpm", 0.0),
        ("phase_cycles_at_start", 1.0),
        ("value_at_start", 0.5),
    ),
)
def test_stage7_state_parser_rejects_physically_inconsistent_active_payloads(
    field: str,
    invalid: object,
) -> None:
    component = VirtualLightDeviceComponent(
        VirtualLightDeviceConfig(simulation_end_time_us=3_000_000)
    )
    engine = runtime(3_000_000)
    deliver(component, engine, command_event(2, 2_000_000, active=True))
    [valid] = tuple(
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == LIGHT_STIMULUS_STATE_EVENT_TYPE
    )
    payload = dict(valid.payload)
    payload[field] = invalid
    malformed = SimulationEvent(
        event_id="malformed-state",
        event_type=valid.event_type,
        source=valid.source,
        scheduled_time_us=valid.scheduled_time_us,
        priority=valid.priority,
        sequence=valid.sequence,
        payload=payload,
    )

    with pytest.raises((TypeError, ValueError)):
        parse_light_stimulus_state_event(malformed)


def test_segments_are_positive_adjacent_and_continuous_only_across_active_commands() -> None:
    component, _engine = build_transition_fixture()
    segments = component.stimulus_segments()

    assert len(segments) == 8
    assert all(segment.duration_us > 0 for segment in segments)
    assert all(
        left.end_time_us == right.start_time_us
        for left, right in zip(segments[:-1], segments[1:], strict=True)
    )
    for left, right in zip(segments[:-1], segments[1:], strict=True):
        if left.active and right.active:
            assert left.phase_cycles_at_end == right.phase_cycles_at_start
    assert all(
        segment.phase_cycles_at_start is None
        and segment.phase_cycles_at_end is None
        and segment.value_at_start == 0.0
        and segment.value_at_end == 0.0
        for segment in segments
        if not segment.active
    )
    assert segments[0].start_time_us == 0
    assert segments[-1].end_time_us == 8_000_000


def test_state_at_holds_command_queries_history_and_uses_new_command_at_boundary() -> None:
    end_time_us = 4_000_000
    component = VirtualLightDeviceComponent(
        VirtualLightDeviceConfig(simulation_end_time_us=end_time_us)
    )
    engine = runtime(end_time_us)
    deliver(component, engine, command_event(0, 1_000_000, active=True))
    deliver(
        component,
        engine,
        command_event(1, 3_000_000, active=True, hue_degree=180.0),
    )
    component.handle_simulation_complete(completion_event(end_time_us), engine)

    before = component.state_at(999_999)
    at_first = component.state_at(1_000_000)
    held = component.state_at(2_000_000)
    at_boundary = component.state_at(3_000_000)
    historical_again = component.state_at(2_000_000)

    assert not before.active and before.current_value == 0.0
    assert before.command_count == 0
    assert at_first.active and at_first.phase_cycles == 0.0
    assert at_first.command_age_us == 0
    assert held.source_signal_index == 0
    assert held.command_age_us == 1_000_000
    assert held.hue_degree == 125.0
    assert at_boundary.source_signal_index == 1
    assert at_boundary.hue_degree == 180.0
    assert at_boundary.command_age_us == 0
    assert historical_again == held

    for invalid in (-1, 4_000_001, True):
        with pytest.raises((TypeError, ValueError)):
            component.state_at(invalid)  # type: ignore[arg-type]


def test_duplicate_reverse_signal_or_time_and_post_completion_commands_are_atomic() -> None:
    end_time_us = 3_000_000
    component = VirtualLightDeviceComponent(
        VirtualLightDeviceConfig(simulation_end_time_us=end_time_us)
    )
    engine = runtime(end_time_us)
    deliver(component, engine, command_event(0, 1_000_000, active=False))
    before = (
        component.command_records(),
        component.stimulus_state_records(),
        component.stimulus_segments(),
    )

    invalid = (
        command_event(1, 1_000_000, active=False, sequence=10),
        command_event(1, 500_000, active=False, sequence=11),
        command_event(0, 2_000_000, active=False, sequence=12),
    )
    for event in invalid:
        with pytest.raises(ValueError):
            deliver(component, engine, event)
        assert (
            component.command_records(),
            component.stimulus_state_records(),
            component.stimulus_segments(),
        ) == before

    component.handle_simulation_complete(completion_event(end_time_us), engine)
    with pytest.raises(RuntimeError):
        deliver(component, engine, command_event(1, 3_000_000, active=False))


def test_standard_command_series_has_241_states_240_segments_and_no_frame_events() -> None:
    component, engine = build_standard_count_fixture()
    snapshot = component.snapshot()
    segments = component.stimulus_segments()
    samples = component.waveform_samples()

    assert snapshot.command_count == 241
    assert snapshot.state_event_count == 241
    assert snapshot.active_command_count == 180
    assert snapshot.inactive_command_count == 61
    assert snapshot.phase_reset_count == 1
    assert snapshot.phase_continuation_count == 179
    assert not snapshot.active
    assert snapshot.current_value == 0.0
    assert snapshot.phase_cycles is None
    assert len(segments) == 240
    assert sum(segment.active for segment in segments) == 180
    assert sum(not segment.active for segment in segments) == 60
    assert len(samples) == 12_001
    assert samples[0].sample_index == 0 and samples[0].time_us == 0
    assert samples[-1].sample_index == 12_000
    assert samples[-1].time_us == 240_000_000
    assert not samples[-1].active and samples[-1].value == 0.0

    pending = engine.scheduler.pending_events()
    assert len(pending) == 241
    assert {event.event_type for event in pending} == {
        LIGHT_STIMULUS_STATE_EVENT_TYPE
    }
    assert not any("sample" in event.event_type or "frame" in event.event_type for event in pending)


def test_reset_reproduces_all_device_digests_and_snapshot_reads_are_observational() -> None:
    component, _engine = build_standard_count_fixture()
    first = (
        component.command_digest(),
        component.stimulus_state_digest(),
        component.segment_digest(),
        component.waveform_sample_digest(),
    )
    component.snapshot()
    component.state_at(60_000_000)
    component.state_at(123_456_789)
    component.waveform_samples()
    assert (
        component.command_digest(),
        component.stimulus_state_digest(),
        component.segment_digest(),
        component.waveform_sample_digest(),
    ) == first

    component.reset()
    assert component.command_records() == ()
    assert component.stimulus_state_records() == ()
    assert component.stimulus_segments() == ()
    assert component.snapshot().command_count == 0
    with pytest.raises(RuntimeError, match="completed"):
        component.waveform_samples()

    engine = runtime()
    for signal_index in range(241):
        deliver(
            component,
            engine,
            command_event(
                signal_index,
                signal_index * 1_000_000,
                active=60 <= signal_index < 240,
            ),
        )
    component.handle_simulation_complete(completion_event(240_000_000), engine)
    assert (
        component.command_digest(),
        component.stimulus_state_digest(),
        component.segment_digest(),
        component.waveform_sample_digest(),
    ) == first


def test_four_csv_exports_have_exact_schema_rows_and_do_not_change_digests(
    tmp_path: Path,
) -> None:
    component, _engine = build_standard_count_fixture()
    before = (
        component.command_digest(),
        component.stimulus_state_digest(),
        component.segment_digest(),
        component.waveform_sample_digest(),
    )
    paths = export_light_diagnostics(tmp_path, component)
    expected = (
        (paths.commands, LIGHT_COMMANDS_CSV_FILENAME, LIGHT_COMMAND_CSV_FIELDS, 241),
        (
            paths.stimulus_states,
            LIGHT_STIMULUS_STATES_CSV_FILENAME,
            LIGHT_STIMULUS_STATE_CSV_FIELDS,
            241,
        ),
        (
            paths.stimulus_segments,
            LIGHT_STIMULUS_SEGMENTS_CSV_FILENAME,
            LIGHT_STIMULUS_SEGMENT_CSV_FIELDS,
            240,
        ),
        (
            paths.waveform_samples,
            LIGHT_WAVEFORM_SAMPLES_CSV_FILENAME,
            LIGHT_WAVEFORM_SAMPLE_CSV_FIELDS,
            12_001,
        ),
    )
    for path, filename, fields, count in expected:
        assert path.name == filename
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
        assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == count
    assert (
        component.command_digest(),
        component.stimulus_state_digest(),
        component.segment_digest(),
        component.waveform_sample_digest(),
    ) == before
