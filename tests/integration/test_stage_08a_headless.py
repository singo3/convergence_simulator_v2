"""Stage 8A CLI, strict state, CSV, and canonical summary contracts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from symbiotic_sim_v2.convergence import RollingConvergenceConfig
from symbiotic_sim_v2.runtime.multi_session import (
    CONVERGENCE_HISTORY_CSV_FILENAME,
    PATTERN_TRAJECTORY_CSV_FILENAME,
    PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME,
    SESSION_OUTCOMES_CSV_FILENAME,
    STATIONARY_USER_TYPES_CSV_FILENAME,
    USER_TYPE_COMPARISON_CSV_FILENAME,
    MultiSessionRelationMemoryRunner,
    MultiSessionRunnerConfig,
    export_multi_session_state_file,
)

CANONICAL_DIGESTS = {
    "session_outcome_digest": (
        "4e19eb4306b88415795c704e676c31e1f684d4c56405804d05eb599083ec786b"
    ),
    "convergence_history_digest": (
        "15fe1c1e6506d58dab1dc7a79e5afecc08c3bba3bc883ae21df66e70a578d28a"
    ),
    "final_multi_session_state_digest": (
        "0197621dd11d4687cf445ef0117e65a54b089b413222c99ae430230de93717d1"
    ),
}


def _project_root() -> Path:
    return Path(__file__).parents[2]


def _run_cli(*arguments: str) -> dict[str, object]:
    environment = {**os.environ, "PYTHONPATH": str(_project_root() / "src")}
    completed = subprocess.run(
        [sys.executable, "-m", "symbiotic_sim_v2", *arguments],
        cwd=_project_root(),
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


@pytest.fixture(scope="module")
def canonical_cli_result() -> dict[str, object]:
    return _run_cli(
        "--headless-multi-session-convergence-demo",
        "--maximum-sessions",
        "4",
    )


def test_headless_summary_has_versions_convergence_truth_flags_and_digests(
    canonical_cli_result: dict[str, object],
) -> None:
    result = canonical_cli_result
    assert result["project_version"] == "0.10.0"
    assert result["normative_version_tuple"] == {
        "document_version": "v2.0",
        "profile_version": "symbiotic_signal_loop_reference_v1_0",
        "algorithm_version": "adaptive_random_search_confirmed_v1",
        "state_schema_version": "relation_memory_state_v2",
    }
    assert result["runner_version"] == "multi_session_relation_memory_runner_v0_1"
    assert result["stationary_landscape_version"] == (
        "stationary_preference_landscape_v0_1"
    )
    assert result["completed_sessions"] == result["valid_sessions"] == 4
    assert result["invalid_sessions"] == 0
    assert result["first_convergence_session_index"] == 3
    assert result["current_convergence_state"] == "converged_monitoring"
    assert result["currently_converged"] is True
    assert result["dominant_holder_id"] == "life-green"
    assert result["cluster_support"] == 3
    assert result["cluster_member_session_indices"] == [0, 1, 3]
    assert result["outlier_session_indices"] == [2]
    assert result["truth_classification"] == "stable_suboptimal"
    assert {name: result[name] for name in CANONICAL_DIGESTS} == CANONICAL_DIGESTS
    assert len(result["per_session_full_event_digests"]) == 4
    assert len(result["session_outcomes"]) == 4
    assert len(result["convergence_history"]) == 4
    assert len(result["truth_alignment_history"]) == 4
    assert result["stationary_preference"] is True
    assert result["moving_preference"] is False
    assert result["convergence_is_diagnostic_only"] is True
    assert result["exploration_continues_after_convergence"] is True
    assert result["v2_coefficients_modified"] is False
    assert result["multi_session"] is True
    assert result["Monte_Carlo"] is False


def test_state_and_six_csv_exports_do_not_change_the_run(
    canonical_cli_result: dict[str, object],
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    csv_root = tmp_path / "csv"
    exported = _run_cli(
        "--headless-multi-session-convergence-demo",
        "--maximum-sessions",
        "4",
        "--export-final-multi-session-state-json",
        str(state_path),
        "--export-multi-session-csv",
        str(csv_root),
    )
    assert {name: exported[name] for name in CANONICAL_DIGESTS} == {
        name: canonical_cli_result[name] for name in CANONICAL_DIGESTS
    }
    assert state_path.read_bytes().endswith(b"\n")
    assert json.loads(state_path.read_text(encoding="utf-8"))[
        "completed_session_count"
    ] == 4
    expected = {
        STATIONARY_USER_TYPES_CSV_FILENAME,
        SESSION_OUTCOMES_CSV_FILENAME,
        CONVERGENCE_HISTORY_CSV_FILENAME,
        PATTERN_TRAJECTORY_CSV_FILENAME,
        PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME,
        USER_TYPE_COMPARISON_CSV_FILENAME,
    }
    assert {path.name for path in csv_root.iterdir()} == expected
    assert set(exported["diagnostic_csvs"]) == expected


def test_repeat_seed_policy_keeps_physiology_seed_and_not_preference_fixed_only() -> None:
    result = _run_cli(
        "--headless-multi-session-convergence-demo",
        "--maximum-sessions",
        "4",
        "--session-seed-policy",
        "repeat_same_physiology_seed_v0_1",
    )
    seeds = {
        outcome["physiology_root_seed"] for outcome in result["session_outcomes"]
    }
    assert seeds == {20_260_802}
    assert result["user_type_profile"]["user_type_id"] == (
        "green_narrow_moderate"
    )


def test_cli_resume_uses_nondefault_saved_settings_authoritatively(
    tmp_path: Path,
) -> None:
    config = MultiSessionRunnerConfig(
        user_type_id="red_blue_dual_peak",
        master_seed=2**32 - 1,
        session_seed_policy="repeat_same_physiology_seed_v0_1",
        convergence_config=RollingConvergenceConfig(
            hue_tolerance_degree=3.5,
            blink_bpm_tolerance=18.0,
            truth_response_gap_threshold=0.075,
            maximum_sessions=4,
        ),
    )
    paused = MultiSessionRelationMemoryRunner(config)
    paused.run_next_session()
    paused.run_next_session()
    state_path = tmp_path / "nondefault-paused-state.json"
    export_multi_session_state_file(state_path, paused.state())

    resumed = _run_cli(
        "--headless-multi-session-convergence-demo",
        "--initial-multi-session-state-json",
        str(state_path),
    )
    uninterrupted = _run_cli(
        "--headless-multi-session-convergence-demo",
        "--stationary-user-type",
        "red_blue_dual_peak",
        "--maximum-sessions",
        "4",
        "--master-seed",
        str(2**32 - 1),
        "--session-seed-policy",
        "repeat_same_physiology_seed_v0_1",
        "--hue-tolerance-degree",
        "3.5",
        "--blink-bpm-tolerance",
        "18.0",
        "--truth-response-gap-threshold",
        "0.075",
    )

    assert resumed["master_seed"] == 2**32 - 1
    assert resumed["user_type_profile"]["user_type_id"] == "red_blue_dual_peak"
    assert resumed["convergence_config"] == uninterrupted["convergence_config"]
    assert {name: resumed[name] for name in CANONICAL_DIGESTS} == {
        name: uninterrupted[name] for name in CANONICAL_DIGESTS
    }
    assert resumed["per_session_full_event_digests"] == uninterrupted[
        "per_session_full_event_digests"
    ]


def test_cli_comparison_returns_all_fixed_types_and_a_stable_digest() -> None:
    result = _run_cli(
        "--headless-multi-session-convergence-demo",
        "--maximum-sessions",
        "4",
        "--compare-all-stationary-user-types",
    )
    comparison = result["user_type_comparison"]
    assert len(comparison["rows"]) == 6
    assert len(comparison["config_by_user_type"]) == 6
    assert len(result["comparison_digest"]) == 64
