"""Subprocess tests for the Stage 3 JSON and diagnostic-CSV CLI boundary."""

from __future__ import annotations

import csv
import json
import subprocess
import sys

from symbiotic_sim_v2.devices.polar_h10.diagnostics import (
    H10_DIAGNOSTIC_CSV_FIELDS,
    H10_DIAGNOSTIC_NOTICE,
)

STAGE_2_HEARTBEAT_DIGEST = (
    "4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765"
)
STAGE_3_MEASUREMENT_DIGEST = (
    "69d645f9e742f8cb9dbb16d9deb65ff10ce77b31c66c35e8fd01cfc5c97272b3"
)
STAGE_3_FULL_EVENT_DIGEST = (
    "d5a174f007a160a1442569b017fe404806db61cc18e0b6a0cda99cd2995b6572"
)

EXPECTED_HEADLESS_KEYS = {
    "project_version",
    "virtual_user_model_version",
    "polar_h10_model_version",
    "rri_event_schema_version",
    "virtual_user_config",
    "polar_h10_config",
    "final_virtual_time_us",
    "final_state",
    "executed_event_count",
    "heartbeat_count",
    "observed_heartbeat_count",
    "rri_measurement_count",
    "first_rri_event_time_us",
    "last_rri_event_time_us",
    "first_measured_rri_us",
    "last_measured_rri_us",
    "mean_measured_rri_ms",
    "minimum_measured_rri_ms",
    "maximum_measured_rri_ms",
    "matched_measurement_count",
    "mismatched_measurement_count",
    "maximum_absolute_error_us",
    "heartbeat_digest",
    "rri_measurement_digest",
    "full_event_digest",
    "diagnostic_notice",
}


def run_h10_cli(*extra_args: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-m", "symbiotic_sim_v2", "--headless-h10-demo", *extra_args],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def test_headless_h10_json_has_exact_schema_counts_versions_and_fixed_digests() -> None:
    output = run_h10_cli()
    assert set(output) == EXPECTED_HEADLESS_KEYS
    assert output["project_version"] == "0.3.0"
    assert output["virtual_user_model_version"] == "baseline_virtual_user_physiology_v0_1"
    assert output["polar_h10_model_version"] == "ideal_polar_h10_rri_device_v0_1"
    assert output["rri_event_schema_version"] == "rri_measurement_event_v1"
    assert output["polar_h10_config"] == {
        "device_id": "polar-h10-sim-001",
        "expected_user_id": "virtual-user-001",
        "model_version": "ideal_polar_h10_rri_device_v0_1",
        "event_schema_version": "rri_measurement_event_v1",
    }
    assert output["final_virtual_time_us"] == 180_000_000
    assert output["final_state"] == "completed"
    assert output["executed_event_count"] == 422
    assert output["heartbeat_count"] == 211
    assert output["observed_heartbeat_count"] == 211
    assert output["rri_measurement_count"] == 210
    assert output["first_rri_event_time_us"] == 855_679
    assert output["last_rri_event_time_us"] == 179_810_668
    assert output["first_measured_rri_us"] == 855_679
    assert output["last_measured_rri_us"] == 844_384
    assert output["matched_measurement_count"] == 210
    assert output["mismatched_measurement_count"] == 0
    assert output["maximum_absolute_error_us"] == 0
    assert output["heartbeat_digest"] == STAGE_2_HEARTBEAT_DIGEST
    assert output["rri_measurement_digest"] == STAGE_3_MEASUREMENT_DIGEST
    assert output["full_event_digest"] == STAGE_3_FULL_EVENT_DIGEST
    assert output["diagnostic_notice"] == H10_DIAGNOSTIC_NOTICE


def test_headless_h10_json_has_raw_rri_statistics_but_no_garden_or_hrv_outputs() -> None:
    output = run_h10_cli()
    assert output["minimum_measured_rri_ms"] <= output["mean_measured_rri_ms"]  # type: ignore[operator]
    assert output["mean_measured_rri_ms"] <= output["maximum_measured_rri_ms"]  # type: ignore[operator]
    forbidden = {
        "rmssd",
        "n",
        "n_baseline",
        "nd",
        "w",
        "artifact",
        "evaluation_quality",
        "baseline",
        "session_signal",
    }
    assert {key.lower() for key in output}.isdisjoint(forbidden)


def test_headless_h10_csv_option_writes_exact_diagnostic_schema_without_changing_results(
    tmp_path,
) -> None:
    output_path = tmp_path / "polar_h10_rri_measurement_diagnostics.csv"
    output = run_h10_cli("--export-h10-csv", str(output_path))
    assert set(output) == EXPECTED_HEADLESS_KEYS | {"diagnostic_csv"}
    assert output["diagnostic_csv"] == str(output_path)
    assert output["rri_measurement_digest"] == STAGE_3_MEASUREMENT_DIGEST
    assert output["full_event_digest"] == STAGE_3_FULL_EVENT_DIGEST
    with output_path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        assert tuple(reader.fieldnames or ()) == H10_DIAGNOSTIC_CSV_FIELDS
    assert len(rows) == 210
    assert all(row["match"] == "True" for row in rows)
    assert all(row["absolute_error_us"] == "0" for row in rows)
    assert all(row["diagnostic_notice"] == H10_DIAGNOSTIC_NOTICE for row in rows)
    assert rows[0]["rri_us"] == rows[0]["diagnostic_true_rri_us"]
    assert rows[-1]["rri_us"] == rows[-1]["diagnostic_true_rri_us"]


def test_headless_h10_csv_directory_reports_the_actual_created_file(tmp_path) -> None:
    output = run_h10_cli("--export-h10-csv", str(tmp_path))
    actual_path = tmp_path / "polar_h10_rri_measurement_diagnostics.csv"
    assert output["diagnostic_csv"] == str(actual_path)
    assert actual_path.exists()


def test_export_h10_csv_requires_the_h10_headless_mode(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "symbiotic_sim_v2",
            "--export-h10-csv",
            str(tmp_path / "should-not-exist.csv"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "--export-h10-csv requires --headless-h10-demo" in completed.stderr
