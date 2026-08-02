"""Subprocess checks for the Stage 5B JSON and four diagnostic CSVs."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from symbiotic_sim_v2.__main__ import run_headless_three_life_competition_demo
from symbiotic_sim_v2.digital_life.second_round_diagnostics import (
    SECOND_ROUND_CSV_FIELDS,
    SECOND_ROUND_CSV_FILENAME,
)
from symbiotic_sim_v2.garden.output_layer.diagnostics import (
    QUALIFICATION_CSV_FIELDS,
    QUALIFICATION_CSV_FILENAME,
    QUALIFIED_B_CSV_FIELDS,
    QUALIFIED_B_CSV_FILENAME,
    TOUCH_CSV_FIELDS,
    TOUCH_CSV_FILENAME,
)
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    create_three_digital_life_competition_simulation,
)

TOUCH_DIGEST = "d2ed8461f5121e52a2e5bf3f482a625de129eaf0e70dcdc81148195102b58db0"
QUALIFICATION_DIGEST = (
    "1dd880f811bf1dd6e56e2842a65d565aa82c7e4fb61cbb4a5b2f123946102eed"
)
QUALIFIED_B_DIGEST = (
    "c918db83d56ce108bc3e714afa12e63c8e5872599832351472d37ffa36c32141"
)
FEEDBACK_DIGEST = (
    "121c9bfdee73a3411864829f146958afc134fc2b08d96c70a71f20d11fc0ff62"
)
FULL_EVENT_DIGEST = (
    "3707317810b37824b2fc9aa830fb42747592b1b526ef855ca62c0f245a09e57e"
)
SECOND_ROUND_DIGESTS = {
    "life-blue": "d299790089141d8285c1de9fcf8e7ce2756f91e2ed3535ab3340d544412866b6",
    "life-green": "cf7ed41be629cc6a7bd9f054c6f2758332facdf31d381acf970a3b4da6e8ebdc",
    "life-red": "d299790089141d8285c1de9fcf8e7ce2756f91e2ed3535ab3340d544412866b6",
}


def run_cli(export_directory: Path | None = None) -> dict[str, object]:
    command = [
        sys.executable,
        "-m",
        "symbiotic_sim_v2",
        "--headless-three-life-competition-demo",
    ]
    if export_directory is not None:
        command.extend(
            ["--export-three-life-competition-csv", str(export_directory)]
        )
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def test_headless_stage5b_contract_counts_state_versions_and_digests() -> None:
    output = run_cli()
    assert output["project_version"] == "0.6.0"
    assert output["document_version"] == "v2.0"
    assert output["profile_version"] == "symbiotic_signal_loop_reference_v1_0"
    assert output["algorithm_version"] == "adaptive_random_search_confirmed_v1"
    assert output["state_schema_version"] == "relation_memory_state_v2"
    assert output["runtime_model_version"] == "three_digital_life_runtime_v0_1"
    assert output["garden_output_model_version"] == (
        "relax_with_light_garden_output_qualification_v0_1"
    )
    assert output["tau_delivery_policy_version"] == (
        "tau_to_microsecond_touch_delivery_v0_1"
    )
    assert output["final_virtual_time_us"] == 240_000_000
    assert output["final_state"] == "completed"
    assert output["executed_event_count"] == 2_805
    assert output["garden_signal_count"] == 241
    assert output["touch_count"] == 540
    assert output["feedback_count"] == 723
    assert output["qualified_b_output_count"] == 241
    assert output["active_output_count"] == 180
    assert output["inactive_output_count"] == 61
    assert output["assignment_count"] == 1
    assert output["release_count"] == 1
    assert output["qualification_holder_id_during_session"] == "life-green"
    assert output["final_qualification_holder_id"] is None
    assert output["holder_assignment_signal_index"] == 60
    assert output["touch_count_by_life"] == {
        "life-blue": 180,
        "life-green": 180,
        "life-red": 180,
    }
    assert output["first_touch_order"] == ["life-green", "life-blue", "life-red"]
    assert output["per_life_first_round_count"] == {
        "life-blue": 241,
        "life-green": 241,
        "life-red": 241,
    }
    assert output["per_life_second_round_count"] == {
        "life-blue": 241,
        "life-green": 241,
        "life-red": 241,
    }
    assert output["per_life_final_G"] == {
        "life-blue": 0,
        "life-green": 0,
        "life-red": 0,
    }
    assert output["per_life_q_update_count"] == {
        "life-blue": 0,
        "life-green": 3,
        "life-red": 0,
    }
    assert output["k_update_count"] == 0
    assert output["touch_digest"] == TOUCH_DIGEST
    assert output["qualification_digest"] == QUALIFICATION_DIGEST
    assert output["qualified_b_digest"] == QUALIFIED_B_DIGEST
    assert output["feedback_digest"] == FEEDBACK_DIGEST
    assert output["second_round_digest_by_life"] == SECOND_ROUND_DIGESTS
    assert output["full_event_digest"] == FULL_EVENT_DIGEST

    encoded = json.dumps(output, ensure_ascii=False).lower()
    for forbidden in (
        '"hue"',
        '"bpm"',
        '"light_waveform"',
        '"i"',
        '"exploration"',
        '"candidate"',
        '"trial"',
        '"adoption"',
    ):
        assert forbidden not in encoded


def test_headless_stage5b_csvs_have_exact_columns_rows_and_do_not_change_digests(
    tmp_path: Path,
) -> None:
    output = run_cli(tmp_path)
    assert output["touch_digest"] == TOUCH_DIGEST
    assert output["qualification_digest"] == QUALIFICATION_DIGEST
    assert output["qualified_b_digest"] == QUALIFIED_B_DIGEST
    assert output["feedback_digest"] == FEEDBACK_DIGEST
    assert output["second_round_digest_by_life"] == SECOND_ROUND_DIGESTS
    assert output["full_event_digest"] == FULL_EVENT_DIGEST

    expected = (
        (TOUCH_CSV_FILENAME, TOUCH_CSV_FIELDS, 540),
        (QUALIFICATION_CSV_FILENAME, QUALIFICATION_CSV_FIELDS, 241),
        (QUALIFIED_B_CSV_FILENAME, QUALIFIED_B_CSV_FIELDS, 241),
        (SECOND_ROUND_CSV_FILENAME, SECOND_ROUND_CSV_FIELDS, 723),
    )
    for filename, fields, row_count in expected:
        path = tmp_path / filename
        assert path.is_file()
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
            assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == row_count

    paths = output["diagnostic_csvs"]
    assert isinstance(paths, dict)
    assert set(paths) == {"touches", "qualification", "qualified_b", "second_round"}


def test_headless_helper_and_shared_factory_have_identical_stage5b_digests(
    capsys: pytest.CaptureFixture[str],
) -> None:
    direct = create_three_digital_life_competition_simulation()
    direct.engine.run_until_end()

    assert run_headless_three_life_competition_demo() == 0
    output = json.loads(capsys.readouterr().out)
    garden = direct.garden_output_component
    assert output["touch_digest"] == garden.touch_digest()
    assert output["qualification_digest"] == garden.qualification_digest()
    assert output["qualified_b_digest"] == garden.qualified_b_digest()
    assert output["feedback_digest"] == garden.feedback_digest()
    assert output["second_round_digest_by_life"] == {
        life_id: component.second_round_digest()
        for life_id, component in direct.digital_life_components.items()
    }
    assert output["full_event_digest"] == direct.engine.deterministic_digest()
