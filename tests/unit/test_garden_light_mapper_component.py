"""GardenQualifiedBEvent-v2 to LightCommandEvent-v1 component boundary tests."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.light_mapper.component import GardenLightMapperComponent
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.events import parse_light_command_event
from symbiotic_sim_v2.garden.output_layer.events import (
    GARDEN_OUTPUT_EVENT_SOURCE,
    GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler


@dataclass(frozen=True, slots=True)
class EmptyScenario:
    start_time_us: int = 0
    end_time_us: int = 300_000_000

    def schedule(self, _scheduler: EventScheduler) -> None:
        return None


def qualified_b_event(
    *,
    signal_index: int,
    signal_time_us: int,
    effective_time_us: int,
    active: bool,
    source: str = GARDEN_OUTPUT_EVENT_SOURCE,
    schema_version: str = "garden_qualified_b_event_v2",
) -> SimulationEvent:
    b = (125 / 360, 0.5, 0.5, 0.5) if active else None
    return SimulationEvent(
        event_id=f"qb-{signal_index}",
        event_type=GARDEN_QUALIFIED_B_EVENT_TYPE,
        source=source,
        scheduled_time_us=effective_time_us,
        priority=GARDEN_QUALIFIED_B_EVENT_PRIORITY,
        sequence=signal_index,
        payload={
            "garden_id": "relax-with-light",
            "signal_index": signal_index,
            "signal_time_us": signal_time_us,
            "effective_time_us": effective_time_us,
            "s": int(active),
            "active": active,
            "qualification_holder_id": "life-green" if active else None,
            "b_f": None if b is None else b[0],
            "b_a": None if b is None else b[1],
            "b_t": None if b is None else b[2],
            "b_d": None if b is None else b[3],
            "emission_policy_version": "qualified_b_on_holder_touch_v0_1",
            "schema_version": schema_version,
        },
    )


def test_mapper_emits_exactly_one_priority_66_command_per_formal_qb() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenLightMapperComponent(GardenLightMapperConfig())
    component.handle_garden_qualified_b(
        qualified_b_event(
            signal_index=0,
            signal_time_us=0,
            effective_time_us=0,
            active=False,
        ),
        engine,
    )
    component.handle_garden_qualified_b(
        qualified_b_event(
            signal_index=1,
            signal_time_us=1_000_000,
            effective_time_us=1_551_540,
            active=True,
        ),
        engine,
    )

    pending = engine.scheduler.pending_events()
    assert len(pending) == 2
    commands = tuple(parse_light_command_event(event) for event in pending)
    assert [command.source_signal_index for command in commands] == [0, 1]
    assert commands[0].command_effective_time_us == 0
    assert not commands[0].active
    assert commands[1].command_effective_time_us == 1_551_540
    assert commands[1].active
    assert commands[1].hue_degree == pytest.approx(125.0)
    assert commands[1].blink_bpm == 87.5
    assert len(component.command_records()) == 2
    snapshot = component.snapshot()
    assert snapshot.command_count == 2
    assert snapshot.active_command_count == snapshot.inactive_command_count == 1


@pytest.mark.parametrize(
    ("source", "schema"),
    (("digital_life", "garden_qualified_b_event_v2"), ("garden_output", "v1")),
)
def test_mapper_accepts_only_the_formal_qb_v2_boundary(
    source: str,
    schema: str,
) -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenLightMapperComponent(GardenLightMapperConfig())
    with pytest.raises(ValueError):
        component.handle_garden_qualified_b(
            qualified_b_event(
                signal_index=0,
                signal_time_us=0,
                effective_time_us=0,
                active=False,
                source=source,
                schema_version=schema,
            ),
            engine,
        )
    assert component.command_records() == ()


def test_mapper_rejects_duplicate_reverse_and_skipped_signal_indexes() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenLightMapperComponent(GardenLightMapperConfig())
    first = qualified_b_event(
        signal_index=0,
        signal_time_us=0,
        effective_time_us=0,
        active=False,
    )
    component.handle_garden_qualified_b(first, engine)
    for invalid_index in (0, 2):
        with pytest.raises(ValueError, match="signal_index"):
            component.handle_garden_qualified_b(
                qualified_b_event(
                    signal_index=invalid_index,
                    signal_time_us=1_000_000,
                    effective_time_us=1_000_000,
                    active=False,
                ),
                engine,
            )
    assert len(component.command_records()) == 1


def test_mapper_requires_first_index_zero_and_rejects_index_above_240() -> None:
    engine = SimulationEngine(EmptyScenario())
    for invalid_index in (1, 241):
        component = GardenLightMapperComponent(GardenLightMapperConfig())
        with pytest.raises(ValueError, match="signal_index"):
            component.handle_garden_qualified_b(
                qualified_b_event(
                    signal_index=invalid_index,
                    signal_time_us=invalid_index * 1_000_000,
                    effective_time_us=invalid_index * 1_000_000,
                    active=False,
                ),
                engine,
            )


def test_mapper_rejects_qb_event_and_effective_time_mismatch() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenLightMapperComponent(GardenLightMapperConfig())
    event = qualified_b_event(
        signal_index=0,
        signal_time_us=0,
        effective_time_us=0,
        active=False,
    )
    with pytest.raises(ValueError, match="scheduled"):
        component.handle_garden_qualified_b(
            replace(event, scheduled_time_us=1),
            engine,
        )
    assert component.command_records() == ()


def test_mapper_rejects_foreign_garden_id_without_scheduling() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenLightMapperComponent(GardenLightMapperConfig())
    event = qualified_b_event(
        signal_index=0,
        signal_time_us=0,
        effective_time_us=0,
        active=False,
    )
    payload = event.to_dict()["payload"]
    payload["garden_id"] = "another-garden"
    with pytest.raises(ValueError, match="garden_id"):
        component.handle_garden_qualified_b(
            replace(event, payload=payload),
            engine,
        )
    assert engine.scheduler.pending_count == 0


def test_mapper_rejects_reverse_effective_time_atomically() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenLightMapperComponent(GardenLightMapperConfig())
    component.handle_garden_qualified_b(
        qualified_b_event(
            signal_index=0,
            signal_time_us=100,
            effective_time_us=100,
            active=False,
        ),
        engine,
    )
    digest = component.command_digest()
    with pytest.raises(ValueError, match="effective time"):
        component.handle_garden_qualified_b(
            qualified_b_event(
                signal_index=1,
                signal_time_us=50,
                effective_time_us=50,
                active=False,
            ),
            engine,
        )
    assert len(component.command_records()) == 1
    assert component.command_digest() == digest


def test_mapper_reset_clears_state_and_reproduces_command_digest() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenLightMapperComponent(GardenLightMapperConfig())
    event = qualified_b_event(
        signal_index=0,
        signal_time_us=0,
        effective_time_us=0,
        active=False,
    )
    component.handle_garden_qualified_b(event, engine)
    first_digest = component.command_digest()
    component.reset()
    assert component.command_records() == ()
    assert component.snapshot().current_command is None

    second_engine = SimulationEngine(EmptyScenario())
    component.handle_garden_qualified_b(event, second_engine)
    assert component.command_digest() == first_digest
    assert component.command_records()[0].command_index == 0


def test_mapper_has_no_hidden_life_values_in_record_or_command_payload() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenLightMapperComponent(GardenLightMapperConfig())
    component.handle_garden_qualified_b(
        qualified_b_event(
            signal_index=0,
            signal_time_us=1_000_000,
            effective_time_us=1_551_540,
            active=True,
        ),
        engine,
    )
    record_fields = set(component.command_records()[0].to_dict())
    payload_fields = set(engine.scheduler.pending_events()[0].payload)
    forbidden = {
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
        "touch_order",
        "rri",
        "rmssd",
        "evaluation_result",
    }
    assert record_fields.isdisjoint(forbidden)
    assert payload_fields.isdisjoint(forbidden)
