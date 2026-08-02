"""Unit tests for immutable device-visible RRI measurement records."""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from symbiotic_sim_v2.devices.polar_h10.records import RriMeasurementRecord

VALID_VALUES = {
    "measurement_index": 0,
    "event_id": "evt-000004",
    "device_id": "polar-h10-sim-001",
    "user_id": "virtual-user-001",
    "previous_beat_index": 0,
    "current_beat_index": 1,
    "previous_heartbeat_time_us": 0,
    "current_heartbeat_time_us": 855_679,
    "rri_us": 855_679,
    "rri_ms": 855.679,
    "event_schema_version": "rri_measurement_event_v1",
}


def make_record(**overrides: object) -> RriMeasurementRecord:
    values = {**VALID_VALUES, **overrides}
    return RriMeasurementRecord(**values)  # type: ignore[arg-type]


def test_record_contains_only_device_observable_fields_and_is_json_serializable() -> None:
    record = make_record()
    assert record.event_time_us == record.current_heartbeat_time_us
    assert record.to_dict() == VALID_VALUES
    assert json.loads(json.dumps(record.to_dict(), allow_nan=False)) == VALID_VALUES
    assert set(RriMeasurementRecord.__dataclass_fields__) == set(VALID_VALUES)
    forbidden = {
        "true_rri_us",
        "true_rri_ms",
        "rmssd",
        "n",
        "nd",
        "w",
        "artifact",
        "respiratory_component_ms",
        "slow_wave_component_ms",
        "correlated_component_ms",
        "beat_jitter_component_ms",
        "clamped",
    }
    assert set(record.to_dict()).isdisjoint(forbidden)


def test_record_is_frozen_and_to_dict_is_detached() -> None:
    record = make_record()
    detached = record.to_dict()
    detached["rri_us"] = 1
    assert record.rri_us == 855_679
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.rri_us = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "exception"),
    (
        ("measurement_index", True, TypeError),
        ("measurement_index", -1, ValueError),
        ("previous_beat_index", 1.0, TypeError),
        ("current_beat_index", -1, ValueError),
        ("previous_heartbeat_time_us", False, TypeError),
        ("current_heartbeat_time_us", -1, ValueError),
        ("rri_us", 855_679.0, TypeError),
        ("rri_us", 0, ValueError),
    ),
)
def test_integer_fields_reject_bool_non_integer_or_negative_values(
    field: str,
    value: object,
    exception: type[Exception],
) -> None:
    with pytest.raises(exception):
        make_record(**{field: value})


@pytest.mark.parametrize("field", ("event_id", "device_id", "user_id", "event_schema_version"))
@pytest.mark.parametrize("value", ("", "  ", None, False, 5))
def test_identifier_fields_reject_empty_or_non_string_values(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        make_record(**{field: value})


@pytest.mark.parametrize(
    ("overrides", "match"),
    (
        ({"current_beat_index": 0}, "beat_index"),
        ({"current_beat_index": 3, "previous_beat_index": 4}, "beat_index"),
        ({"current_heartbeat_time_us": 0}, "heartbeat times"),
        (
            {"previous_heartbeat_time_us": 900_000, "current_heartbeat_time_us": 855_679},
            "heartbeat times",
        ),
        ({"rri_us": 855_678}, "timestamp difference"),
        ({"rri_ms": 855.0}, "rri_us / 1000"),
    ),
)
def test_record_rejects_inconsistent_indices_times_or_interval(
    overrides: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        make_record(**overrides)


@pytest.mark.parametrize("value", (True, "855.679", None))
def test_rri_ms_rejects_implicit_numeric_conversion(value: object) -> None:
    with pytest.raises(TypeError, match="rri_ms"):
        make_record(rri_ms=value)


@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_rri_ms_must_be_finite(value: float) -> None:
    with pytest.raises(ValueError, match="rri_ms"):
        make_record(rri_ms=value)
