"""Stage 5C CLI, state handoff, CSV, and digest acceptance contracts."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import symbiotic_sim_v2.__main__ as cli
from symbiotic_sim_v2.digital_life.relation_memory.diagnostics import (
    ADAPTIVE_SIGNALS_CSV_FIELDS,
    ADAPTIVE_SIGNALS_CSV_FILENAME,
    INTRINSIC_PROFILES_CSV_FIELDS,
    INTRINSIC_PROFILES_CSV_FILENAME,
    PERSISTENT_STATES_CSV_FIELDS,
    PERSISTENT_STATES_CSV_FILENAME,
    RELATION_TRANSITIONS_CSV_FIELDS,
    RELATION_TRANSITIONS_CSV_FILENAME,
    SESSION_SUMMARY_CSV_FIELDS,
    SESSION_SUMMARY_CSV_FILENAME,
)

LIFE_IDS = {"life-red", "life-green", "life-blue"}
DIGEST_KEYS = (
    "intrinsic_profile_digest",
    "adaptive_signal_digest",
    "relation_memory_transition_digest",
    "final_persistent_state_digest",
    "session_summary_digest",
    "physical_audit_segment_digest",
    "response_dynamics_epoch_digest",
    "full_event_digest",
)


def _project_root() -> Path:
    return Path(__file__).parents[2]


def _run_cli(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONPATH": str(_project_root() / "src")}
    return subprocess.run(
        [sys.executable, "-m", "symbiotic_sim_v2", *arguments],
        cwd=_project_root(),
        env=environment,
        check=check,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture(scope="module")
def standard_exported_run(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[dict[str, Any], Path, Path]:
    root = tmp_path_factory.mktemp("stage05c-standard")
    state_path = root / "final-relation-state.json"
    csv_root = root / "csv"
    completed = _run_cli(
        "--headless-relation-memory-demo",
        "--export-final-relation-state-json",
        str(state_path),
        "--export-relation-memory-csv",
        str(csv_root),
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout), state_path, csv_root


@pytest.fixture(scope="module")
def standard_unexported_run() -> dict[str, Any]:
    completed = _run_cli("--headless-relation-memory-demo")
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def test_standard_off_center_json_versions_flags_counters_and_digests(
    standard_exported_run: tuple[dict[str, Any], Path, Path],
) -> None:
    output, _state_path, _csv_root = standard_exported_run
    required_keys = {
        "project_version",
        "document_version",
        "profile_version",
        "algorithm_version",
        "state_schema_version",
        "adaptive_life_model_version",
        "intrinsic_profile_schema_version",
        "transition_schema_version",
        "persistent_state_schema_version",
        "session_state_schema_version",
        "adaptive_signal_schema_version",
        "relation_update_effective_policy_version",
        "bundle1_reject_policy_version",
        "light_response_preset",
        "final_virtual_time_us",
        "final_state",
        "executed_event_count",
        "holder_id",
        "final_holder_id",
        "initial_persistent_state_by_life",
        "final_persistent_state_by_life",
        "intrinsic_relation_profile_by_life",
        "session_state_by_life",
        "per_life_adaptation_phase",
        "per_life_exploration_decision",
        "per_life_adoption_result",
        "per_life_initial_k_anchor",
        "per_life_k_trial",
        "per_life_final_k_anchor",
        "per_life_trial_count_before",
        "per_life_trial_count_after",
        "per_life_session_count_before",
        "per_life_session_count_after",
        "holder_W_anchor_session",
        "holder_W_trial_1",
        "holder_W_trial_2",
        "holder_sigma",
        "holder_p_explore",
        "holder_u_explore",
        "holder_epsilon_accept",
        "bundle_0_evaluation",
        "bundle_1_evaluation",
        "bundle_2_evaluation",
        "qualified_B_by_bundle",
        "Hue_BPM_by_bundle",
        "relation_memory_transition_count",
        "k_anchor_update_count",
        "candidate_count",
        "single_session_only",
        "convergence_evaluated",
        "multi_session_not_implemented",
        *DIGEST_KEYS,
    }
    assert required_keys <= set(output)
    assert output["project_version"] == "0.9.0"
    assert output["document_version"] == "v2.0"
    assert output["profile_version"] == "symbiotic_signal_loop_reference_v1_0"
    assert output["algorithm_version"] == "adaptive_random_search_confirmed_v1"
    assert output["state_schema_version"] == "relation_memory_state_v2"
    assert output["adaptive_life_model_version"] == ("adaptive_relation_memory_connected_life_v0_1")
    assert output["relation_update_effective_policy_version"] == (
        "relation_update_effective_next_signal_v0_1"
    )
    assert output["light_response_preset"] == "off_center_green"
    assert output["final_virtual_time_us"] == 240_000_000
    assert output["final_state"] == "completed"
    assert output["executed_event_count"] == 3_285
    assert output["holder_id"] == "life-green"
    assert output["final_holder_id"] is None
    assert output["single_session_only"] is True
    assert output["convergence_evaluated"] is False
    assert output["multi_session_not_implemented"] is True

    for field in (
        "initial_persistent_state_by_life",
        "final_persistent_state_by_life",
        "intrinsic_relation_profile_by_life",
        "session_state_by_life",
        "per_life_adaptation_phase",
        "per_life_exploration_decision",
        "per_life_adoption_result",
        "per_life_initial_k_anchor",
        "per_life_k_trial",
        "per_life_final_k_anchor",
        "per_life_trial_count_before",
        "per_life_trial_count_after",
        "per_life_session_count_before",
        "per_life_session_count_after",
    ):
        assert set(output[field]) == LIFE_IDS
    assert set(output["qualified_B_by_bundle"]) == {"0", "1", "2"}
    assert set(output["Hue_BPM_by_bundle"]) == {"0", "1", "2"}
    assert set(output[f"bundle_{index}_evaluation"]["bundle_index"] for index in range(3)) == {
        0,
        1,
        2,
    }
    assert output["per_life_session_count_before"] == dict.fromkeys(LIFE_IDS, 0)
    assert output["per_life_session_count_after"] == dict.fromkeys(LIFE_IDS, 1)
    assert output["per_life_trial_count_before"] == dict.fromkeys(LIFE_IDS, 0)
    assert output["per_life_trial_count_after"] == dict.fromkeys(LIFE_IDS, 0)
    assert output["relation_memory_transition_count"] == 12
    assert output["candidate_count"] == 0
    assert output["k_anchor_update_count"] == 0

    assert {key: output[key] for key in DIGEST_KEYS} == {
        "intrinsic_profile_digest": (
            "90751d6ce46cd810ade11db5bfcc7a26642c264cbd18426e4b4476cc099811cf"
        ),
        "adaptive_signal_digest": (
            "534b24088f5d39d51a11640e659813da322f54f3056ad2ef900cc4aa530873f6"
        ),
        "relation_memory_transition_digest": (
            "a0166bf6c27b9b42629a7bcbf86c5b8ecf0a62f458f1e7ea4b1a98c921e8a999"
        ),
        "final_persistent_state_digest": (
            "7d5b885d843e251171ad18c29e753355ddddf1646a2f7f18b692537d55d0070c"
        ),
        "session_summary_digest": (
            "edd74c6da4136319f46f7ade2c56baf9b887330dd19e634cdce266e42e3669e4"
        ),
        "physical_audit_segment_digest": (
            "f764fcbcc6a4e5bba0db9b080c8056bcaedd49a0a12ac573953593b40f4e4647"
        ),
        "response_dynamics_epoch_digest": (
            "2afb235b6b41b98fd6a34dd1dcc3b1e2365ed93d26e27ee76e71f0cb71689de1"
        ),
        "full_event_digest": ("97289a7bd4672edb5ffc7ecb56543a7602638c1a9b76a0859b81bbef332c67d2"),
    }


def test_state_export_is_strictly_importable_and_roundtrips_as_next_session(
    standard_exported_run: tuple[dict[str, Any], Path, Path],
    tmp_path: Path,
) -> None:
    first, state_path, _csv_root = standard_exported_run
    exported = json.loads(state_path.read_text(encoding="utf-8"))
    assert exported == first["final_persistent_state_by_life"]
    assert state_path.read_bytes().endswith(b"\n")

    next_state_path = tmp_path / "next-final.json"
    completed = _run_cli(
        "--headless-relation-memory-demo",
        "--initial-relation-state-json",
        str(state_path),
        "--export-final-relation-state-json",
        str(next_state_path),
    )
    second = json.loads(completed.stdout)
    assert second["initial_persistent_state_by_life"] == exported
    assert (
        json.loads(next_state_path.read_text(encoding="utf-8"))
        == second["final_persistent_state_by_life"]
    )
    assert second["per_life_session_count_before"] == dict.fromkeys(LIFE_IDS, 1)
    assert second["per_life_session_count_after"] == dict.fromkeys(LIFE_IDS, 2)
    assert second["per_life_trial_count_before"] == first["per_life_trial_count_after"]

    invalid = json.loads(state_path.read_text(encoding="utf-8"))
    invalid["life-green"]["algorithm_version"] = "unknown_algorithm"
    invalid_path = tmp_path / "invalid-version.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
    rejected = _run_cli(
        "--headless-relation-memory-demo",
        "--initial-relation-state-json",
        str(invalid_path),
        check=False,
    )
    assert rejected.returncode != 0
    assert "algorithm_version must be adaptive_random_search_confirmed_v1" in (rejected.stderr)


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def test_five_csv_contracts_and_export_do_not_change_any_digest(
    standard_exported_run: tuple[dict[str, Any], Path, Path],
    standard_unexported_run: dict[str, Any],
) -> None:
    exported, _state_path, csv_root = standard_exported_run
    expected = (
        (INTRINSIC_PROFILES_CSV_FILENAME, INTRINSIC_PROFILES_CSV_FIELDS, 3),
        (RELATION_TRANSITIONS_CSV_FILENAME, RELATION_TRANSITIONS_CSV_FIELDS, 12),
        (ADAPTIVE_SIGNALS_CSV_FILENAME, ADAPTIVE_SIGNALS_CSV_FIELDS, 723),
        (PERSISTENT_STATES_CSV_FILENAME, PERSISTENT_STATES_CSV_FIELDS, 6),
        (SESSION_SUMMARY_CSV_FILENAME, SESSION_SUMMARY_CSV_FIELDS, 3),
    )
    assert {path.name for path in csv_root.iterdir()} == {
        filename for filename, _fields, _count in expected
    }
    for filename, fields, row_count in expected:
        actual_fields, rows = _read_csv(csv_root / filename)
        assert actual_fields == fields
        assert len(rows) == row_count
    assert set(exported["relation_memory_csvs"]) == {
        "intrinsic_profiles",
        "relation_transitions",
        "adaptive_signals",
        "persistent_states",
        "session_summary",
    }
    assert "relation_memory_csvs" not in standard_unexported_run
    assert {key: exported[key] for key in DIGEST_KEYS} == {
        key: standard_unexported_run[key] for key in DIGEST_KEYS
    }


@pytest.mark.parametrize(
    "option",
    (
        "--initial-relation-state-json",
        "--export-final-relation-state-json",
        "--export-relation-memory-csv",
    ),
)
def test_relation_state_and_csv_options_require_relation_memory_mode(
    option: str,
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Stage 5C state/CSV options require --headless-relation-memory-demo",
    ):
        cli.main([option, str(tmp_path / "unused")])


def test_stage7_default_preset_remains_aligned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_stage7(*, preset_name: str, export_csv: Path | None) -> int:
        observed.update(preset_name=preset_name, export_csv=export_csv)
        return 23

    monkeypatch.setattr(cli, "run_headless_light_responsive_user_demo", fake_stage7)
    assert cli.main(["--headless-light-responsive-user-demo"]) == 23
    assert observed == {
        "preset_name": "aligned_green_center",
        "export_csv": None,
    }
