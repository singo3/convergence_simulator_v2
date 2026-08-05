"""One real 48-session smoke validates orchestration, artifacts, and resume."""

from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import pytest

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    ARM_IDS,
    AUTONOMOUS_ARM,
    RANDOM_ARM,
    YOKED_ARM,
    ValidationConfig,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.fingerprint import (
    ValidationCodeFingerprint,
    ValidationCodeFingerprintError,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.runner import (
    AdaptivePlaceboValidationRunner,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("stage08a3-smoke")
    fingerprint = ValidationCodeFingerprint.capture(ROOT, allow_dirty=True)
    config = ValidationConfig.create(
        validation_preset="smoke",
        output_directory=str(output),
        retain_details="representative",
    )
    progress: list[dict[str, object]] = []
    runner = AdaptivePlaceboValidationRunner(
        config,
        repo_root=ROOT,
        progress_callback=progress.append,
        code_fingerprint=fingerprint,
        allow_dirty_code=True,
    )
    summary = runner.run()
    return runner, summary, fingerprint, progress


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_real_smoke_completes_exact_target_budget(smoke_run) -> None:
    _runner, summary, _fingerprint, progress = smoke_run
    assert summary.status == "completed"
    assert summary.completed_session_runs == 48
    assert summary.planned_session_runs == 48
    assert len(progress) == 12
    assert all(
        item["donor"] is not None
        for item in progress
        if item["arm"] == YOKED_ARM
    )
    assert summary.completed_participant_arm_jobs == 12


@pytest.mark.parametrize(
    "filename",
    (
        "validation_manifest.json",
        "validation_plan.json",
        "checkpoint.json",
        "participant_profiles.csv",
        "yoke_map.csv",
        "bundle_outcomes.csv",
        "session_outcomes.csv",
        "contemporaneous_response.csv",
        "arm_pair_differences.csv",
        "lagged_coupling.csv",
        "prospective_selection_enrichment.csv",
        "prediction_metrics.csv",
        "permutation_null.csv",
        "participant_effects.csv",
        "user_type_summary.csv",
        "overall_summary.csv",
        "condition_summary.csv",
        "invalid_data.csv",
        "digests.json",
        "report/report.html",
        "logs/validation.log",
    ),
)
def test_real_smoke_writes_required_artifact(smoke_run, filename: str) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    path = summary.run_directory / filename
    assert path.is_file() and path.stat().st_size > 0


def test_real_smoke_record_counts(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    assert len(_csv_rows(summary.run_directory / "participant_profiles.csv")) == 4
    assert len(_csv_rows(summary.run_directory / "yoke_map.csv")) == 4
    assert len(_csv_rows(summary.run_directory / "session_outcomes.csv")) == 48
    assert len(_csv_rows(summary.run_directory / "bundle_outcomes.csv")) == 144
    assert len(list((summary.run_directory / "report/participants").glob("*.html"))) == 4
    assert len(
        list((summary.run_directory / "details/event_ledgers").glob("*.json"))
    ) == 2 * 3 * 4


def test_real_smoke_autonomous_precedes_yoke_and_random(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    entries = [
        json.loads(line)
        for line in (summary.run_directory / "logs/validation.log").read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    completed = [item for item in entries if item["message"] == "participant_arm_completed"]
    by_type: dict[str, list[str]] = defaultdict(list)
    profiles = {
        row["participant_id"]: row["user_type_id"]
        for row in _csv_rows(summary.run_directory / "participant_profiles.csv")
    }
    for item in completed:
        _condition, participant, arm = item["job_id"].split("|")
        by_type[profiles[participant]].append(arm)
    assert all(
        arms == [AUTONOMOUS_ARM] * 2 + [YOKED_ARM] * 2 + [RANDOM_ARM] * 2
        for arms in by_type.values()
    )


def test_real_smoke_yoke_map_is_cyclic_and_donor_differs(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    rows = _csv_rows(summary.run_directory / "yoke_map.csv")
    assert all(row["target_participant_id"] != row["donor_participant_id"] for row in rows)
    assert all(row["hidden_donor"] == "false" for row in rows)
    assert all(row["donor_arm"] == AUTONOMOUS_ARM for row in rows)


def test_real_smoke_has_no_duplicate_autonomous_donor_run(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    donor_files = list((summary.run_directory / "donor_sequences").glob("*.json"))
    assert len(donor_files) == 4 * 4


def test_real_smoke_yoke_exactly_matches_donor_bundle_outputs(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    bundles = _csv_rows(summary.run_directory / "bundle_outcomes.csv")
    lookup = {
        (
            row["participant_id"],
            row["condition_id"],
            row["arm"],
            row["session_index"],
            row["bundle_index"],
        ): row
        for row in bundles
    }
    for row in bundles:
        if row["arm"] != YOKED_ARM:
            continue
        donor = lookup[
            (
                row["source_participant_id"],
                row["condition_id"],
                AUTONOMOUS_ARM,
                row["session_index"],
                row["bundle_index"],
            )
        ]
        assert row["displayed_life_id"] == donor["displayed_life_id"]
        assert row["displayed_hue_degree"] == donor["displayed_hue_degree"]
        assert row["displayed_blink_bpm"] == donor["displayed_blink_bpm"]
        assert row["displayed_b"] == donor["displayed_b"]

    sessions = _csv_rows(summary.run_directory / "session_outcomes.csv")
    session_lookup = {
        (
            row["participant_id"],
            row["condition_id"],
            row["arm"],
            row["session_index"],
        ): row
        for row in sessions
    }
    for row in sessions:
        if row["arm"] != YOKED_ARM:
            continue
        donor = session_lookup[
            (
                row["source_participant_id"],
                row["condition_id"],
                AUTONOMOUS_ARM,
                row["session_index"],
            )
        ]
        assert row["output_sequence_digest"] == donor["output_sequence_digest"]


def test_real_smoke_physiology_seed_and_baseline_are_paired(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    rows = _csv_rows(summary.run_directory / "session_outcomes.csv")
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["participant_id"], row["condition_id"], row["session_index"])].append(row)
    assert all({row["arm"] for row in group} == set(ARM_IDS) for group in groups.values())
    assert all(len({row["physiology_seed"] for row in group}) == 1 for group in groups.values())
    assert all(len({row["baseline_rmssd_ms"] for row in group}) == 1 for group in groups.values())
    assert _csv_rows(summary.run_directory / "invalid_data.csv") == []


def test_real_smoke_placebo_leakage_flags_are_false(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    rows = _csv_rows(summary.run_directory / "bundle_outcomes.csv")
    for row in rows:
        expected = "true" if row["arm"] == AUTONOMOUS_ARM else "false"
        assert row["target_rmssd_used_for_future_output"] == expected


def test_real_smoke_random_has_no_adaptive_anchor_or_decision(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    rows = _csv_rows(summary.run_directory / "session_outcomes.csv")
    for row in rows:
        if row["arm"] == RANDOM_ARM:
            assert row["final_committed_anchor"] == ""
            assert row["exploration_decision"] == ""
            assert row["candidate_generated"] == "false"


def test_real_smoke_report_is_self_contained_and_has_required_charts(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    report = summary.report_path.read_text(encoding="utf-8")
    assert "https://" not in report and "http://" not in report
    assert "<script src" not in report and "cdn" not in report.lower()
    assert "overall-delta" in report
    assert "overall-adaptation-metrics" in report
    assert "classification-bars" in report
    assert "user-type-trajectory" in report
    assert "correlation-scatter" in report
    for path in (summary.run_directory / "report/participants").glob("*.html"):
        participant = path.read_text(encoding="utf-8")
        assert "participant-trajectory" in participant
        assert "blink BPM" in participant
        assert "session index" in participant


def test_real_smoke_checkpoint_is_complete(smoke_run) -> None:
    _runner, summary, _fingerprint, _progress = smoke_run
    checkpoint = json.loads(summary.checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["completed_session_runs"] == 48
    assert checkpoint["analysis_complete"] is True
    assert checkpoint["report_complete"] is True
    assert checkpoint["phase"] == "completed"


def test_real_smoke_resume_skips_all_completed_jobs(smoke_run) -> None:
    _runner, summary, fingerprint, _progress = smoke_run
    before = json.loads(summary.checkpoint_path.read_text(encoding="utf-8"))
    progress: list[dict[str, object]] = []
    resumed = AdaptivePlaceboValidationRunner(
        repo_root=ROOT,
        resume_directory=summary.run_directory,
        progress_callback=progress.append,
        code_fingerprint=fingerprint,
        allow_dirty_code=True,
    ).run()
    after = json.loads(summary.checkpoint_path.read_text(encoding="utf-8"))
    assert resumed.status == "completed"
    assert before["completed_jobs"] == after["completed_jobs"]
    assert before["completed_session_runs"] == after["completed_session_runs"] == 48
    assert progress == []


def test_resume_rejects_code_fingerprint_change(smoke_run) -> None:
    _runner, summary, fingerprint, _progress = smoke_run
    changed = replace(fingerprint, package_version="changed")
    with pytest.raises(ValidationCodeFingerprintError, match="VALIDATION_CODE_CHANGED"):
        AdaptivePlaceboValidationRunner(
            repo_root=ROOT,
            resume_directory=summary.run_directory,
            code_fingerprint=changed,
            allow_dirty_code=True,
        )


def test_resume_rejects_tampered_donor_checksum(smoke_run, tmp_path: Path) -> None:
    _runner, summary, fingerprint, _progress = smoke_run
    copied = tmp_path / "tampered"
    shutil.copytree(summary.run_directory, copied)
    donor = next((copied / "donor_sequences").glob("*.json"))
    wrapper = json.loads(donor.read_text(encoding="utf-8"))
    wrapper["payload"][0]["scheduled_time_us"] += 1
    donor.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        AdaptivePlaceboValidationRunner(
            repo_root=ROOT,
            resume_directory=copied,
            code_fingerprint=fingerprint,
            allow_dirty_code=True,
        )


def test_graceful_cancel_commits_no_partial_job(tmp_path: Path) -> None:
    fingerprint = ValidationCodeFingerprint.capture(ROOT, allow_dirty=True)
    config = ValidationConfig.create(
        validation_preset="smoke",
        output_directory=str(tmp_path),
    )
    runner = AdaptivePlaceboValidationRunner(
        config,
        repo_root=ROOT,
        code_fingerprint=fingerprint,
        allow_dirty_code=True,
    )
    runner.request_cancel()
    summary = runner.run()
    assert summary.status == "cancelled"
    assert summary.completed_session_runs == 0
    assert runner.checkpoint.completed_jobs == {}


def test_factory_error_does_not_commit_participant_job(tmp_path: Path) -> None:
    fingerprint = ValidationCodeFingerprint.capture(ROOT, allow_dirty=True)
    config = ValidationConfig.create(
        validation_preset="smoke",
        output_directory=str(tmp_path),
    )

    def broken_factory(*_args, **_kwargs):
        raise RuntimeError("fixture factory failure")

    runner = AdaptivePlaceboValidationRunner(
        config,
        repo_root=ROOT,
        code_fingerprint=fingerprint,
        allow_dirty_code=True,
        autonomous_runner_factory=broken_factory,
    )
    with pytest.raises(RuntimeError, match="fixture factory failure"):
        runner.run()
    assert runner.checkpoint.completed_session_runs == 0
    assert runner.checkpoint.completed_jobs == {}
    assert len(list((runner.run_directory / "failed_jobs").glob("*.json"))) == 1
