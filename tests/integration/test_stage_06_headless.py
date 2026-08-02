"""Subprocess checks for the Stage 6 JSON and four diagnostic CSVs."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from symbiotic_sim_v2.__main__ import run_headless_light_device_demo
from symbiotic_sim_v2.devices.virtual_light.diagnostics import (
    LIGHT_COMMANDS_CSV_FIELDS,
    LIGHT_COMMANDS_CSV_FILENAME,
    LIGHT_STIMULUS_SEGMENTS_CSV_FIELDS,
    LIGHT_STIMULUS_SEGMENTS_CSV_FILENAME,
    LIGHT_STIMULUS_STATES_CSV_FIELDS,
    LIGHT_STIMULUS_STATES_CSV_FILENAME,
    LIGHT_WAVEFORM_SAMPLES_CSV_FIELDS,
    LIGHT_WAVEFORM_SAMPLES_CSV_FILENAME,
)
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    create_light_feedback_simulation,
)

COMMAND_DIGEST = "306648650d4b286a48b3f9188f7fd640764b05fb135c581c4b9d00b487d06020"
STATE_DIGEST = "1dbf214e1448802a665031f73fb798cdbf04471210aeddf438c68b72b616265e"
SEGMENT_DIGEST = "9dabc1b018b52f9be603ba164655f3c5fa79ff4f6579ae8a6bfd48047d8fd763"
WAVEFORM_DIGEST = "a075f488a588d7d2f78548e4ae339e7cac59c88f8e4508b2a89f0ca6e36cc0c0"
FULL_EVENT_DIGEST = "f2ef166cd2bbea252d2c848b7f67d80cad1840534fe736d792087639b5b2a833"


def _run_cli(export_directory: Path | None = None) -> dict[str, object]:
    command = [
        sys.executable,
        "-m",
        "symbiotic_sim_v2",
        "--headless-light-device-demo",
    ]
    if export_directory is not None:
        command.extend(["--export-light-device-csv", str(export_directory)])
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def test_stage_06_headless_contract_versions_counts_mapping_and_digests() -> None:
    output = _run_cli()

    assert output["project_version"] == "0.7.0"
    assert output["document_version"] == "v2.0"
    assert output["profile_version"] == "symbiotic_signal_loop_reference_v1_0"
    assert output["algorithm_version"] == "adaptive_random_search_confirmed_v1"
    assert output["state_schema_version"] == "relation_memory_state_v2"
    assert output["garden_light_mapper_model_version"] == (
        "relax_with_light_b_to_i_mapper_v0_1"
    )
    assert output["mapping_version"] == "relax_with_light_pc_hsv_sine_mapping_v0_1"
    assert output["light_command_schema_version"] == "light_command_event_v1"
    assert output["virtual_light_device_model_version"] == (
        "virtual_pc_light_device_v0_1"
    )
    assert output["light_stimulus_state_schema_version"] == (
        "light_stimulus_state_event_v1"
    )
    assert output["light_stimulus_segment_schema_version"] == (
        "light_stimulus_segment_v1"
    )
    assert output["phase_policy_version"] == "continuous_phase_integrator_v0_1"
    assert output["command_hold_policy_version"] == "hold_until_next_command_v0_1"
    assert output["inactive_output_policy_version"] == "light_off_black_v0_1"
    assert output["waveform_sample_policy_version"] == (
        "fixed_virtual_grid_20ms_v0_1"
    )

    assert output["final_virtual_time_us"] == 240_000_000
    assert output["final_state"] == "completed"
    assert output["executed_event_count"] == 3_287
    assert output["qualified_b_input_count"] == 241
    assert output["light_command_count"] == 241
    assert output["light_stimulus_state_event_count"] == 241
    assert output["segment_count"] == 240
    assert output["active_command_count"] == 180
    assert output["inactive_command_count"] == 61
    assert output["active_segment_count"] == 180
    assert output["inactive_segment_count"] == 60

    assert output["first_active_effective_time_us"] == 60_551_540
    assert output["last_active_effective_time_us"] == 239_589_850
    assert output["closing_inactive_effective_time_us"] == 240_000_000
    assert output["first_active_holder_id"] == "life-green"
    assert output["first_active_source_b"] == [125.0 / 360.0, 0.5, 0.5, 0.5]
    assert output["first_active_hue_degree"] == 125.0
    assert output["first_active_blink_bpm"] == 87.5
    assert output["first_active_phase_cycles"] == 0.0
    assert output["first_active_value"] == 0.425
    assert output["phase_reset_count"] == 1
    assert output["phase_continuation_count"] == 179
    assert output["equivalent_command_count"] == 238
    assert output["physical_parameter_change_count"] == 3
    assert output["final_active"] is False
    assert output["final_value"] == 0.0
    assert output["final_phase"] is None
    assert output["waveform_sample_interval_us"] == 20_000
    assert output["waveform_sample_count"] == 12_001
    assert output["command_digest"] == COMMAND_DIGEST
    assert output["stimulus_state_digest"] == STATE_DIGEST
    assert output["segment_digest"] == SEGMENT_DIGEST
    assert output["waveform_sample_digest"] == WAVEFORM_DIGEST
    assert output["full_event_digest"] == FULL_EVENT_DIGEST

    encoded = json.dumps(output, ensure_ascii=False).lower()
    for forbidden in (
        "virtualuser light response",
        "rri change",
        "n change",
        "w change",
        '"candidate"',
        '"trial"',
        '"adoption"',
        '"convergence"',
        "physical luminance",
        "cd/m²",
    ):
        assert forbidden not in encoded


def test_stage_06_csvs_have_exact_columns_rows_and_do_not_change_digests(
    tmp_path: Path,
) -> None:
    plain = _run_cli()
    exported = _run_cli(tmp_path)
    paths = exported.pop("diagnostic_csvs")
    assert exported == plain
    assert isinstance(paths, dict)
    assert set(paths) == {
        "commands",
        "stimulus_states",
        "stimulus_segments",
        "waveform_samples",
    }

    expected = (
        (LIGHT_COMMANDS_CSV_FILENAME, LIGHT_COMMANDS_CSV_FIELDS, 241),
        (LIGHT_STIMULUS_STATES_CSV_FILENAME, LIGHT_STIMULUS_STATES_CSV_FIELDS, 241),
        (
            LIGHT_STIMULUS_SEGMENTS_CSV_FILENAME,
            LIGHT_STIMULUS_SEGMENTS_CSV_FIELDS,
            240,
        ),
        (
            LIGHT_WAVEFORM_SAMPLES_CSV_FILENAME,
            LIGHT_WAVEFORM_SAMPLES_CSV_FIELDS,
            12_001,
        ),
    )
    for filename, fields, expected_rows in expected:
        path = tmp_path / filename
        assert path.is_file()
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
        assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == expected_rows


def test_stage_06_headless_helper_uses_shared_factory_digests(
    capsys: pytest.CaptureFixture[str],
) -> None:
    direct = create_light_feedback_simulation()
    direct.engine.run_until_end()

    assert run_headless_light_device_demo() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["command_digest"] == direct.mapper.command_digest()
    assert output["stimulus_state_digest"] == direct.device.stimulus_state_digest()
    assert output["segment_digest"] == direct.device.segment_digest()
    assert output["waveform_sample_digest"] == direct.device.waveform_sample_digest()
    assert output["full_event_digest"] == direct.engine.deterministic_digest()
