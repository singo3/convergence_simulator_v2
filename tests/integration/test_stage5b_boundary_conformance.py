"""Focused Stage 5B formal-boundary and exported-value conformance tests."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.connected_component import (
    ConnectedDigitalLifeComponent,
)
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
from symbiotic_sim_v2.garden.output_layer.component import GardenOutputComponent
from symbiotic_sim_v2.garden.output_layer.config import GardenOutputConfig
from symbiotic_sim_v2.garden.output_layer.diagnostics import (
    export_qualification_records_csv,
    export_qualified_b_records_csv,
    export_touch_records_csv,
)
from symbiotic_sim_v2.garden.output_layer.events import (
    DIGITAL_LIFE_TOUCH_EVENT_PRIORITY,
    DIGITAL_LIFE_TOUCH_EVENT_SOURCE,
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    GARDEN_OUTPUT_EVENT_SOURCE,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE,
    GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
)
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    create_three_digital_life_competition_simulation,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler

BASELINE_ID = "test-baseline"
BASELINE_N = 0.2


@dataclass(frozen=True, slots=True)
class EmptyScenario:
    start_time_us: int = 0
    end_time_us: int = 300_000_000

    def schedule(self, _scheduler: EventScheduler) -> None:
        return None


def evaluation_event(
    *,
    evaluation_id: str,
    time_us: int,
    evaluation_kind: str,
    bundle_index: int | None,
    quality: str,
    is_valid: bool,
    n: float | None,
    revision: int,
) -> SimulationEvent:
    return SimulationEvent(
        event_id=f"evaluation-{evaluation_id}",
        event_type=GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
        source=GARDEN_INPUT_EVENT_SOURCE,
        scheduled_time_us=time_us,
        priority=GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
        sequence=revision,
        payload={
            "evaluation_id": evaluation_id,
            "evaluation_kind": evaluation_kind,
            "bundle_index": bundle_index,
            "quality": quality,
            "is_valid": is_valid,
            "n": n,
            "n_revision": revision,
            "baseline_id": BASELINE_ID,
            "schema_version": "garden_evaluation_finalized_event_v1",
        },
    )


def signal_event(
    *,
    signal_index: int,
    time_us: int,
    s: int,
    n_current: float | None,
    revision: int,
    latest_evaluation_id: str | None,
) -> SimulationEvent:
    return SimulationEvent(
        event_id=f"signal-{signal_index}",
        event_type=GARDEN_INPUT_SIGNAL_EVENT_TYPE,
        source=GARDEN_INPUT_EVENT_SOURCE,
        scheduled_time_us=time_us,
        priority=GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
        sequence=10_000 + signal_index,
        payload={
            "signal_index": signal_index,
            "signal_time_us": time_us,
            "s": s,
            "phase": "bundle_0_discard" if s else "baseline_evaluation",
            "bundle_index": 0 if s else None,
            "window_role": "discard" if s else "evaluation",
            "n_current": n_current,
            "n_available": n_current is not None,
            "n_baseline_session": BASELINE_N if n_current is not None else None,
            "baseline_available": n_current is not None,
            "latest_valid_evaluation_id": latest_evaluation_id,
            "valid_evaluation_revision": revision,
            "session_status": "active" if s else "baseline",
            "schema_version": "garden_input_signal_event_v1",
        },
    )


def feedback_event(
    *,
    signal_index: int,
    signal_time_us: int,
    recipient: str,
    holder: str | None,
    returned_b: tuple[float, float, float, float] | None,
    s: int = 1,
    attribution_source: str = "current_signal_touch",
    closing: bool = False,
    event_id_suffix: str = "",
) -> SimulationEvent:
    return SimulationEvent(
        event_id=f"feedback-{signal_index}-{recipient}{event_id_suffix}",
        event_type=GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
        source=GARDEN_OUTPUT_EVENT_SOURCE,
        scheduled_time_us=signal_time_us + (999_999 if s else 0),
        priority=GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
        sequence=20_000 + signal_index,
        payload={
            "garden_id": "relax-with-light",
            "recipient_digital_life_id": recipient,
            "signal_index": signal_index,
            "signal_time_us": signal_time_us,
            "s": s,
            "qualification_holder_id": holder,
            "returned_b_f": None if returned_b is None else returned_b[0],
            "returned_b_a": None if returned_b is None else returned_b[1],
            "returned_b_t": None if returned_b is None else returned_b[2],
            "returned_b_d": None if returned_b is None else returned_b[3],
            "attribution_source": attribution_source,
            "closing_evaluation_attribution": closing,
            "schema_version": "garden_interoceptive_feedback_event_v1",
        },
    )


def apply_baseline(
    component: ConnectedDigitalLifeComponent,
    engine: SimulationEngine,
) -> tuple[SimulationEvent, tuple[float, float, float, float]]:
    time_us = 60_000_000
    component.handle_evaluation_finalized(
        evaluation_event(
            evaluation_id=BASELINE_ID,
            time_us=time_us,
            evaluation_kind="baseline",
            bundle_index=None,
            quality="valid",
            is_valid=True,
            n=BASELINE_N,
            revision=1,
        ),
        engine,
    )
    signal = signal_event(
        signal_index=60,
        time_us=time_us,
        s=1,
        n_current=BASELINE_N,
        revision=1,
        latest_evaluation_id=BASELINE_ID,
    )
    intent = component.begin_signal(signal, engine)
    assert intent is not None
    component.mark_touch_dispatched(60, time_us + 500_000)
    return signal, intent.b


@pytest.mark.parametrize("failure", ("wrong-recipient", "returned-b-mismatch"))
def test_actual_connected_feedback_rejection_is_atomic(failure: str) -> None:
    engine = SimulationEngine(EmptyScenario())
    component = ConnectedDigitalLifeComponent(digital_life_config_for_role("green"))
    signal, expected_b = apply_baseline(component, engine)
    initial = component.snapshot()
    recipient = "life-red" if failure == "wrong-recipient" else "life-green"
    returned_b = (
        (expected_b[0], expected_b[1], expected_b[2], expected_b[3] + 0.1)
        if failure == "returned-b-mismatch"
        else expected_b
    )

    with pytest.raises(ValueError):
        component.handle_interoceptive_feedback(
            feedback_event(
                signal_index=60,
                signal_time_us=signal.scheduled_time_us,
                recipient=recipient,
                holder="life-green",
                returned_b=returned_b,
            ),
            engine,
        )

    after_failure = component.snapshot()
    assert component.has_pending_second_round()
    assert component.second_round_records() == ()
    assert after_failure.e == initial.e
    assert after_failure.q == initial.q
    component.handle_interoceptive_feedback(
        feedback_event(
            signal_index=60,
            signal_time_us=signal.scheduled_time_us,
            recipient="life-green",
            holder="life-green",
            returned_b=expected_b,
            event_id_suffix="-retry",
        ),
        engine,
    )
    assert len(component.second_round_records()) == 1


def test_actual_connected_duplicate_feedback_is_rejected_without_second_update() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = ConnectedDigitalLifeComponent(digital_life_config_for_role("green"))
    signal, expected_b = apply_baseline(component, engine)
    feedback = feedback_event(
        signal_index=60,
        signal_time_us=signal.scheduled_time_us,
        recipient="life-green",
        holder="life-green",
        returned_b=expected_b,
    )
    component.handle_interoceptive_feedback(feedback, engine)
    after_first = component.snapshot()

    with pytest.raises(ValueError, match="no pending"):
        component.handle_interoceptive_feedback(feedback, engine)
    assert len(component.second_round_records()) == 1
    assert component.snapshot().e == after_first.e
    assert component.snapshot().q == after_first.q


def test_rejected_evaluation_reaches_actual_second_round_and_never_updates_q() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = ConnectedDigitalLifeComponent(digital_life_config_for_role("green"))
    baseline_signal, baseline_b = apply_baseline(component, engine)
    component.handle_interoceptive_feedback(
        feedback_event(
            signal_index=60,
            signal_time_us=baseline_signal.scheduled_time_us,
            recipient="life-green",
            holder="life-green",
            returned_b=baseline_b,
        ),
        engine,
    )
    q_before = component.snapshot().q

    component.handle_evaluation_finalized(
        evaluation_event(
            evaluation_id="rejected-bundle",
            time_us=120_000_000,
            evaluation_kind="bundle",
            bundle_index=0,
            quality="rejected",
            is_valid=False,
            n=None,
            revision=1,
        ),
        engine,
    )
    signal = signal_event(
        signal_index=120,
        time_us=120_000_000,
        s=1,
        n_current=BASELINE_N,
        revision=1,
        latest_evaluation_id=BASELINE_ID,
    )
    intent = component.begin_signal(signal, engine)
    assert intent is not None
    component.mark_touch_dispatched(120, 120_500_000)
    component.handle_interoceptive_feedback(
        feedback_event(
            signal_index=120,
            signal_time_us=120_000_000,
            recipient="life-green",
            holder="life-green",
            returned_b=intent.b,
        ),
        engine,
    )

    record = component.second_round_records()[-1]
    assert record.evaluation_id == "rejected-bundle"
    assert record.evaluation_quality == "rejected"
    assert not record.is_new_valid_evaluation
    assert not record.q_update_applied
    assert record.q_skip_reason == "evaluation_rejected"
    assert record.q_before == record.q_after == q_before


def test_e_and_q_updates_never_recompute_the_same_signal_first_round() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = ConnectedDigitalLifeComponent(digital_life_config_for_role("green"))
    baseline_signal, baseline_b = apply_baseline(component, engine)
    component.handle_interoceptive_feedback(
        feedback_event(
            signal_index=60,
            signal_time_us=baseline_signal.scheduled_time_us,
            recipient="life-green",
            holder="life-green",
            returned_b=baseline_b,
        ),
        engine,
    )

    component.handle_evaluation_finalized(
        evaluation_event(
            evaluation_id="bundle-0",
            time_us=120_000_000,
            evaluation_kind="bundle",
            bundle_index=0,
            quality="valid",
            is_valid=True,
            n=0.4,
            revision=2,
        ),
        engine,
    )
    signal_120 = signal_event(
        signal_index=120,
        time_us=120_000_000,
        s=1,
        n_current=0.4,
        revision=2,
        latest_evaluation_id="bundle-0",
    )
    intent_120 = component.begin_signal(signal_120, engine)
    assert intent_120 is not None
    component.mark_touch_dispatched(120, 120_500_000)
    first_round_120 = component.first_round_records()[-1]
    assert first_round_120.q == 0.5
    tau_120 = first_round_120.tau
    v_120 = first_round_120.v

    component.handle_interoceptive_feedback(
        feedback_event(
            signal_index=120,
            signal_time_us=120_000_000,
            recipient="life-green",
            holder="life-green",
            returned_b=intent_120.b,
        ),
        engine,
    )
    second_120 = component.second_round_records()[-1]
    assert second_120.q_before == first_round_120.q == 0.5
    assert second_120.q_after == pytest.approx(0.6)
    assert component.first_round_records()[-1] == first_round_120
    assert component.first_round_records()[-1].tau == tau_120
    assert component.first_round_records()[-1].v == v_120

    signal_121 = signal_event(
        signal_index=121,
        time_us=121_000_000,
        s=1,
        n_current=0.4,
        revision=2,
        latest_evaluation_id="bundle-0",
    )
    intent_121 = component.begin_signal(signal_121, engine)
    assert intent_121 is not None
    first_round_121 = component.first_round_records()[-1]
    assert first_round_121.q == pytest.approx(second_120.q_after)
    assert first_round_121.e == pytest.approx(second_120.e_after)
    assert first_round_121.v != v_120
    assert first_round_121.tau != tau_120


def test_pre_session_s_zero_emits_inactive_output_and_three_null_feedbacks() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenOutputComponent(
        GardenOutputConfig(
            expected_digital_life_ids=("life-blue", "life-green", "life-red")
        )
    )
    component.begin_round(
        signal_index=0,
        signal_time_us=0,
        s=0,
        session_status="baseline",
        closing_signal=False,
        round_finalize_time_us=0,
    )
    finalize = SimulationEvent(
        event_id="no-touch-finalize-0",
        event_type=GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
        source=GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE,
        scheduled_time_us=0,
        priority=GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_PRIORITY,
        sequence=0,
        payload={"signal_index": 0, "signal_time_us": 0},
    )
    component.handle_round_finalize(finalize, engine)

    output = component.qualified_b_records()
    feedback = component.feedback_records()
    assert len(output) == 1
    assert output[0].s == 0
    assert not output[0].active
    assert output[0].qualification_holder_id is None
    assert output[0].b is None
    assert len(feedback) == 3
    assert {record.recipient_digital_life_id for record in feedback} == {
        "life-blue",
        "life-green",
        "life-red",
    }
    assert all(record.s == 0 for record in feedback)
    assert all(record.qualification_holder_id is None for record in feedback)
    assert all(record.returned_b is None for record in feedback)
    assert all(record.attribution_source == "none" for record in feedback)
    assert all(not record.closing_evaluation_attribution for record in feedback)


ARBITRARY_IDS = ("participant-a", "participant-b", "participant-c")
ARBITRARY_B = {
    "participant-a": (0.1, 0.2, 0.3, 0.4),
    "participant-b": (0.2, 0.3, 0.4, 0.5),
    "participant-c": (0.3, 0.4, 0.5, 0.6),
}


def _formal_touch(
    life_id: str,
    signal_index: int,
    signal_time_us: int,
    arrival_time_us: int,
    sequence: int,
) -> SimulationEvent:
    b = ARBITRARY_B[life_id]
    return SimulationEvent(
        event_id=f"touch-{signal_index}-{life_id}",
        event_type=DIGITAL_LIFE_TOUCH_EVENT_TYPE,
        source=DIGITAL_LIFE_TOUCH_EVENT_SOURCE,
        scheduled_time_us=arrival_time_us,
        priority=DIGITAL_LIFE_TOUCH_EVENT_PRIORITY,
        sequence=sequence,
        payload={
            "digital_life_id": life_id,
            "signal_index": signal_index,
            "signal_time_us": signal_time_us,
            "b_f": b[0],
            "b_a": b[1],
            "b_t": b[2],
            "b_d": b[3],
            "schema_version": "digital_life_touch_event_v2",
        },
    )


def _active_finalize(signal_index: int, signal_time_us: int) -> SimulationEvent:
    return SimulationEvent(
        event_id=f"finalize-{signal_index}",
        event_type=GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
        source=GARDEN_OUTPUT_RUNTIME_EVENT_SOURCE,
        scheduled_time_us=signal_time_us + 999_999,
        priority=GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY,
        sequence=100 + signal_index,
        payload={"signal_index": signal_index, "signal_time_us": signal_time_us},
    )


def _begin_active(component: GardenOutputComponent, signal_index: int) -> int:
    signal_time_us = signal_index * 1_000_000
    component.begin_round(
        signal_index=signal_index,
        signal_time_us=signal_time_us,
        s=1,
        session_status="active",
        closing_signal=False,
        round_finalize_time_us=signal_time_us + 999_999,
    )
    return signal_time_us


def _establish_arbitrary_holder(
    component: GardenOutputComponent,
    engine: SimulationEngine,
) -> None:
    signal_time_us = _begin_active(component, 60)
    for sequence, (life_id, offset) in enumerate(
        (("participant-b", 100_000), ("participant-a", 200_000), ("participant-c", 300_000))
    ):
        component.handle_touch(
            _formal_touch(
                life_id,
                60,
                signal_time_us,
                signal_time_us + offset,
                sequence,
            ),
            engine,
        )
    component.handle_round_finalize(_active_finalize(60, signal_time_us), engine)


@pytest.mark.parametrize(
    ("arrival_order", "holder_position"),
    (
        (("participant-b", "participant-a", "participant-c"), 1),
        (("participant-a", "participant-b", "participant-c"), 2),
        (("participant-a", "participant-c", "participant-b"), 3),
    ),
)
def test_arbitrary_roster_emits_once_only_when_holder_touch_actually_arrives(
    arrival_order: tuple[str, str, str],
    holder_position: int,
) -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenOutputComponent(
        GardenOutputConfig(
            expected_digital_life_ids=(
                "participant-c",
                "participant-a",
                "participant-b",
            )
        )
    )
    assert component.config.expected_digital_life_ids == ARBITRARY_IDS
    _establish_arbitrary_holder(component, engine)
    initial_output_count = len(component.qualified_b_records())
    signal_time_us = _begin_active(component, 61)

    for position, life_id in enumerate(arrival_order, start=1):
        component.handle_touch(
            _formal_touch(
                life_id,
                61,
                signal_time_us,
                signal_time_us + position * 100_000,
                position,
            ),
            engine,
        )
        expected_count = initial_output_count + int(position >= holder_position)
        assert len(component.qualified_b_records()) == expected_count

    output = component.qualified_b_records()[-1]
    assert output.signal_index == 61
    assert output.qualification_holder_id == "participant-b"
    assert output.b == ARBITRARY_B["participant-b"]
    assert output.effective_time_us == signal_time_us + holder_position * 100_000
    component.handle_round_finalize(_active_finalize(61, signal_time_us), engine)
    assert len(component.qualified_b_records()) == initial_output_count + 1

    scheduled = [
        event
        for event in engine.scheduler.pending_events()
        if event.event_type == GARDEN_QUALIFIED_B_EVENT_TYPE
        and event.payload["signal_index"] == 61
    ]
    assert len(scheduled) == 1
    assert scheduled[0].priority == GARDEN_QUALIFIED_B_EVENT_PRIORITY
    assert scheduled[0].scheduled_time_us == output.effective_time_us
    assert scheduled[0].payload["effective_time_us"] == output.effective_time_us
    assert "role" not in scheduled[0].payload


def test_exact_tie_assigns_lexical_id_and_emits_its_b_at_tie_time() -> None:
    engine = SimulationEngine(EmptyScenario())
    component = GardenOutputComponent(
        GardenOutputConfig(expected_digital_life_ids=tuple(reversed(ARBITRARY_IDS)))
    )
    signal_time_us = _begin_active(component, 60)
    tie_time_us = signal_time_us + 500_000
    for sequence, life_id in enumerate(ARBITRARY_IDS):
        component.handle_touch(
            _formal_touch(life_id, 60, signal_time_us, tie_time_us, sequence),
            engine,
        )
    component.handle_round_finalize(_active_finalize(60, signal_time_us), engine)

    output = component.qualified_b_records()[0]
    assert output.qualification_holder_id == "participant-a"
    assert output.b == ARBITRARY_B["participant-a"]
    assert output.effective_time_us == tie_time_us
    assert len(component.qualified_b_records()) == 1
    assert all(record.exact_time_tie for record in component.touch_records())


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def _optional_text(value: str) -> str | None:
    return None if value == "" else value


def _optional_float(value: str) -> float | None:
    return None if value == "" else float(value)


def test_garden_csv_rows_match_every_immutable_source_record(tmp_path: Path) -> None:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()
    component = simulation.garden_output_component

    touch_rows = _read_csv(
        export_touch_records_csv(tmp_path / "touch.csv", component.touch_records())
    )
    assert len(touch_rows) == len(component.touch_records())
    for row, record in zip(touch_rows, component.touch_records(), strict=True):
        assert int(row["signal_index"]) == record.signal_index
        assert int(row["signal_time_us"]) == record.signal_time_us
        assert int(row["arrival_order"]) == record.arrival_order
        assert int(row["arrival_time_us"]) == record.arrival_time_us
        assert row["digital_life_id"] == record.digital_life_id
        assert "role" not in row
        assert tuple(float(row[name]) for name in ("b_f", "b_a", "b_t", "b_d")) == (
            record.b
        )
        assert _optional_text(row["holder_before"]) == record.holder_before
        assert _optional_text(row["holder_after"]) == record.holder_after
        assert (row["assigned"] == "True") is record.assigned_holder_on_this_touch
        assert (row["exact_time_tie"] == "True") is record.exact_time_tie
        assert row["tie_break_policy"] == record.tie_break_policy
        assert row["touch_schema_version"] == record.schema_version

    qualification_rows = _read_csv(
        export_qualification_records_csv(
            tmp_path / "qualification.csv",
            component.qualification_records(),
        )
    )
    assert len(qualification_rows) == len(component.qualification_records())
    for row, record in zip(
        qualification_rows,
        component.qualification_records(),
        strict=True,
    ):
        assert int(row["signal_index"]) == record.signal_index
        assert int(row["signal_time_us"]) == record.signal_time_us
        assert int(row["s"]) == record.s
        assert _optional_text(row["holder_before"]) == record.holder_before
        assert _optional_text(row["holder_after"]) == record.holder_after
        assert (row["assigned_this_signal"] == "True") is record.assigned_this_signal
        assert _optional_text(row["assignment_touch_id"]) == record.assignment_touch_id
        assert (
            None
            if row["assignment_touch_time_us"] == ""
            else int(row["assignment_touch_time_us"])
        ) == record.assignment_touch_time_us
        assert (row["held_from_previous_signal"] == "True") is (
            record.held_from_previous_signal
        )
        assert (row["released_after_second_round"] == "True") is (
            record.released_after_second_round
        )
        assert tuple(json.loads(row["touch_order"])) == record.touch_order
        assert (row["active_output"] == "True") is record.active_output
        assert tuple(
            _optional_float(row[name])
            for name in (
                "qualified_b_f",
                "qualified_b_a",
                "qualified_b_t",
                "qualified_b_d",
            )
        ) == ((None, None, None, None) if record.qualified_b is None else record.qualified_b)

    output_rows = _read_csv(
        export_qualified_b_records_csv(
            tmp_path / "qualified-b.csv",
            component.qualified_b_records(),
        )
    )
    assert len(output_rows) == len(component.qualified_b_records())
    for row, record in zip(output_rows, component.qualified_b_records(), strict=True):
        assert int(row["signal_index"]) == record.signal_index
        assert int(row["signal_time_us"]) == record.signal_time_us
        assert int(row["effective_time_us"]) == record.effective_time_us
        assert int(row["s"]) == record.s
        assert (row["active"] == "True") is record.active
        assert _optional_text(row["holder_id"]) == record.qualification_holder_id
        assert tuple(
            _optional_float(row[name]) for name in ("b_f", "b_a", "b_t", "b_d")
        ) == ((None, None, None, None) if record.b is None else record.b)
        assert row["emission_policy_version"] == record.emission_policy_version
        assert row["schema_version"] == record.schema_version
