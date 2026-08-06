"""Strict resume, checksum, cancellation, and atomic-job boundaries."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.fingerprint import (
    ValidationCodeFingerprint,
    ValidationCodeFingerprintError,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.config import (
    FactorialValidationConfig,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.runner import (
    FatigueRecoverySigmaFactorialRunner,
)


def _file_state(paths: list[Path]) -> dict[str, tuple[int, int]]:
    return {str(path): (path.stat().st_size, path.stat().st_mtime_ns) for path in paths}


def test_completed_resume_skips_jobs_and_shared_random(stage08a31_real_smoke) -> None:
    summary = stage08a31_real_smoke["summary"]
    fingerprint = stage08a31_real_smoke["fingerprint"]
    paths = sorted((summary.run_directory / "completed_jobs").glob("*.json")) + sorted(
        (summary.run_directory / "donor_sequences").glob("*.json")
    )
    before_files = _file_state(paths)
    before_checkpoint = json.loads(summary.checkpoint_path.read_text(encoding="utf-8"))
    progress: list[dict[str, object]] = []
    resumed = FatigueRecoverySigmaFactorialRunner(
        repo_root=stage08a31_real_smoke["repo_root"],
        resume_directory=summary.run_directory,
        progress_callback=progress.append,
        code_fingerprint=fingerprint,
        allow_dirty_code=True,
    ).run()
    after_checkpoint = json.loads(summary.checkpoint_path.read_text(encoding="utf-8"))
    assert resumed.status == "completed"
    assert progress == []
    assert before_checkpoint == after_checkpoint
    assert before_files == _file_state(paths)


def test_resume_rejects_changed_code_fingerprint(stage08a31_real_smoke) -> None:
    fingerprint = stage08a31_real_smoke["fingerprint"]
    base = ValidationCodeFingerprint.from_dict(
        dict(fingerprint.reused_stage08a3_fingerprint)
    )
    changed_base = replace(base, python_version=base.python_version + ".changed")
    changed = replace(
        fingerprint,
        reused_stage08a3_fingerprint=changed_base.to_dict(),
    )
    with pytest.raises(ValidationCodeFingerprintError, match="CODE_CHANGED"):
        FatigueRecoverySigmaFactorialRunner(
            repo_root=stage08a31_real_smoke["repo_root"],
            resume_directory=stage08a31_real_smoke["summary"].run_directory,
            code_fingerprint=changed,
            allow_dirty_code=True,
        )


def test_resume_rejects_tampered_shared_random_cache(
    stage08a31_real_smoke,
    tmp_path: Path,
) -> None:
    copied = tmp_path / "tampered"
    shutil.copytree(stage08a31_real_smoke["summary"].run_directory, copied)
    cache = next((copied / "donor_sequences").glob("*.json"))
    wrapper = json.loads(cache.read_text(encoding="utf-8"))
    wrapper["payload"]["sessions"][0]["physiology_seed"] += 1
    cache.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        FatigueRecoverySigmaFactorialRunner(
            repo_root=stage08a31_real_smoke["repo_root"],
            resume_directory=copied,
            code_fingerprint=stage08a31_real_smoke["fingerprint"],
            allow_dirty_code=True,
        )


def test_graceful_prestart_cancel_commits_no_session(tmp_path: Path) -> None:
    config = FactorialValidationConfig.create(
        validation_preset="smoke",
        output_directory=str(tmp_path),
    )
    runner = FatigueRecoverySigmaFactorialRunner(
        config,
        repo_root=Path(__file__).resolve().parents[2],
        allow_dirty_code=True,
    )
    runner.request_cancel()
    summary = runner.run()
    assert summary.status == "cancelled"
    assert summary.completed_actual_simulation_sessions == 0
    assert runner.checkpoint.completed_jobs == {}


def test_atomic_checkpoint_uses_shared_stage8a3_store(stage08a31_real_smoke) -> None:
    checkpoint = json.loads(
        stage08a31_real_smoke["summary"].checkpoint_path.read_text(encoding="utf-8")
    )
    assert len(checkpoint["completed_jobs"]) == 30
    assert len(checkpoint["donor_sequence_checksums"]) == 6
    assert all(
        value["checksum"]
        for value in checkpoint["completed_jobs"].values()
    )
