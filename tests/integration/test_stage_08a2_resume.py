"""Strict completed-job resume and checksum tests."""

from __future__ import annotations

import json
import shutil

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search import AutoSearchRunner
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.fingerprint import (
    CodeFingerprintError,
)


def test_completed_smoke_resume_skips_every_completed_job(stage08a2_real_smoke) -> None:
    summary = stage08a2_real_smoke["summary"]
    before = {
        path.name: (path.stat().st_mtime_ns, path.read_bytes())
        for path in (summary.run_directory / "completed_jobs").glob("*.json")
    }
    resumed = AutoSearchRunner(
        repo_root=stage08a2_real_smoke["repo_root"],
        resume_directory=summary.run_directory,
        code_fingerprint=stage08a2_real_smoke["fingerprint"],
    ).run()
    after = {
        path.name: (path.stat().st_mtime_ns, path.read_bytes())
        for path in (summary.run_directory / "completed_jobs").glob("*.json")
    }
    assert resumed.status == "completed"
    assert resumed.completed_session_runs == 32
    assert before == after


def test_resume_rejects_changed_code_fingerprint(stage08a2_real_smoke) -> None:
    recorded = stage08a2_real_smoke["fingerprint"]
    changed = type(recorded)(
        **{
            **{
                key: value
                for key, value in recorded.to_dict().items()
                if key != "fingerprint_digest"
            },
            "git_head_sha": "b" * 40,
        }
    )
    with pytest.raises(CodeFingerprintError, match="AUTO_SEARCH_CODE_CHANGED"):
        AutoSearchRunner(
            repo_root=stage08a2_real_smoke["repo_root"],
            resume_directory=stage08a2_real_smoke["summary"].run_directory,
            code_fingerprint=changed,
        )


def test_resume_rejects_corrupted_completed_result(
    stage08a2_real_smoke,
    monkeypatch,
) -> None:
    summary = stage08a2_real_smoke["summary"]
    target = next((summary.run_directory / "completed_jobs").glob("*.json"))
    original = target.read_bytes()
    wrapper = json.loads(original)
    wrapper["payload"]["arm"] = "tampered"
    target.write_text(json.dumps(wrapper), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="checksum"):
            AutoSearchRunner(
                repo_root=stage08a2_real_smoke["repo_root"],
                resume_directory=summary.run_directory,
                code_fingerprint=stage08a2_real_smoke["fingerprint"],
            )
    finally:
        target.write_bytes(original)


def test_resume_rejects_plan_that_differs_from_manifest_config(
    tmp_path,
    stage08a2_real_smoke,
) -> None:
    source = stage08a2_real_smoke["summary"].run_directory
    copied = tmp_path / "tampered-plan-run"
    shutil.copytree(source, copied)
    plan_path = copied / "search_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["phases"][0]["maximum_sessions"] = 5
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="derived field|manifest config"):
        AutoSearchRunner(
            repo_root=stage08a2_real_smoke["repo_root"],
            resume_directory=copied,
            code_fingerprint=stage08a2_real_smoke["fingerprint"],
        )
