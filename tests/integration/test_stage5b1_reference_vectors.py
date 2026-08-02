"""Freshness and production agreement for fixed Stage 5B.1 boundary vectors."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.domain.events import thaw_json
from symbiotic_sim_v2.garden.output_layer.config import (
    DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
    GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION,
    GARDEN_OUTPUT_MODEL_VERSION,
    GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION,
    GARDEN_QUALIFIED_B_SCHEMA_VERSION,
    QUALIFIED_B_EMISSION_POLICY_VERSION,
    GardenOutputConfig,
)
from symbiotic_sim_v2.garden.output_layer.events import (
    DIGITAL_LIFE_TOUCH_EVENT_PRIORITY,
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
    GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
)
from symbiotic_sim_v2.runtime.multi_life.config import (
    TAU_TOUCH_DELIVERY_POLICY_VERSION,
    THREE_DIGITAL_LIFE_RUNTIME_MODEL_VERSION,
    MultiLifeRuntimeConfig,
)
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    create_three_digital_life_competition_simulation,
)


def project_root() -> Path:
    return Path(__file__).parents[2]


def vectors() -> dict[str, object]:
    path = project_root() / "docs" / "conformance" / "stage-05b1-reference-vectors.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_stage5b1_reference_file_is_fresh_and_generator_has_no_production_import() -> None:
    generator = project_root() / "tools" / "generate_stage_05b1_reference_vectors.py"
    completed = subprocess.run(
        [sys.executable, str(generator), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert "symbiotic_sim_v2" not in generator.read_text(encoding="utf-8")


def test_stage5b1_versions_priorities_and_arbitrary_roster_match_fixed_vectors() -> None:
    data = vectors()
    assumptions = data["simulation_assumptions"]
    boundaries = data["formal_boundaries"]
    roster = data["runtime_roster"]

    assert __version__ == "0.7.0"
    assert assumptions["project_version"] == "0.6.1"
    assert assumptions["runtime_model_version"] == THREE_DIGITAL_LIFE_RUNTIME_MODEL_VERSION
    assert assumptions["garden_output_model_version"] == GARDEN_OUTPUT_MODEL_VERSION
    assert assumptions["touch_schema_version"] == DIGITAL_LIFE_TOUCH_SCHEMA_VERSION
    assert assumptions["qualified_b_schema_version"] == GARDEN_QUALIFIED_B_SCHEMA_VERSION
    assert (
        assumptions["qualified_b_emission_policy_version"]
        == QUALIFIED_B_EMISSION_POLICY_VERSION
    )
    assert assumptions["tau_delivery_policy_version"] == TAU_TOUCH_DELIVERY_POLICY_VERSION
    assert (
        assumptions["feedback_schema_version"]
        == GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION
    )
    assert (
        assumptions["qualification_state_schema_version"]
        == GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION
    )
    assert boundaries["touch"]["priority"] == DIGITAL_LIFE_TOUCH_EVENT_PRIORITY
    assert boundaries["qualified_b"]["priority"] == GARDEN_QUALIFIED_B_EVENT_PRIORITY
    assert (
        boundaries["round_finalize_priority"]
        == GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY
    )
    assert boundaries["feedback_priority"] == GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY

    runtime_config = MultiLifeRuntimeConfig(
        expected_digital_life_ids=tuple(roster["injected_ids"])
    )
    garden_config = GardenOutputConfig(
        expected_digital_life_ids=tuple(roster["injected_ids"])
    )
    expected_ids = tuple(roster["expected_normalized_ids"])
    assert runtime_config.expected_digital_life_ids == expected_ids
    assert garden_config.expected_digital_life_ids == expected_ids


def test_standard_fixture_matches_touch_and_qualified_b_timing_vectors() -> None:
    data = vectors()
    boundaries = data["formal_boundaries"]
    timing = data["timing_vectors"]
    expected = data["standard_fixture_regression"]
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()
    garden = simulation.garden_output_component
    snapshot = garden.snapshot()
    touches = garden.touch_records()
    outputs = garden.qualified_b_records()
    events = simulation.engine.executed_events()

    assert simulation.runtime_config.expected_digital_life_ids == (
        simulation.garden_output_config.expected_digital_life_ids
    )
    assert len(touches) == expected["touch_count"]
    assert snapshot.feedback_count == expected["feedback_count"]
    assert len(outputs) == expected["qualified_b_count"]
    assert snapshot.active_output_count == expected["active_output_count"]
    assert snapshot.inactive_output_count == expected["inactive_output_count"]
    assert snapshot.assignment_count == expected["assignment_count"]
    assert snapshot.release_count == expected["release_count"]
    assert snapshot.last_assigned_holder_id == expected["holder_id"]
    assert snapshot.qualification_holder_id == expected["final_holder_id"]
    assert snapshot.qualification_assigned_signal_index == (
        expected["holder_assignment_signal_index"]
    )
    assert snapshot.qualification_assignment_time_us == expected["holder_assignment_time_us"]

    touch_events = tuple(
        event for event in events if event.event_type == DIGITAL_LIFE_TOUCH_EVENT_TYPE
    )
    qualified_events = tuple(
        event for event in events if event.event_type == GARDEN_QUALIFIED_B_EVENT_TYPE
    )
    assert len(touch_events) == expected["touch_count"]
    assert len(qualified_events) == expected["qualified_b_count"]
    assert sorted(thaw_json(touch_events[0].payload)) == boundaries["touch"][
        "exact_payload_fields_sorted"
    ]
    assert sorted(thaw_json(qualified_events[0].payload)) == boundaries["qualified_b"][
        "exact_payload_fields_sorted"
    ]
    touch_keys_casefold = {key.casefold() for key in thaw_json(touch_events[0].payload)}
    assert {
        key.casefold() for key in boundaries["touch"]["forbidden_payload_fields"]
    }.isdisjoint(touch_keys_casefold)

    active = tuple(record for record in outputs if record.active)
    inactive = tuple(record for record in outputs if not record.active)
    assert active[0].effective_time_us == timing["first_active_holder_assignment"][
        "expected_effective_time_us"
    ]
    assert active[0].qualification_holder_id == timing["first_active_holder_assignment"][
        "expected_holder_id"
    ]
    assert active[1].effective_time_us == timing["subsequent_holder_first"][
        "expected_effective_time_us"
    ]
    assert active[-1].effective_time_us == expected[
        "last_active_qualified_b_effective_time_us"
    ]
    assert inactive[0].effective_time_us == timing["baseline_inactive"][
        "expected_effective_time_us"
    ]
    assert outputs[-1].effective_time_us == timing["closing_inactive"][
        "expected_effective_time_us"
    ]

    touches_by_signal_and_id = {
        (record.signal_index, record.digital_life_id): record for record in touches
    }
    assert all(
        record.effective_time_us
        == touches_by_signal_and_id[
            (record.signal_index, record.qualification_holder_id)
        ].arrival_time_us
        for record in active
    )
    assert max(
        record.effective_time_us
        - touches_by_signal_and_id[
            (record.signal_index, record.qualification_holder_id)
        ].arrival_time_us
        for record in active
    ) == expected["holder_touch_to_qualified_b_delay_us_max"]
    assert len({record.signal_index for record in outputs}) == len(outputs)
    assert sum(
        record.effective_time_us == record.signal_time_us + 999_999 for record in active
    ) == expected["active_qualified_b_at_round_finalize_count"]
    assert all(
        event.scheduled_time_us == event.payload["effective_time_us"]
        for event in qualified_events
    )

    closing_types = {
        GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
        "garden_holder_release",
        "simulation_complete",
    }
    closing_priorities = [
        event.priority
        for event in events
        if event.scheduled_time_us == 240_000_000 and event.event_type in closing_types
    ]
    assert closing_priorities == timing["closing_inactive"]["ordered_priorities"]


def test_active_event_order_is_touch_then_output_then_finalize_then_feedback() -> None:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()
    events = simulation.engine.executed_events()
    holder_touch_time = vectors()["timing_vectors"]["first_active_holder_assignment"][
        "expected_effective_time_us"
    ]
    at_holder_touch = [
        (event.priority, event.event_type)
        for event in events
        if event.scheduled_time_us == holder_touch_time
        and event.event_type
        in {DIGITAL_LIFE_TOUCH_EVENT_TYPE, GARDEN_QUALIFIED_B_EVENT_TYPE}
    ]
    at_finalize = [
        (event.priority, event.event_type)
        for event in events
        if event.scheduled_time_us == 60_999_999
        and event.event_type
        in {
            GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
            GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
            GARDEN_QUALIFIED_B_EVENT_TYPE,
        }
    ]

    assert at_holder_touch == [
        (DIGITAL_LIFE_TOUCH_EVENT_PRIORITY, DIGITAL_LIFE_TOUCH_EVENT_TYPE),
        (GARDEN_QUALIFIED_B_EVENT_PRIORITY, GARDEN_QUALIFIED_B_EVENT_TYPE),
    ]
    assert at_finalize == [
        (GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_PRIORITY, GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE),
        *[
            (
                GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_PRIORITY,
                GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
            )
            for _ in range(3)
        ],
    ]
