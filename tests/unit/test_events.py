"""Unit tests for immutable event values and time conversion helpers."""

from __future__ import annotations

import dataclasses
import json

import pytest

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.simulation.time_utils import format_time_us, seconds_to_us


def make_event(payload=None) -> SimulationEvent:
    return SimulationEvent(
        event_id="evt-test",
        event_type="demo",
        source="test",
        scheduled_time_us=7_300_000,
        priority=20,
        sequence=3,
        payload={} if payload is None else payload,
    )


def test_event_is_deeply_immutable_and_detached() -> None:
    original = {"nested": [1, {"ok": True}]}
    event = make_event(original)
    original["nested"].append(2)
    assert event.to_dict()["payload"] == {"nested": [1, {"ok": True}]}
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.priority = 99  # type: ignore[misc]
    with pytest.raises(TypeError):
        event.payload["new"] = 1  # type: ignore[index]


@pytest.mark.parametrize("payload", [{"bad": {1, 2}}, {"bad": float("nan")}, object()])
def test_payload_must_be_strict_json(payload) -> None:
    with pytest.raises(ValueError, match="JSON"):
        make_event(payload)


def test_event_record_is_json_serializable() -> None:
    event = make_event({"list": [1, 2], "日本語": "値"})
    encoded = json.dumps(event.to_dict(), ensure_ascii=False)
    assert "日本語" in encoded


def test_time_helpers_do_not_accumulate_float_error() -> None:
    assert seconds_to_us(2.5) == 2_500_000
    assert seconds_to_us("7.3") == 7_300_000
    assert sum(seconds_to_us("0.1") for _ in range(10)) == 1_000_000
    assert format_time_us(7_300_000) == "00:00:07.300"


def test_sub_microsecond_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="whole microsecond"):
        seconds_to_us("0.0000001")
