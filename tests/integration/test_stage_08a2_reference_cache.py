"""Reference arm cache reuse across conditions and equal-length phases."""

from __future__ import annotations

import json
from dataclasses import replace

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search import (
    AutoSearchConfig,
    AutoSearchRunner,
)


def test_reference_arm_runs_once_per_cache_key_across_conditions_and_phases(
    tmp_path,
    stage08a2_real_smoke,
    stage08a2_paired_result_template,
) -> None:
    calls = []

    class FakeRunner:
        def __init__(self, condition, *, compare_reference_arm=False):
            self.condition = condition
            self.compare_reference_arm = compare_reference_arm
            self.steps = 0
            self.stopped_on_error = False
            calls.append(compare_reference_arm)

        @property
        def can_run_next_session(self):
            return self.steps < self.condition.maximum_sessions

        def run_next_session(self):
            self.steps += 1

        def result(self):
            return replace(
                stage08a2_paired_result_template,
                condition=self.condition.to_dict(),
                sessions_completed=self.steps,
                sessions_valid=self.steps,
                stopped_on_error=False,
                reference_arm_result=(
                    stage08a2_paired_result_template.reference_arm_result
                    if self.compare_reference_arm
                    else None
                ),
            )

    config = AutoSearchConfig.create(
        search_preset="standard",
        user_type_ids=("flat_control",),
        include_reference_arm=True,
        output_directory=str(tmp_path),
        stop_after_phase="refine",
    )
    result = AutoSearchRunner(
        config,
        repo_root=stage08a2_real_smoke["repo_root"],
        single_runner_factory=FakeRunner,
        code_fingerprint=stage08a2_real_smoke["fingerprint"],
    ).run()
    assert result.status == "completed"
    # coarse has replicate 0..2; refine has 0..4 at the same 24-session
    # cache key shape, so only replicate 3 and 4 are new reference executions.
    assert sum(calls) == 5
    cache_files = tuple((result.run_directory / "reference_cache").glob("*.json"))
    assert len(cache_files) == 5
    reference_jobs = []
    for path in (result.run_directory / "completed_jobs").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
        if payload["arm"] == "reference":
            reference_jobs.append(payload)
    assert len(reference_jobs) == 8
    assert sum(bool(item["cache_hit"]) for item in reference_jobs) == 3


def test_reference_cache_results_carry_checksums_and_no_condition_seed(
    stage08a2_real_smoke,
) -> None:
    from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
        AutoSearchVersionMetadata,
    )
    from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import (
        AutoSearchJob,
        reference_cache_key,
    )
    from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.plan import (
        ConditionPoint,
    )

    common = {
        "phase": "coarse",
        "user_type_id": "flat_control",
        "maximum_sessions": 24,
        "replicate_index": 0,
        "base_master_seed": 123,
        "arm": "reference",
        "code_fingerprint": stage08a2_real_smoke["fingerprint"].digest,
        "versions": AutoSearchVersionMetadata(),
    }
    first = AutoSearchJob.create(point=ConditionPoint(0.0, 0.5), **common)
    second = AutoSearchJob.create(point=ConditionPoint(0.2, 1.5), **common)
    assert first.replicate_master_seed == second.replicate_master_seed
    assert reference_cache_key(first) == reference_cache_key(second)
