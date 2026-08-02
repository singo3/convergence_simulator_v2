"""Hand-calculated boundary tests for the GUI-independent ideal H10."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

from symbiotic_sim_v2.devices.polar_h10.component import (
    PolarH10Component,
    PolarH10State,
)
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.domain.event_priorities import (
    HEARTBEAT_EVENT_PRIORITY,
    RRI_MEASUREMENT_EVENT_PRIORITY,
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import (
    POLAR_H10_EVENT_SOURCE,
    VIRTUAL_USER_EVENT_SOURCE,
)
from symbiotic_sim_v2.domain.event_types import (
    HEARTBEAT_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent, thaw_json


class RecordingEngine:
    """Small schedule-at spy that still returns production SimulationEvent values."""

    def __init__(self, event_number_offset: int = 0) -> None:
        self.event_number_offset = event_number_offset
        self.scheduled_events: list[SimulationEvent] = []

    def schedule_at(
        self,
        scheduled_time_us: int,
        event_type: str,
        *,
        source: str = "handler",
        priority: int = 100,
        payload: Any = None,
        event_id: str | None = None,
    ) -> SimulationEvent:
        number = self.event_number_offset + len(self.scheduled_events)
        event = SimulationEvent(
            event_id=event_id or f"evt-output-{number:06d}",
            event_type=event_type,
            source=source,
            scheduled_time_us=scheduled_time_us,
            priority=priority,
            sequence=number,
            payload={} if payload is None else payload,
        )
        self.scheduled_events.append(event)
        return event


def make_heartbeat(
    time_us: int,
    beat_index: object,
    *,
    event_type: str = HEARTBEAT_EVENT_TYPE,
    source: str = VIRTUAL_USER_EVENT_SOURCE,
    priority: int = HEARTBEAT_EVENT_PRIORITY,
    user_id: object = "virtual-user-001",
    include_beat_index: bool = True,
    extra_payload: dict[str, object] | None = None,
) -> SimulationEvent:
    payload: dict[str, object] = {"user_id": user_id}
    if include_beat_index:
        payload["beat_index"] = beat_index
    if extra_payload:
        payload.update(extra_payload)
    return SimulationEvent(
        event_id=f"evt-heartbeat-{time_us}-{beat_index}",
        event_type=event_type,
        source=source,
        scheduled_time_us=time_us,
        priority=priority,
        sequence=0,
        payload=payload,
    )


def handle_series(
    component: PolarH10Component,
    engine: RecordingEngine,
    times_and_indices: tuple[tuple[int, int], ...],
) -> None:
    for time_us, beat_index in times_and_indices:
        component.handle_heartbeat(make_heartbeat(time_us, beat_index), engine)  # type: ignore[arg-type]


def test_first_valid_heartbeat_is_observed_without_rri_output() -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    assert component.snapshot().state is PolarH10State.READY

    component.handle_heartbeat(make_heartbeat(0, 0), engine)  # type: ignore[arg-type]

    snapshot = component.snapshot()
    assert snapshot.state is PolarH10State.MEASURING
    assert snapshot.observed_heartbeat_count == 1
    assert snapshot.rri_measurement_count == 0
    assert snapshot.previous_heartbeat_time_us == 0
    assert snapshot.previous_beat_index == 0
    assert snapshot.latest_rri_us is None
    assert component.measurement_records() == ()
    assert engine.scheduled_events == []


@pytest.mark.parametrize(
    ("event_kwargs", "exception", "match"),
    (
        ({"event_type": "not_heartbeat"}, ValueError, "only accepts heartbeat"),
        ({"source": "other_source"}, ValueError, "source"),
        ({"priority": 39}, ValueError, "priority"),
        ({"user_id": "another-user"}, ValueError, "user_id"),
        ({"include_beat_index": False}, ValueError, "payload"),
        ({"extra_payload": {"rri_ms": 800.0}}, ValueError, "payload"),
        ({"beat_index": True}, TypeError, "beat_index"),
        ({"beat_index": 1.0}, TypeError, "beat_index"),
        ({"beat_index": "1"}, TypeError, "beat_index"),
        ({"beat_index": -1}, ValueError, "non-negative"),
    ),
)
def test_invalid_heartbeat_boundary_inputs_are_explicitly_rejected(
    event_kwargs: dict[str, object],
    exception: type[Exception],
    match: str,
) -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    kwargs = {"time_us": 0, "beat_index": 0, **event_kwargs}
    event = make_heartbeat(**kwargs)  # type: ignore[arg-type]
    with pytest.raises(exception, match=match):
        component.handle_heartbeat(event, engine)  # type: ignore[arg-type]
    assert component.snapshot().observed_heartbeat_count == 0
    assert component.measurement_records() == ()


def test_negative_heartbeat_time_is_rejected_by_the_formal_event_value() -> None:
    with pytest.raises(ValueError, match="scheduled_time_us"):
        make_heartbeat(-1, 0)


@pytest.mark.parametrize("next_index", (4, 3))
def test_duplicate_or_retrograde_beat_index_is_rejected(next_index: int) -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    component.handle_heartbeat(make_heartbeat(1_000_000, 4), engine)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="beat_index"):
        component.handle_heartbeat(make_heartbeat(2_000_000, next_index), engine)  # type: ignore[arg-type]
    assert component.snapshot().observed_heartbeat_count == 1
    assert component.measurement_records() == ()


@pytest.mark.parametrize("next_time_us", (1_000_000, 999_999))
def test_duplicate_or_retrograde_heartbeat_time_is_rejected(next_time_us: int) -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    component.handle_heartbeat(make_heartbeat(1_000_000, 4), engine)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="heartbeat times"):
        component.handle_heartbeat(make_heartbeat(next_time_us, 5), engine)  # type: ignore[arg-type]
    assert component.snapshot().observed_heartbeat_count == 1
    assert component.measurement_records() == ()


def test_three_hand_calculated_heartbeats_emit_two_exact_rri_events_and_records() -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    handle_series(component, engine, ((0, 0), (855_679, 1), (1_700_000, 2)))

    records = component.measurement_records()
    assert len(records) == 2
    first, second = records
    assert (first.measurement_index, second.measurement_index) == (0, 1)
    assert (first.previous_beat_index, first.current_beat_index) == (0, 1)
    assert (second.previous_beat_index, second.current_beat_index) == (1, 2)
    assert (first.previous_heartbeat_time_us, first.current_heartbeat_time_us) == (
        0,
        855_679,
    )
    assert (
        second.previous_heartbeat_time_us,
        second.current_heartbeat_time_us,
    ) == (855_679, 1_700_000)
    assert (first.rri_us, first.rri_ms) == (855_679, 855.679)
    assert (second.rri_us, second.rri_ms) == (844_321, 844.321)

    for record, event in zip(records, engine.scheduled_events, strict=True):
        assert event.event_type == RRI_MEASUREMENT_EVENT_TYPE
        assert event.source == POLAR_H10_EVENT_SOURCE
        assert event.priority == RRI_MEASUREMENT_EVENT_PRIORITY
        assert event.scheduled_time_us == record.current_heartbeat_time_us
        assert event.event_id == record.event_id
        assert thaw_json(event.payload) == {
            "device_id": "polar-h10-sim-001",
            "user_id": "virtual-user-001",
            "measurement_index": record.measurement_index,
            "previous_beat_index": record.previous_beat_index,
            "current_beat_index": record.current_beat_index,
            "previous_heartbeat_time_us": record.previous_heartbeat_time_us,
            "current_heartbeat_time_us": record.current_heartbeat_time_us,
            "rri_us": record.rri_us,
            "rri_ms": record.rri_ms,
            "event_schema_version": "rri_measurement_event_v1",
        }
        assert json.loads(json.dumps(event.to_dict(), allow_nan=False))["payload"] == thaw_json(
            event.payload
        )

    snapshot = component.snapshot()
    assert snapshot.observed_heartbeat_count == 3
    assert snapshot.rri_measurement_count == 2
    assert snapshot.latest_rri_us == 844_321
    assert snapshot.latest_rri_ms == 844.321
    assert snapshot.latest_measurement_time_us == 1_700_000


def test_formal_rri_payload_is_deeply_immutable_and_has_no_future_stage_signals() -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    handle_series(component, engine, ((0, 0), (800_000, 1)))
    event = engine.scheduled_events[0]
    forbidden = {
        "true_rri_us",
        "true_rri_ms",
        "rmssd",
        "hrv",
        "n",
        "n_baseline",
        "nd",
        "w",
        "artifact",
        "evaluation_quality",
        "respiratory_component_ms",
        "slow_wave_component_ms",
        "correlated_component_ms",
        "beat_jitter_component_ms",
        "unclamped_rri_ms",
        "clamped",
    }
    assert set(event.payload).isdisjoint(forbidden)
    with pytest.raises(TypeError, match="immutable"):
        event.payload["rri_us"] = 1  # type: ignore[index]


@pytest.mark.parametrize(
    "interval_us",
    (1, 299_000, 300_000, 2_000_000, 2_001_000, 12_345_678),
    ids=("one-microsecond", "299ms", "300ms", "2000ms", "2001ms", "very-long"),
)
def test_every_positive_raw_interval_passes_through_without_clipping(
    interval_us: int,
) -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    handle_series(component, engine, ((0, 0), (interval_us, 1)))
    record = component.measurement_records()[0]
    event = engine.scheduled_events[0]
    assert record.rri_us == interval_us
    assert record.rri_ms == interval_us / 1_000.0
    assert event.payload["rri_us"] == interval_us
    assert event.payload["rri_ms"] == interval_us / 1_000.0


def test_nonconsecutive_beat_indices_produce_one_uninterpolated_observed_interval() -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    handle_series(component, engine, ((100_000, 2), (2_101_000, 8)))
    assert len(engine.scheduled_events) == 1
    record = component.measurement_records()[0]
    assert record.previous_beat_index == 2
    assert record.current_beat_index == 8
    assert record.rri_us == 2_001_000


def test_reset_clears_all_state_records_and_reproduces_the_series_and_digest() -> None:
    component = PolarH10Component(PolarH10Config())
    first_engine = RecordingEngine()
    series = ((0, 0), (800_000, 1), (1_700_000, 2))
    handle_series(component, first_engine, series)
    first_records = component.measurement_records()
    first_digest = component.measurement_digest()

    component.reset()
    snapshot = component.snapshot()
    assert snapshot.state is PolarH10State.READY
    assert snapshot.observed_heartbeat_count == 0
    assert snapshot.rri_measurement_count == 0
    assert snapshot.previous_heartbeat_time_us is None
    assert snapshot.previous_beat_index is None
    assert snapshot.latest_rri_us is None
    assert component.measurement_records() == ()

    second_engine = RecordingEngine()
    handle_series(component, second_engine, series)
    assert component.measurement_records() == first_records
    assert component.measurement_digest() == first_digest


def test_digest_ignores_scheduler_event_identity_but_not_raw_measurements() -> None:
    series = ((0, 0), (800_000, 1), (1_700_000, 2))
    first = PolarH10Component(PolarH10Config())
    second = PolarH10Component(PolarH10Config())
    handle_series(first, RecordingEngine(0), series)
    handle_series(second, RecordingEngine(100), series)
    assert first.measurement_records() != second.measurement_records()
    assert first.measurement_digest() == second.measurement_digest()

    changed = PolarH10Component(PolarH10Config())
    handle_series(changed, RecordingEngine(), ((0, 0), (800_001, 1), (1_700_000, 2)))
    assert changed.measurement_digest() != first.measurement_digest()


def test_snapshot_records_and_record_values_cannot_be_mutated_externally() -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    handle_series(component, engine, ((0, 0), (800_000, 1)))
    snapshot = component.snapshot()
    records = component.measurement_records()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.observed_heartbeat_count = 10  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        records[0].rri_us = 1  # type: ignore[misc]
    with pytest.raises(TypeError):
        records[0] = records[0]  # type: ignore[index]


def test_completion_state_is_terminal_until_reset() -> None:
    component = PolarH10Component(PolarH10Config())
    engine = RecordingEngine()
    component.handle_heartbeat(make_heartbeat(0, 0), engine)  # type: ignore[arg-type]
    completion = SimulationEvent(
        event_id="evt-complete",
        event_type=SIMULATION_COMPLETE_EVENT_TYPE,
        source="scenario",
        scheduled_time_us=10_000_000,
        priority=SIMULATION_COMPLETE_EVENT_PRIORITY,
        sequence=1,
        payload={},
    )
    component.handle_simulation_complete(completion, engine)  # type: ignore[arg-type]
    assert component.snapshot().state is PolarH10State.COMPLETED
    with pytest.raises(RuntimeError, match="completed"):
        component.handle_heartbeat(make_heartbeat(11_000_000, 1), engine)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "event",
    (
        SimulationEvent(
            event_id="wrong-type",
            event_type="other",
            source="scenario",
            scheduled_time_us=1,
            priority=SIMULATION_COMPLETE_EVENT_PRIORITY,
            sequence=0,
            payload={},
        ),
        SimulationEvent(
            event_id="wrong-priority",
            event_type=SIMULATION_COMPLETE_EVENT_TYPE,
            source="scenario",
            scheduled_time_us=1,
            priority=SIMULATION_COMPLETE_EVENT_PRIORITY - 1,
            sequence=0,
            payload={},
        ),
    ),
)
def test_completion_handler_rejects_wrong_contract(event: SimulationEvent) -> None:
    component = PolarH10Component(PolarH10Config())
    with pytest.raises(ValueError):
        component.handle_simulation_complete(event, RecordingEngine())  # type: ignore[arg-type]
