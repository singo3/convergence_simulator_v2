"""Checkpointed Stage 8A.3.1 orchestration over the reused simulation paths."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.convergence.structured import WCeilingObservation
from symbiotic_sim_v2.digital_life.relation_memory.intrinsic import (
    derive_relation_memory_intrinsic_profile,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    RANDOM_ARM,
    ValidationParticipant,
    build_participants,
    validation_condition,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    V2_REFERENCE_CONDITION as STAGE08A3_REFERENCE_CONDITION,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.open_loop import (
    create_random_open_loop_session,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.output_policy import (
    deterministic_random_session_outputs,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.profiles import (
    base_profile_payloads,
    participant_profile,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
    bundle_outcomes_from_dicts,
    session_outcomes_from_dicts,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.session_projection import (
    project_validation_session,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.condition import FatigueSigmaCondition
from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    GRADUAL_REFERENCE_ONLY_SESSION_END_POLICY_VERSION,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    NO_SESSION_END_RECOVERY_FRACTION,
    SelectedSessionFatiguePolicy,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.checkpoint import (
    atomic_write_json,
    utc_now,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import sha256_canonical
from symbiotic_sim_v2.runtime.experimental_multi_session.runner import (
    FatigueSigmaSingleConditionRunner,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.session_outcome import (
    ExperimentalSessionOutcome,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    physiology_root_seed_for_session,
)

from .analysis import analyze_factorial_records
from .conditions import (
    V2_REFERENCE_CONDITION,
    FactorialValidationCondition,
)
from .config import (
    AUTONOMOUS_ARM,
    FACTORIAL_MANIFEST_VERSION,
    FACTORIAL_PLAN_VERSION,
    SHARED_RANDOM_ARM,
    SHARED_RANDOM_COMPARATOR_VERSION,
    FactorialValidationConfig,
)
from .exports import export_factorial_results, write_artifact_digests
from .html_report import write_html_reports
from .persistence import (
    FactorialCodeFingerprint,
    RunDirectoryLock,
    ValidationCheckpoint,
    ValidationStore,
    load_checkpoint,
    write_checkpoint,
)
from .recommendation import condition_summary_rows, recommend_condition
from .shared_random import (
    clone_shared_random_for_condition,
    shared_random_cache_key,
    shared_random_result_checksum,
)

type ProgressCallback = Callable[[dict[str, Any]], None]
type AutonomousRunnerFactory = Callable[..., FatigueSigmaSingleConditionRunner]


@dataclass(frozen=True, slots=True)
class FactorialValidationRunSummary:
    run_id: str
    run_directory: Path
    status: str
    completed_actual_simulation_sessions: int
    planned_actual_simulation_sessions: int
    logical_comparison_sessions: int
    completed_jobs: int
    shared_random_participant_jobs: int
    report_path: Path
    checkpoint_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_directory": str(self.run_directory),
            "status": self.status,
            "completed_actual_simulation_sessions": (self.completed_actual_simulation_sessions),
            "planned_actual_simulation_sessions": (self.planned_actual_simulation_sessions),
            "logical_comparison_sessions": self.logical_comparison_sessions,
            "completed_jobs": self.completed_jobs,
            "shared_random_participant_jobs": self.shared_random_participant_jobs,
            "report_path": str(self.report_path),
            "checkpoint_path": str(self.checkpoint_path),
        }


def _random_job_id(participant_id: str) -> str:
    return f"shared_random|{participant_id}"


def _autonomous_job_id(condition_id: str, participant_id: str) -> str:
    return f"autonomous|{condition_id}|{participant_id}"


class FatigueRecoverySigmaFactorialRunner:
    """Run one shared random cohort and four participant-paired autonomous cohorts."""

    def __init__(
        self,
        config: FactorialValidationConfig | None = None,
        *,
        repo_root: Path | None = None,
        resume_directory: Path | None = None,
        progress_callback: ProgressCallback | None = None,
        autonomous_runner_factory: AutonomousRunnerFactory = (FatigueSigmaSingleConditionRunner),
        code_fingerprint: FactorialCodeFingerprint | None = None,
        allow_dirty_code: bool = False,
        timestamp_factory: Callable[[], str] = utc_now,
    ) -> None:
        if (config is None) == (resume_directory is None):
            raise ValueError("provide exactly one of config or resume_directory")
        if not callable(autonomous_runner_factory):
            raise TypeError("autonomous_runner_factory must be callable")
        if progress_callback is not None and not callable(progress_callback):
            raise TypeError("progress_callback must be callable")
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self._progress_callback = progress_callback
        self._runner_factory = autonomous_runner_factory
        self._provided_fingerprint = code_fingerprint
        self._allow_dirty_code = allow_dirty_code
        self._timestamp_factory = timestamp_factory
        self._cancel_requested = False
        self._started = 0.0
        self._shared_random_bundles: list[BundleOutcome] = []
        self._shared_random_sessions: list[SessionOutcome] = []
        self._autonomous_bundles: list[BundleOutcome] = []
        self._autonomous_sessions: list[SessionOutcome] = []
        self._session_audits: list[dict[str, Any]] = []
        self._shared_random_checksums: dict[str, str] = {}
        self._logical_bundles: list[BundleOutcome] = []
        self._logical_sessions: list[SessionOutcome] = []
        self._analysis: dict[str, tuple[dict[str, Any], ...]] = {}
        if resume_directory is None:
            assert config is not None
            self._prepare_new(config)
        else:
            self._prepare_resume(resume_directory.resolve())

    @property
    def config(self) -> FactorialValidationConfig:
        return self._config

    @property
    def run_directory(self) -> Path:
        return self._run_directory

    @property
    def checkpoint(self) -> ValidationCheckpoint:
        return self._checkpoint

    def request_cancel(self) -> None:
        self._cancel_requested = True
        self._checkpoint.cancel_requested = True
        write_checkpoint(self._checkpoint_path, self._checkpoint)

    def _capture_fingerprint(self) -> FactorialCodeFingerprint:
        return self._provided_fingerprint or FactorialCodeFingerprint.capture(
            self.repo_root,
            allow_dirty=self._allow_dirty_code,
        )

    def _prepare_new(self, config: FactorialValidationConfig) -> None:
        self._config = config
        self._fingerprint = self._capture_fingerprint()
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        created = self._timestamp_factory()
        identity = sha256_canonical(
            {
                "config": config.to_dict(),
                "fingerprint": self._fingerprint.digest,
                "created_at": created,
            }
        )[:10]
        self.run_id = f"{stamp}-{config.validation_preset}-{identity}"
        base = Path(config.output_directory)
        if not base.is_absolute():
            base = self.repo_root / base
        self._run_directory = base / self.run_id
        if self._run_directory.exists():
            raise FileExistsError(f"run directory already exists: {self._run_directory}")
        for name in ("logs", "report", "report/participants", "report/user_types"):
            (self._run_directory / name).mkdir(parents=True, exist_ok=True)
        if config.retain_details != "compact":
            (self._run_directory / "details" / "event_ledgers").mkdir(
                parents=True,
                exist_ok=True,
            )
        self._checkpoint_path = self._run_directory / "checkpoint.json"
        self._store = ValidationStore(self._run_directory)
        self._participants = build_participants(
            user_type_ids=config.user_type_ids,
            participants_per_type=config.participants_per_type,
            base_master_seed=config.base_master_seed,
            profile_payloads=base_profile_payloads(),
        )
        self._checkpoint = ValidationCheckpoint(
            run_id=self.run_id,
            planned_session_runs=config.planned_actual_simulation_sessions,
            created_at=created,
            updated_at=created,
        )
        self._manifest = self._manifest_payload(created)
        atomic_write_json(
            self._run_directory / "validation_manifest.json",
            self._manifest,
        )
        atomic_write_json(
            self._run_directory / "validation_plan.json",
            {
                "run_id": self.run_id,
                "config": config.to_dict(),
                "participants": [item.to_dict() for item in self._participants],
                "execution_order": [
                    "shared_random",
                    *[item.condition_id for item in config.conditions],
                ],
                "actual_simulation_sessions": config.planned_actual_simulation_sessions,
                "logical_comparison_sessions": config.planned_logical_comparison_sessions,
                "shared_random_reused_across_condition_count": len(config.conditions),
                "yoked_arm_included": False,
                "formal_spec_adoption": False,
                "schema_version": FACTORIAL_PLAN_VERSION,
            },
        )
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        self._log("run_prepared", created_at=created)

    def _manifest_payload(self, created_at: str) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": created_at,
            "config": self._config.to_dict(),
            "plan": {
                "autonomous_sessions": self._config.planned_autonomous_sessions,
                "shared_random_sessions": self._config.planned_shared_random_sessions,
                "logical_comparison_sessions": (self._config.planned_logical_comparison_sessions),
                "actual_simulation_sessions": (self._config.planned_actual_simulation_sessions),
            },
            "participants": [item.to_dict() for item in self._participants],
            "code_fingerprint": self._fingerprint.to_dict(),
            "shared_random_comparator_version": SHARED_RANDOM_COMPARATOR_VERSION,
            "shared_random_cache_key_fields": [
                "participant_id",
                "user_type_id",
                "physiology_seed",
                "maximum_sessions",
                "random_output_version",
                "code_fingerprint",
            ],
            "condition_in_physiology_seed": False,
            "condition_in_random_output_seed": False,
            "yoked_arm_included": False,
            "formal_spec_adoption": False,
            "simulation_only": True,
            "local_python_only": True,
            "external_network_used": False,
            "openai_codex_chatgpt_external_llm_used": False,
            "stage_08a3_records_analysis_charts_reused": True,
            "stage_08a2_checkpoint_io_reused": True,
            "simulation_core_copied": False,
            "architecture_receipt": {
                "selected_eta_shared_by_all_conditions": True,
                "within_session_rho_shared_by_all_conditions": True,
                "only_recovery_and_sigma_vary": True,
                "shared_random_executed_once_per_participant": True,
                "participant_is_aggregation_unit": True,
                "bundle_rows_pooled_as_participants": False,
                "cross_session_primary_measure": "delta_rmssd_ms",
                "cross_session_w_comparison": False,
                "past_sessions_only_history": True,
                "hidden_truth_used_by_observed_analysis": False,
            },
            "schema_version": FACTORIAL_MANIFEST_VERSION,
        }

    def _prepare_resume(self, run_directory: Path) -> None:
        manifest_path = run_directory / "validation_manifest.json"
        plan_path = run_directory / "validation_plan.json"
        checkpoint_path = run_directory / "checkpoint.json"
        if not all(path.is_file() for path in (manifest_path, plan_path, checkpoint_path)):
            raise ValueError("resume directory lacks manifest, plan, or checkpoint")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != FACTORIAL_MANIFEST_VERSION:
            raise ValueError("factorial validation manifest schema differs")
        self._manifest = manifest
        self.run_id = str(manifest["run_id"])
        self._run_directory = run_directory
        self._checkpoint_path = checkpoint_path
        self._config = FactorialValidationConfig.from_dict(manifest["config"])
        stored_fingerprint = FactorialCodeFingerprint.from_dict(dict(manifest["code_fingerprint"]))
        current_fingerprint = self._capture_fingerprint()
        stored_fingerprint.require_match(current_fingerprint)
        self._fingerprint = current_fingerprint
        self._checkpoint = load_checkpoint(checkpoint_path)
        if self._checkpoint.run_id != self.run_id:
            raise ValueError("checkpoint and manifest run IDs differ")
        if self._checkpoint.planned_session_runs != self._config.planned_actual_simulation_sessions:
            raise ValueError("checkpoint actual-session plan differs from manifest")
        if self._checkpoint.cancel_requested:
            self._checkpoint.cancel_requested = False
            write_checkpoint(self._checkpoint_path, self._checkpoint)
        self._store = ValidationStore(run_directory)
        self._participants = build_participants(
            user_type_ids=self._config.user_type_ids,
            participants_per_type=self._config.participants_per_type,
            base_master_seed=self._config.base_master_seed,
            profile_payloads=base_profile_payloads(),
        )
        if [item.to_dict() for item in self._participants] != manifest["participants"]:
            raise ValueError("reconstructed participants differ from manifest")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if plan.get("schema_version") != FACTORIAL_PLAN_VERSION:
            raise ValueError("factorial validation plan schema differs")
        if plan.get("config") != self._config.to_dict():
            raise ValueError("factorial validation plan differs from manifest config")
        if plan.get("participants") != manifest["participants"]:
            raise ValueError("factorial validation plan participants differ from manifest")
        if plan.get("actual_simulation_sessions") != self._checkpoint.planned_session_runs:
            raise ValueError("factorial validation plan differs from checkpoint budget")
        self._validate_completed_random_cache()
        self._log("run_resumed")

    def _log(self, message: str, **values: Any) -> None:
        path = self._run_directory / "logs" / "validation.log"
        record = {
            "time": utc_now(),
            "message": message,
            **values,
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()

    @staticmethod
    def _physiology_seed(
        participant: ValidationParticipant,
        session_index: int,
    ) -> int:
        return physiology_root_seed_for_session(
            master_seed=participant.physiology_seed,
            stationary_user_type_id=participant.user_type_id,
            session_index=session_index,
            policy=DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
        )

    def _condition_runner(
        self,
        participant: ValidationParticipant,
        condition: FactorialValidationCondition,
    ) -> FatigueSigmaSingleConditionRunner:
        # A remains the existing reference Core; B/C/D use the existing
        # Stage 8A.1 experimental Core with only recovery and sigma injected.
        internal_target = 0.0 if condition.condition_id == V2_REFERENCE_CONDITION else 0.15
        internal = FatigueSigmaCondition.create(
            user_type_id="green_hue_dominant_broad_bpm",
            selected_session_fatigue_target=internal_target,
            sigma_multiplier=condition.sigma_multiplier,
            maximum_sessions=self._config.maximum_sessions,
            master_seed=participant.physiology_seed,
            condition_id=(f"stage8a31:{condition.condition_id}:{participant.participant_id}"),
        )
        fatigue_override = None
        if not condition.is_stage8a3_reference_equivalent and not condition.uses_full_recovery:
            fatigue_override = SelectedSessionFatiguePolicy(
                selected_session_fatigue_target=0.15,
                unselected_session_end_recovery_fraction=(NO_SESSION_END_RECOVERY_FRACTION),
                session_end_policy_version=(GRADUAL_REFERENCE_ONLY_SESSION_END_POLICY_VERSION),
            )
        return self._runner_factory(
            internal,
            compare_reference_arm=False,
            stationary_user_type_profile_override=participant_profile(
                participant.user_type_id,
                participant.response_strength_scale,
            ),
            primary_reference_arm=condition.is_stage8a3_reference_equivalent,
            fatigue_policy_override=fatigue_override,
        )

    def _retain_event_ledger(
        self,
        *,
        participant: ValidationParticipant,
        condition_id: str,
        arm: str,
        session_index: int,
        engine: Any,
    ) -> None:
        policy = self._config.retain_details
        if policy == "compact" or (
            policy == "representative" and participant.participant_index != 0
        ):
            return
        filename = sha256_canonical(
            {
                "condition_id": condition_id,
                "participant_id": participant.participant_id,
                "arm": arm,
                "session_index": session_index,
            }
        )
        events = [item.to_dict() for item in engine.executed_events()]
        atomic_write_json(
            self._run_directory / "details" / "event_ledgers" / f"{filename}.json",
            {
                "participant_id": participant.participant_id,
                "user_type_id": participant.user_type_id,
                "condition_id": condition_id,
                "arm": arm,
                "session_index": session_index,
                "events": events,
                "engine_digest": engine.deterministic_digest(),
                "retention_policy": policy,
            },
        )

    def _run_shared_random_participant(
        self,
        participant: ValidationParticipant,
    ) -> tuple[tuple[BundleOutcome, ...], tuple[SessionOutcome, ...]]:
        bundles: list[BundleOutcome] = []
        sessions: list[SessionOutcome] = []
        profile = participant_profile(
            participant.user_type_id,
            participant.response_strength_scale,
        )
        projection_condition = validation_condition(STAGE08A3_REFERENCE_CONDITION)
        for session_index in range(self._config.maximum_sessions):
            outputs = deterministic_random_session_outputs(
                validation_master_seed=self._config.base_master_seed,
                participant_id=participant.participant_id,
                session_index=session_index,
            )
            seed = self._physiology_seed(participant, session_index)
            simulation = create_random_open_loop_session(
                physiology_root_seed=seed,
                profile=profile,
                outputs=outputs,
            )
            simulation.engine.run_until_end()
            if simulation.device is None:
                raise RuntimeError("shared random session did not attach the light device")
            projected_bundles, projected_session = project_validation_session(
                participant_id=participant.participant_id,
                user_type_id=participant.user_type_id,
                response_strength_scale=participant.response_strength_scale,
                condition=projection_condition,
                arm=RANDOM_ARM,
                session_index=session_index,
                physiology_seed=seed,
                evaluations=simulation.garden_input_component.evaluation_records(),
                states=simulation.device.stimulus_state_records(),
                engine_digest=simulation.engine.deterministic_digest(),
                random_outputs=outputs,
            )
            self._retain_event_ledger(
                participant=participant,
                condition_id="shared_condition_independent_random",
                arm=SHARED_RANDOM_ARM,
                session_index=session_index,
                engine=simulation.engine,
            )
            bundles.extend(projected_bundles)
            sessions.append(projected_session)
        return tuple(bundles), tuple(sessions)

    @staticmethod
    def _outcome_audit(
        participant: ValidationParticipant,
        condition: FactorialValidationCondition,
        outcome: ExperimentalSessionOutcome,
    ) -> dict[str, Any]:
        observation = None
        if outcome.holder_id is not None:
            epsilon = derive_relation_memory_intrinsic_profile(outcome.holder_id).epsilon_accept
            observation = WCeilingObservation.from_outcome(
                outcome,
                epsilon_accept=epsilon,
            )
        fatigue_records = [dict(value) for value in outcome.fatigue_trajectory_by_life.values()]
        sigma_records = [dict(value) for value in outcome.sigma_trajectory_by_life.values()]
        holder_sigma = next(
            (item for item in sigma_records if item.get("digital_life_id") == outcome.holder_id),
            {},
        )
        return {
            "participant_id": participant.participant_id,
            "user_type_id": participant.user_type_id,
            "condition_id": condition.condition_id,
            "configured_effective_selected_session_fatigue_target": (
                condition.effective_selected_session_fatigue_target
            ),
            "configured_eta_selected": condition.eta_selected,
            "configured_rho": condition.rho,
            "configured_session_end_recovery_policy": (
                condition.session_end_recovery_policy
            ),
            "configured_sigma_multiplier": condition.sigma_multiplier,
            "session_index": outcome.session_index,
            "physiology_seed": outcome.physiology_root_seed,
            "reference_arm": outcome.reference_arm,
            "candidate_generated": outcome.candidate_generated,
            "candidate_accepted": outcome.candidate_accepted,
            "adoption_result": outcome.adoption_result,
            "provisional_success": (
                False if observation is None else observation.provisional_success
            ),
            "confirmation_success": (
                False if observation is None else observation.confirmation_success
            ),
            "w_ceiling_blocked": (
                False
                if observation is None
                else observation.mathematically_impossible_provisional_adoption
            ),
            "w_anchor_session": (None if observation is None else observation.w_anchor_session),
            "epsilon_accept": (None if observation is None else observation.epsilon_accept),
            "nonselected_full_recovery_count": sum(
                bool(item.get("full_recovery_applied")) for item in fatigue_records
            ),
            "session_end_policy_versions": tuple(
                sorted({str(item.get("session_end_policy_version")) for item in fatigue_records})
            ),
            "eta_selected_values": tuple(
                sorted(
                    {
                        float(item["eta_selected"])
                        for item in fatigue_records
                        if item.get("eta_selected") is not None
                    }
                )
            ),
            "rho_values": tuple(
                sorted(
                    {
                        float(item["rho_reference"])
                        for item in fatigue_records
                        if item.get("rho_reference") is not None
                    }
                )
            ),
            "effective_sigma": holder_sigma.get("effective_sigma"),
            "sigma_multiplier": holder_sigma.get("sigma_multiplier"),
            "holder_id": outcome.holder_id,
            "holder_final_hue_degree": outcome.holder_final_hue_degree,
            "holder_final_blink_bpm": outcome.holder_final_blink_bpm,
        }

    def _run_autonomous_participant(
        self,
        participant: ValidationParticipant,
        condition: FactorialValidationCondition,
    ) -> tuple[
        tuple[BundleOutcome, ...],
        tuple[SessionOutcome, ...],
        tuple[dict[str, Any], ...],
    ]:
        runner = self._condition_runner(participant, condition)
        bundles: list[BundleOutcome] = []
        sessions: list[SessionOutcome] = []
        audits: list[dict[str, Any]] = []
        while runner.can_run_next_session:
            outcome = runner.run_next_session()
            simulation = runner.current_simulation
            if simulation is None or not outcome.valid_for_convergence:
                raise RuntimeError(
                    f"autonomous session failed before atomic completion: {outcome.invalid_reason}"
                )
            seed = self._physiology_seed(participant, outcome.session_index)
            if outcome.physiology_root_seed != seed:
                raise RuntimeError("autonomous physiology seed differs from paired policy")
            states = simulation.virtual_light_device_component.stimulus_state_records()
            projected_bundles, projected_session = project_validation_session(
                participant_id=participant.participant_id,
                user_type_id=participant.user_type_id,
                response_strength_scale=participant.response_strength_scale,
                condition=condition,  # type: ignore[arg-type]
                arm=AUTONOMOUS_ARM,
                session_index=outcome.session_index,
                physiology_seed=seed,
                evaluations=simulation.garden_input_component.evaluation_records(),
                states=states,
                engine_digest=simulation.engine.deterministic_digest(),
                autonomous_outcome=outcome,
            )
            self._retain_event_ledger(
                participant=participant,
                condition_id=condition.condition_id,
                arm=AUTONOMOUS_ARM,
                session_index=outcome.session_index,
                engine=simulation.engine,
            )
            bundles.extend(projected_bundles)
            sessions.append(projected_session)
            audits.append(self._outcome_audit(participant, condition, outcome))
        if len(sessions) != self._config.maximum_sessions:
            raise RuntimeError("autonomous participant did not reach planned sessions")
        return tuple(bundles), tuple(sessions), tuple(audits)

    def _write_completed(
        self,
        *,
        job_id: str,
        payload: Mapping[str, Any],
        session_count: int,
    ) -> None:
        path, checksum = self._store.write_completed(job_id, dict(payload))
        self._checkpoint.completed_jobs[job_id] = {
            "path": str(path.relative_to(self._run_directory)),
            "checksum": checksum,
        }
        self._checkpoint.completed_session_runs += session_count
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        self._log("job_completed", job_id=job_id, session_count=session_count)

    def _complete_shared_random(
        self,
        participant: ValidationParticipant,
        bundles: tuple[BundleOutcome, ...],
        sessions: tuple[SessionOutcome, ...],
    ) -> None:
        key = shared_random_cache_key(
            participant,
            maximum_sessions=self._config.maximum_sessions,
            code_fingerprint=self._fingerprint.digest,
        )
        result_checksum = shared_random_result_checksum(bundles, sessions)
        cache_payload = {
            "cache_key": key.to_dict(),
            "cache_key_digest": key.digest,
            "participant": participant.to_dict(),
            "bundles": [item.to_dict() for item in bundles],
            "sessions": [item.to_dict() for item in sessions],
            "result_checksum": result_checksum,
            "condition_independent": True,
            "schema_version": "shared_random_participant_result_v1",
        }
        _path, cache_checksum = self._store.write_donor_sequence(
            key.digest,
            cache_payload,
        )
        self._checkpoint.donor_sequence_checksums[key.digest] = cache_checksum
        self._write_completed(
            job_id=_random_job_id(participant.participant_id),
            payload={"job_kind": "shared_random", **cache_payload},
            session_count=len(sessions),
        )

    def _complete_autonomous(
        self,
        participant: ValidationParticipant,
        condition: FactorialValidationCondition,
        bundles: tuple[BundleOutcome, ...],
        sessions: tuple[SessionOutcome, ...],
        audits: tuple[dict[str, Any], ...],
    ) -> None:
        self._write_completed(
            job_id=_autonomous_job_id(
                condition.condition_id,
                participant.participant_id,
            ),
            payload={
                "job_kind": "autonomous",
                "participant": participant.to_dict(),
                "condition": condition.to_dict(),
                "bundles": [item.to_dict() for item in bundles],
                "sessions": [item.to_dict() for item in sessions],
                "session_audits": list(audits),
                "schema_version": "factorial_autonomous_participant_result_v1",
            },
            session_count=len(sessions),
        )

    def _progress(
        self,
        *,
        participant: ValidationParticipant,
        condition_id: str,
        arm: str,
    ) -> None:
        if self._progress_callback is None:
            return
        completed = self._checkpoint.completed_session_runs
        planned = self._checkpoint.planned_session_runs
        elapsed = max(0.0, time.monotonic() - self._started)
        eta = None if completed == 0 else elapsed * (planned - completed) / completed
        self._progress_callback(
            {
                "run_id": self.run_id,
                "condition": condition_id,
                "arm": arm,
                "user_type": participant.user_type_id,
                "participant": participant.participant_id,
                "completed_actual_simulation_sessions": completed,
                "planned_actual_simulation_sessions": planned,
                "logical_comparison_sessions": (self._config.planned_logical_comparison_sessions),
                "elapsed_seconds": elapsed,
                "eta_seconds": eta,
                "checkpoint": str(self._checkpoint_path),
                "report_path": str(self._run_directory / "report" / "report.html"),
            }
        )

    def _run_jobs(self) -> None:
        self._checkpoint.phase = "shared_random"
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        for participant in self._participants:
            if self._cancel_requested:
                return
            job_id = _random_job_id(participant.participant_id)
            if job_id in self._checkpoint.completed_jobs:
                continue
            try:
                bundles, sessions = self._run_shared_random_participant(participant)
            except Exception as exc:
                self._store.write_failed(
                    job_id,
                    {"error_type": type(exc).__name__, "error": str(exc)},
                )
                raise
            self._complete_shared_random(participant, bundles, sessions)
            self._progress(
                participant=participant,
                condition_id="shared_condition_independent_random",
                arm=SHARED_RANDOM_ARM,
            )
        for condition in self._config.conditions:
            self._checkpoint.phase = f"autonomous:{condition.condition_id}"
            write_checkpoint(self._checkpoint_path, self._checkpoint)
            for participant in self._participants:
                if self._cancel_requested:
                    return
                job_id = _autonomous_job_id(
                    condition.condition_id,
                    participant.participant_id,
                )
                if job_id in self._checkpoint.completed_jobs:
                    continue
                try:
                    bundles, sessions, audits = self._run_autonomous_participant(
                        participant,
                        condition,
                    )
                except Exception as exc:
                    self._store.write_failed(
                        job_id,
                        {"error_type": type(exc).__name__, "error": str(exc)},
                    )
                    raise
                self._complete_autonomous(
                    participant,
                    condition,
                    bundles,
                    sessions,
                    audits,
                )
                self._progress(
                    participant=participant,
                    condition_id=condition.condition_id,
                    arm=AUTONOMOUS_ARM,
                )

    def _validate_completed_random_cache(self) -> None:
        for participant in self._participants:
            job_id = _random_job_id(participant.participant_id)
            if job_id not in self._checkpoint.completed_jobs:
                continue
            payload = self._store.read_completed(self._checkpoint, job_id)
            if payload.get("job_kind") != "shared_random":
                raise ValueError("shared random completed job has the wrong kind")
            key = shared_random_cache_key(
                participant,
                maximum_sessions=self._config.maximum_sessions,
                code_fingerprint=self._fingerprint.digest,
            )
            if payload.get("cache_key") != key.to_dict():
                raise ValueError("shared random cache key differs on resume")
            cache_checksum = self._checkpoint.donor_sequence_checksums.get(key.digest)
            if cache_checksum is None:
                raise ValueError("shared random cache checksum is missing")
            cached = self._store.read_donor_sequence(key.digest, cache_checksum)
            expected_cache = {key: value for key, value in payload.items() if key != "job_kind"}
            if cached != expected_cache:
                raise ValueError("shared random cache payload differs from completed job")
            bundles = bundle_outcomes_from_dicts(payload["bundles"])
            sessions = session_outcomes_from_dicts(payload["sessions"])
            if shared_random_result_checksum(bundles, sessions) != payload.get("result_checksum"):
                raise ValueError("shared random result checksum differs on resume")

    def _load_completed_results(self) -> None:
        self._shared_random_bundles.clear()
        self._shared_random_sessions.clear()
        self._autonomous_bundles.clear()
        self._autonomous_sessions.clear()
        self._session_audits.clear()
        self._shared_random_checksums.clear()
        self._validate_completed_random_cache()
        for job_id in sorted(self._checkpoint.completed_jobs):
            payload = self._store.read_completed(self._checkpoint, job_id)
            kind = payload.get("job_kind")
            bundles = bundle_outcomes_from_dicts(payload["bundles"])
            sessions = session_outcomes_from_dicts(payload["sessions"])
            if kind == "shared_random":
                self._shared_random_bundles.extend(bundles)
                self._shared_random_sessions.extend(sessions)
                participant_id = str(payload["participant"]["participant_id"])
                self._shared_random_checksums[participant_id] = str(payload["result_checksum"])
            elif kind == "autonomous":
                self._autonomous_bundles.extend(bundles)
                self._autonomous_sessions.extend(sessions)
                self._session_audits.extend(dict(item) for item in payload["session_audits"])
            else:
                raise ValueError(f"unknown completed factorial job kind: {kind!r}")

    def _build_logical_comparisons(self) -> None:
        self._logical_bundles = list(self._autonomous_bundles)
        self._logical_sessions = list(self._autonomous_sessions)
        raw_bundles = tuple(self._shared_random_bundles)
        raw_sessions = tuple(self._shared_random_sessions)
        raw_checksum = shared_random_result_checksum(raw_bundles, raw_sessions)
        for condition in self._config.conditions:
            bundles, sessions = clone_shared_random_for_condition(
                raw_bundles,
                raw_sessions,
                condition_id=condition.condition_id,
            )
            if shared_random_result_checksum(bundles, sessions) != raw_checksum:
                raise RuntimeError("logical condition changed shared random comparator")
            self._logical_bundles.extend(bundles)
            self._logical_sessions.extend(sessions)
        if len(self._logical_sessions) != (self._config.planned_logical_comparison_sessions):
            raise RuntimeError("logical comparison session count differs from plan")

    def _validate_pairing(self) -> None:
        random_by_key = {
            (item.participant_id, item.condition_id, item.session_index): item
            for item in self._logical_sessions
            if item.arm == SHARED_RANDOM_ARM
        }
        for item in self._logical_sessions:
            if item.arm != AUTONOMOUS_ARM:
                continue
            random = random_by_key[(item.participant_id, item.condition_id, item.session_index)]
            if item.physiology_seed != random.physiology_seed:
                raise RuntimeError("autonomous/random physiology seed pairing differs")
            if (
                item.baseline_rmssd_ms is not None
                and random.baseline_rmssd_ms is not None
                and not math.isclose(
                    item.baseline_rmssd_ms,
                    random.baseline_rmssd_ms,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
            ):
                raise RuntimeError("autonomous/random baseline pairing differs")

    def _analyze_and_report(self) -> None:
        self._build_logical_comparisons()
        self._validate_pairing()
        self._analysis = analyze_factorial_records(
            self._logical_bundles,
            self._logical_sessions,
            session_audits=self._session_audits,
        )
        summaries = condition_summary_rows(self._analysis["participant_condition_effects"])
        recommendation = recommend_condition(summaries)
        export_factorial_results(
            self._run_directory,
            participants=self._participants,
            conditions=self._config.conditions,
            shared_random_bundles=self._shared_random_bundles,
            shared_random_sessions=self._shared_random_sessions,
            autonomous_bundles=self._autonomous_bundles,
            autonomous_sessions=self._autonomous_sessions,
            logical_bundles=self._logical_bundles,
            logical_sessions=self._logical_sessions,
            session_audits=self._session_audits,
            shared_random_checksums=self._shared_random_checksums,
            analysis=self._analysis,
            condition_summaries=summaries,
            recommendation=recommendation,
        )
        self._checkpoint.analysis_complete = True
        self._checkpoint.phase = "analysis"
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        reproduction_command = (
            "python -m symbiotic_sim_v2 "
            "--headless-fatigue-recovery-sigma-factorial-validation "
            f"--resume {self._run_directory}"
        )
        report_path, participant_paths, user_type_paths = write_html_reports(
            self._run_directory,
            manifest=self._manifest,
            conditions=self._config.conditions,
            participants=self._participants,
            bundles=self._logical_bundles,
            sessions=self._logical_sessions,
            analysis=self._analysis,
            condition_summaries=summaries,
            recommendation=recommendation,
            reproduction_command=reproduction_command,
        )
        write_artifact_digests(self._run_directory)
        self._checkpoint.report_complete = True
        self._checkpoint.phase = "completed"
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        self._log(
            "report_completed",
            report_path=str(report_path),
            participant_report_count=len(participant_paths),
            user_type_report_count=len(user_type_paths),
        )

    def _summary(self, status: str) -> FactorialValidationRunSummary:
        return FactorialValidationRunSummary(
            run_id=self.run_id,
            run_directory=self._run_directory,
            status=status,
            completed_actual_simulation_sessions=(self._checkpoint.completed_session_runs),
            planned_actual_simulation_sessions=(self._checkpoint.planned_session_runs),
            logical_comparison_sessions=(self._config.planned_logical_comparison_sessions),
            completed_jobs=len(self._checkpoint.completed_jobs),
            shared_random_participant_jobs=sum(
                job_id.startswith("shared_random|") for job_id in self._checkpoint.completed_jobs
            ),
            report_path=self._run_directory / "report" / "report.html",
            checkpoint_path=self._checkpoint_path,
        )

    def run(self) -> FactorialValidationRunSummary:
        self._started = time.monotonic()
        with RunDirectoryLock(self._run_directory):
            if self._checkpoint.report_complete:
                self._validate_completed_random_cache()
                return self._summary("completed")
            self._run_jobs()
            if self._cancel_requested:
                self._checkpoint.phase = "cancelled"
                write_checkpoint(self._checkpoint_path, self._checkpoint)
                return self._summary("cancelled")
            if self._checkpoint.completed_session_runs != (
                self._config.planned_actual_simulation_sessions
            ):
                raise RuntimeError("completed actual sessions differ from plan")
            self._load_completed_results()
            self._analyze_and_report()
            return self._summary("completed")


__all__ = [
    "FactorialValidationRunSummary",
    "FatigueRecoverySigmaFactorialRunner",
]
