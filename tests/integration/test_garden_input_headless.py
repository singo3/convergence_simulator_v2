"""Subprocess tests for the Stage 4 JSON and three diagnostic CSV boundaries."""

from __future__ import annotations

import csv
import json
import subprocess
import sys

from symbiotic_sim_v2.garden.input_layer.diagnostics import (
    GARDEN_EVALUATION_CSV_FIELDS,
    GARDEN_EVALUATION_CSV_FILENAME,
    GARDEN_RRI_CSV_FIELDS,
    GARDEN_RRI_CSV_FILENAME,
    GARDEN_SIGNAL_CSV_FIELDS,
    GARDEN_SIGNAL_CSV_FILENAME,
)

STAGE_4_ARTIFACT_DIGEST = (
    "4bea74309fcc62922325bd94a6a6a8561daf63740a4fe1b853c9a26f3b6838f1"
)
STAGE_4_EVALUATION_DIGEST = (
    "371f7d7618b8dbc1259f17765409fed1167eaa8fd4bdf62bef743891b726dd1e"
)
STAGE_4_SIGNAL_DIGEST = (
    "0f68cde436e712e7dad5608ad6347af216cee80945ca951404cf511825785add"
)
STAGE_4_FULL_EVENT_DIGEST = (
    "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72"
)


def run_garden_cli(*extra_args: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "symbiotic_sim_v2",
            "--headless-garden-input-demo",
            *extra_args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def test_headless_garden_json_reports_versions_counts_evaluations_and_digests() -> None:
    output = run_garden_cli()
    assert output["project_version"] == "0.4.0"
    assert output["document_version"] == "v2.0"
    assert output["profile_version"] == "symbiotic_signal_loop_reference_v1_0"
    assert output["garden_manifest_version"] == "relax_with_light_garden_manifest_v0_1"
    assert output["garden_input_model_version"] == "relax_with_light_garden_input_v0_1"
    assert output["garden_input_signal_schema_version"] == "garden_input_signal_event_v1"
    assert output["garden_evaluation_schema_version"] == (
        "garden_evaluation_finalized_event_v1"
    )
    assert output["garden_phase_schema_version"] == "garden_phase_event_v1"
    assert output["rri_window_membership_policy"] == "measurement_end_time"
    assert output["baseline_invalid_policy"] == (
        "keep_s_zero_and_skip_main_evaluations"
    )
    assert output["final_virtual_time_us"] == 240_000_000
    assert output["final_state"] == "completed"
    assert output["heartbeat_count"] == 280
    assert output["rri_measurement_count"] == 279
    assert output["garden_signal_count"] == 241
    assert output["phase_event_count"] == 9
    assert output["evaluation_count"] == 4
    assert output["received_rri_count"] == 279
    assert output["valid_rri_count"] == 279
    assert output["artifact_rri_count"] == 0
    assert output["baseline_available"] is True
    assert output["valid_evaluation_revision"] == 4
    assert output["artifact_digest"] == STAGE_4_ARTIFACT_DIGEST
    assert output["evaluation_digest"] == STAGE_4_EVALUATION_DIGEST
    assert output["signal_digest"] == STAGE_4_SIGNAL_DIGEST
    assert output["full_event_digest"] == STAGE_4_FULL_EVENT_DIGEST

    evaluations = output["evaluations"]
    assert isinstance(evaluations, list)
    assert [record["evaluation_id"] for record in evaluations] == [
        "session-001-baseline",
        "session-001-bundle-0",
        "session-001-bundle-1",
        "session-001-bundle-2",
    ]
    assert all(record["quality"] == "valid" for record in evaluations)
    assert all(record["is_valid"] is True for record in evaluations)
    assert all(record["n"] is not None for record in evaluations)


def test_headless_garden_json_has_no_future_stage_outputs() -> None:
    output = run_garden_cli()
    encoded = json.dumps(output, ensure_ascii=False).lower()
    for forbidden_key in (
        '"nd"',
        '"w"',
        '"q"',
        '"e"',
        '"p"',
        '"v"',
        '"b"',
        '"g"',
        '"tau"',
        '"k"',
    ):
        assert forbidden_key not in encoded


def test_headless_garden_csvs_have_exact_columns_rows_and_do_not_change_digests(
    tmp_path,
) -> None:
    output = run_garden_cli("--export-garden-input-csv", str(tmp_path))
    assert output["artifact_digest"] == STAGE_4_ARTIFACT_DIGEST
    assert output["evaluation_digest"] == STAGE_4_EVALUATION_DIGEST
    assert output["signal_digest"] == STAGE_4_SIGNAL_DIGEST
    assert output["full_event_digest"] == STAGE_4_FULL_EVENT_DIGEST

    expected = (
        (GARDEN_RRI_CSV_FILENAME, GARDEN_RRI_CSV_FIELDS, 279),
        (GARDEN_EVALUATION_CSV_FILENAME, GARDEN_EVALUATION_CSV_FIELDS, 4),
        (GARDEN_SIGNAL_CSV_FILENAME, GARDEN_SIGNAL_CSV_FIELDS, 241),
    )
    for filename, fields, row_count in expected:
        with (tmp_path / filename).open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
            assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == row_count
