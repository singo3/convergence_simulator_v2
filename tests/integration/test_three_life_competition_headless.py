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

TOUCH_DIGEST = "0d5f8671fd3859f74be7c758954952c8976eb02dcea62b7074ec459063a76c75"
QUALIFICATION_DIGEST = (
    "1dd880f811bf1dd6e56e2842a65d565aa82c7e4fb61cbb4a5b2f123946102eed"
)
QUALIFIED_B_DIGEST = (
    "6157d8251af0e0ceb784b664d90d01368b8506efeb37665962244f991b6a57b7"
)
FEEDBACK_DIGEST = (
    "121c9bfdee73a3411864829f146958afc134fc2b08d96c70a71f20d11fc0ff62"
)
FULL_EVENT_DIGEST = (
    "fa68733a98a962fcad7aeb58d7ec12439e860d8d02c43beaae42e345d5a0884f"
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
    assert output["project_version"] == "0.6.1"
    assert output["document_version"] == "v2.0"
    assert output["profile_version"] == "symbiotic_signal_loop_reference_v1_0"
    assert output["algorithm_version"] == "adaptive_random_search_confirmed_v1"
    assert output["state_schema_version"] == "relation_memory_state_v2"
    assert output["runtime_model_version"] == "three_digital_life_runtime_v0_2"
    assert output["garden_output_model_version"] == (
        "relax_with_light_garden_output_qualification_v0_2"
    )
    assert output["tau_delivery_policy_version"] == (
        "tau_to_microsecond_touch_delivery_v0_1"
    )
    assert output["qualified_b_emission_policy_version"] == (
        "qualified_b_on_holder_touch_v0_1"
    )
    assert output["digital_life_touch_schema_version"] == (
        "digital_life_touch_event_v2"
    )
    assert output["garden_qualified_b_schema_version"] == (
        "garden_qualified_b_event_v2"
    )
    assert output["event_schema_versions"]["touch"] == (
        "digital_life_touch_event_v2"
    )
    assert output["event_schema_versions"]["qualified_b"] == (
        "garden_qualified_b_event_v2"
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
    assert output["holder_assignment_time_us"] == 60_551_540
    assert output["first_active_qualified_b_effective_time_us"] == 60_551_540
    assert output["last_active_qualified_b_effective_time_us"] == 239_589_850
    assert output["closing_inactive_effective_time_us"] == 240_000_000
    assert output["holder_touch_to_qualified_b_delay_us_max"] == 0
    assert output["active_qualified_b_at_holder_touch_count"] == 180
    assert output["active_qualified_b_at_round_finalize_count"] == 0
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
    assert output["per_life_final_E"] == {
        "life-blue": 0.0,
        "life-green": 0.14991222526166195,
        "life-red": 0.0,
    }
    assert output["per_life_final_q"] == {
        "life-blue": 0.5,
        "life-green": 0.5041270950772643,
        "life-red": 0.5,
    }
    assert output["per_life_final_k"] == {
        "life-blue": [0.5, 0.5, 0.5, 0.5],
        "life-green": [0.5, 0.5, 0.5, 0.5],
        "life-red": [0.5, 0.5, 0.5, 0.5],
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

        if filename == TOUCH_CSV_FILENAME:
            assert "role" not in (reader.fieldnames or ())
            assert {row["touch_schema_version"] for row in rows} == {
                "digital_life_touch_event_v2"
            }
        if filename == QUALIFIED_B_CSV_FILENAME:
            active_rows = [row for row in rows if row["active"] == "True"]
            inactive_rows = [row for row in rows if row["active"] == "False"]
            assert len(active_rows) == 180
            assert len(inactive_rows) == 61
            assert all(
                int(row["signal_time_us"])
                < int(row["effective_time_us"])
                < int(row["signal_time_us"]) + 1_000_000
                for row in active_rows
            )
            assert all(
                int(row["effective_time_us"]) == int(row["signal_time_us"])
                for row in inactive_rows
            )
            assert {row["emission_policy_version"] for row in rows} == {
                "qualified_b_on_holder_touch_v0_1"
            }
            assert {row["schema_version"] for row in rows} == {
                "garden_qualified_b_event_v2"
            }

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
