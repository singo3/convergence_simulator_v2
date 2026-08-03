"""Subprocess JSON and exact CSV contracts for the Stage 7 demo."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from symbiotic_sim_v2.virtual_user.light_response.diagnostics import (
    LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FIELDS,
    LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FILENAME,
    LIGHT_RESPONSE_SAMPLES_CSV_FIELDS,
    LIGHT_RESPONSE_SAMPLES_CSV_FILENAME,
    LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS,
    LIGHT_RESPONSE_SEGMENTS_CSV_FILENAME,
    LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS,
    LIGHT_RESPONSIVE_HEARTBEATS_CSV_FILENAME,
    LIGHT_STIMULUS_RECEIPTS_CSV_FIELDS,
    LIGHT_STIMULUS_RECEIPTS_CSV_FILENAME,
)


def project_root() -> Path:
    return Path(__file__).parents[2]


def run_stage7(preset: str, export_path: Path | None = None) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "symbiotic_sim_v2",
        "--headless-light-responsive-user-demo",
        "--light-response-preset",
        preset,
    ]
    if export_path is not None:
        command.extend(("--export-light-responsive-user-csv", str(export_path)))
    environment = {**os.environ, "PYTHONPATH": str(project_root() / "src")}
    completed = subprocess.run(
        command,
        cwd=project_root(),
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


@pytest.fixture(scope="module")
def aligned_output() -> dict[str, Any]:
    return run_stage7("aligned_green_center")


@pytest.fixture(scope="module")
def control_output() -> dict[str, Any]:
    return run_stage7("light_insensitive_control")


def test_aligned_headless_json_has_required_versions_counts_and_causality(
    aligned_output: dict[str, Any],
) -> None:
    required = {
        "project_version",
        "document_version",
        "profile_version",
        "algorithm_version",
        "state_schema_version",
        "light_responsive_user_model_version",
        "physical_projection_version",
        "preference_model_version",
        "response_dynamics_version",
        "response_segment_schema_version",
        "response_dynamics_epoch_schema_version",
        "physical_stimulus_change_policy_version",
        "physical_light_parameter_signature_version",
        "segment_split_policy_version",
        "physiology_coupling_version",
        "heartbeat_causality_policy_version",
        "virtual_user_config",
        "light_response_config",
        "preset",
        "final_virtual_time_us",
        "final_state",
        "executed_event_count",
        "light_stimulus_input_count",
        "active_light_input_count",
        "inactive_light_input_count",
        "response_target_change_count",
        "physical_stimulus_change_count",
        "physical_audit_segment_count",
        "response_dynamics_epoch_count",
        "response_segment_count",
        "response_sample_count",
        "first_active_effective_time_us",
        "first_heartbeat_at_or_after_active_time_us",
        "first_light_affected_interval_start_us",
        "first_light_affected_interval_end_us",
        "baseline_evaluation",
        "bundle_0_evaluation",
        "bundle_1_evaluation",
        "bundle_2_evaluation",
        "heartbeat_digest",
        "responsive_diagnostic_digest",
        "light_receipt_digest",
        "physical_audit_segment_digest",
        "response_segment_digest",
        "response_dynamics_epoch_digest",
        "response_sample_digest",
        "full_event_digest",
    }
    assert required <= set(aligned_output)
    assert aligned_output["project_version"] == "0.8.1"
    assert aligned_output["preset"] == "aligned_green_center"
    assert aligned_output["final_virtual_time_us"] == 240_000_000
    assert aligned_output["final_state"] == "completed"
    assert aligned_output["light_stimulus_input_count"] == 241
    assert aligned_output["active_light_input_count"] == 180
    assert aligned_output["inactive_light_input_count"] == 61
    assert aligned_output["response_target_change_count"] == 2
    assert aligned_output["physical_stimulus_change_count"] == 2
    assert aligned_output["physical_audit_segment_count"] == 2
    assert aligned_output["response_dynamics_epoch_count"] == 2
    assert aligned_output["response_segment_count"] == 2
    assert aligned_output["response_sample_count"] == 2_401
    assert aligned_output["first_active_effective_time_us"] == 60_551_540
    assert aligned_output["first_active_hue_degree"] == 125.0
    assert aligned_output["first_active_blink_bpm"] == 87.5
    assert aligned_output["first_active_hue_match"] == 1.0
    assert aligned_output["first_active_bpm_match"] == 1.0
    assert aligned_output["first_active_preference_match"] == 1.0
    assert aligned_output["first_heartbeat_at_or_after_active_time_us"] == (
        aligned_output["first_light_affected_interval_start_us"]
    )
    assert aligned_output["first_light_affected_interval_end_us"] > (
        aligned_output["first_light_affected_interval_start_us"]
    )
    assert aligned_output["response_at_90s"] > 0.95
    assert aligned_output["response_at_120s"] > 0.99
    assert aligned_output["response_at_180s"] > aligned_output["response_at_120s"]
    assert aligned_output["response_at_240s"] > 0.999
    assert aligned_output["heartbeat_count"] == 277
    assert aligned_output["rri_measurement_count"] == 276
    assert aligned_output["artifact_count"] == 0
    assert aligned_output["evaluation_count"] == 4
    assert aligned_output["holder_id"] == "life-green"
    assert aligned_output["final_holder_id"] is None
    assert aligned_output["heartbeat_digest"] == (
        "3392698943c200a9ab08964644ca72d56f50dfc1944c225b8c3e7933c5a229ae"
    )
    assert aligned_output["responsive_diagnostic_digest"] == (
        "f8240cabbc882ceef81b537c29f907b60c23bad3bc207dac3c4a51b52aaca3cd"
    )
    assert aligned_output["light_receipt_digest"] == (
        "8d46a403067232d1d4532ba878d22881ddc2e5f5b7e429394b5d26b02a03e706"
    )
    assert aligned_output["physical_audit_segment_digest"] == (
        "b09c15e82e25ee42eaaea0d374ac7ba041494f59c742fb953ec178a31f5ffe85"
    )
    assert aligned_output["response_segment_digest"] == (
        "b09c15e82e25ee42eaaea0d374ac7ba041494f59c742fb953ec178a31f5ffe85"
    )
    assert aligned_output["response_dynamics_epoch_digest"] == (
        "d1be764aa7ffa60a8545e03e7f1fc853a4a95291a95dad09b873d1b9e2a31916"
    )
    assert aligned_output["response_sample_digest"] == (
        "b230c3d38ca3d1f85ba910c5970f667970c8d6e66533c84b3ecca7abe7c30bb7"
    )
    assert aligned_output["full_event_digest"] == (
        "db9948271c0a664cd990c9954b131ebefc855a553005225241a6f94ac00625bf"
    )


def test_responsive_bundles_rise_over_control_while_baseline_is_identical(
    aligned_output: dict[str, Any],
    control_output: dict[str, Any],
) -> None:
    assert aligned_output["baseline_evaluation"] == control_output[
        "baseline_evaluation"
    ]
    for index in range(3):
        responsive = aligned_output[f"bundle_{index}_evaluation"]
        control = control_output[f"bundle_{index}_evaluation"]
        assert responsive["rmssd_ms"] > control["rmssd_ms"]
        assert responsive["n"] > control["n"]
    assert control_output["heartbeat_count"] == 280
    assert control_output["rri_measurement_count"] == 279
    assert control_output["heartbeat_digest"] == (
        "dfc32d05a372482a81a40ffbb9dc721aed8edcada4709a4dcb86e76719ddf17b"
    )
    assert control_output["full_event_digest"] == (
        "f2ef166cd2bbea252d2c848b7f67d80cad1840534fe736d792087639b5b2a833"
    )
    assert control_output["light_stimulus_input_count"] == 241


def test_off_center_preset_is_fixed_and_lower_than_aligned(
    aligned_output: dict[str, Any],
) -> None:
    output = run_stage7("off_center_green")
    assert output["preset"] == "off_center_green"
    assert output["light_response_config"]["preference_stationary"] is True
    assert output["light_response_config"]["preferred_hue_degree"] == 129.0
    assert output["light_response_config"]["preferred_blink_bpm"] == 125.0
    assert 0.0 < output["first_active_preference_match"] < 1.0
    assert output["first_active_preference_match"] < aligned_output[
        "first_active_preference_match"
    ]


def test_json_excludes_deferred_search_and_medical_claim_fields(
    aligned_output: dict[str, Any],
) -> None:
    serialized = json.dumps(aligned_output, ensure_ascii=False, sort_keys=True)
    forbidden = (
        '"candidate"',
        '"k_trial"',
        '"W_anchor_session"',
        '"adoption"',
        '"convergence"',
        '"moving_preference"',
        '"physical_luminance"',
        '"medical_claims"',
    )
    assert all(term not in serialized for term in forbidden)


def read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def test_exact_csv_contract_rows_and_export_digest_invariance(
    tmp_path: Path,
    aligned_output: dict[str, Any],
) -> None:
    output = run_stage7("aligned_green_center", tmp_path)
    expected = (
        (
            LIGHT_STIMULUS_RECEIPTS_CSV_FILENAME,
            LIGHT_STIMULUS_RECEIPTS_CSV_FIELDS,
            241,
        ),
        (LIGHT_RESPONSE_SEGMENTS_CSV_FILENAME, LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS, 2),
        (
            LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FILENAME,
            LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FIELDS,
            2,
        ),
        (
            LIGHT_RESPONSIVE_HEARTBEATS_CSV_FILENAME,
            LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS,
            277,
        ),
        (LIGHT_RESPONSE_SAMPLES_CSV_FILENAME, LIGHT_RESPONSE_SAMPLES_CSV_FIELDS, 2_401),
    )
    rows_by_name: dict[str, list[dict[str, str]]] = {}
    for filename, fields, row_count in expected:
        actual_fields, rows = read_csv(tmp_path / filename)
        assert actual_fields == fields
        assert len(rows) == row_count
        rows_by_name[filename] = rows
    assert all(
        row["provenance_used_by_physiology"] == "False"
        for row in rows_by_name[LIGHT_STIMULUS_RECEIPTS_CSV_FILENAME]
    )
    digest_keys = (
        "heartbeat_digest",
        "responsive_diagnostic_digest",
        "light_receipt_digest",
        "physical_audit_segment_digest",
        "response_segment_digest",
        "response_dynamics_epoch_digest",
        "response_sample_digest",
        "full_event_digest",
    )
    assert {key: output[key] for key in digest_keys} == {
        key: aligned_output[key] for key in digest_keys
    }
