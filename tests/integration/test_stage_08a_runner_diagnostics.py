"""Stage 8A canonical digests, CSVs, summary, and type comparison."""

from __future__ import annotations

import csv

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
    compare_stationary_user_types,
    convergence_history_digest,
    export_multi_session_diagnostics,
    final_multi_session_state_digest,
    multi_session_summary,
    session_outcome_digest,
    stationary_user_type_digest,
    user_type_comparison_digest,
)
from symbiotic_sim_v2.runtime.multi_session.diagnostics import (
    CONVERGENCE_HISTORY_CSV_FIELDS,
    PATTERN_TRAJECTORY_CSV_FIELDS,
    PERSISTENT_STATE_TRAJECTORY_CSV_FIELDS,
    SESSION_OUTCOMES_CSV_FIELDS,
    STATIONARY_USER_TYPES_CSV_FIELDS,
    USER_TYPE_COMPARISON_CSV_FIELDS,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    stationary_user_type_ids,
)


@pytest.fixture(scope="module")
def completed_runner() -> MultiSessionRelationMemoryRunner:
    runner = MultiSessionRelationMemoryRunner(
        MultiSessionRunnerConfig(
            convergence_config=RollingConvergenceConfig(maximum_sessions=4)
        )
    )
    runner.run_all()
    return runner


@pytest.fixture(scope="module")
def comparison(completed_runner):
    return compare_stationary_user_types(completed_runner.config)


def digests(runner, comparison_value=None):
    state = runner.state()
    return (
        stationary_user_type_digest(),
        session_outcome_digest(state.session_outcomes),
        convergence_history_digest(state.convergence_records),
        final_multi_session_state_digest(state),
        None
        if comparison_value is None
        else user_type_comparison_digest(comparison_value),
    )


def test_summary_contains_required_versions_flags_counts_and_full_event_digests(
    completed_runner,
    comparison,
) -> None:
    state = completed_runner.state()
    summary = multi_session_summary(
        state,
        completed_runner.user_type_profile,
        completed_runner.truth_alignment_records(),
        initial_persistent_state_by_life=(
            completed_runner.initial_persistent_state_by_life()
        ),
        comparison=comparison,
    )

    assert summary["completed_sessions"] == 4
    assert summary["valid_sessions"] == 4
    assert summary["runner_version"] == "multi_session_relation_memory_runner_v0_1"
    assert summary["stationary_landscape_version"] == (
        "stationary_preference_landscape_v0_1"
    )
    assert summary["stationary_preference"] is True
    assert summary["moving_preference"] is False
    assert summary["convergence_is_diagnostic_only"] is True
    assert summary["exploration_continues_after_convergence"] is True
    assert summary["v2_coefficients_modified"] is False
    assert summary["multi_session"] is True
    assert summary["Monte_Carlo"] is False
    assert set(summary["per_session_full_event_digests"]) == {"0", "1", "2", "3"}
    assert summary["comparison_digest"] == user_type_comparison_digest(comparison)


def test_all_six_csvs_have_fixed_names_rows_and_no_digest_side_effect(
    tmp_path,
    completed_runner,
    comparison,
) -> None:
    before = digests(completed_runner, comparison)
    paths = export_multi_session_diagnostics(
        tmp_path,
        completed_runner.state(),
        completed_runner.truth_alignment_records(),
        comparison=comparison,
    )
    after = digests(completed_runner, comparison)

    assert before == after
    assert tuple(path.name for path in paths) == (
        STATIONARY_USER_TYPES_CSV_FILENAME,
        SESSION_OUTCOMES_CSV_FILENAME,
        CONVERGENCE_HISTORY_CSV_FILENAME,
        PATTERN_TRAJECTORY_CSV_FILENAME,
        PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME,
        USER_TYPE_COMPARISON_CSV_FILENAME,
    )
    rows_by_name = {}
    headers_by_name = {}
    for path in paths:
        with path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            rows_by_name[path.name] = tuple(reader)
            headers_by_name[path.name] = tuple(reader.fieldnames or ())
    assert headers_by_name == {
        STATIONARY_USER_TYPES_CSV_FILENAME: STATIONARY_USER_TYPES_CSV_FIELDS,
        SESSION_OUTCOMES_CSV_FILENAME: SESSION_OUTCOMES_CSV_FIELDS,
        CONVERGENCE_HISTORY_CSV_FILENAME: CONVERGENCE_HISTORY_CSV_FIELDS,
        PATTERN_TRAJECTORY_CSV_FILENAME: PATTERN_TRAJECTORY_CSV_FIELDS,
        PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME: (
            PERSISTENT_STATE_TRAJECTORY_CSV_FIELDS
        ),
        USER_TYPE_COMPARISON_CSV_FILENAME: USER_TYPE_COMPARISON_CSV_FIELDS,
    }
    assert len(rows_by_name[STATIONARY_USER_TYPES_CSV_FILENAME]) == 7
    assert len(rows_by_name[SESSION_OUTCOMES_CSV_FILENAME]) == 4
    assert len(rows_by_name[CONVERGENCE_HISTORY_CSV_FILENAME]) == 4
    pattern_rows = rows_by_name[PATTERN_TRAJECTORY_CSV_FILENAME]
    expected_segments = sum(
        len(outcome.bundle_presentations)
        for outcome in completed_runner.session_outcomes()
    )
    assert len(pattern_rows) == 4 + expected_segments
    assert sum(row["point_kind"] == "final_committed" for row in pattern_rows) == 4
    assert sum(
        row["point_kind"] == "bundle_presentation" for row in pattern_rows
    ) == expected_segments
    assert {int(row["bundle_index"]) for row in pattern_rows if row["bundle_index"]} == {
        0,
        1,
        2,
    }
    assert len(rows_by_name[PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME]) == 24
    assert len(rows_by_name[USER_TYPE_COMPARISON_CSV_FILENAME]) == 6

    persistent_rows = rows_by_name[PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME]
    by_key = {
        (int(row["session_index"]), row["state_position"], row["digital_life_id"]): row
        for row in persistent_rows
    }
    for session_index in range(1, 4):
        for life_id in completed_runner.digital_life_ids:
            previous = by_key[(session_index - 1, "final", life_id)]
            current = by_key[(session_index, "initial", life_id)]
            for field in (
                "k_anchor",
                "q",
                "e",
                "trial_count",
                "session_count",
                "profile_version",
                "algorithm_version",
                "state_schema_version",
            ):
                assert current[field] == previous[field]


def test_type_comparison_runs_every_preset_independently_with_same_config(
    completed_runner,
    comparison,
) -> None:
    expected_ids = stationary_user_type_ids()
    assert tuple(row.user_type_id for row in comparison.rows) == expected_ids
    assert tuple(comparison.config_by_user_type) == expected_ids
    assert all(
        config.master_seed == completed_runner.config.master_seed
        and config.session_seed_policy == completed_runner.config.session_seed_policy
        and config.convergence_config == completed_runner.config.convergence_config
        for config in comparison.config_by_user_type.values()
    )
    assert all(row.completed_session_count == 4 for row in comparison.rows)
    assert all(len(row.final_k_anchor_by_life) == 3 for row in comparison.rows)
    flat = next(row for row in comparison.rows if row.user_type_id == "flat_control")
    dual = next(
        row for row in comparison.rows if row.user_type_id == "red_blue_dual_peak"
    )
    assert flat.truth_classification == "no_preference_control"
    assert dual.truth_classification in {
        "not_converged",
        "correct_convergence",
        "stable_suboptimal",
    }
    assert len(user_type_comparison_digest(comparison)) == 64
