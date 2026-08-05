"""Checkpointed local orchestration for the three Stage 8A.3 arms."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma.condition import FatigueSigmaCondition
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.checkpoint import (
    atomic_write_json,
    utc_now,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import sha256_canonical
from symbiotic_sim_v2.runtime.experimental_multi_session.runner import (
    FatigueSigmaSingleConditionRunner,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    physiology_root_seed_for_session,
)

from .analysis import analyze_validation_records
from .config import (
    ARM_IDS,
    AUTONOMOUS_ARM,
    RANDOM_ARM,
    VALIDATION_MANIFEST_VERSION,
    YOKED_ARM,
    ValidationCondition,
    ValidationConfig,
    ValidationParticipant,
    arm_contract,
    build_participants,
)
from .exports import export_validation_results
from .fingerprint import ValidationCodeFingerprint
from .html_report import write_html_reports
from .open_loop import create_random_open_loop_session, create_yoked_replay_session
from .output_policy import (
    YokeAssignment,
    cyclic_yoke_map,
    deterministic_random_session_outputs,
)
from .persistence import (
    RunDirectoryLock,
    ValidationCheckpoint,
    ValidationStore,
    load_checkpoint,
    write_checkpoint,
)
from .profiles import base_profile_payloads, participant_profile
from .records import (
    BundleOutcome,
    ReplayLightState,
    SessionOutcome,
    bundle_outcomes_from_dicts,
    session_outcomes_from_dicts,
)
from .session_projection import (
    light_state_records_from_replay,
    project_validation_session,
    replay_states_from_device,
)

type ProgressCallback = Callable[[dict[str, Any]], None]
type AutonomousRunnerFactory = Callable[..., FatigueSigmaSingleConditionRunner]


@dataclass(frozen=True, slots=True)
class ValidationRunSummary:
    run_id: str
    run_directory: Path
    status: str
    completed_session_runs: int
    planned_session_runs: int
    completed_participant_arm_jobs: int
    report_path: Path
    checkpoint_path: Path
    valid_participant_count: int
    current_autonomous_minus_yoked_effect_ms: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_directory": str(self.run_directory),
            "status": self.status,
            "completed_session_runs": self.completed_session_runs,
            "planned_session_runs": self.planned_session_runs,
            "completed_participant_arm_jobs": self.completed_participant_arm_jobs,
            "report_path": str(self.report_path),
            "checkpoint_path": str(self.checkpoint_path),
            "valid_participant_count": self.valid_participant_count,
            "current_autonomous_minus_yoked_effect_ms": (
                self.current_autonomous_minus_yoked_effect_ms
            ),
        }


def _hidden_seed(participant: ValidationParticipant) -> int:
    payload = (
        f"stage8a3-hidden-donor:{participant.participant_id}:"
        f"{participant.physiology_seed}"
    ).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _job_id(condition_id: str, participant_id: str, arm: str) -> str:
    return f"{condition_id}|{participant_id}|{arm}"


def _donor_identity(
    condition_id: str,
    participant_id: str,
    session_index: int,
) -> str:
    return f"{condition_id}|{participant_id}|session-{session_index:04d}"


def _participant_payload(
    *,
    participant: ValidationParticipant,
    condition: ValidationCondition,
    arm: str,
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
) -> dict[str, Any]:
    return {
        "participant": participant.to_dict(),
        "condition": condition.to_dict(),
        "arm_contract": arm_contract(arm).to_dict(),
        "bundles": [item.to_dict() for item in bundles],
        "sessions": [item.to_dict() for item in sessions],
        "session_count": len(sessions),
        "schema_version": "adaptive_placebo_participant_arm_result_v1",
    }


class AdaptivePlaceboValidationRunner:
    """Run autonomous cohorts, then exact yokes, then random open-loop cohorts."""

    def __init__(
        self,
        config: ValidationConfig | None = None,
        *,
        repo_root: Path | None = None,
        resume_directory: Path | None = None,
        progress_callback: ProgressCallback | None = None,
        autonomous_runner_factory: AutonomousRunnerFactory = (
            FatigueSigmaSingleConditionRunner
        ),
        code_fingerprint: ValidationCodeFingerprint | None = None,
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
        self._bundles: list[BundleOutcome] = []
        self._sessions: list[SessionOutcome] = []
        self._yoke_rows: list[dict[str, Any]] = []
        self._baseline_diagnostics: list[dict[str, Any]] = []
        self._analysis: dict[str, tuple[dict[str, Any], ...]] = {}
        if resume_directory is None:
            assert config is not None
            self._prepare_new(config)
        else:
            self._prepare_resume(resume_directory.resolve())

    @property
    def config(self) -> ValidationConfig:
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

    def _capture_fingerprint(self) -> ValidationCodeFingerprint:
        return self._provided_fingerprint or ValidationCodeFingerprint.capture(
            self.repo_root,
            allow_dirty=self._allow_dirty_code,
        )

    def _prepare_new(self, config: ValidationConfig) -> None:
        self._config = config
        self._fingerprint = self._capture_fingerprint()
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        identity = sha256_canonical(
            {
                "config": config.to_dict(),
                "fingerprint": self._fingerprint.digest,
                "created_at": self._timestamp_factory(),
            }
        )[:10]
        self.run_id = f"{stamp}-{config.validation_preset}-{identity}"
        base = Path(config.output_directory)
        if not base.is_absolute():
            base = self.repo_root / base
        self._run_directory = base / self.run_id
        if self._run_directory.exists():
            raise FileExistsError(f"run directory already exists: {self._run_directory}")
        for name in ("logs", "report", "report/participants"):
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
        created = self._timestamp_factory()
        self._checkpoint = ValidationCheckpoint(
            run_id=self.run_id,
            planned_session_runs=config.planned_target_session_runs,
            created_at=created,
            updated_at=created,
        )
        self._manifest = self._manifest_payload(created)
        atomic_write_json(self._run_directory / "validation_manifest.json", self._manifest)
        atomic_write_json(
            self._run_directory / "validation_plan.json",
            {
                "run_id": self.run_id,
                "config": config.to_dict(),
                "participants": [item.to_dict() for item in self._participants],
                "execution_order": list(ARM_IDS),
                "autonomous_cohort_must_complete_before_yoke": True,
                "autonomous_donor_runs_reused": True,
                "planned_target_session_runs": config.planned_target_session_runs,
                "schema_version": "adaptive_placebo_validation_plan_v1",
            },
        )
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        self._log("run_created")

    def _manifest_payload(self, created_at: str) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": created_at,
            "config": self._config.to_dict(),
            "code_fingerprint": self._fingerprint.to_dict(),
            "checkpoint_path": "checkpoint.json",
            "formal_spec_adoption": False,
            "local_python_only": True,
            "external_network_used": False,
            "openai_codex_chatgpt_external_llm_used": False,
            "stage_08a1_runner_reused": True,
            "stage_08a2_checkpoint_report_io_reused": True,
            "simulation_core_copied": False,
            "event_ledger_retention": {
                "policy": self._config.retain_details,
                "compact_saves_no_event_ledger": True,
                "representative_participant_index": (
                    0 if self._config.retain_details == "representative" else None
                ),
                "all_is_smoke_only": True,
            },
            "architecture_receipt": {
                "only_autonomous_uses_target_rmssd_for_future_output": True,
                "yoked_target_rmssd_used_for_output": False,
                "random_target_rmssd_used_for_output": False,
                "past_sessions_only_history": True,
                "future_data_leakage": False,
                "hidden_preference_used_by_observed_analysis": False,
                "condition_arm_donor_excluded_from_physiology_seed": True,
                "participant_is_aggregation_unit": True,
                "cross_session_primary_physiology_measure": "delta_rmssd_ms",
                "cross_session_w_comparison": False,
            },
            "schema_version": VALIDATION_MANIFEST_VERSION,
        }

    def _prepare_resume(self, run_directory: Path) -> None:
        manifest_path = run_directory / "validation_manifest.json"
        plan_path = run_directory / "validation_plan.json"
        checkpoint_path = run_directory / "checkpoint.json"
        if not all(path.is_file() for path in (manifest_path, plan_path, checkpoint_path)):
            raise ValueError("resume directory is missing manifest, plan, or checkpoint")
        self._run_directory = run_directory
        self._checkpoint_path = checkpoint_path
        self._manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if self._manifest.get("schema_version") != VALIDATION_MANIFEST_VERSION:
            raise ValueError("validation manifest schema mismatch")
        self.run_id = str(self._manifest["run_id"])
        self._config = ValidationConfig.from_dict(self._manifest["config"])
        self._fingerprint = self._capture_fingerprint()
        recorded = ValidationCodeFingerprint.from_dict(
            self._manifest["code_fingerprint"]
        )
        recorded.require_match(self._fingerprint)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if plan.get("config") != self._config.to_dict():
            raise ValueError("resume plan differs from manifest config")
        self._participants = tuple(
            ValidationParticipant.from_dict(item) for item in plan["participants"]
        )
        self._checkpoint = load_checkpoint(checkpoint_path)
        if (
            self._checkpoint.run_id != self.run_id
            or self._checkpoint.planned_session_runs
            != self._config.planned_target_session_runs
        ):
            raise ValueError("resume checkpoint differs from manifest plan")
        self._checkpoint.cancel_requested = False
        self._store = ValidationStore(run_directory)
        if self._config.retain_details != "compact":
            (run_directory / "details" / "event_ledgers").mkdir(
                parents=True,
                exist_ok=True,
            )
        for identity, checksum in self._checkpoint.donor_sequence_checksums.items():
            self._store.read_donor_sequence(identity, checksum)
        self._load_completed_results()
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        self._log("run_resumed")

    def _log(self, message: str, **values: Any) -> None:
        path = self._run_directory / "logs" / "validation.log"
        payload = {
            "timestamp": self._timestamp_factory(),
            "message": message,
            **values,
        }
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()

    def _load_completed_results(self) -> None:
        self._bundles.clear()
        self._sessions.clear()
        for job_id in sorted(self._checkpoint.completed_jobs):
            payload = self._store.read_completed(self._checkpoint, job_id)
            self._bundles.extend(bundle_outcomes_from_dicts(payload["bundles"]))
            self._sessions.extend(session_outcomes_from_dicts(payload["sessions"]))

    def _condition_runner(
        self,
        participant: ValidationParticipant,
        condition: ValidationCondition,
    ) -> FatigueSigmaSingleConditionRunner:
        # The existing condition type validates only the Stage 8A.1 registry.
        # The explicit profile override is the narrow Stage 8A.3 injection seam.
        internal = FatigueSigmaCondition.create(
            user_type_id="green_hue_dominant_broad_bpm",
            selected_session_fatigue_target=condition.selected_session_fatigue_target,
            sigma_multiplier=condition.sigma_multiplier,
            maximum_sessions=self._config.maximum_sessions,
            master_seed=participant.physiology_seed,
            condition_id=(
                f"stage8a3:{condition.condition_id}:{participant.participant_id}"
            ),
        )
        return self._runner_factory(
            internal,
            compare_reference_arm=False,
            stationary_user_type_profile_override=participant_profile(
                participant.user_type_id,
                participant.response_strength_scale,
            ),
            primary_reference_arm=condition.is_reference,
        )

    def _retain_event_ledger(
        self,
        *,
        participant: ValidationParticipant,
        condition: ValidationCondition,
        arm: str,
        session_index: int,
        engine: Any,
    ) -> None:
        policy = self._config.retain_details
        if policy == "compact" or (
            policy == "representative" and participant.participant_index != 0
        ):
            return
        identity = _job_id(condition.condition_id, participant.participant_id, arm)
        filename = sha256_canonical(
            {"job_id": identity, "session_index": session_index}
        )
        events = [event.to_dict() for event in engine.executed_events()]
        atomic_write_json(
            self._run_directory / "details" / "event_ledgers" / f"{filename}.json",
            {
                "participant_id": participant.participant_id,
                "user_type_id": participant.user_type_id,
                "condition_id": condition.condition_id,
                "arm": arm,
                "session_index": session_index,
                "event_count": len(events),
                "engine_digest": engine.deterministic_digest(),
                "events": events,
                "retention_policy": policy,
                "schema_version": "adaptive_placebo_event_ledger_v1",
            },
        )

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

    def _run_autonomous_participant(
        self,
        participant: ValidationParticipant,
        condition: ValidationCondition,
        *,
        count_as_target: bool = True,
    ) -> tuple[tuple[BundleOutcome, ...], tuple[SessionOutcome, ...]]:
        runner = self._condition_runner(participant, condition)
        bundles: list[BundleOutcome] = []
        sessions: list[SessionOutcome] = []
        while runner.can_run_next_session:
            outcome = runner.run_next_session()
            simulation = runner.current_simulation
            if simulation is None or not outcome.valid_for_convergence:
                raise RuntimeError(
                    "autonomous participant session failed before atomic completion: "
                    f"{outcome.invalid_reason}"
                )
            session_index = outcome.session_index
            seed = self._physiology_seed(participant, session_index)
            if outcome.physiology_root_seed != seed:
                raise RuntimeError("autonomous physiology seed differs from paired policy")
            states = simulation.virtual_light_device_component.stimulus_state_records()
            replay = replay_states_from_device(
                session_index=session_index,
                source_participant_id=participant.participant_id,
                states=states,
            )
            identity = _donor_identity(
                condition.condition_id,
                participant.participant_id,
                session_index,
            )
            _path, checksum = self._store.write_donor_sequence(
                identity,
                [item.to_dict() for item in replay],
            )
            self._checkpoint.donor_sequence_checksums[identity] = checksum
            projected_bundles, projected_session = project_validation_session(
                participant_id=participant.participant_id,
                user_type_id=participant.user_type_id,
                response_strength_scale=participant.response_strength_scale,
                condition=condition,
                arm=AUTONOMOUS_ARM,
                session_index=session_index,
                physiology_seed=seed,
                evaluations=simulation.garden_input_component.evaluation_records(),
                states=states,
                engine_digest=simulation.engine.deterministic_digest(),
                autonomous_outcome=outcome,
            )
            self._retain_event_ledger(
                participant=participant,
                condition=condition,
                arm=AUTONOMOUS_ARM,
                session_index=session_index,
                engine=simulation.engine,
            )
            bundles.extend(projected_bundles)
            sessions.append(projected_session)
        if count_as_target and len(sessions) != self._config.maximum_sessions:
            raise RuntimeError("autonomous participant did not reach the planned sessions")
        return tuple(bundles), tuple(sessions)

    def _run_yoked_participant(
        self,
        target: ValidationParticipant,
        donor: ValidationParticipant,
        condition: ValidationCondition,
    ) -> tuple[tuple[BundleOutcome, ...], tuple[SessionOutcome, ...]]:
        bundles: list[BundleOutcome] = []
        sessions: list[SessionOutcome] = []
        profile = participant_profile(
            target.user_type_id,
            target.response_strength_scale,
        )
        for session_index in range(self._config.maximum_sessions):
            identity = _donor_identity(
                condition.condition_id,
                donor.participant_id,
                session_index,
            )
            checksum = self._checkpoint.donor_sequence_checksums.get(identity)
            if checksum is None:
                raise RuntimeError("yoked replay started before donor cohort completed")
            payload = self._store.read_donor_sequence(identity, checksum)
            replay = tuple(ReplayLightState.from_dict(item) for item in payload)
            if any(item.source_participant_id != donor.participant_id for item in replay):
                raise RuntimeError("donor sequence provenance differs from yoke map")
            seed = self._physiology_seed(target, session_index)
            simulation = create_yoked_replay_session(
                physiology_root_seed=seed,
                profile=profile,
                replay_states=replay,
            )
            simulation.engine.run_until_end()
            projected_bundles, projected_session = project_validation_session(
                participant_id=target.participant_id,
                user_type_id=target.user_type_id,
                response_strength_scale=target.response_strength_scale,
                condition=condition,
                arm=YOKED_ARM,
                session_index=session_index,
                physiology_seed=seed,
                evaluations=simulation.garden_input_component.evaluation_records(),
                states=light_state_records_from_replay(replay),
                engine_digest=simulation.engine.deterministic_digest(),
                source_participant_id=donor.participant_id,
            )
            self._retain_event_ledger(
                participant=target,
                condition=condition,
                arm=YOKED_ARM,
                session_index=session_index,
                engine=simulation.engine,
            )
            bundles.extend(projected_bundles)
            sessions.append(projected_session)
        return tuple(bundles), tuple(sessions)

    def _run_random_participant(
        self,
        participant: ValidationParticipant,
        condition: ValidationCondition,
    ) -> tuple[tuple[BundleOutcome, ...], tuple[SessionOutcome, ...]]:
        bundles: list[BundleOutcome] = []
        sessions: list[SessionOutcome] = []
        profile = participant_profile(
            participant.user_type_id,
            participant.response_strength_scale,
        )
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
                raise RuntimeError("random open loop did not attach the existing light device")
            projected_bundles, projected_session = project_validation_session(
                participant_id=participant.participant_id,
                user_type_id=participant.user_type_id,
                response_strength_scale=participant.response_strength_scale,
                condition=condition,
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
                condition=condition,
                arm=RANDOM_ARM,
                session_index=session_index,
                engine=simulation.engine,
            )
            bundles.extend(projected_bundles)
            sessions.append(projected_session)
        return tuple(bundles), tuple(sessions)

    def _complete_job(
        self,
        *,
        participant: ValidationParticipant,
        condition: ValidationCondition,
        arm: str,
        bundles: Sequence[BundleOutcome],
        sessions: Sequence[SessionOutcome],
        donor: str | None = None,
    ) -> None:
        job_id = _job_id(condition.condition_id, participant.participant_id, arm)
        payload = _participant_payload(
            participant=participant,
            condition=condition,
            arm=arm,
            bundles=bundles,
            sessions=sessions,
        )
        path, checksum = self._store.write_completed(job_id, payload)
        self._checkpoint.completed_jobs[job_id] = {
            "path": str(path.relative_to(self._run_directory)),
            "checksum": checksum,
        }
        self._checkpoint.completed_session_runs += len(sessions)
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        self._bundles.extend(bundles)
        self._sessions.extend(sessions)
        self._log(
            "participant_arm_completed",
            job_id=job_id,
            session_count=len(sessions),
        )
        self._progress(
            condition=condition,
            participant=participant,
            arm=arm,
            donor=donor,
        )

    def _progress(
        self,
        *,
        condition: ValidationCondition,
        participant: ValidationParticipant,
        arm: str,
        donor: str | None,
    ) -> None:
        if self._progress_callback is None:
            return
        elapsed = max(0.0, time.monotonic() - self._started)
        completed = self._checkpoint.completed_session_runs
        planned = self._checkpoint.planned_session_runs
        eta = None if completed == 0 else elapsed * (planned - completed) / completed
        effect, valid = self._current_effect()
        self._progress_callback(
            {
                "run_id": self.run_id,
                "condition": condition.condition_id,
                "arm": arm,
                "user_type": participant.user_type_id,
                "participant": participant.participant_id,
                "donor": donor,
                "completed_sessions": completed,
                "planned_sessions": planned,
                "elapsed_seconds": elapsed,
                "eta_seconds": eta,
                "current_aggregate_autonomous_minus_yoked_effect_ms": effect,
                "current_valid_participant_count": valid,
                "checkpoint": str(self._checkpoint_path),
                "report_path": str(self._run_directory / "report" / "report.html"),
            }
        )

    def _current_effect(self) -> tuple[float | None, int]:
        by_key: dict[tuple[str, str, str], list[SessionOutcome]] = defaultdict(list)
        for item in self._sessions:
            by_key[(item.participant_id, item.condition_id, item.arm)].append(item)
        differences: list[float] = []
        for participant_id, condition_id, arm in sorted(by_key):
            if arm != AUTONOMOUS_ARM:
                continue
            auto = [
                item.mean_valid_bundle_delta_rmssd_ms
                for item in by_key[(participant_id, condition_id, AUTONOMOUS_ARM)]
                if item.mean_valid_bundle_delta_rmssd_ms is not None
            ]
            yoke = [
                item.mean_valid_bundle_delta_rmssd_ms
                for item in by_key.get((participant_id, condition_id, YOKED_ARM), ())
                if item.mean_valid_bundle_delta_rmssd_ms is not None
            ]
            if auto and yoke:
                third = max(1, math.ceil(min(len(auto), len(yoke)) / 3))
                differences.append(
                    sum(auto[-third:]) / third - sum(yoke[-third:]) / third
                )
        return (
            None if not differences else sum(differences) / len(differences),
            len(differences),
        )

    def _participants_for_type(self, user_type_id: str) -> tuple[ValidationParticipant, ...]:
        return tuple(
            item for item in self._participants if item.user_type_id == user_type_id
        )

    def _hidden_donor(
        self,
        target: ValidationParticipant,
    ) -> ValidationParticipant:
        return ValidationParticipant(
            participant_id=f"{target.participant_id}__hidden_donor",
            user_type_id=target.user_type_id,
            participant_index=target.participant_index + 1,
            physiology_seed=_hidden_seed(target),
            response_strength_scale=target.response_strength_scale,
            profile_hash=target.profile_hash,
        )

    def _assignment_donor(
        self,
        assignment: YokeAssignment,
        participants: Sequence[ValidationParticipant],
    ) -> ValidationParticipant:
        if assignment.hidden_donor:
            target = next(
                item
                for item in participants
                if item.participant_id == assignment.target_participant_id
            )
            return self._hidden_donor(target)
        return next(
            item
            for item in participants
            if item.participant_id == assignment.donor_participant_id
        )

    def _ensure_hidden_donor(
        self,
        donor: ValidationParticipant,
        condition: ValidationCondition,
    ) -> None:
        first_identity = _donor_identity(condition.condition_id, donor.participant_id, 0)
        if first_identity in self._checkpoint.donor_sequence_checksums:
            for session_index in range(self._config.maximum_sessions):
                identity = _donor_identity(
                    condition.condition_id,
                    donor.participant_id,
                    session_index,
                )
                checksum = self._checkpoint.donor_sequence_checksums[identity]
                self._store.read_donor_sequence(identity, checksum)
            return
        self._run_autonomous_participant(donor, condition, count_as_target=False)
        write_checkpoint(self._checkpoint_path, self._checkpoint)

    def _make_yoke_rows(
        self,
        condition: ValidationCondition,
        assignments: Sequence[YokeAssignment],
        participants: Sequence[ValidationParticipant],
    ) -> None:
        existing = {
            (row["condition_id"], row["target_participant_id"])
            for row in self._yoke_rows
        }
        for assignment in assignments:
            key = (condition.condition_id, assignment.target_participant_id)
            if key in existing:
                continue
            target = next(
                item
                for item in participants
                if item.participant_id == assignment.target_participant_id
            )
            donor = self._assignment_donor(assignment, participants)
            checksums = [
                self._checkpoint.donor_sequence_checksums[
                    _donor_identity(
                        condition.condition_id,
                        donor.participant_id,
                        session_index,
                    )
                ]
                for session_index in range(self._config.maximum_sessions)
            ]
            self._yoke_rows.append(
                {
                    **assignment.to_dict(),
                    "condition_id": condition.condition_id,
                    "donor_arm": AUTONOMOUS_ARM,
                    "target_response_strength_scale": target.response_strength_scale,
                    "donor_response_strength_scale": donor.response_strength_scale,
                    "target_physiology_seed": target.physiology_seed,
                    "donor_physiology_seed": donor.physiology_seed,
                    "output_sequence_digest": sha256_canonical(checksums),
                }
            )

    def _run_jobs(self) -> None:
        for condition in self._config.conditions:
            for user_type_id in self._config.user_type_ids:
                participants = self._participants_for_type(user_type_id)
                self._checkpoint.phase = "autonomous"
                for participant in participants:
                    if self._cancel_requested:
                        return
                    job_id = _job_id(
                        condition.condition_id,
                        participant.participant_id,
                        AUTONOMOUS_ARM,
                    )
                    if job_id in self._checkpoint.completed_jobs:
                        continue
                    try:
                        bundles, sessions = self._run_autonomous_participant(
                            participant,
                            condition,
                        )
                    except Exception as exc:
                        self._store.write_failed(
                            job_id,
                            {
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            },
                        )
                        self._log("participant_arm_failed", job_id=job_id, error=str(exc))
                        raise
                    self._complete_job(
                        participant=participant,
                        condition=condition,
                        arm=AUTONOMOUS_ARM,
                        bundles=bundles,
                        sessions=sessions,
                    )
                assignments = cyclic_yoke_map(participants)
                for assignment in assignments:
                    if assignment.hidden_donor:
                        self._ensure_hidden_donor(
                            self._assignment_donor(assignment, participants),
                            condition,
                        )
                scope = f"{condition.condition_id}|{user_type_id}"
                if scope not in self._checkpoint.yoke_maps_completed:
                    self._make_yoke_rows(condition, assignments, participants)
                    self._checkpoint.yoke_maps_completed = tuple(
                        sorted((*self._checkpoint.yoke_maps_completed, scope))
                    )
                    write_checkpoint(self._checkpoint_path, self._checkpoint)
                else:
                    self._make_yoke_rows(condition, assignments, participants)
                self._checkpoint.phase = "yoked"
                for assignment in assignments:
                    if self._cancel_requested:
                        return
                    target = next(
                        item
                        for item in participants
                        if item.participant_id == assignment.target_participant_id
                    )
                    donor = self._assignment_donor(assignment, participants)
                    job_id = _job_id(
                        condition.condition_id,
                        target.participant_id,
                        YOKED_ARM,
                    )
                    if job_id in self._checkpoint.completed_jobs:
                        continue
                    bundles, sessions = self._run_yoked_participant(
                        target,
                        donor,
                        condition,
                    )
                    self._complete_job(
                        participant=target,
                        condition=condition,
                        arm=YOKED_ARM,
                        bundles=bundles,
                        sessions=sessions,
                        donor=donor.participant_id,
                    )
                self._checkpoint.phase = "random"
                for participant in participants:
                    if self._cancel_requested:
                        return
                    job_id = _job_id(
                        condition.condition_id,
                        participant.participant_id,
                        RANDOM_ARM,
                    )
                    if job_id in self._checkpoint.completed_jobs:
                        continue
                    bundles, sessions = self._run_random_participant(
                        participant,
                        condition,
                    )
                    self._complete_job(
                        participant=participant,
                        condition=condition,
                        arm=RANDOM_ARM,
                        bundles=bundles,
                        sessions=sessions,
                    )

    def _baseline_audit(self) -> None:
        self._baseline_diagnostics.clear()
        lookup = {
            (item.participant_id, item.condition_id, item.session_index, item.arm): item
            for item in self._sessions
        }
        for participant in self._participants:
            for condition in self._config.conditions:
                for session_index in range(self._config.maximum_sessions):
                    values = {
                        arm: lookup[
                            (
                                participant.participant_id,
                                condition.condition_id,
                                session_index,
                                arm,
                            )
                        ].baseline_rmssd_ms
                        for arm in ARM_IDS
                    }
                    finite = [value for value in values.values() if value is not None]
                    equal = len(finite) == len(ARM_IDS) and all(
                        math.isclose(finite[0], value, rel_tol=0.0, abs_tol=1e-12)
                        for value in finite[1:]
                    )
                    if not equal:
                        self._baseline_diagnostics.append(
                            {
                                "record_type": "baseline_pairing",
                                "participant_id": participant.participant_id,
                                "user_type_id": participant.user_type_id,
                                "condition_id": condition.condition_id,
                                "session_index": session_index,
                                "reason": (
                                    "baseline_missing_or_arm_mismatch; inspect event digests "
                                    "and pre-light scheduling"
                                ),
                                "autonomous_baseline_rmssd_ms": values[AUTONOMOUS_ARM],
                                "yoked_baseline_rmssd_ms": values[YOKED_ARM],
                                "random_baseline_rmssd_ms": values[RANDOM_ARM],
                            }
                        )

    def _analyze_and_report(self) -> None:
        self._baseline_audit()
        self._analysis = analyze_validation_records(
            self._bundles,
            self._sessions,
            permutation_count=self._config.permutation_count,
            hue_bandwidth_degree=self._config.hue_bandwidth_degree,
            bpm_bandwidth=self._config.bpm_bandwidth,
            minimum_history_count=self._config.minimum_history_count,
            classification_policy=self._config.classification_policy,
        )
        export_validation_results(
            self._run_directory,
            participants=self._participants,
            conditions=self._config.conditions,
            yoke_rows=self._yoke_rows,
            bundles=self._bundles,
            sessions=self._sessions,
            analysis=self._analysis,
            baseline_diagnostics=self._baseline_diagnostics,
        )
        self._checkpoint.analysis_complete = True
        self._checkpoint.phase = "analysis"
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        command = (
            "python -m symbiotic_sim_v2 --headless-adaptive-placebo-validation "
            f"--resume {self._run_directory}"
        )
        report_path, participant_paths = write_html_reports(
            self._run_directory,
            manifest=self._manifest,
            conditions=self._config.conditions,
            participants=[item.to_dict() for item in self._participants],
            yoke_rows=self._yoke_rows,
            bundles=self._bundles,
            sessions=self._sessions,
            analysis=self._analysis,
            baseline_diagnostics=self._baseline_diagnostics,
            reproduction_command=command,
        )
        self._checkpoint.report_complete = True
        self._checkpoint.phase = "completed"
        write_checkpoint(self._checkpoint_path, self._checkpoint)
        self._log(
            "report_completed",
            report_path=str(report_path),
            participant_report_count=len(participant_paths),
        )

    def _summary(self, status: str) -> ValidationRunSummary:
        effect, valid = self._current_effect()
        return ValidationRunSummary(
            run_id=self.run_id,
            run_directory=self._run_directory,
            status=status,
            completed_session_runs=self._checkpoint.completed_session_runs,
            planned_session_runs=self._checkpoint.planned_session_runs,
            completed_participant_arm_jobs=len(self._checkpoint.completed_jobs),
            report_path=self._run_directory / "report" / "report.html",
            checkpoint_path=self._checkpoint_path,
            valid_participant_count=valid,
            current_autonomous_minus_yoked_effect_ms=effect,
        )

    def run(self) -> ValidationRunSummary:
        self._started = time.monotonic()
        with RunDirectoryLock(self._run_directory):
            if self._checkpoint.report_complete:
                return self._summary("completed")
            self._run_jobs()
            if self._cancel_requested:
                self._checkpoint.phase = "cancelled"
                write_checkpoint(self._checkpoint_path, self._checkpoint)
                return self._summary("cancelled")
            if self._checkpoint.completed_session_runs != self._config.planned_target_session_runs:
                raise RuntimeError("completed target session count differs from the plan")
            self._load_completed_results()
            # Recreate deterministic yoke rows on resume before final export.
            self._yoke_rows.clear()
            for condition in self._config.conditions:
                for user_type_id in self._config.user_type_ids:
                    participants = self._participants_for_type(user_type_id)
                    self._make_yoke_rows(
                        condition,
                        cyclic_yoke_map(participants),
                        participants,
                    )
            self._analyze_and_report()
            return self._summary("completed")


__all__ = ["AdaptivePlaceboValidationRunner", "ValidationRunSummary"]
