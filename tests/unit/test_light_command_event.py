"""Strict formal LightCommandEvent v1 tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.events import (
    LIGHT_COMMAND_EVENT_PRIORITY,
    LIGHT_COMMAND_EVENT_SOURCE,
    LIGHT_COMMAND_EVENT_TYPE,
    light_command_payload,
    parse_light_command_event,
)
from symbiotic_sim_v2.garden.light_mapper.mapping import map_b_to_i
from symbiotic_sim_v2.garden.light_mapper.records import LightCommandRecord


def command_record(*, active: bool = True) -> LightCommandRecord:
    config = GardenLightMapperConfig()
    mapped = map_b_to_i(
        active=active,
        b=(125 / 360, 0.5, 0.5, 0.5) if active else None,
        config=config,
    )
    return LightCommandRecord(
        command_index=0,
        garden_id=config.garden_id,
        source_signal_index=60 if active else 0,
        source_signal_time_us=60_000_000 if active else 0,
        source_effective_time_us=60_551_540 if active else 0,
        command_effective_time_us=60_551_540 if active else 0,
        active=active,
        qualification_holder_id="life-green" if active else None,
        source_b=mapped.source_b,
        hue_degree=mapped.hue_degree,
        render_hue_degree=mapped.render_hue_degree,
        saturation=mapped.saturation,
        value_center=mapped.value_center,
        value_amplitude=mapped.value_amplitude,
        value_min=mapped.value_min,
        value_max=mapped.value_max,
        blink_bpm=mapped.blink_bpm,
        waveform=mapped.waveform,
        mapping_version=config.mapping_version,
        phase_policy_version=config.phase_policy_version,
        command_hold_policy_version=config.command_hold_policy_version,
        inactive_output_policy_version=config.inactive_output_policy_version,
        schema_version=config.output_schema_version,
    )


def command_event(record: LightCommandRecord, **changes: object) -> SimulationEvent:
    payload = light_command_payload(record)
    payload.update(changes.pop("payload_changes", {}))
    return SimulationEvent(
        event_id="command",
        event_type=changes.pop("event_type", LIGHT_COMMAND_EVENT_TYPE),
        source=changes.pop("source", LIGHT_COMMAND_EVENT_SOURCE),
        scheduled_time_us=changes.pop(
            "scheduled_time_us", record.command_effective_time_us
        ),
        priority=changes.pop("priority", LIGHT_COMMAND_EVENT_PRIORITY),
        sequence=1,
        payload=payload,
    )


def test_active_light_command_round_trips_strict_formal_payload() -> None:
    event = command_event(command_record())
    parsed = parse_light_command_event(event)
    assert event.event_type == "light_command"
    assert event.source == "garden_light_mapper"
    assert event.priority == 66
    assert parsed.active
    assert parsed.qualification_holder_id == "life-green"
    assert parsed.source_b == (125 / 360, 0.5, 0.5, 0.5)
    assert parsed.hue_degree == pytest.approx(125.0)
    assert parsed.blink_bpm == 87.5
    assert not {
        "N",
        "Nd",
        "W",
        "P",
        "V",
        "tau",
        "E",
        "q",
        "k",
        "G",
        "RRI",
        "RMSSD",
    } & set(event.payload)


def test_inactive_light_command_is_null_b_and_black_off() -> None:
    parsed = parse_light_command_event(command_event(command_record(active=False)))
    assert not parsed.active
    assert parsed.qualification_holder_id is parsed.source_b is None
    assert parsed.hue_degree is parsed.render_hue_degree is parsed.blink_bpm is None
    assert parsed.saturation == parsed.value_center == parsed.value_amplitude == 0.0
    assert parsed.value_min == parsed.value_max == 0.0
    assert parsed.waveform == "off"


@pytest.mark.parametrize(
    ("change", "value"),
    (
        ("event_type", "wrong"),
        ("source", "wrong"),
        ("priority", 65),
        ("scheduled_time_us", 60_551_541),
    ),
)
def test_light_command_rejects_wrong_envelope(change: str, value: object) -> None:
    with pytest.raises(ValueError):
        parse_light_command_event(command_event(command_record(), **{change: value}))


def test_light_command_rejects_unknown_missing_or_wrong_schema_fields() -> None:
    record = command_record()
    payload = light_command_payload(record)
    payload["hidden"] = 1
    with pytest.raises(ValueError, match="fields"):
        parse_light_command_event(command_event(record, payload_changes=payload))

    payload = light_command_payload(record)
    del payload["source_b_a"]
    event = command_event(record)
    with pytest.raises(ValueError, match="fields"):
        parse_light_command_event(
            replace(event, payload=payload)
        )

    with pytest.raises(ValueError, match="schema_version"):
        parse_light_command_event(
            command_event(record, payload_changes={"schema_version": "wrong"})
        )


def test_light_command_rejects_active_inactive_field_inconsistency() -> None:
    active = command_record()
    with pytest.raises(ValueError, match="holder"):
        parse_light_command_event(
            command_event(active, payload_changes={"qualification_holder_id": None})
        )
    inactive = command_record(active=False)
    with pytest.raises(ValueError, match="Hue"):
        parse_light_command_event(
            command_event(inactive, payload_changes={"hue_degree": 0.0})
        )
    with pytest.raises(ValueError, match="modulo"):
        parse_light_command_event(
            command_event(active, payload_changes={"render_hue_degree": 200.0})
        )


def test_light_command_payload_is_deeply_immutable_and_finite_json() -> None:
    event = command_event(command_record())
    with pytest.raises(TypeError):
        event.payload["active"] = False  # type: ignore[index]
    with pytest.raises(ValueError, match="finite"):
        parse_light_command_event(
            command_event(command_record(), payload_changes={"blink_bpm": float("nan")})
        )
