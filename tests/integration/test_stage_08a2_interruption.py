"""Safe-boundary cancellation, pending recovery, and resume tests."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search import (
    AutoSearchConfig,
    AutoSearchRunner,
)


def _fake_factory(template, instances):
    class FakeRunner:
        def __init__(self, condition, *, compare_reference_arm=False):
            self.condition = condition
            self.compare_reference_arm = compare_reference_arm
            self.steps = 0
            self.stopped_on_error = False
            instances.append(self)

        @property
        def can_run_next_session(self):
            return self.steps < self.condition.maximum_sessions

        def run_next_session(self):
            self.steps += 1

        def result(self):
            return replace(
                template,
                condition=self.condition.to_dict(),
                sessions_completed=self.steps,
                sessions_valid=self.steps,
                stopped_on_error=False,
                reference_arm_result=(
                    template.reference_arm_result if self.compare_reference_arm else None
                ),
            )

    return FakeRunner


def test_graceful_cancellation_leaves_running_job_pending_and_resumable(
    tmp_path,
    stage08a2_real_smoke,
    stage08a2_paired_result_template,
) -> None:
    instances = []
    holder = {}

    def progress(payload):
        if payload["message"] == "session_boundary" and not holder.get("cancelled"):
            holder["cancelled"] = True
            holder["runner"].request_cancel()

    config = AutoSearchConfig.create(
        search_preset="smoke",
        output_directory=str(tmp_path),
    )
    runner = AutoSearchRunner(
        config,
        repo_root=stage08a2_real_smoke["repo_root"],
        single_runner_factory=_fake_factory(
            stage08a2_paired_result_template,
            instances,
        ),
        progress_callback=progress,
        code_fingerprint=stage08a2_real_smoke["fingerprint"],
    )
    holder["runner"] = runner
    cancelled = runner.run()
    checkpoint = json.loads(cancelled.checkpoint_path.read_text(encoding="utf-8"))
    assert cancelled.status == "cancelled"
    assert sum(item["status"] == "pending" for item in checkpoint["jobs"]) == 8
    assert instances[0].steps == 1
    resumed = AutoSearchRunner(
        repo_root=stage08a2_real_smoke["repo_root"],
        resume_directory=cancelled.run_directory,
        single_runner_factory=_fake_factory(
            stage08a2_paired_result_template,
            instances,
        ),
        code_fingerprint=stage08a2_real_smoke["fingerprint"],
    ).run()
    assert resumed.status == "completed"
    assert resumed.completed_session_runs == 32
    assert resumed.completed_jobs == 8


def test_immediate_cancellation_preserves_parseable_checkpoint(
    tmp_path,
    stage08a2_real_smoke,
    stage08a2_paired_result_template,
) -> None:
    instances = []
    holder = {}

    def progress(payload):
        if payload["message"] == "session_boundary":
            holder["runner"].request_cancel(immediate=True)

    runner = AutoSearchRunner(
        AutoSearchConfig.create(
            search_preset="smoke",
            output_directory=str(tmp_path),
        ),
        repo_root=stage08a2_real_smoke["repo_root"],
        single_runner_factory=_fake_factory(
            stage08a2_paired_result_template,
            instances,
        ),
        progress_callback=progress,
        code_fingerprint=stage08a2_real_smoke["fingerprint"],
    )
    holder["runner"] = runner
    with pytest.raises(KeyboardInterrupt):
        runner.run()
    checkpoint = json.loads((runner.run_directory / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["cancel_requested"] is True
    assert {item["status"] for item in checkpoint["jobs"]} == {"pending"}
    assert not (runner.run_directory / ".auto_search.lock").exists()
