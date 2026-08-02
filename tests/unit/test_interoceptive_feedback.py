"""Formal qualified-B and recipient-specific feedback boundary tests."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.events import (
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    GARDEN_OUTPUT_EVENT_SOURCE,
    GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
    parse_garden_interoceptive_feedback_event,
    parse_garden_qualified_b_event,
)


def feedback_event(
    *,
    s: int = 1,
    holder: str | None = "life-green",
    returned_b: tuple[float, float, float, float] | None = (0.3, 0.5, 0.5, 0.5),
    attribution_source: str = "current_signal_touch",
    closing: bool = False,
    payload_updates: dict[str, object] | None = None,
) -> SimulationEvent:
    payload: dict[str, object] = {
        "garden_id": "relax-with-light",
        "recipient_digital_life_id": "life-green",
        "signal_index": 60,
        "signal_time_us": 60_000_000,
        "s": s,
        "qualification_holder_id": holder,
        "returned_b_f": None if returned_b is None else returned_b[0],
        "returned_b_a": None if returned_b is None else returned_b[1],
        "returned_b_t": None if returned_b is None else returned_b[2],
        "returned_b_d": None if returned_b is None else returned_b[3],
        "attribution_source": attribution_source,
        "closing_evaluation_attribution": closing,
        "schema_version": "garden_interoceptive_feedback_event_v1",
    }
    payload.update(payload_updates or {})
    return SimulationEvent(
        event_id="feedback",
        event_type=GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
        source=GARDEN_OUTPUT_EVENT_SOURCE,
        scheduled_time_us=60_999_999,
        priority=GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
        sequence=0,
        payload=payload,
    )


def test_feedback_parser_returns_only_recipient_holder_and_own_b_boundary() -> None:
    parsed = parse_garden_interoceptive_feedback_event(feedback_event())

    assert parsed.recipient_digital_life_id == "life-green"
    assert parsed.qualification_holder_id == "life-green"
    assert parsed.returned_b == (0.3, 0.5, 0.5, 0.5)
    assert parsed.attribution_source == "current_signal_touch"
    assert not hasattr(parsed, "g")
    assert not hasattr(parsed, "touch_order")


def test_inactive_and_closing_feedback_contracts_are_distinct() -> None:
    inactive = parse_garden_interoceptive_feedback_event(
        feedback_event(
            s=0,
            holder=None,
            returned_b=None,
            attribution_source="none",
        )
    )
    assert inactive.returned_b is None
    assert inactive.qualification_holder_id is None

    closing = parse_garden_interoceptive_feedback_event(
        feedback_event(
            s=0,
            attribution_source="last_active_touch",
            closing=True,
        )
    )
    assert closing.qualification_holder_id == "life-green"
    assert closing.returned_b is not None
    assert closing.closing_evaluation_attribution


@pytest.mark.parametrize(
    "updates",
    (
        {"g": 1},
        {"tau": 0.2},
        {"returned_b_d": None},
        {"qualification_holder_id": None},
        {"schema_version": "future"},
        {"s": True},
        {"closing_evaluation_attribution": 1},
    ),
)
def test_feedback_rejects_extra_partial_wrong_version_or_implicit_values(
    updates: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        parse_garden_interoceptive_feedback_event(
            feedback_event(payload_updates=updates)
        )


def test_qualified_b_boundary_is_active_only_with_holder_and_complete_b() -> None:
    event = SimulationEvent(
        event_id="qualified",
        event_type=GARDEN_QUALIFIED_B_EVENT_TYPE,
        source=GARDEN_OUTPUT_EVENT_SOURCE,
        scheduled_time_us=60_999_999,
        priority=GARDEN_QUALIFIED_B_EVENT_PRIORITY,
        sequence=0,
        payload={
            "garden_id": "relax-with-light",
            "signal_index": 60,
            "signal_time_us": 60_000_000,
            "s": 1,
            "active": True,
            "qualification_holder_id": "life-green",
            "b_f": 0.3,
            "b_a": 0.5,
            "b_t": 0.5,
            "b_d": 0.5,
            "schema_version": "garden_qualified_b_event_v1",
        },
    )

    parsed = parse_garden_qualified_b_event(event)
    assert parsed.active
    assert parsed.qualification_holder_id == "life-green"
    assert parsed.b == (0.3, 0.5, 0.5, 0.5)
    assert not hasattr(parsed, "hue")
    assert not hasattr(parsed, "bpm")
    assert not hasattr(parsed, "i")
