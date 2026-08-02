"""Unit tests for the Stage 5B integer-microsecond touch policy."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from symbiotic_sim_v2.digital_life.touch_intent import DigitalLifeTouchIntent
from symbiotic_sim_v2.domain.events import thaw_json
from symbiotic_sim_v2.runtime.multi_life.config import MultiLifeRuntimeConfig
from symbiotic_sim_v2.runtime.multi_life.touch_delivery import (
    DIGITAL_LIFE_TOUCH_EVENT_PRIORITY,
    DIGITAL_LIFE_TOUCH_EVENT_SOURCE,
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
    schedule_touch_intent,
    tau_to_touch_offset_us,
    touch_arrival_time_us,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler


@dataclass(frozen=True, slots=True)
class EmptyScenario:
    start_time_us: int = 0
    end_time_us: int = 2_000_000

    def schedule(self, _scheduler: EventScheduler) -> None:
        return None


def touch_intent(*, tau: float = 0.5) -> DigitalLifeTouchIntent:
    return DigitalLifeTouchIntent(
        signal_index=1,
        signal_time_us=1_000_000,
        digital_life_id="life-green",
        role="green",
        b=(0.25, 0.5, 0.75, 0.5),
        tau=tau,
        touch_enabled=True,
    )


def test_tau_policy_exact_boundaries_and_integer_midpoint() -> None:
    assert tau_to_touch_offset_us(0.0) == 1
    assert tau_to_touch_offset_us(1.0) == 999_998
    assert tau_to_touch_offset_us(0.5) == 499_999
    assert touch_arrival_time_us(1_000_000, 0.5) == 1_499_999
    assert isinstance(tau_to_touch_offset_us(0.25), int)


@pytest.mark.parametrize("bad_tau", [True, float("nan"), float("inf"), "0.5"])
def test_tau_policy_rejects_non_finite_boolean_and_non_numeric_values(
    bad_tau: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        tau_to_touch_offset_us(bad_tau)


def test_tau_policy_clips_only_the_logical_tau_boundary() -> None:
    assert tau_to_touch_offset_us(-1.0) == 1
    assert tau_to_touch_offset_us(2.0) == 999_998


def test_formal_touch_event_contains_only_id_role_signal_and_b() -> None:
    engine = SimulationEngine(EmptyScenario())
    event = schedule_touch_intent(engine, touch_intent())

    assert event.event_type == DIGITAL_LIFE_TOUCH_EVENT_TYPE
    assert event.source == DIGITAL_LIFE_TOUCH_EVENT_SOURCE
    assert event.priority == DIGITAL_LIFE_TOUCH_EVENT_PRIORITY
    assert event.scheduled_time_us == 1_499_999
    payload = thaw_json(event.payload)
    assert set(payload) == {
        "digital_life_id",
        "role",
        "signal_index",
        "signal_time_us",
        "b_f",
        "b_a",
        "b_t",
        "b_d",
        "schema_version",
    }
    assert payload["schema_version"] == "digital_life_touch_event_v1"
    assert {
        "p",
        "v",
        "tau",
        "touch_offset_us",
        "w",
        "e",
        "q",
        "k",
        "g",
    }.isdisjoint(payload)
    with pytest.raises(TypeError):
        event.payload["tau"] = 0.5  # type: ignore[index]


def test_disabled_intent_is_never_scheduled() -> None:
    engine = SimulationEngine(EmptyScenario())
    disabled = DigitalLifeTouchIntent(
        signal_index=0,
        signal_time_us=0,
        digital_life_id="life-green",
        role="green",
        b=(0.25, 0.5, 0.75, 0.5),
        tau=None,
        touch_enabled=False,
    )
    with pytest.raises(ValueError, match="disabled"):
        schedule_touch_intent(engine, disabled)
    assert engine.scheduler.pending_count == 0


def test_runtime_config_is_strict_and_round_trips_json() -> None:
    config = MultiLifeRuntimeConfig()
    assert MultiLifeRuntimeConfig.from_json(config.to_json()) == config
    with pytest.raises(ValueError, match="unknown"):
        MultiLifeRuntimeConfig.from_dict(config.to_dict() | {"winner_rule": "minimum_tau"})
    with pytest.raises(ValueError, match="canonical"):
        MultiLifeRuntimeConfig(
            expected_digital_life_ids=("life-red", "life-green", "life-blue")
        )
