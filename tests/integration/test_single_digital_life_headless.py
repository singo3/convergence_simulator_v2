"""Subprocess checks for the Stage 5A JSON, role presets, and CSV boundary."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys

from symbiotic_sim_v2.digital_life.diagnostics import (
    EVALUATION_UPDATE_CSV_FIELDS,
    EVALUATION_UPDATE_CSV_FILENAME,
    FIRST_ROUND_CSV_FIELDS,
    FIRST_ROUND_CSV_FILENAME,
)
from symbiotic_sim_v2.garden.input_layer.diagnostics import (
    GARDEN_EVALUATION_CSV_FILENAME,
    GARDEN_RRI_CSV_FILENAME,
    GARDEN_SIGNAL_CSV_FILENAME,
)

GREEN_FIRST_ROUND_DIGEST = (
    "661c2c74942d6b217a635fb4f2cb142bee8cff2e0e842cd21ccdd511682028b8"
)
EVALUATION_UPDATE_DIGEST = (
    "f7bf973cc20a2af77ccd7b38fa0e2407801353890a23cc1b3e30e9d7feeba4c3"
)
STAGE_4_FULL_EVENT_DIGEST = (
    "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72"
)


def run_life_cli(*extra_args: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "symbiotic_sim_v2",
            "--headless-single-life-demo",
            *extra_args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def test_headless_life_json_reports_exact_contract_counts_and_digests() -> None:
    output = run_life_cli()
    assert output["project_version"] == "0.5.0"
    assert output["document_version"] == "v2.0"
    assert output["profile_version"] == "symbiotic_signal_loop_reference_v1_0"
    assert output["algorithm_version"] == "adaptive_random_search_confirmed_v1"
    assert output["state_schema_version"] == "relation_memory_state_v2"
    assert output["digital_life_model_version"] == (
        "single_digital_life_first_round_v0_1"
    )
    assert output["digital_life_config_schema_version"] == "digital_life_config_v1"
    assert output["selected_life_config"]["role"] == "green"
    assert output["final_virtual_time_us"] == 240_000_000
    assert output["final_state"] == "completed"
    assert output["executed_event_count"] == 1_059
    assert output["garden_signal_count"] == 241
    assert output["first_round_record_count"] == 241
    assert output["evaluation_update_count"] == 4
    assert output["new_valid_evaluation_count"] == 4
    assert output["baseline_initialized"] is True
    assert output["final_Nd"] == output["final_W"]
    assert output["final_P"] == 1.0
    assert output["final_E"] == 0.0
    assert output["final_q"] == 0.5
    assert output["final_k_anchor"] == [0.5, 0.5, 0.5, 0.5]
    assert output["final_k_current"] == [0.5, 0.5, 0.5, 0.5]
    assert output["final_tau"] is None
    assert output["G_status"] == "not_connected"
    assert output["second_round_connected"] is False
    assert output["touch_dispatched_count"] == 0
    assert output["first_round_digest"] == GREEN_FIRST_ROUND_DIGEST
    assert output["evaluation_update_digest"] == EVALUATION_UPDATE_DIGEST
    assert output["full_event_digest"] == STAGE_4_FULL_EVENT_DIGEST

    encoded = json.dumps(output, ensure_ascii=False).lower()
    for forbidden in (
        '"holder"',
        '"qualification',
        '"touch_order"',
        '"actual_g"',
        '"accepted_candidate"',
        '"k_trial"',
        '"w_anchor"',
        '"light_output"',
    ):
        assert forbidden not in encoded


def test_headless_role_changes_only_life_intrinsics() -> None:
    red = run_life_cli("--life-role", "red")
    green = run_life_cli("--life-role", "green")
    blue = run_life_cli("--life-role", "blue")
    outputs = (red, green, blue)
    assert [output["selected_life_config"]["role"] for output in outputs] == [
        "red",
        "green",
        "blue",
    ]
    assert {output["full_event_digest"] for output in outputs} == {
        STAGE_4_FULL_EVENT_DIGEST
    }
    assert {output["evaluation_update_digest"] for output in outputs} == {
        EVALUATION_UPDATE_DIGEST
    }
    assert len({output["first_round_digest"] for output in outputs}) == 3
    assert len({output["intrinsic_values"]["p_intrinsic"] for output in outputs}) == 3
    assert len({tuple(output["final_B"]) for output in outputs}) == 3


def test_headless_life_csvs_have_exact_columns_and_are_observational(tmp_path) -> None:
    output = run_life_cli("--export-single-life-csv", str(tmp_path))
    assert output["first_round_digest"] == GREEN_FIRST_ROUND_DIGEST
    assert output["evaluation_update_digest"] == EVALUATION_UPDATE_DIGEST
    assert output["full_event_digest"] == STAGE_4_FULL_EVENT_DIGEST

    expected = (
        (
            FIRST_ROUND_CSV_FILENAME,
            FIRST_ROUND_CSV_FIELDS,
            241,
            70_966,
            "10cf8d4b77b6a1f74ed4b5a0fe092c4bbc608276ea94dd9173cac3197faf63ac",
        ),
        (
            EVALUATION_UPDATE_CSV_FILENAME,
            EVALUATION_UPDATE_CSV_FIELDS,
            4,
            772,
            "1983f408976411aa2af23bba00b3ab7562e4a31917c18395d446555bc9919b08",
        ),
    )
    for filename, fields, row_count, byte_count, sha256 in expected:
        path = tmp_path / filename
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
            assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == row_count
        payload = path.read_bytes()
        assert len(payload) == byte_count
        assert hashlib.sha256(payload).hexdigest() == sha256


def test_stage4_csv_bytes_remain_identical_after_stage5a(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "symbiotic_sim_v2",
            "--headless-garden-input-demo",
            "--export-garden-input-csv",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    output = json.loads(completed.stdout)
    assert output["project_version"] == "0.4.0"
    expected = {
        GARDEN_RRI_CSV_FILENAME: (
            55_216,
            "7caa4953887d3dee9b9dbb1ad8ae992a0f5c12ac190cdac24ba1d022985618fc",
        ),
        GARDEN_EVALUATION_CSV_FILENAME: (
            755,
            "e54567bf2257bdf90856b9e8acce5b389e005cdc4ef729b3b71f99a9f9d19865",
        ),
        GARDEN_SIGNAL_CSV_FILENAME: (
            28_376,
            "b694fd74137540e7b6a90563c5a8f5cfa95dc6595ccaaf61220bb03701b7bd17",
        ),
    }
    for filename, (expected_size, expected_sha256) in expected.items():
        payload = (tmp_path / filename).read_bytes()
        assert len(payload) == expected_size
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
