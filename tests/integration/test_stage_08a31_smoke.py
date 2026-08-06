"""One real 120-session smoke validates the Stage 8A.3.1 deliverables."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import pytest

from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    CONDITION_IDS,
    REFERENCE_ETA,
    REFERENCE_RHO,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.exports import (
    REQUIRED_RESULT_FILENAMES,
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_smoke_completes_exact_actual_and_logical_budgets(stage08a31_real_smoke) -> None:
    summary = stage08a31_real_smoke["summary"]
    progress = stage08a31_real_smoke["progress"]
    assert summary.status == "completed"
    assert summary.completed_actual_simulation_sessions == 120
    assert summary.planned_actual_simulation_sessions == 120
    assert summary.logical_comparison_sessions == 192
    assert summary.completed_jobs == 30
    assert summary.shared_random_participant_jobs == 6
    assert len(progress) == 30


@pytest.mark.parametrize("filename", REQUIRED_RESULT_FILENAMES)
def test_smoke_writes_each_required_artifact(
    stage08a31_real_smoke,
    filename: str,
) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    path = run / filename
    assert path.is_file()
    assert path.stat().st_size > 0


@pytest.mark.parametrize(
    ("filename", "expected"),
    (
        ("conditions.csv", 4),
        ("participant_profiles.csv", 6),
        ("shared_random_sessions.csv", 24),
        ("autonomous_sessions.csv", 96),
        ("logical_session_outcomes.csv", 192),
        ("bundle_outcomes.csv", 576),
        ("arm_pair_differences.csv", 24),
        ("factorial_participant_effects.csv", 42),
        ("factorial_user_type_effects.csv", 21),
        ("factorial_overall_effects.csv", 7),
        ("condition_summary.csv", 4),
    ),
)
def test_smoke_csv_record_count(
    stage08a31_real_smoke,
    filename: str,
    expected: int,
) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    assert len(_rows(run / filename)) == expected


def test_smoke_has_four_conditions_and_two_arms(stage08a31_real_smoke) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    rows = _rows(run / "logical_session_outcomes.csv")
    assert {row["condition_id"] for row in rows} == set(CONDITION_IDS)
    assert {row["arm"] for row in rows} == {
        "autonomous_closed_loop",
        "pure_random_open_loop",
    }
    assert "response_decoupled_yoked_replay" not in {row["arm"] for row in rows}


def test_shared_random_is_physically_executed_once_per_participant(
    stage08a31_real_smoke,
) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    shared = _rows(run / "shared_random_sessions.csv")
    logical = [
        row
        for row in _rows(run / "logical_session_outcomes.csv")
        if row["arm"] == "pure_random_open_loop"
    ]
    assert len(shared) == 6 * 4
    assert len(logical) == 4 * len(shared)
    assert len(list((run / "donor_sequences").glob("*.json"))) == 6
    assert all(row["logical_condition_reference_count"] == "4" for row in shared)
    assert all(row["shared_random_condition_independent"] == "true" for row in shared)


def test_shared_random_physiology_outputs_and_rmssd_match_all_conditions(
    stage08a31_real_smoke,
) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    rows = [
        row
        for row in _rows(run / "logical_session_outcomes.csv")
        if row["arm"] == "pure_random_open_loop"
    ]
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["participant_id"], row["session_index"])].append(row)
    for group in grouped.values():
        assert {row["condition_id"] for row in group} == set(CONDITION_IDS)
        for field in (
            "physiology_seed",
            "baseline_rmssd_ms",
            "bundle_rmssd_ms",
            "bundle_delta_rmssd_ms",
            "bundle_life_ids",
            "bundle_hue_degrees",
            "bundle_blink_bpms",
            "output_sequence_digest",
        ):
            assert len({row[field] for row in group}) == 1


def test_autonomous_and_random_are_participant_seed_paired(
    stage08a31_real_smoke,
) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    rows = _rows(run / "logical_session_outcomes.csv")
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["participant_id"], row["condition_id"], row["session_index"])].append(
            row
        )
    assert all(len(group) == 2 for group in grouped.values())
    assert all(len({row["physiology_seed"] for row in group}) == 1 for group in grouped.values())
    assert all(
        len({row["baseline_rmssd_ms"] for row in group}) == 1 for group in grouped.values()
    )


def test_smoke_conditions_share_eta_rho_and_target(stage08a31_real_smoke) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    rows = _rows(run / "conditions.csv")
    assert {float(row["eta_selected"]) for row in rows} == {REFERENCE_ETA}
    assert {float(row["rho"]) for row in rows} == {REFERENCE_RHO}
    assert {float(row["effective_selected_session_fatigue_target"]) for row in rows} == {
        0.15
    }


def test_smoke_recovery_and_sigma_audits_match_condition_matrix(
    stage08a31_real_smoke,
) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    rows = _rows(run / "autonomous_sessions.csv")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["condition_id"]].append(row)
    assert {row["sigma_multiplier"] for row in grouped[CONDITION_IDS[0]]} <= {"", "1.0"}
    assert {row["sigma_multiplier"] for row in grouped[CONDITION_IDS[1]]} <= {"0.5"}
    assert {row["sigma_multiplier"] for row in grouped[CONDITION_IDS[2]]} <= {"1.0"}
    assert {row["sigma_multiplier"] for row in grouped[CONDITION_IDS[3]]} <= {"0.5"}
    recovery_counts = {
        condition_id: {
            int(row["nonselected_full_recovery_count"])
            for row in grouped[condition_id]
        }
        for condition_id in CONDITION_IDS
    }
    assert recovery_counts == {
        CONDITION_IDS[0]: {0},
        CONDITION_IDS[1]: {0},
        CONDITION_IDS[2]: {2},
        CONDITION_IDS[3]: {2},
    }


def test_smoke_factorial_interaction_identity_is_exact(stage08a31_real_smoke) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    rows = _rows(run / "factorial_participant_effects.csv")
    finite = [row for row in rows if row["interaction_identity_error"]]
    assert finite
    assert all(abs(float(row["interaction_identity_error"])) <= 1.0e-12 for row in finite)


def test_smoke_report_is_offline_and_has_drilldowns(stage08a31_real_smoke) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    report = (run / "report/report.html").read_text(encoding="utf-8")
    lowered = report.lower()
    assert "https://" not in lowered and "http://" not in lowered
    assert "<script src" not in lowered and "cdn" not in lowered
    assert "formal_spec_adoption=false" in report
    assert "factor-plot" in report
    assert "user-type-heatmap" in report
    assert len(list((run / "report/participants").glob("*.html"))) == 6
    assert len(list((run / "report/user_types").glob("*.html"))) == 3


def test_smoke_checkpoint_and_recommendation_are_complete(stage08a31_real_smoke) -> None:
    run = stage08a31_real_smoke["summary"].run_directory
    checkpoint = json.loads((run / "checkpoint.json").read_text(encoding="utf-8"))
    recommendation = json.loads(
        (run / "condition_recommendation.json").read_text(encoding="utf-8")
    )
    assert checkpoint["completed_session_runs"] == 120
    assert checkpoint["analysis_complete"] is True
    assert checkpoint["report_complete"] is True
    assert checkpoint["phase"] == "completed"
    assert recommendation["formal_spec_adoption"] is False
    assert recommendation["opaque_composite_score_used"] is False
    assert recommendation["overall_decision"] == "v2_reference_remains_preferred"
