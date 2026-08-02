"""Freshness and production agreement for independent Stage 6 vectors."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from symbiotic_sim_v2.devices.virtual_light.config import (
    LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION,
    LIGHT_STIMULUS_STATE_SCHEMA_VERSION,
    VIRTUAL_LIGHT_DEVICE_MODEL_VERSION,
    WAVEFORM_SAMPLE_POLICY_VERSION,
)
from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
)
from symbiotic_sim_v2.devices.virtual_light.phase import phase_cycles_at
from symbiotic_sim_v2.devices.virtual_light.waveform import sine_value
from symbiotic_sim_v2.domain.events import thaw_json
from symbiotic_sim_v2.garden.light_mapper.config import (
    B_TO_I_MAPPING_VERSION,
    COMMAND_HOLD_POLICY_VERSION,
    CONTINUOUS_PHASE_POLICY_VERSION,
    GARDEN_LIGHT_MAPPER_MODEL_VERSION,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_COMMAND_SCHEMA_VERSION,
    GardenLightMapperConfig,
)
from symbiotic_sim_v2.garden.light_mapper.events import (
    LIGHT_COMMAND_EVENT_PRIORITY,
    LIGHT_COMMAND_EVENT_SOURCE,
    LIGHT_COMMAND_EVENT_TYPE,
)
from symbiotic_sim_v2.garden.light_mapper.mapping import map_active_b_to_light
from symbiotic_sim_v2.garden.output_layer.events import (
    GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
)
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    create_light_feedback_simulation,
)


def project_root() -> Path:
    return Path(__file__).parents[2]


def vectors() -> dict[str, object]:
    path = project_root() / "docs" / "conformance" / "stage-06-reference-vectors.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_stage6_reference_file_is_fresh_and_generator_is_production_independent() -> None:
    generator = project_root() / "tools" / "generate_stage_06_reference_vectors.py"
    completed = subprocess.run(
        [sys.executable, str(generator), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == completed.stderr == ""
    assert "symbiotic_sim_v2" not in generator.read_text(encoding="utf-8")


def test_stage6_versions_and_formal_event_contracts_match_fixed_vectors() -> None:
    data = vectors()
    assumptions = data["simulation_assumptions"]
    boundaries = data["formal_boundaries"]
    assert assumptions["project_version"] == "0.7.0"
    assert (
        assumptions["garden_light_mapper_model_version"]
        == GARDEN_LIGHT_MAPPER_MODEL_VERSION
    )
    assert assumptions["mapping_version"] == B_TO_I_MAPPING_VERSION
    assert assumptions["light_command_schema_version"] == LIGHT_COMMAND_SCHEMA_VERSION
    assert (
        assumptions["virtual_light_device_model_version"]
        == VIRTUAL_LIGHT_DEVICE_MODEL_VERSION
    )
    assert (
        assumptions["light_stimulus_state_schema_version"]
        == LIGHT_STIMULUS_STATE_SCHEMA_VERSION
    )
    assert (
        assumptions["light_stimulus_segment_schema_version"]
        == LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION
    )
    assert assumptions["phase_policy_version"] == CONTINUOUS_PHASE_POLICY_VERSION
    assert assumptions["command_hold_policy_version"] == COMMAND_HOLD_POLICY_VERSION
    assert (
        assumptions["inactive_output_policy_version"]
        == INACTIVE_OUTPUT_POLICY_VERSION
    )
    assert (
        assumptions["waveform_sample_policy_version"]
        == WAVEFORM_SAMPLE_POLICY_VERSION
    )
    assert (
        boundaries["qualified_b"]["event_type"],
        boundaries["qualified_b"]["priority"],
    ) == (
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        GARDEN_QUALIFIED_B_EVENT_PRIORITY,
    )
    assert (
        boundaries["light_command"]["event_type"],
        boundaries["light_command"]["source"],
        boundaries["light_command"]["priority"],
    ) == (
        LIGHT_COMMAND_EVENT_TYPE,
        LIGHT_COMMAND_EVENT_SOURCE,
        LIGHT_COMMAND_EVENT_PRIORITY,
    )
    assert (
        boundaries["light_stimulus_state"]["event_type"],
        boundaries["light_stimulus_state"]["source"],
        boundaries["light_stimulus_state"]["priority"],
    ) == (
        LIGHT_STIMULUS_STATE_EVENT_TYPE,
        LIGHT_STIMULUS_STATE_EVENT_SOURCE,
        LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    )


def test_independent_mapping_phase_and_waveform_vectors_match_production() -> None:
    data = vectors()
    mapping = data["mapping_vectors"]
    config = GardenLightMapperConfig()
    for vector in mapping["hue"]:
        result = map_active_b_to_light(
            (vector["f"], 0.5, 0.5, 0.5),
            config,
        )
        assert result.hue_degree == vector["formal_hue_degree"]
        assert result.render_hue_degree == vector["render_hue_degree"]
    for vector in mapping["blink_bpm"]:
        result = map_active_b_to_light(
            (0.5, 0.5, vector["t"], 0.5),
            config,
        )
        assert result.blink_bpm == vector["blink_bpm"]

    invariant = mapping["a_d_invariance"]
    first = map_active_b_to_light(invariant["first_b"], config)
    second = map_active_b_to_light(invariant["second_b"], config)
    assert first.source_b != second.source_b
    assert first.hue_degree == second.hue_degree == invariant["expected_hue_degree"]
    assert first.blink_bpm == second.blink_bpm == invariant["expected_blink_bpm"]

    for vector in data["phase_and_waveform_vectors"]:
        normalized = phase_cycles_at(
            int(vector["phase_cycles"] * 60_000_000),
            start_time_us=0,
            phase_cycles_at_start=0.0,
            blink_bpm=1.0,
        )
        assert normalized == pytest.approx(vector["phase_cycles"] % 1.0)
        assert sine_value(
            vector["phase_cycles"],
            value_center=0.425,
            value_amplitude=0.075,
        ) == pytest.approx(vector["value"], abs=1e-15)


def test_standard_run_matches_fixed_counts_payloads_samples_and_digests() -> None:
    data = vectors()
    expected = data["standard_scenario"]
    boundaries = data["formal_boundaries"]
    fixed_grid = data["fixed_grid"]
    simulation = create_light_feedback_simulation()
    simulation.engine.run_until_end()
    mapper = simulation.mapper
    device = simulation.device
    commands = device.command_records()
    states = device.stimulus_state_records()
    segments = device.stimulus_segments()
    samples = device.waveform_samples()
    events = simulation.engine.executed_events()

    assert len(mapper.command_records()) == expected["qualified_b_input_count"]
    assert len(commands) == expected["light_command_count"]
    assert len(states) == expected["light_stimulus_state_event_count"]
    assert len(segments) == expected["segment_count"]
    assert sum(record.active for record in commands) == expected["active_command_count"]
    assert sum(not record.active for record in commands) == expected[
        "inactive_command_count"
    ]
    assert sum(record.active for record in segments) == expected["active_segment_count"]
    assert sum(not record.active for record in segments) == expected[
        "inactive_segment_count"
    ]
    assert len(events) == expected["executed_event_count"]

    command_event = next(
        event for event in events if event.event_type == LIGHT_COMMAND_EVENT_TYPE
    )
    state_event = next(
        event
        for event in events
        if event.event_type == LIGHT_STIMULUS_STATE_EVENT_TYPE
    )
    assert sorted(thaw_json(command_event.payload)) == boundaries["light_command"][
        "exact_payload_fields_sorted"
    ]
    assert sorted(thaw_json(state_event.payload)) == boundaries[
        "light_stimulus_state"
    ]["exact_payload_fields_sorted"]
    assert {"rgb", "qcolor", "pixel"}.isdisjoint(
        {key.casefold() for key in thaw_json(state_event.payload)}
    )

    active_commands = tuple(record for record in commands if record.active)
    assert active_commands[0].effective_time_us == expected[
        "first_active_effective_time_us"
    ]
    assert active_commands[-1].effective_time_us == expected[
        "last_active_effective_time_us"
    ]
    assert active_commands[0].qualification_holder_id == expected[
        "first_active_holder_id"
    ]
    first_active_state = states[active_commands[0].command_index]
    assert first_active_state.phase_cycles_at_start == expected[
        "first_active_phase_cycles"
    ]
    assert first_active_state.value_at_start == expected["first_active_value"]
    final = device.snapshot()
    assert final.phase_reset_count == expected["phase_reset_count"]
    assert final.phase_continuation_count == expected["phase_continuation_count"]
    assert final.equivalent_command_count == expected["equivalent_command_count"]
    assert final.physical_parameter_change_count == expected[
        "physical_parameter_change_count"
    ]
    assert final.active is expected["final_active"]
    assert final.current_value == expected["final_value"]
    assert final.phase_cycles is expected["final_phase"]

    assert len(samples) == fixed_grid["sample_count"]
    assert simulation.device.config.diagnostic_sample_interval_us == fixed_grid[
        "sample_interval_us"
    ]
    for vector in fixed_grid["samples"]:
        sample = samples[vector["sample_index"]]
        assert sample.time_us == vector["time_us"]
        assert sample.active is vector["active"]
        assert sample.phase_cycles == pytest.approx(vector["phase_cycles"])
        assert sample.value == pytest.approx(vector["value"])
    assert not any(event.event_type == "light_waveform_sample" for event in events)

    assert mapper.command_digest() == device.command_digest() == expected[
        "command_digest"
    ]
    assert device.stimulus_state_digest() == expected["stimulus_state_digest"]
    assert device.segment_digest() == expected["segment_digest"]
    assert device.waveform_sample_digest() == expected["waveform_sample_digest"]
    assert simulation.engine.deterministic_digest() == expected["full_event_digest"]
