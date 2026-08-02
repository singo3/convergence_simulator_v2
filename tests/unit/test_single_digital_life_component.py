"""Formal Garden-event boundary tests for one Stage 5A Digital Life."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from symbiotic_sim_v2.digital_life.component import SingleDigitalLifeComponent
from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.domain.event_priorities import (
    GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
    GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import GARDEN_INPUT_EVENT_SOURCE
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent


def make_signal_event(
    signal_index: int = 0,
    time_us: int = 0,
    *,
    s: int = 0,
    phase: str = "baseline_discard",
    bundle_index: int | None = None,
    window_role: str = "discard",
    n_current: float | None = None,
    n_baseline_session: float | None = None,
    revision: int = 0,
    latest_evaluation_id: str | None = None,
    session_status: str = "baseline",
    event_type: str = GARDEN_INPUT_SIGNAL_EVENT_TYPE,
    source: str = GARDEN_INPUT_EVENT_SOURCE,
    priority: int = GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
    payload_updates: dict[str, object] | None = None,
    omitted_field: str | None = None,
) -> SimulationEvent:
    """Build a literal formal payload without using any Garden record class."""

    payload: dict[str, object] = {
        "garden_id": "relax-with-light",
        "session_id": "session-001",
        "signal_index": signal_index,
        "signal_time_us": time_us,
        "s": s,
        "phase": phase,
        "bundle_index": bundle_index,
        "window_role": window_role,
        "n_current": n_current,
        "n_available": n_current is not None,
        "n_baseline_session": n_baseline_session,
        "baseline_available": n_baseline_session is not None,
        "latest_valid_evaluation_id": latest_evaluation_id,
        "valid_evaluation_revision": revision,
        "session_status": session_status,
        "schema_version": "garden_input_signal_event_v1",
        "diagnostic_only": {"raw_rri_us": 777_777, "rmssd_ms": 47.5},
    }
    if payload_updates:
        payload.update(payload_updates)
    if omitted_field is not None:
        payload.pop(omitted_field)
    return SimulationEvent(
        event_id=f"evt-signal-{signal_index}-{time_us}",
        event_type=event_type,
        source=source,
        scheduled_time_us=time_us,
        priority=priority,
        sequence=10_000 + signal_index,
        payload=payload,
    )


def make_evaluation_event(
    evaluation_id: str = "session-001-baseline",
    time_us: int = 60_000_000,
    *,
    evaluation_kind: str = "baseline",
    bundle_index: int | None = None,
    n: float | None = 0.4,
    revision: int = 1,
    quality: str = "valid",
    is_valid: bool = True,
    baseline_id: str | None = "session-001-baseline",
    event_type: str = GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    source: str = GARDEN_INPUT_EVENT_SOURCE,
    priority: int = GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
    payload_updates: dict[str, object] | None = None,
    omitted_field: str | None = None,
) -> SimulationEvent:
    """Build the real Stage 4 shape, including diagnostics that must be ignored."""

    payload: dict[str, object] = {
        "garden_id": "relax-with-light",
        "session_id": "session-001",
        "evaluation_id": evaluation_id,
        "evaluation_kind": evaluation_kind,
        "bundle_index": bundle_index,
        "window_start_us": max(0, time_us - 30_000_000),
        "window_end_us": time_us,
        "total_rri_count": 35,
        "artifact_rri_count": 0,
        "valid_rri_count": 35,
        "artifact_rate": 0.0,
        "rmssd_ms": 47.5,
        "n": n,
        "quality": quality,
        "is_valid": is_valid,
        "reject_reasons": [] if is_valid else ["artifact_rate_exceeded"],
        "n_revision": revision,
        "baseline_id": baseline_id,
        "schema_version": "garden_evaluation_finalized_event_v1",
        "raw_rri_us": 888_888,
    }
    if payload_updates:
        payload.update(payload_updates)
    if omitted_field is not None:
        payload.pop(omitted_field)
    return SimulationEvent(
        event_id=f"evt-evaluation-{evaluation_id}-{time_us}",
        event_type=event_type,
        source=source,
        scheduled_time_us=time_us,
        priority=priority,
        sequence=20_000 + revision,
        payload=payload,
    )


def handle_evaluation(component: SingleDigitalLifeComponent, event: SimulationEvent) -> None:
    component.handle_evaluation_finalized(event, None)  # type: ignore[arg-type]


def handle_signal(component: SingleDigitalLifeComponent, event: SimulationEvent) -> None:
    component.handle_garden_input_signal(event, None)  # type: ignore[arg-type]


def component_fingerprint(component: SingleDigitalLifeComponent) -> tuple[object, ...]:
    return (
        component.snapshot(),
        component.first_round_records(),
        component.evaluation_update_records(),
        component.first_round_digest(),
        component.evaluation_update_digest(),
    )


def apply_baseline(component: SingleDigitalLifeComponent) -> None:
    handle_evaluation(component, make_evaluation_event())
    handle_signal(
        component,
        make_signal_event(
            60,
            60_000_000,
            s=1,
            phase="bundle_0_discard",
            bundle_index=0,
            n_current=0.4,
            n_baseline_session=0.4,
            revision=1,
            latest_evaluation_id="session-001-baseline",
            session_status="active",
        ),
    )


def apply_complete_revision_sequence(component: SingleDigitalLifeComponent) -> None:
    """Apply baseline, revisions 2/3, one rejection, and closing revision 4."""

    apply_baseline(component)
    handle_signal(
        component,
        make_signal_event(
            61,
            61_000_000,
            s=1,
            phase="bundle_0_discard",
            bundle_index=0,
            n_current=0.4,
            n_baseline_session=0.4,
            revision=1,
            latest_evaluation_id="session-001-baseline",
            session_status="active",
        ),
    )
    for evaluation_id, bundle_index, time_us, n, revision, signal_index in (
        ("session-001-bundle-0", 0, 120_000_000, 0.5, 2, 120),
        ("session-001-bundle-1", 1, 180_000_000, 0.35, 3, 180),
    ):
        handle_evaluation(
            component,
            make_evaluation_event(
                evaluation_id,
                time_us,
                evaluation_kind="bundle",
                bundle_index=bundle_index,
                n=n,
                revision=revision,
            ),
        )
        handle_signal(
            component,
            make_signal_event(
                signal_index,
                time_us,
                s=1,
                phase=f"bundle_{bundle_index + 1}_discard",
                bundle_index=bundle_index + 1,
                n_current=n,
                n_baseline_session=0.4,
                revision=revision,
                latest_evaluation_id=evaluation_id,
                session_status="active",
            ),
        )

    handle_evaluation(
        component,
        make_evaluation_event(
            "session-001-bundle-2-rejected",
            210_000_000,
            evaluation_kind="bundle",
            bundle_index=2,
            n=None,
            revision=3,
            quality="rejected",
            is_valid=False,
        ),
    )
    handle_signal(
        component,
        make_signal_event(
            210,
            210_000_000,
            s=1,
            phase="bundle_2_evaluation",
            bundle_index=2,
            window_role="evaluation",
            n_current=0.35,
            n_baseline_session=0.4,
            revision=3,
            latest_evaluation_id="session-001-bundle-1",
            session_status="active",
        ),
    )
    handle_evaluation(
        component,
        make_evaluation_event(
            "session-001-bundle-2",
            240_000_000,
            evaluation_kind="bundle",
            bundle_index=2,
            n=0.4,
            revision=4,
        ),
    )
    handle_signal(
        component,
        make_signal_event(
            240,
            240_000_000,
            s=0,
            phase="outside",
            bundle_index=None,
            window_role="outside",
            n_current=0.4,
            n_baseline_session=0.4,
            revision=4,
            latest_evaluation_id="session-001-bundle-2",
            session_status="completed",
        ),
    )


def test_evaluation_event_only_caches_metadata_and_signal_formally_applies_it() -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    initial = component.snapshot()
    event = make_evaluation_event()

    handle_evaluation(component, event)

    cached = component.snapshot()
    assert cached.latest_evaluation_id == "session-001-baseline"
    assert cached.n_current == initial.n_current is None
    assert cached.nd == initial.nd == 0.5
    assert cached.w == initial.w == 0.5
    assert not cached.baseline_initialized
    assert cached.last_revision == 0
    assert component.evaluation_update_records() == ()

    apply_signal = make_signal_event(
        60,
        60_000_000,
        s=1,
        phase="bundle_0_discard",
        bundle_index=0,
        n_current=0.4,
        n_baseline_session=0.4,
        revision=1,
        latest_evaluation_id="session-001-baseline",
        session_status="active",
    )
    handle_signal(component, apply_signal)

    snapshot = component.snapshot()
    assert snapshot.baseline_initialized
    assert snapshot.n_baseline_session == snapshot.n_current == 0.4
    assert snapshot.nd == snapshot.w == 0.5
    assert snapshot.last_revision == 1
    assert snapshot.new_valid_evaluation_count == 1
    assert len(component.evaluation_update_records()) == 1


def test_revision_sequence_uses_session_baseline_and_applies_closing_revision_four() -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))

    apply_complete_revision_sequence(component)

    records = component.first_round_records()
    updates = component.evaluation_update_records()
    snapshot = component.snapshot()
    assert len(records) == 6
    assert len(updates) == 5
    assert [record.valid_evaluation_revision for record in records] == [1, 1, 2, 3, 3, 4]
    assert [record.is_new_valid_evaluation for record in records] == [
        True,
        False,
        True,
        True,
        False,
        True,
    ]
    assert records[0].nd == records[0].w == 0.5
    assert records[1].nd == records[1].w == 0.5
    assert records[2].nd == pytest.approx(1.0)
    assert records[2].w == pytest.approx(1.0)
    assert records[3].nd == pytest.approx(0.25)
    assert records[3].w == pytest.approx(0.25)
    assert records[4].nd == records[3].nd
    assert records[4].w == records[3].w
    closing = records[5]
    assert closing.signal_time_us == 240_000_000
    assert closing.s == 0
    assert closing.is_new_valid_evaluation
    assert closing.nd == closing.w == pytest.approx(0.5)
    assert closing.p == 1.0
    assert closing.v == 0.45
    assert closing.tau is None
    assert not closing.touch_enabled
    assert not closing.touch_dispatched
    assert closing.g_status == "not_connected"
    assert not closing.second_round_connected
    assert snapshot.last_revision == 4
    assert snapshot.new_valid_evaluation_count == 4
    assert snapshot.n_baseline_session == 0.4
    assert snapshot.n_current == 0.4
    assert snapshot.e == 0.0
    assert snapshot.q == 0.5
    assert snapshot.k_anchor == snapshot.k_current == (0.5, 0.5, 0.5, 0.5)
    assert snapshot.g_status == "not_connected"
    assert snapshot.touch_dispatched_count == 0

    rejected = updates[3]
    assert rejected.evaluation_id == "session-001-bundle-2-rejected"
    assert not rejected.is_valid
    assert not rejected.applied
    assert rejected.skip_reason == "evaluation_rejected"
    assert rejected.previous_nd == rejected.new_nd == pytest.approx(0.25)
    assert rejected.previous_w == rejected.new_w == pytest.approx(0.25)
    assert updates[-1].evaluation_id == "session-001-bundle-2"
    assert updates[-1].applied
    assert updates[-1].new_nd == pytest.approx(0.5)


def test_same_revision_is_recorded_each_second_but_never_reapplied() -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    apply_baseline(component)
    before = component.snapshot()

    handle_signal(
        component,
        make_signal_event(
            61,
            61_000_000,
            s=1,
            phase="bundle_0_discard",
            bundle_index=0,
            n_current=0.4,
            n_baseline_session=0.4,
            revision=1,
            latest_evaluation_id="session-001-baseline",
            session_status="active",
        ),
    )

    after = component.snapshot()
    assert after.first_round_count == before.first_round_count + 1
    assert after.evaluation_update_count == before.evaluation_update_count == 1
    assert after.new_valid_evaluation_count == before.new_valid_evaluation_count == 1
    assert not component.first_round_records()[-1].is_new_valid_evaluation


def test_rejected_evaluation_is_diagnostic_only_and_never_changes_first_round_state() -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    apply_baseline(component)
    before = component.snapshot()

    handle_evaluation(
        component,
        make_evaluation_event(
            "session-001-bundle-0-rejected",
            120_000_000,
            evaluation_kind="bundle",
            bundle_index=0,
            n=None,
            revision=1,
            quality="rejected",
            is_valid=False,
        ),
    )

    after = component.snapshot()
    assert after.n_current == before.n_current
    assert after.n_baseline_session == before.n_baseline_session
    assert after.nd == before.nd
    assert after.w == before.w
    assert after.last_revision == before.last_revision
    assert after.new_valid_evaluation_count == before.new_valid_evaluation_count
    assert after.first_round_count == before.first_round_count
    assert after.evaluation_update_count == before.evaluation_update_count + 1
    rejected = component.evaluation_update_records()[-1]
    assert not rejected.applied
    assert rejected.skip_reason == "evaluation_rejected"


def test_extra_garden_diagnostics_are_accepted_but_never_copied_to_outputs() -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))

    apply_baseline(component)

    record_fields = set(component.first_round_records()[0].to_dict())
    update_fields = set(component.evaluation_update_records()[0].to_dict())
    snapshot_fields = set(component.snapshot().__dataclass_fields__)
    forbidden = {
        "raw_rri_us",
        "rmssd_ms",
        "artifact_rate",
        "artifact_rri_count",
        "valid_rri_count",
        "diagnostic_only",
    }
    assert record_fields.isdisjoint(forbidden)
    assert update_fields.isdisjoint(forbidden)
    assert snapshot_fields.isdisjoint(forbidden)


@pytest.mark.parametrize(
    "event_kwargs",
    (
        {"event_type": "heartbeat"},
        {"source": "polar_h10"},
        {"priority": 29},
        {"payload_updates": {"schema_version": "future_signal_schema"}},
        {"omitted_field": "signal_index"},
        {"payload_updates": {"signal_index": True}},
        {"payload_updates": {"signal_index": -1}},
        {"payload_updates": {"signal_time_us": 1}},
        {"payload_updates": {"s": True}},
        {"payload_updates": {"s": 2}},
        {"payload_updates": {"phase": "unknown"}},
        {"payload_updates": {"bundle_index": True}},
        {"payload_updates": {"bundle_index": 3}},
        {"payload_updates": {"window_role": "unknown"}},
        {"payload_updates": {"session_status": "unknown"}},
        {"payload_updates": {"n_available": True, "n_current": None}},
        {"payload_updates": {"n_available": False, "n_current": 0.4}},
        {
            "payload_updates": {
                "baseline_available": True,
                "n_baseline_session": None,
            }
        },
        {
            "payload_updates": {
                "baseline_available": True,
                "n_baseline_session": 0.4,
                "n_available": False,
                "n_current": None,
            }
        },
        {"payload_updates": {"valid_evaluation_revision": True}},
        {
            "payload_updates": {
                "valid_evaluation_revision": 1,
                "latest_valid_evaluation_id": None,
            }
        },
        {
            "payload_updates": {
                "valid_evaluation_revision": 0,
                "latest_valid_evaluation_id": "session-001-baseline",
            }
        },
    ),
)
def test_invalid_signal_payload_is_rejected_atomically(
    event_kwargs: dict[str, object],
) -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    before = component_fingerprint(component)
    event = make_signal_event(**event_kwargs)  # type: ignore[arg-type]

    with pytest.raises((TypeError, ValueError)):
        handle_signal(component, event)

    assert component_fingerprint(component) == before


@pytest.mark.parametrize(
    "event_kwargs",
    (
        {"event_type": "garden_input_signal"},
        {"source": "other"},
        {"priority": 24},
        {"payload_updates": {"schema_version": "future_evaluation_schema"}},
        {"omitted_field": "evaluation_id"},
        {"payload_updates": {"evaluation_id": ""}},
        {"payload_updates": {"evaluation_kind": "future"}},
        {"payload_updates": {"bundle_index": 0}},
        {
            "payload_updates": {
                "evaluation_kind": "bundle",
                "bundle_index": None,
            }
        },
        {"payload_updates": {"quality": "unknown"}},
        {"payload_updates": {"quality": "rejected", "is_valid": True}},
        {"payload_updates": {"quality": "valid", "is_valid": False}},
        {"payload_updates": {"n": None}},
        {"payload_updates": {"n": True}},
        {"payload_updates": {"n": 1.01}},
        {"payload_updates": {"n_revision": True}},
        {"payload_updates": {"n_revision": 0}},
        {"payload_updates": {"baseline_id": ""}},
    ),
)
def test_invalid_evaluation_payload_is_rejected_atomically(
    event_kwargs: dict[str, object],
) -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    before = component_fingerprint(component)
    event = make_evaluation_event(**event_kwargs)  # type: ignore[arg-type]

    with pytest.raises((TypeError, ValueError)):
        handle_evaluation(component, event)

    assert component_fingerprint(component) == before


@pytest.mark.parametrize("failure", ("duplicate-index", "time", "revision", "n", "baseline", "id"))
def test_component_level_signal_failures_are_atomic(failure: str) -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    apply_baseline(component)
    before = component_fingerprint(component)
    kwargs: dict[str, Any] = {
        "signal_index": 62,
        "time_us": 62_000_000,
        "s": 1,
        "phase": "bundle_0_discard",
        "bundle_index": 0,
        "n_current": 0.4,
        "n_baseline_session": 0.4,
        "revision": 1,
        "latest_evaluation_id": "session-001-baseline",
        "session_status": "active",
    }
    if failure == "duplicate-index":
        kwargs["signal_index"] = 60
    elif failure == "time":
        kwargs["time_us"] = 60_000_000
    elif failure == "revision":
        kwargs["revision"] = 0
        kwargs["latest_evaluation_id"] = None
    elif failure == "n":
        kwargs["n_current"] = 0.5
    elif failure == "baseline":
        kwargs["n_baseline_session"] = 0.5
    elif failure == "id":
        kwargs["latest_evaluation_id"] = "session-001-other"

    with pytest.raises(ValueError):
        handle_signal(component, make_signal_event(**kwargs))

    assert component_fingerprint(component) == before


@pytest.mark.parametrize("failure", ("id", "n", "availability", "baseline", "baseline-change"))
def test_new_revision_failure_is_atomic_and_keeps_pending_metadata_for_retry(
    failure: str,
) -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    apply_baseline(component)
    handle_evaluation(
        component,
        make_evaluation_event(
            "session-001-bundle-0",
            120_000_000,
            evaluation_kind="bundle",
            bundle_index=0,
            n=0.5,
            revision=2,
        ),
    )
    before = component_fingerprint(component)
    kwargs: dict[str, Any] = {
        "signal_index": 120,
        "time_us": 120_000_000,
        "s": 1,
        "phase": "bundle_1_discard",
        "bundle_index": 1,
        "n_current": 0.5,
        "n_baseline_session": 0.4,
        "revision": 2,
        "latest_evaluation_id": "session-001-bundle-0",
        "session_status": "active",
    }
    if failure == "id":
        kwargs["latest_evaluation_id"] = "session-001-other"
    elif failure == "n":
        kwargs["n_current"] = 0.6
    elif failure == "availability":
        kwargs["n_current"] = None
    elif failure == "baseline":
        kwargs["n_baseline_session"] = None
    elif failure == "baseline-change":
        kwargs["n_baseline_session"] = 0.45

    with pytest.raises(ValueError):
        handle_signal(component, make_signal_event(**kwargs))
    assert component_fingerprint(component) == before

    handle_signal(
        component,
        make_signal_event(
            120,
            120_000_000,
            s=1,
            phase="bundle_1_discard",
            bundle_index=1,
            n_current=0.5,
            n_baseline_session=0.4,
            revision=2,
            latest_evaluation_id="session-001-bundle-0",
            session_status="active",
        ),
    )
    assert component.snapshot().last_revision == 2


def test_first_valid_revision_must_be_one_and_baseline() -> None:
    for revision, evaluation_kind, bundle_index in (
        (2, "bundle", 0),
        (1, "bundle", 0),
    ):
        component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
        handle_evaluation(
            component,
            make_evaluation_event(
                f"session-001-first-{revision}-{evaluation_kind}",
                60_000_000,
                evaluation_kind=evaluation_kind,
                bundle_index=bundle_index,
                n=0.4,
                revision=revision,
            ),
        )
        before = component_fingerprint(component)
        with pytest.raises(ValueError):
            handle_signal(
                component,
                make_signal_event(
                    60,
                    60_000_000,
                    s=1,
                    phase="bundle_0_discard",
                    bundle_index=0,
                    n_current=0.4,
                    n_baseline_session=0.4,
                    revision=revision,
                    latest_evaluation_id=f"session-001-first-{revision}-{evaluation_kind}",
                    session_status="active",
                ),
            )
        assert component_fingerprint(component) == before


@pytest.mark.parametrize(
    "failure",
    ("duplicate-id", "duplicate-revision", "backward-time", "processed"),
)
def test_component_level_evaluation_failures_are_atomic(failure: str) -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    if failure == "processed":
        apply_baseline(component)
        event = make_evaluation_event(
            "session-001-repeat-revision",
            61_000_000,
            n=0.4,
            revision=1,
        )
    else:
        handle_evaluation(component, make_evaluation_event())
        if failure == "duplicate-id":
            event = make_evaluation_event()
        elif failure == "duplicate-revision":
            event = make_evaluation_event(
                "session-001-other-baseline",
                61_000_000,
                n=0.4,
                revision=1,
            )
        else:
            event = make_evaluation_event(
                "session-001-bundle-0",
                59_000_000,
                evaluation_kind="bundle",
                bundle_index=0,
                n=0.5,
                revision=2,
            )
    before = component_fingerprint(component)

    with pytest.raises(ValueError):
        handle_evaluation(component, event)

    assert component_fingerprint(component) == before


def test_snapshot_and_records_are_frozen_and_collections_are_detached_tuples() -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    apply_complete_revision_sequence(component)
    snapshot = component.snapshot()
    first_records = component.first_round_records()
    update_records = component.evaluation_update_records()

    assert isinstance(first_records, tuple)
    assert isinstance(update_records, tuple)
    assert isinstance(snapshot.k_anchor, tuple)
    assert isinstance(snapshot.k_current, tuple)
    assert isinstance(snapshot.b, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.nd = 0.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        first_records[0].w = 0.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        update_records[0].applied = False  # type: ignore[misc]


def test_reset_clears_all_state_and_reproduces_records_and_digests() -> None:
    component = SingleDigitalLifeComponent(digital_life_config_for_role("green"))
    apply_complete_revision_sequence(component)
    expected = component_fingerprint(component)

    component.reset()

    snapshot = component.snapshot()
    assert snapshot.n_current is None
    assert snapshot.n_baseline_session is None
    assert not snapshot.baseline_initialized
    assert snapshot.nd == snapshot.w == 0.5
    assert snapshot.p == 1.0
    assert snapshot.e == 0.0
    assert snapshot.q == 0.5
    assert snapshot.v is None
    assert snapshot.tau is None
    assert snapshot.last_signal_index is None
    assert snapshot.last_revision == 0
    assert snapshot.first_round_count == 0
    assert snapshot.evaluation_update_count == 0
    assert snapshot.new_valid_evaluation_count == 0
    assert snapshot.g_status == "not_connected"
    assert not snapshot.second_round_connected
    assert snapshot.touch_dispatched_count == 0
    assert component.first_round_records() == ()
    assert component.evaluation_update_records() == ()

    apply_complete_revision_sequence(component)
    assert component_fingerprint(component) == expected
