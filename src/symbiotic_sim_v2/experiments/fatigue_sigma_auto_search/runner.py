"""Local CPU orchestration over the existing Stage 8A.1 runner."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma.aggregation import (
    replicate_result_from_single,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.condition import (
    FatigueSigmaCondition,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.runner import (
    FatigueSigmaSingleConditionRunner,
)

from .checkpoint import (
    AutoSearchCheckpoint,
    RunDirectoryLock,
    atomic_write_json,
    utc_now,
)
from .config import (
    RUN_MANIFEST_VERSION,
    AutoSearchConfig,
)
from .exports import export_search_results
from .fingerprint import CodeFingerprint
from .gates import evaluate_all_gates
from .html_report import write_html_report
from .job import AutoSearchJob, jobs_for_phase, reference_cache_key, sha256_canonical
from .job_store import JobStore
from .pareto import evaluate_pareto_frontier
from .phase_coarse import select_refine_seeds
from .phase_confirm import select_confirmation_conditions
from .phase_refine import build_refine_conditions
from .plan import AutoSearchPlan, ConditionPoint, build_search_plan
from .ranking import rank_robust_candidates
from .recommendations import build_recommendations
from .report_data import group_replicates_into_summaries

type ProgressCallback = Callable[[dict[str, Any]], None]
type SingleRunnerFactory = Callable[..., FatigueSigmaSingleConditionRunner]


@dataclass(frozen=True, slots=True)
class AutoSearchRunSummary:
    run_id: str
    run_directory: Path
    status: str
    final_phase: str | None
    completed_jobs: int
    failed_jobs: int
    completed_session_runs: int
    planned_session_runs: int
    report_path: Path
    recommendation_path: Path
    checkpoint_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_directory": str(self.run_directory),
            "status": self.status,
            "final_phase": self.final_phase,
            "completed_jobs": self.completed_jobs,
            "failed_jobs": self.failed_jobs,
            "completed_session_runs": self.completed_session_runs,
            "planned_session_runs": self.planned_session_runs,
            "report_path": str(self.report_path),
            "recommendation_path": str(self.recommendation_path),
            "checkpoint_path": str(self.checkpoint_path),
        }


class AutoSearchRunner:
    """Coarse/refine/confirm orchestration with atomic job boundaries."""

    def __init__(
        self,
        config: AutoSearchConfig | None = None,
        *,
        repo_root: Path | None = None,
        resume_directory: Path | None = None,
        single_runner_factory: SingleRunnerFactory = (FatigueSigmaSingleConditionRunner),
        progress_callback: ProgressCallback | None = None,
        code_fingerprint: CodeFingerprint | None = None,
        allow_dirty_code: bool = False,
        timestamp_factory: Callable[[], str] = utc_now,
    ) -> None:
        if resume_directory is not None and config is not None:
            raise ValueError("resume and new config are mutually exclusive")
        if resume_directory is None and config is None:
            raise ValueError("a new run requires AutoSearchConfig")
        if not callable(single_runner_factory):
            raise TypeError("single_runner_factory must be callable")
        if progress_callback is not None and not callable(progress_callback):
            raise TypeError("progress_callback must be callable")
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self._runner_factory = single_runner_factory
        self._progress_callback = progress_callback
        self._provided_fingerprint = code_fingerprint
        self._allow_dirty_code = allow_dirty_code
        self._timestamp_factory = timestamp_factory
        self._cancel_requested = False
        self._immediate_cancel = False
        self._started_monotonic = 0.0
        self._provisional_pareto_count = 0
        self._provisional_robust_candidate: str | None = None
        self._phase_selection_history: list[dict[str, Any]] = []
        self._manifest: dict[str, Any]
        self._checkpoint: AutoSearchCheckpoint
        self._store: JobStore
        self._fingerprint: CodeFingerprint
        self._plan: AutoSearchPlan
        if resume_directory is None:
            assert config is not None
            self._prepare_new(config)
        else:
            self._prepare_resume(resume_directory.resolve())

    @property
    def config(self) -> AutoSearchConfig:
        return self._config

    @property
    def plan(self) -> AutoSearchPlan:
        return self._plan

    @property
    def run_directory(self) -> Path:
        return self._run_directory

    @property
    def checkpoint(self) -> AutoSearchCheckpoint:
        return self._checkpoint

    def request_cancel(self, *, immediate: bool = False) -> None:
        self._cancel_requested = True
        self._immediate_cancel = self._immediate_cancel or immediate
        self._checkpoint = replace(
            self._checkpoint,
            cancel_requested=True,
            updated_at=self._timestamp_factory(),
        )
        self._save_checkpoint()

    def _capture_fingerprint(self) -> CodeFingerprint:
        return self._provided_fingerprint or CodeFingerprint.capture(
            self.repo_root,
            allow_dirty=self._allow_dirty_code,
        )

    def _prepare_new(self, config: AutoSearchConfig) -> None:
        self._config = config
        self._fingerprint = self._capture_fingerprint()
        self._plan = build_search_plan(config)
        run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        identity = sha256_canonical(
            {
                "config": config.to_dict(),
                "fingerprint": self._fingerprint.digest,
                "created_at": self._timestamp_factory(),
            }
        )[:10]
        self.run_id = f"{run_stamp}-{config.search_preset}-{identity}"
        base = Path(config.output_directory)
        if not base.is_absolute():
            base = self.repo_root / base
        self._run_directory = base / self.run_id
        if self._run_directory.exists():
            raise FileExistsError(f"run directory already exists: {self._run_directory}")
        for name in ("logs", "results", "report"):
            (self._run_directory / name).mkdir(parents=True, exist_ok=True)
        self._store = JobStore(self._run_directory)
        first_phase = self._plan.phases[0]
        jobs = jobs_for_phase(
            first_phase,
            base_master_seed=config.base_master_seed,
            include_reference_arm=config.include_reference_arm,
            code_fingerprint=self._fingerprint.digest,
            versions=config.version_metadata,
        )
        self._store.register_jobs(jobs)
        self._checkpoint = AutoSearchCheckpoint.create(
            run_id=self.run_id,
            current_phase=first_phase.phase,
            job_ids=tuple(job.job_id for job in jobs),
            planned_session_runs=self._plan.maximum_planned_session_runs,
            timestamp=self._timestamp_factory(),
        )
        self._manifest = {
            "run_id": self.run_id,
            "created_at": self._checkpoint.created_at,
            "config": config.to_dict(),
            "code_fingerprint": self._fingerprint.to_dict(),
            "formal_spec_adoption": False,
            "local_python_only": True,
            "external_network_used": False,
            "openai_codex_chatgpt_used": False,
            "stage_08a1_runner_reused": True,
            "simulation_core_copied": False,
            "schema_version": RUN_MANIFEST_VERSION,
        }
        atomic_write_json(self._run_directory / "search_manifest.json", self._manifest)
        self._write_plan()
        self._save_checkpoint()
        self._log("run_created")

    def _prepare_resume(self, run_directory: Path) -> None:
        self._run_directory = run_directory
        manifest_path = run_directory / "search_manifest.json"
        plan_path = run_directory / "search_plan.json"
        checkpoint_path = run_directory / "checkpoint.json"
        if not manifest_path.is_file() or not plan_path.is_file() or not checkpoint_path.is_file():
            raise ValueError("resume directory is missing manifest, plan, or checkpoint")
        self._manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_fields = {
            "run_id",
            "created_at",
            "config",
            "code_fingerprint",
            "formal_spec_adoption",
            "local_python_only",
            "external_network_used",
            "openai_codex_chatgpt_used",
            "stage_08a1_runner_reused",
            "simulation_core_copied",
            "schema_version",
        }
        if set(self._manifest) != manifest_fields:
            raise ValueError("run manifest fields differ")
        if self._manifest.get("schema_version") != RUN_MANIFEST_VERSION:
            raise ValueError("run manifest schema mismatch")
        required_flags = {
            "formal_spec_adoption": False,
            "local_python_only": True,
            "external_network_used": False,
            "openai_codex_chatgpt_used": False,
            "stage_08a1_runner_reused": True,
            "simulation_core_copied": False,
        }
        if any(self._manifest.get(name) is not value for name, value in required_flags.items()):
            raise ValueError("run manifest architecture flags differ")
        self._config = AutoSearchConfig.from_dict(self._manifest["config"])
        recorded = CodeFingerprint.from_dict(self._manifest["code_fingerprint"])
        current = self._capture_fingerprint()
        recorded.require_match(current)
        self._fingerprint = current
        encoded_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self._plan = AutoSearchPlan.from_dict(encoded_plan)
        history = encoded_plan.get("phase_selection_history", [])
        if not isinstance(history, list) or not all(isinstance(item, dict) for item in history):
            raise ValueError("phase selection history must be a list of objects")
        self._phase_selection_history = list(history)
        encoded_checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        self._checkpoint = AutoSearchCheckpoint.from_dict(encoded_checkpoint)
        if self._checkpoint.run_id != self._manifest["run_id"]:
            raise ValueError("checkpoint run ID differs from manifest")
        if self._checkpoint.created_at != self._manifest["created_at"]:
            raise ValueError("checkpoint creation time differs from manifest")
        self.run_id = self._checkpoint.run_id
        self._store = JobStore(run_directory)
        self._store.load_jobs()
        self._checkpoint = self._checkpoint.recover_running()
        self._validate_resume_consistency()
        for state in self._checkpoint.jobs:
            if state.status not in {"completed", "failed"}:
                if state.result_path is not None or state.result_checksum is not None:
                    raise ValueError("non-terminal checkpoint has result metadata")
                continue
            if state.result_path is None or state.result_checksum is None:
                raise ValueError("terminal checkpoint lacks result metadata")
            self._store.read_checked(
                run_directory / state.result_path,
                expected_checksum=state.result_checksum,
            )
        self._save_checkpoint()
        self._log("run_resumed")

    def _validate_resume_consistency(self) -> None:
        baseline = build_search_plan(self._config)
        if (
            self._plan.search_preset != baseline.search_preset
            or self._plan.maximum_total_session_runs != baseline.maximum_total_session_runs
            or self._plan.include_reference_arm != baseline.include_reference_arm
            or tuple(item.phase for item in self._plan.phases)
            != tuple(item.phase for item in baseline.phases)
        ):
            raise ValueError("resume plan differs from manifest config")
        baseline_by_phase = {item.phase: item for item in baseline.phases}
        for phase in self._plan.phases:
            expected = baseline_by_phase[phase.phase]
            if (
                phase.phase_number != expected.phase_number
                or phase.maximum_condition_count != expected.maximum_condition_count
                or phase.maximum_sessions != expected.maximum_sessions
                or phase.replicate_count != expected.replicate_count
                or phase.user_type_ids != expected.user_type_ids
                or phase.condition_count > phase.maximum_condition_count
                or len(set(phase.conditions)) != phase.condition_count
            ):
                raise ValueError("resume phase plan differs from manifest config")
            if phase.phase == "coarse" and phase.conditions != expected.conditions:
                raise ValueError("resume coarse grid differs from manifest config")
        if (
            self._plan.maximum_planned_session_runs != baseline.maximum_planned_session_runs
            or self._plan.maximum_planned_session_runs > self._config.maximum_total_session_runs
            or self._checkpoint.planned_session_runs != self._plan.maximum_planned_session_runs
            or self._checkpoint.current_phase not in {item.phase for item in self._plan.phases}
        ):
            raise ValueError("resume budget or phase differs from search plan")
        checkpoint_ids = {item.job_id for item in self._checkpoint.jobs}
        stored_ids = {item.job_id for item in self._store.jobs}
        if checkpoint_ids != stored_ids:
            raise ValueError("checkpoint jobs differ from jobs.jsonl")
        phase_by_name = {item.phase: item for item in self._plan.phases}
        for job in self._store.jobs:
            phase = phase_by_name.get(job.phase)
            if phase is None:
                raise ValueError("job refers to an unknown phase")
            point = ConditionPoint(
                job.selected_session_fatigue_target,
                job.sigma_multiplier,
            )
            if job.arm == "experimental" and point not in phase.conditions:
                raise ValueError("experimental job condition is absent from the plan")
            if job.arm == "reference" and point != ConditionPoint(0.0, 1.0):
                raise ValueError("reference job condition differs")
            if (
                job.user_type_id not in phase.user_type_ids
                or not 0 <= job.replicate_index < phase.replicate_count
            ):
                raise ValueError("job user type or replicate differs from the plan")
            expected_job = AutoSearchJob.create(
                phase=job.phase,
                user_type_id=job.user_type_id,
                point=point,
                maximum_sessions=phase.maximum_sessions,
                replicate_index=job.replicate_index,
                base_master_seed=self._config.base_master_seed,
                arm=job.arm,
                code_fingerprint=self._fingerprint.digest,
                versions=self._config.version_metadata,
            )
            if job != expected_job:
                raise ValueError("stored job differs from the canonical plan job")

    def _write_plan(self) -> None:
        atomic_write_json(
            self._run_directory / "search_plan.json",
            {
                **self._plan.to_dict(),
                "phase_selection_history": self._phase_selection_history,
            },
        )

    def _save_checkpoint(self) -> None:
        atomic_write_json(
            self._run_directory / "checkpoint.json",
            self._checkpoint.to_dict(),
        )

    def _log(self, message: str, **values: Any) -> None:
        payload = {
            "timestamp": self._timestamp_factory(),
            "message": message,
            **values,
        }
        path = self._run_directory / "logs" / "auto_search.log"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _emit(self, *, job: AutoSearchJob | None, message: str, session_offset: int = 0) -> None:
        completed_jobs = sum(item.status == "completed" for item in self._checkpoint.jobs)
        total_jobs = len(self._checkpoint.jobs)
        elapsed = max(0.0, time.monotonic() - self._started_monotonic)
        completed_sessions = self._checkpoint.completed_session_runs + session_offset
        speed = 0.0 if elapsed == 0.0 else completed_sessions / elapsed
        remaining = max(0, self._checkpoint.planned_session_runs - completed_sessions)
        eta = None if speed == 0.0 else remaining / speed
        payload = {
            "run_id": self.run_id,
            "phase": self._checkpoint.current_phase,
            "current_job": None if job is None else job.job_id,
            "completed_jobs": completed_jobs,
            "total_jobs": total_jobs,
            "completed_sessions": completed_sessions,
            "planned_sessions": self._checkpoint.planned_session_runs,
            "elapsed_seconds": elapsed,
            "moving_average_sessions_per_second": speed,
            "estimated_remaining_seconds": eta,
            "eta_is_prediction": True,
            "latest_checkpoint": str(self._run_directory / "checkpoint.json"),
            "current_provisional_pareto_count": self._provisional_pareto_count,
            "current_provisional_robust_candidate": (self._provisional_robust_candidate),
            "report_path": str(self._run_directory / "report" / "report.html"),
            "message": message,
        }
        if self._progress_callback is not None:
            self._progress_callback(payload)

    def _register_phase_jobs(self, phase_name: str) -> tuple[AutoSearchJob, ...]:
        phase = self._plan.phase(phase_name)
        jobs = jobs_for_phase(
            phase,
            base_master_seed=self._config.base_master_seed,
            include_reference_arm=self._config.include_reference_arm,
            code_fingerprint=self._fingerprint.digest,
            versions=self._config.version_metadata,
        )
        self._store.register_jobs(jobs)
        self._checkpoint = self._checkpoint.add_jobs(
            tuple(job.job_id for job in jobs),
            planned_session_runs=self._plan.maximum_planned_session_runs,
        )
        self._save_checkpoint()
        return jobs

    def _phase_jobs(self, phase_name: str) -> tuple[AutoSearchJob, ...]:
        return tuple(job for job in self._store.jobs if job.phase == phase_name)

    def _full_details_required(self, job: AutoSearchJob) -> bool:
        policy = self._config.retain_full_details_policy
        return policy == "all_full" or (policy == "phase3_full" and job.phase == "confirm")

    def _run_stage_08a1_job(self, job: AutoSearchJob) -> tuple[dict[str, Any] | None, int]:
        if job.arm == "reference":
            cache_key = reference_cache_key(job)
            cached = self._store.read_reference(
                cache_key,
                code_fingerprint=self._fingerprint.digest,
            )
            if cached is not None:
                return {
                    "job": job.to_dict(),
                    "arm": "reference",
                    "cache_key": cache_key,
                    "cache_hit": True,
                    "reference_result": cached,
                }, 0
        condition = FatigueSigmaCondition.create(
            user_type_id=job.user_type_id,
            selected_session_fatigue_target=job.selected_session_fatigue_target,
            sigma_multiplier=job.sigma_multiplier,
            maximum_sessions=job.maximum_sessions,
            master_seed=job.replicate_master_seed,
        )
        runner = self._runner_factory(
            condition,
            compare_reference_arm=job.arm == "reference",
        )
        sessions = 0
        while runner.can_run_next_session:
            if self._immediate_cancel:
                raise KeyboardInterrupt
            if self._cancel_requested:
                return None, sessions
            runner.run_next_session()
            sessions += 1
            self._emit(job=job, message="session_boundary", session_offset=sessions)
            if runner.stopped_on_error:
                break
        result = runner.result()
        if job.arm == "reference":
            reference = result.reference_arm_result
            if reference is None:
                raise RuntimeError("Stage 8A.1 reference arm result is missing")
            latest_structured = (
                None
                if not reference["structured_convergence_history"]
                else reference["structured_convergence_history"][-1]
            )
            latest_truth = (
                None
                if not reference["truth_alignment_history"]
                else reference["truth_alignment_history"][-1]
            )
            compact = {
                "user_type_id": job.user_type_id,
                "maximum_sessions": job.maximum_sessions,
                "replicate_index": job.replicate_index,
                "replicate_master_seed": job.replicate_master_seed,
                "latest_structured_convergence": latest_structured,
                "latest_truth_alignment": latest_truth,
                "w_ceiling_diagnostics": reference["w_ceiling_diagnostics"],
                "reference_digest": reference["digest"],
            }
            cache_key = reference_cache_key(job)
            self._store.write_reference(
                cache_key,
                code_fingerprint=self._fingerprint.digest,
                payload=compact,
            )
            return {
                "job": job.to_dict(),
                "arm": "reference",
                "cache_key": cache_key,
                "cache_hit": False,
                "reference_result": compact,
            }, 0
        replicate = replicate_result_from_single(
            result,
            replicate_index=job.replicate_index,
            replicate_master_seed=job.replicate_master_seed,
        ).to_dict()
        return {
            "job": job.to_dict(),
            "arm": "experimental",
            "replicate_result": replicate,
            "digests": dict(result.digests),
            "full_details": result.to_dict() if self._full_details_required(job) else None,
            "retain_full_details_policy": self._config.retain_full_details_policy,
        }, int(replicate["sessions_completed"])

    def _failed_payload(self, job: AutoSearchJob, error: str) -> dict[str, Any]:
        return {
            "job": job.to_dict(),
            "arm": job.arm,
            "error": error,
            "replicate_result": None
            if job.arm == "reference"
            else {
                "condition_id": (
                    f"{job.user_type_id}__fatigue_"
                    f"{job.selected_session_fatigue_target:.6f}__sigma_"
                    f"{job.sigma_multiplier:.6f}__sessions_{job.maximum_sessions}"
                ),
                "user_type_id": job.user_type_id,
                "selected_session_fatigue_target": (job.selected_session_fatigue_target),
                "sigma_multiplier": job.sigma_multiplier,
                "replicate_index": job.replicate_index,
                "replicate_master_seed": job.replicate_master_seed,
                "sessions_completed": 0,
                "sessions_expected": job.maximum_sessions,
                "completed": False,
                "failed": True,
                "failure_reason": error,
                "summary_classification": "failed",
                "truth_classification": "not_converged",
                "life_dominant_converged": False,
                "bpm_common_converged": False,
                "multi_attractor_converged": False,
                "single_life_pattern_converged": False,
                "first_life_convergence_session": None,
                "first_bpm_convergence_session": None,
                "first_multi_attractor_session": None,
                "dominant_life_share": None,
                "bpm_cluster_width": None,
                "post_convergence_outlier_rate": 0.0,
                "return_within_1_rate": 0.0,
                "return_within_2_rate": 0.0,
                "mechanical_rotation": {},
                "w_ceiling": {},
                "explore_count": 0,
                "candidate_count": 0,
                "accepted_count": 0,
                "selected_life_mean_e": None,
                "selected_life_max_e": None,
                "nonselected_full_recovery_count": 0,
                "effective_sigma_mean": None,
                "effective_sigma_min": None,
                "effective_sigma_max": None,
                "candidate_delta_hue": [],
                "candidate_delta_bpm": [],
                "result_digest": sha256_canonical({"job_id": job.job_id, "error": error}),
                "schema_version": "fatigue_sigma_replicate_result_v1",
            },
        }

    def _execute_phase(self, phase_name: str) -> bool:
        self._checkpoint = replace(
            self._checkpoint,
            current_phase=phase_name,
            updated_at=self._timestamp_factory(),
        )
        self._save_checkpoint()
        for job in self._phase_jobs(phase_name):
            state = self._checkpoint.state_for(job.job_id)
            if state.status in {"completed", "failed"}:
                continue
            if self._cancel_requested:
                return False
            self._checkpoint = self._checkpoint.transition(job.job_id, "running")
            self._save_checkpoint()
            self._emit(job=job, message="job_started")
            self._log("job_started", job_id=job.job_id, phase=phase_name)
            try:
                payload, sessions = self._run_stage_08a1_job(job)
                if payload is None:
                    self._checkpoint = self._checkpoint.transition(job.job_id, "pending")
                    self._save_checkpoint()
                    return False
                replicate = payload.get("replicate_result")
                failed = bool(replicate is not None and replicate.get("failed"))
                if failed:
                    path, checksum = self._store.write_failed(job, payload)
                    status = "failed"
                else:
                    path, checksum = self._store.write_completed(job, payload)
                    status = "completed"
                relative = str(path.relative_to(self._run_directory))
                self._checkpoint = self._checkpoint.transition(
                    job.job_id,
                    status,
                    result_path=relative,
                    result_checksum=checksum,
                    error=None if not failed else replicate.get("failure_reason"),
                    completed_session_delta=(sessions if job.arm == "experimental" else 0),
                )
            except KeyboardInterrupt:
                self._checkpoint = self._checkpoint.transition(job.job_id, "pending")
                self._save_checkpoint()
                raise
            except Exception as exc:
                error = f"{type(exc).__name__}:{exc}"
                payload = self._failed_payload(job, error)
                path, checksum = self._store.write_failed(job, payload)
                self._checkpoint = self._checkpoint.transition(
                    job.job_id,
                    "failed",
                    result_path=str(path.relative_to(self._run_directory)),
                    result_checksum=checksum,
                    error=error,
                )
            self._save_checkpoint()
            if self._condition_is_at_result_boundary(job):
                self._refresh_provisional_status(phase_name)
            self._emit(job=job, message="replicate_boundary")
            self._log(
                "job_finished",
                job_id=job.job_id,
                status=self._checkpoint.state_for(job.job_id).status,
            )
        self._log("phase_finished", phase=phase_name)
        self._save_checkpoint()
        return True

    def _payload_for_state(self, job_id: str) -> dict[str, Any]:
        state = self._checkpoint.state_for(job_id)
        if state.result_path is None or state.result_checksum is None:
            raise ValueError(f"job has no result: {job_id}")
        return self._store.read_checked(
            self._run_directory / state.result_path,
            expected_checksum=state.result_checksum,
        )

    def _phase_replicates(self, phase_name: str) -> tuple[dict[str, Any], ...]:
        rows = []
        for job in self._phase_jobs(phase_name):
            if job.arm != "experimental":
                continue
            state = self._checkpoint.state_for(job.job_id)
            if state.status not in {"completed", "failed"}:
                continue
            payload = self._payload_for_state(job.job_id)
            replicate = payload.get("replicate_result")
            if replicate is not None:
                rows.append(
                    {
                        **dict(replicate),
                        "phase": phase_name,
                        "job_id": job.job_id,
                    }
                )
        return tuple(sorted(rows, key=lambda item: str(item["job_id"])))

    def _phase_analysis(
        self,
        phase_name: str,
    ) -> tuple[
        tuple[dict[str, Any], ...],
        dict[str, Any],
        dict[str, Any],
        tuple[dict[str, Any], ...],
    ]:
        phase = self._plan.phase(phase_name)
        summaries = group_replicates_into_summaries(
            phase=phase_name,
            maximum_sessions=phase.maximum_sessions,
            replicate_payloads=self._phase_replicates(phase_name),
            expected_user_type_ids=phase.user_type_ids,
        )
        final_gates = evaluate_all_gates(
            summaries,
            self._config.candidate_gate_config,
        )
        coarse_gates = evaluate_all_gates(
            summaries,
            self._config.candidate_gate_config,
            coarse=True,
        )
        pareto = evaluate_pareto_frontier(summaries, final_gates)
        return summaries, final_gates, coarse_gates, pareto

    def _refresh_provisional_status(self, phase_name: str) -> None:
        """Refresh progress-only Pareto/ranking after a safe result boundary."""

        summaries, final_gates, _coarse_gates, pareto = self._phase_analysis(phase_name)
        self._provisional_pareto_count = sum(int(item["pareto_rank"] == 1) for item in pareto)
        robust = rank_robust_candidates(summaries, final_gates)
        self._provisional_robust_candidate = (
            None
            if self._config.search_preset == "smoke" or not robust
            else str(robust[0]["candidate_id"])
        )

    def _condition_is_at_result_boundary(self, job: AutoSearchJob) -> bool:
        if job.arm != "experimental":
            return False
        related = (
            candidate
            for candidate in self._phase_jobs(job.phase)
            if candidate.arm == "experimental"
            and candidate.selected_session_fatigue_target == job.selected_session_fatigue_target
            and candidate.sigma_multiplier == job.sigma_multiplier
        )
        return all(
            self._checkpoint.state_for(candidate.job_id).status in {"completed", "failed"}
            for candidate in related
        )

    def _ensure_next_phase(self, completed_phase: str) -> None:
        if completed_phase == "coarse" and any(
            item.phase == "refine" for item in self._plan.phases
        ):
            refine = self._plan.phase("refine")
            if refine.conditions:
                return
            summaries, final_gates, coarse_gates, pareto = self._phase_analysis("coarse")
            seeds = select_refine_seeds(
                summaries,
                coarse_gates,
                final_gates,
                pareto,
            )
            conditions = build_refine_conditions(
                seeds,
                maximum_conditions=refine.maximum_condition_count,
            )
            self._plan = self._plan.with_phase_conditions("refine", conditions)
            self._phase_selection_history.append(
                {
                    "from_phase": "coarse",
                    "to_phase": "refine",
                    "seed_conditions": [item.to_dict() for item in seeds],
                    "selected_conditions": [item.to_dict() for item in conditions],
                }
            )
            self._write_plan()
            self._register_phase_jobs("refine")
        elif completed_phase == "refine" and any(
            item.phase == "confirm" for item in self._plan.phases
        ):
            confirm = self._plan.phase("confirm")
            if confirm.conditions:
                return
            summaries, final_gates, _coarse_gates, pareto = self._phase_analysis("refine")
            conditions = select_confirmation_conditions(
                summaries,
                final_gates,
                pareto,
                maximum_conditions=confirm.maximum_condition_count,
            )
            self._plan = self._plan.with_phase_conditions("confirm", conditions)
            self._phase_selection_history.append(
                {
                    "from_phase": "refine",
                    "to_phase": "confirm",
                    "selected_conditions": [item.to_dict() for item in conditions],
                }
            )
            self._write_plan()
            self._register_phase_jobs("confirm")

    def _reference_results(self) -> tuple[dict[str, Any], ...]:
        by_cache: dict[str, dict[str, Any]] = {}
        for job in self._store.jobs:
            if job.arm != "reference":
                continue
            state = self._checkpoint.state_for(job.job_id)
            if state.status != "completed":
                continue
            payload = self._payload_for_state(job.job_id)
            cache_key = str(payload["cache_key"])
            by_cache[cache_key] = {
                "cache_key": cache_key,
                "cache_hit": payload["cache_hit"],
                **dict(payload["reference_result"]),
            }
        return tuple(by_cache[key] for key in sorted(by_cache))

    def _reproduction_commands(self) -> tuple[str, ...]:
        return (
            (
                ".venv/bin/python -m symbiotic_sim_v2 "
                "--headless-fatigue-sigma-auto-search "
                f"--resume {self._run_directory}"
            ),
            (
                ".venv/bin/python -m symbiotic_sim_v2 "
                "--headless-fatigue-sigma-auto-search "
                f"--search-preset {self._config.search_preset}"
            ),
        )

    def _finalize(self, *, status: str, final_phase: str | None) -> AutoSearchRunSummary:
        phase_summaries: dict[str, tuple[dict[str, Any], ...]] = {}
        phase_pareto: dict[str, tuple[dict[str, Any], ...]] = {}
        for phase in self._plan.phases:
            if not phase.conditions or not self._phase_replicates(phase.phase):
                continue
            summaries, _final, _coarse, pareto = self._phase_analysis(phase.phase)
            phase_summaries[phase.phase] = summaries
            phase_pareto[phase.phase] = pareto
        selected_phase = final_phase
        if selected_phase is None or selected_phase not in phase_summaries:
            selected_phase = next(reversed(phase_summaries), None)
        selected_summaries = () if selected_phase is None else phase_summaries[selected_phase]
        selected_gates = evaluate_all_gates(
            selected_summaries,
            self._config.candidate_gate_config,
        )
        selected_pareto = () if selected_phase is None else phase_pareto[selected_phase]
        commands = self._reproduction_commands()
        recommendations = build_recommendations(
            summaries=selected_summaries,
            gates=selected_gates,
            pareto_records=selected_pareto,
            generated_at=self._timestamp_factory(),
            code_fingerprint=self._fingerprint.to_dict(),
            search_preset=self._config.search_preset,
            reproduction_commands=commands,
        )
        all_replicates = tuple(
            item for phase in self._plan.phases for item in self._phase_replicates(phase.phase)
        )
        references = self._reference_results()
        paths = export_search_results(
            self._run_directory,
            phase_summaries=phase_summaries,
            replicate_results=all_replicates,
            pareto_records=selected_pareto,
            recommendations=recommendations,
            reference_results=references,
        )
        completed_jobs = sum(item.status == "completed" for item in self._checkpoint.jobs)
        failed_jobs = sum(item.status == "failed" for item in self._checkpoint.jobs)
        elapsed = max(0.0, time.monotonic() - self._started_monotonic)
        runtime_summary = {
            "run_id": self.run_id,
            "status": status,
            "final_phase": selected_phase,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "completed_session_runs": self._checkpoint.completed_session_runs,
            "planned_session_runs": self._checkpoint.planned_session_runs,
            "reference_cache_entries": len(references),
            "elapsed_seconds": elapsed,
            "finished_at": self._timestamp_factory(),
            "report_path": str(self._run_directory / "report" / "report.html"),
        }
        atomic_write_json(self._run_directory / "runtime_summary.json", runtime_summary)
        report_path = write_html_report(
            self._run_directory / "report" / "report.html",
            manifest=self._manifest,
            runtime_summary=runtime_summary,
            summaries=selected_summaries,
            pareto_records=selected_pareto,
            recommendations=recommendations,
            phase_selection_history=self._phase_selection_history,
            reproduction_commands=commands,
            reference_results=references,
        )
        if selected_phase is not None:
            self._refresh_provisional_status(selected_phase)
        self._emit(job=None, message="report_generated")
        return AutoSearchRunSummary(
            run_id=self.run_id,
            run_directory=self._run_directory,
            status=status,
            final_phase=selected_phase,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            completed_session_runs=self._checkpoint.completed_session_runs,
            planned_session_runs=self._checkpoint.planned_session_runs,
            report_path=report_path,
            recommendation_path=paths["recommended_conditions.json"],
            checkpoint_path=self._run_directory / "checkpoint.json",
        )

    def run(self) -> AutoSearchRunSummary:
        self._started_monotonic = time.monotonic()
        final_phase: str | None = None
        lock = RunDirectoryLock(self._run_directory)
        with lock:
            try:
                for phase in self._plan.phases:
                    if not phase.conditions:
                        previous = "coarse" if phase.phase == "refine" else "refine"
                        self._ensure_next_phase(previous)
                    if not self._phase_jobs(phase.phase):
                        self._register_phase_jobs(phase.phase)
                    completed = self._execute_phase(phase.phase)
                    if not completed:
                        return self._finalize(status="cancelled", final_phase=final_phase)
                    final_phase = phase.phase
                    self._ensure_next_phase(phase.phase)
                return self._finalize(status="completed", final_phase=final_phase)
            except KeyboardInterrupt:
                self._log("immediate_interruption")
                self._save_checkpoint()
                raise


__all__ = [
    "AutoSearchRunSummary",
    "AutoSearchRunner",
    "ProgressCallback",
    "SingleRunnerFactory",
]
