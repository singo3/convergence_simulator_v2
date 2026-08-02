"""Garden RRI boundary, evaluation state, quality, and signal tests."""

from __future__ import annotations

import math
from typing import Any

import pytest

from symbiotic_sim_v2.domain.event_priorities import (
    GARDEN_EVALUATION_FINALIZE_TRIGGER_PRIORITY,
    GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
    GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
    RRI_MEASUREMENT_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import (
    GARDEN_INPUT_EVENT_SOURCE,
    POLAR_H10_EVENT_SOURCE,
)
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent, thaw_json
from symbiotic_sim_v2.garden.input_layer.component import (
    GARDEN_INPUT_SCENARIO_SOURCE,
    GardenInputComponent,
)
from symbiotic_sim_v2.garden.input_layer.config import (
    GARDEN_EVALUATION_SCHEMA_VERSION,
    GARDEN_INPUT_SIGNAL_SCHEMA_VERSION,
    RRI_INPUT_SCHEMA_VERSION,
    RRI_WINDOW_MEMBERSHIP_POLICY,
    GardenInputConfig,
)


class RecordingEngine:
    """Minimal engine boundary spy used by component handler tests."""

    def __init__(self) -> None:
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
        sequence = len(self.scheduled_events)
        event = SimulationEvent(
            event_id=event_id or f"evt-output-{sequence:06d}",
            event_type=event_type,
            source=source,
            scheduled_time_us=scheduled_time_us,
            priority=priority,
            sequence=sequence,
            payload={} if payload is None else payload,
        )
        self.scheduled_events.append(event)
        return event


def make_rri_event(
    time_us: int,
    rri_us: int,
    measurement_index: int = 0,
    *,
    event_type: str = RRI_MEASUREMENT_EVENT_TYPE,
    source: str = POLAR_H10_EVENT_SOURCE,
    priority: int = RRI_MEASUREMENT_EVENT_PRIORITY,
    payload_overrides: dict[str, object] | None = None,
    omitted_field: str | None = None,
    event_id: str | None = None,
) -> SimulationEvent:
    payload: dict[str, object] = {
        "device_id": "polar-h10-sim-001",
        "user_id": "virtual-user-001",
        "measurement_index": measurement_index,
        "previous_beat_index": measurement_index,
        "current_beat_index": measurement_index + 1,
        "previous_heartbeat_time_us": time_us - rri_us,
        "current_heartbeat_time_us": time_us,
        "rri_us": rri_us,
        "rri_ms": rri_us / 1_000.0,
        "event_schema_version": RRI_INPUT_SCHEMA_VERSION,
    }
    if payload_overrides:
        payload.update(payload_overrides)
    if omitted_field is not None:
        payload.pop(omitted_field)
    return SimulationEvent(
        event_id=event_id or f"evt-rri-{measurement_index:04d}-{time_us}",
        event_type=event_type,
        source=source,
        scheduled_time_us=time_us,
        priority=priority,
        sequence=measurement_index,
        payload=payload,
    )


def feed_values(
    component: GardenInputComponent,
    values_us: tuple[int, ...],
    *,
    start_time_us: int,
    first_index: int = 0,
    step_us: int = 100_000,
) -> None:
    for offset, rri_us in enumerate(values_us):
        event = make_rri_event(
            start_time_us + offset * step_us,
            rri_us,
            first_index + offset,
        )
        component.handle_rri_measurement(event, None)  # type: ignore[arg-type]


def finalize(
    component: GardenInputComponent,
    evaluation_id: str,
    window_end_us: int,
    engine: RecordingEngine | None = None,
):
    selected_engine = engine or RecordingEngine()
    trigger = SimulationEvent(
        event_id=f"evt-finalize-{evaluation_id}",
        event_type=GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
        source=GARDEN_INPUT_SCENARIO_SOURCE,
        scheduled_time_us=window_end_us,
        priority=GARDEN_EVALUATION_FINALIZE_TRIGGER_PRIORITY,
        sequence=10_000 + len(component.evaluation_records()),
        payload={"evaluation_id": evaluation_id},
    )
    component.handle_evaluation_finalize_trigger(  # type: ignore[arg-type]
        trigger,
        selected_engine,
    )
    return component.evaluation_records()[-1], selected_engine.scheduled_events[-1]


def emit_signal(
    component: GardenInputComponent,
    signal_index: int,
    engine: RecordingEngine,
) -> None:
    trigger = SimulationEvent(
        event_id=f"evt-signal-trigger-{signal_index:04d}",
        event_type=GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
        source=GARDEN_INPUT_SCENARIO_SOURCE,
        scheduled_time_us=signal_index * 1_000_000,
        priority=GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
        sequence=20_000 + signal_index,
        payload={"signal_index": signal_index},
    )
    component.handle_signal_trigger(trigger, engine)  # type: ignore[arg-type]


def valid_rmssd_47_5_fixture() -> tuple[int, ...]:
    # Four adjacent absolute differences of 47.5 ms give RMSSD 47.5 ms.
    return (800_000, 847_500, 800_000, 847_500, 800_000)


def test_valid_formal_rri_event_is_accepted_and_recorded_without_transformation() -> None:
    component = GardenInputComponent(GardenInputConfig())
    event = make_rri_event(30_000_000, 855_679, 7)

    component.handle_rri_measurement(event, None)  # type: ignore[arg-type]

    (record,) = component.rri_records()
    assert record.input_measurement_index == 7
    assert record.input_event_id == event.event_id
    assert record.event_time_us == 30_000_000
    assert record.raw_rri_us == 855_679
    assert record.raw_rri_ms == 855.679
    assert record.phase == "baseline_evaluation"
    assert record.evaluation_id == "session-001-baseline"
    assert record.included_in_evaluation_window
    assert record.accepted_into_valid_history
    assert not record.artifact


@pytest.mark.parametrize(
    ("event_kwargs", "exception", "match"),
    (
        ({"event_type": "heartbeat"}, ValueError, "only accepts"),
        ({"source": "virtual_user"}, ValueError, "source"),
        (
            {"payload_overrides": {"event_schema_version": "future_schema"}},
            ValueError,
            "event_schema_version",
        ),
        ({"omitted_field": "device_id"}, ValueError, "payload fields"),
        (
            {"payload_overrides": {"measurement_index": True}},
            TypeError,
            "measurement_index",
        ),
        (
            {"payload_overrides": {"rri_us": True}},
            TypeError,
            "rri_us",
        ),
        (
            {"payload_overrides": {"rri_us": 800_001}},
            ValueError,
            "timestamp difference",
        ),
        (
            {
                "payload_overrides": {
                    "previous_heartbeat_time_us": 29_200_001,
                    "current_heartbeat_time_us": 30_000_001,
                }
            },
            ValueError,
            "event time",
        ),
    ),
)
def test_invalid_rri_boundary_inputs_are_rejected_without_state_change(
    event_kwargs: dict[str, object],
    exception: type[Exception],
    match: str,
) -> None:
    component = GardenInputComponent(GardenInputConfig())
    event = make_rri_event(30_000_000, 800_000, **event_kwargs)  # type: ignore[arg-type]

    with pytest.raises(exception, match=match):
        component.handle_rri_measurement(event, None)  # type: ignore[arg-type]

    assert component.rri_records() == ()
    assert component.snapshot().received_rri_count == 0


@pytest.mark.parametrize(
    (
        "time_us",
        "phase",
        "bundle_index",
        "role",
        "evaluation_id",
        "included",
    ),
    (
        (29_999_999, "baseline_discard", None, "discard", None, False),
        (
            30_000_000,
            "baseline_evaluation",
            None,
            "evaluation",
            "session-001-baseline",
            True,
        ),
        (
            59_999_999,
            "baseline_evaluation",
            None,
            "evaluation",
            "session-001-baseline",
            True,
        ),
        (60_000_000, "bundle_0_discard", 0, "discard", None, False),
        (
            90_000_000,
            "bundle_0_evaluation",
            0,
            "evaluation",
            "session-001-bundle-0",
            True,
        ),
        (120_000_000, "bundle_1_discard", 1, "discard", None, False),
        (
            150_000_000,
            "bundle_1_evaluation",
            1,
            "evaluation",
            "session-001-bundle-1",
            True,
        ),
        (180_000_000, "bundle_2_discard", 2, "discard", None, False),
        (
            210_000_000,
            "bundle_2_evaluation",
            2,
            "evaluation",
            "session-001-bundle-2",
            True,
        ),
        (240_000_000, "outside", None, "outside", None, False),
    ),
)
def test_measurement_end_time_alone_determines_window_membership(
    time_us: int,
    phase: str,
    bundle_index: int | None,
    role: str,
    evaluation_id: str | None,
    included: bool,
) -> None:
    component = GardenInputComponent(GardenInputConfig())

    component.handle_rri_measurement(  # type: ignore[arg-type]
        make_rri_event(time_us, 800_000),
        None,
    )

    (record,) = component.rri_records()
    assert record.phase == phase
    assert record.bundle_index == bundle_index
    assert record.window_role == role
    assert record.evaluation_id == evaluation_id
    assert record.included_in_evaluation_window is included
    assert record.membership_policy == RRI_WINDOW_MEMBERSHIP_POLICY


def test_artifact_is_kept_raw_but_not_added_to_valid_history() -> None:
    component = GardenInputComponent(GardenInputConfig())
    feed_values(component, (1_000_000,) * 5, start_time_us=10_000_000)
    component.handle_rri_measurement(  # type: ignore[arg-type]
        make_rri_event(20_000_000, 299_999, 5),
        None,
    )

    artifact = component.rri_records()[-1]
    snapshot = component.snapshot()
    assert artifact.raw_rri_us == 299_999
    assert artifact.raw_rri_ms == 299.999
    assert artifact.artifact
    assert artifact.artifact_reason == "too_short"
    assert not artifact.accepted_into_valid_history
    assert snapshot.recent_valid_history_count == 5
    assert snapshot.valid_rri_count == 5
    assert snapshot.artifact_rri_count == 1


def test_discard_rri_participates_in_global_median_history() -> None:
    component = GardenInputComponent(GardenInputConfig())
    feed_values(component, (1_000_000,) * 5, start_time_us=10_000_000)
    component.handle_rri_measurement(  # type: ignore[arg-type]
        make_rri_event(31_000_000, 1_200_000, 5),
        None,
    )

    record = component.rri_records()[-1]
    assert record.phase == "baseline_evaluation"
    assert record.median_history_count_before == 5
    assert record.median_rri_us_before == 1_000_000.0
    assert record.relative_deviation == pytest.approx(0.20)
    assert not record.artifact


def test_valid_history_is_not_reset_at_a_bundle_boundary() -> None:
    component = GardenInputComponent(GardenInputConfig())
    feed_values(component, (1_000_000,) * 5, start_time_us=119_000_000, step_us=100_000)
    component.handle_rri_measurement(  # type: ignore[arg-type]
        make_rri_event(120_000_000, 1_200_000, 5),
        None,
    )

    boundary_record = component.rri_records()[-1]
    assert boundary_record.phase == "bundle_1_discard"
    assert boundary_record.median_history_count_before == 5
    assert boundary_record.median_rri_us_before == 1_000_000.0
    assert not boundary_record.artifact


def test_component_reset_clears_history_records_buffers_and_digests() -> None:
    component = GardenInputComponent(GardenInputConfig())
    feed_values(component, (1_000_000,) * 5, start_time_us=10_000_000)
    populated_digest = component.artifact_digest()

    component.reset()
    component.handle_rri_measurement(  # type: ignore[arg-type]
        make_rri_event(31_000_000, 1_200_001, 0, event_id="evt-after-reset"),
        None,
    )

    record = component.rri_records()[0]
    assert record.median_history_count_before == 0
    assert not record.artifact
    assert component.snapshot().recent_valid_history_count == 1
    assert component.artifact_digest() != populated_digest


def test_evaluation_rmssd_excludes_artifact_and_discard_values() -> None:
    component = GardenInputComponent(GardenInputConfig())
    # This discard value belongs to history but not the baseline evaluation.
    feed_values(component, (1_100_000,), start_time_us=29_000_000)
    # Valid chronological differences: 30, 40, 30, 40 ms. The short artifact is ignored.
    feed_values(
        component,
        (800_000, 830_000, 299_999, 870_000, 900_000, 940_000),
        start_time_us=31_000_000,
        first_index=1,
    )

    record, _ = finalize(component, "session-001-baseline", 60_000_000)

    assert record.total_rri_count == 6
    assert record.artifact_rri_count == 1
    assert record.valid_rri_count == 5
    assert record.rmssd_ms == pytest.approx(math.sqrt(1_250.0))


def test_evaluation_sorts_valid_rri_by_event_time_not_arrival_order() -> None:
    component = GardenInputComponent(GardenInputConfig())
    timed_values = (
        (33_000_000, 870_000),
        (31_000_000, 800_000),
        (35_000_000, 940_000),
        (32_000_000, 830_000),
        (34_000_000, 900_000),
    )
    for index, (time_us, rri_us) in enumerate(timed_values):
        component.handle_rri_measurement(  # type: ignore[arg-type]
            make_rri_event(time_us, rri_us, index),
            None,
        )

    record, _ = finalize(component, "session-001-baseline", 60_000_000)

    assert record.rmssd_ms == pytest.approx(math.sqrt(1_250.0))


def test_rmssd_does_not_include_a_difference_across_evaluation_windows() -> None:
    component = GardenInputComponent(GardenInputConfig())
    values = (800_000, 830_000, 870_000, 900_000, 940_000)
    feed_values(component, values, start_time_us=31_000_000)
    baseline, _ = finalize(component, "session-001-baseline", 60_000_000)
    feed_values(component, values, start_time_us=91_000_000, first_index=5)
    bundle, _ = finalize(component, "session-001-bundle-0", 120_000_000)

    # A cross-window 940->800 difference is intentionally absent from both values.
    assert baseline.rmssd_ms == pytest.approx(math.sqrt(1_250.0))
    assert bundle.rmssd_ms == pytest.approx(math.sqrt(1_250.0))


@pytest.mark.parametrize(
    ("valid_count", "artifact_count", "rate", "quality", "is_valid", "reasons"),
    (
        (
            0,
            0,
            1.0,
            "rejected",
            False,
            ("no_rri", "artifact_rate_exceeded", "insufficient_valid_rri"),
        ),
        (19, 1, 0.05, "valid", True, ()),
        (15, 1, 0.0625, "low_confidence", True, ()),
        (9, 1, 0.10, "low_confidence", True, ()),
        (8, 1, 1 / 9, "rejected", False, ("artifact_rate_exceeded",)),
        (4, 0, 0.0, "rejected", False, ("insufficient_valid_rri",)),
        (5, 0, 0.0, "valid", True, ()),
        (
            4,
            1,
            0.20,
            "rejected",
            False,
            ("artifact_rate_exceeded", "insufficient_valid_rri"),
        ),
    ),
)
def test_quality_thresholds_and_reject_reasons_are_exact(
    valid_count: int,
    artifact_count: int,
    rate: float,
    quality: str,
    is_valid: bool,
    reasons: tuple[str, ...],
) -> None:
    component = GardenInputComponent(GardenInputConfig())
    values = (1_000_000,) * valid_count + (299_999,) * artifact_count
    feed_values(component, values, start_time_us=31_000_000)

    record, _ = finalize(component, "session-001-baseline", 60_000_000)

    assert record.valid_rri_count == valid_count
    assert record.artifact_rri_count == artifact_count
    assert record.artifact_rate == pytest.approx(rate)
    assert record.quality == quality
    assert record.is_valid is is_valid
    assert record.reject_reasons == reasons
    assert (record.n is not None) is is_valid


def test_valid_baseline_sets_reference_current_revision_and_formal_event() -> None:
    component = GardenInputComponent(GardenInputConfig())
    feed_values(component, valid_rmssd_47_5_fixture(), start_time_us=31_000_000)
    engine = RecordingEngine()

    record, output = finalize(
        component,
        "session-001-baseline",
        60_000_000,
        engine,
    )

    snapshot = component.snapshot()
    assert record.rmssd_ms == 47.5
    assert record.n == 0.5
    assert record.quality == "valid"
    assert record.n_revision == 1
    assert record.baseline_id == "session-001-baseline"
    assert record.schema_version == GARDEN_EVALUATION_SCHEMA_VERSION
    assert snapshot.n_baseline_session == 0.5
    assert snapshot.n_current == 0.5
    assert snapshot.baseline_available
    assert snapshot.valid_evaluation_revision == 1
    assert output.event_type == GARDEN_EVALUATION_FINALIZED_EVENT_TYPE
    assert output.source == GARDEN_INPUT_EVENT_SOURCE
    assert output.priority == GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY
    assert output.scheduled_time_us == 60_000_000
    expected_record_payload = record.to_dict()
    expected_record_payload["reject_reasons"] = list(record.reject_reasons)
    assert thaw_json(output.payload) == {
        "garden_id": "relax-with-light",
        "session_id": "session-001",
        **expected_record_payload,
    }


def test_three_valid_bundles_update_current_and_revision_but_never_baseline() -> None:
    component = GardenInputComponent(GardenInputConfig())
    feed_values(component, valid_rmssd_47_5_fixture(), start_time_us=31_000_000)
    finalize(component, "session-001-baseline", 60_000_000)
    fixtures = (
        ("session-001-bundle-0", 91_000_000, 120_000_000, 65_000, 50 / 65),
        ("session-001-bundle-1", 151_000_000, 180_000_000, 32_500, 17.5 / 65),
        ("session-001-bundle-2", 211_000_000, 240_000_000, 15_000, 0.0),
    )

    for bundle_index, (evaluation_id, start, end, delta, expected_n) in enumerate(fixtures):
        values = (800_000, 800_000 + delta, 800_000, 800_000 + delta, 800_000)
        feed_values(component, values, start_time_us=start, first_index=5 + bundle_index * 5)
        record, _ = finalize(component, evaluation_id, end)
        snapshot = component.snapshot()
        assert record.rmssd_ms == delta / 1_000
        assert record.n == pytest.approx(expected_n)
        assert record.n_revision == bundle_index + 2
        assert record.baseline_id == "session-001-baseline"
        assert snapshot.n_current == pytest.approx(expected_n)
        assert snapshot.n_baseline_session == 0.5
        assert snapshot.valid_evaluation_revision == bundle_index + 2


def test_rejected_bundle_keeps_last_valid_n_and_revision() -> None:
    component = GardenInputComponent(GardenInputConfig())
    feed_values(component, valid_rmssd_47_5_fixture(), start_time_us=31_000_000)
    finalize(component, "session-001-baseline", 60_000_000)
    before = component.snapshot()

    rejected, _ = finalize(component, "session-001-bundle-0", 120_000_000)
    after = component.snapshot()

    assert rejected.quality == "rejected"
    assert rejected.n is None
    assert after.n_current == before.n_current == 0.5
    assert after.n_baseline_session == before.n_baseline_session == 0.5
    assert after.valid_evaluation_revision == before.valid_evaluation_revision == 1


def test_rejected_baseline_keeps_s_zero_and_skips_bundle_evaluations() -> None:
    component = GardenInputComponent(GardenInputConfig())
    baseline, _ = finalize(component, "session-001-baseline", 60_000_000)
    signal_engine = RecordingEngine()
    for signal_index in range(61):
        emit_signal(component, signal_index, signal_engine)

    bundle, _ = finalize(component, "session-001-bundle-0", 120_000_000)
    for signal_index in range(61, 121):
        emit_signal(component, signal_index, signal_engine)

    snapshot = component.snapshot()
    assert baseline.quality == "rejected"
    assert baseline.n is None
    assert not snapshot.baseline_available
    assert snapshot.n_baseline_session is None
    assert snapshot.n_current is None
    assert snapshot.valid_evaluation_revision == 0
    assert "skipped_baseline_invalid" in bundle.reject_reasons
    assert bundle.n is None
    assert component.signal_records()[60].s == 0
    assert component.signal_records()[60].session_status == "baseline_invalid"
    assert component.signal_records()[120].s == 0


def test_signal_stream_exposes_only_n_s_and_revision_at_evaluation_boundaries() -> None:
    component = GardenInputComponent(GardenInputConfig())
    signal_engine = RecordingEngine()
    for signal_index in range(60):
        emit_signal(component, signal_index, signal_engine)
    feed_values(component, valid_rmssd_47_5_fixture(), start_time_us=31_000_000)
    finalize(component, "session-001-baseline", 60_000_000)
    for signal_index in range(60, 120):
        emit_signal(component, signal_index, signal_engine)

    delta = 65_000
    bundle_values = (800_000, 865_000, 800_000, 865_000, 800_000)
    feed_values(component, bundle_values, start_time_us=91_000_000, first_index=5)
    finalize(component, "session-001-bundle-0", 120_000_000)
    emit_signal(component, 120, signal_engine)

    records = component.signal_records()
    assert records[0].s == records[59].s == 0
    assert records[0].n_current is None
    assert not records[0].n_available
    assert records[60].s == records[119].s == 1
    assert records[60].n_current == records[119].n_current == 0.5
    assert records[60].valid_evaluation_revision == 1
    assert records[120].s == 1
    assert records[120].n_current == pytest.approx((delta / 1_000 - 15) / 65)
    assert records[120].n_baseline_session == 0.5
    assert records[120].valid_evaluation_revision == 2
    assert records[120].schema_version == GARDEN_INPUT_SIGNAL_SCHEMA_VERSION

    output = signal_engine.scheduled_events[-1]
    payload = thaw_json(output.payload)
    assert output.event_type == GARDEN_INPUT_SIGNAL_EVENT_TYPE
    assert output.source == GARDEN_INPUT_EVENT_SOURCE
    assert output.priority == GARDEN_INPUT_SIGNAL_EVENT_PRIORITY
    assert payload == records[120].to_dict()
    assert set(payload).isdisjoint({"nd", "Nd", "w", "W"})
