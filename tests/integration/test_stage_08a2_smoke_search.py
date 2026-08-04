"""One real Stage 8A.2 32-session smoke search."""

from __future__ import annotations

import csv
import json


def test_real_smoke_completes_32_sessions_and_all_jobs(stage08a2_real_smoke) -> None:
    summary = stage08a2_real_smoke["summary"]
    checkpoint = json.loads(summary.checkpoint_path.read_text(encoding="utf-8"))
    assert summary.status == "completed"
    assert summary.final_phase == "coarse"
    assert summary.completed_session_runs == summary.planned_session_runs == 32
    assert summary.completed_jobs == 8
    assert summary.failed_jobs == 0
    assert {item["status"] for item in checkpoint["jobs"]} == {"completed"}
    assert not (summary.run_directory / ".auto_search.lock").exists()


def test_real_smoke_generates_all_compact_results_and_report(stage08a2_real_smoke) -> None:
    summary = stage08a2_real_smoke["summary"]
    required = {
        "phase_1_coarse_results.csv",
        "phase_2_refined_results.csv",
        "phase_3_confirmation_results.csv",
        "all_replicate_results.csv",
        "all_condition_summaries.csv",
        "user_type_breakdown.csv",
        "flat_control_diagnostics.csv",
        "mechanical_rotation_diagnostics.csv",
        "w_ceiling_diagnostics.csv",
        "pareto_frontier.csv",
        "robust_candidates.csv",
        "specialist_candidates.csv",
        "reference_arm_comparison.csv",
        "candidate_blockers.csv",
        "recommended_conditions.json",
    }
    assert required == {path.name for path in (summary.run_directory / "results").iterdir()}
    assert summary.report_path.is_file()
    assert summary.report_path.stat().st_size > 2_000
    report = summary.report_path.read_text(encoding="utf-8")
    assert "formal_spec_adoption=false" in report
    assert "Smoke is an implementation check only" in report
    assert "Pareto frontier" in report
    assert "http://" not in report and "https://" not in report


def test_real_smoke_does_not_claim_candidate_validity(stage08a2_real_smoke) -> None:
    summary = stage08a2_real_smoke["summary"]
    recommendation = json.loads(summary.recommendation_path.read_text(encoding="utf-8"))
    assert recommendation["status"] == "smoke_diagnostic_only"
    assert recommendation["robust_candidate"] is None
    assert recommendation["robust_candidates"] == []
    assert recommendation["formal_spec_adoption"] is False
    assert recommendation["smoke_does_not_establish_candidate_validity"] is True


def test_real_smoke_uses_compact_job_details(stage08a2_real_smoke) -> None:
    summary = stage08a2_real_smoke["summary"]
    paths = sorted((summary.run_directory / "completed_jobs").glob("*.json"))
    assert len(paths) == 8
    for path in paths:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        assert wrapper["payload"]["full_details"] is None
        assert wrapper["payload"]["retain_full_details_policy"] == "phase3_full"


def test_real_smoke_csvs_have_deterministic_job_order(stage08a2_real_smoke) -> None:
    path = stage08a2_real_smoke["summary"].run_directory / "results" / "all_replicate_results.csv"
    with path.open(encoding="utf-8", newline="") as source:
        rows = tuple(csv.DictReader(source))
    assert len(rows) == 8
    assert [row["job_id"] for row in rows] == sorted(row["job_id"] for row in rows)


def test_real_smoke_progress_reports_current_provisional_pareto(
    stage08a2_real_smoke,
) -> None:
    progress = stage08a2_real_smoke["progress"]
    assert progress[-1]["message"] == "report_generated"
    assert progress[-1]["current_provisional_pareto_count"] >= 1
    assert progress[-1]["current_provisional_robust_candidate"] is None
    assert progress[-1]["report_path"].endswith("report/report.html")
