"""Canonical Stage 8A.2 job identities and paired-seed isolation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION,
    FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
    PAIRED_REPLICATE_SEED_POLICY_VERSION,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.replicate_seed import (
    paired_replicate_master_seed,
)

from .config import (
    REFERENCE_CACHE_SCHEMA_VERSION,
    SEARCH_JOB_SCHEMA_VERSION,
    AutoSearchVersionMetadata,
)
from .plan import ConditionPoint, SearchPhasePlan


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AutoSearchJob:
    job_id: str
    phase: str
    user_type_id: str
    selected_session_fatigue_target: float
    sigma_multiplier: float
    maximum_sessions: int
    replicate_index: int
    replicate_master_seed: int
    arm: str
    code_fingerprint: str
    stage_08a1_model_version: str
    experiment_profile_version: str
    paired_seed_policy_version: str
    document_version: str
    profile_version: str
    algorithm_version: str
    state_schema_version: str
    schema_version: str = SEARCH_JOB_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SEARCH_JOB_SCHEMA_VERSION:
            raise ValueError("auto-search job schema mismatch")
        if self.arm not in {"experimental", "reference"}:
            raise ValueError("arm must be experimental or reference")
        if self.job_id != sha256_canonical(self.identity_body()):
            raise ValueError("auto-search job ID does not match its canonical body")

    @classmethod
    def create(
        cls,
        *,
        phase: str,
        user_type_id: str,
        point: ConditionPoint,
        maximum_sessions: int,
        replicate_index: int,
        base_master_seed: int,
        arm: str,
        code_fingerprint: str,
        versions: AutoSearchVersionMetadata,
    ) -> AutoSearchJob:
        if arm not in {"experimental", "reference"}:
            raise ValueError("arm must be experimental or reference")
        seed = paired_replicate_master_seed(base_master_seed, replicate_index)
        body = {
            "phase": phase,
            "user_type_id": user_type_id,
            "selected_session_fatigue_target": (point.selected_session_fatigue_target),
            "sigma_multiplier": point.sigma_multiplier,
            "maximum_sessions": maximum_sessions,
            "replicate_index": replicate_index,
            "replicate_master_seed": seed,
            "arm": arm,
            "code_fingerprint": code_fingerprint,
            "stage_08a1_model_version": (FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION),
            "experiment_profile_version": FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
            "paired_seed_policy_version": PAIRED_REPLICATE_SEED_POLICY_VERSION,
            "document_version": versions.document_version,
            "profile_version": versions.profile_version,
            "algorithm_version": versions.algorithm_version,
            "state_schema_version": versions.state_schema_version,
            "schema_version": SEARCH_JOB_SCHEMA_VERSION,
        }
        return cls(job_id=sha256_canonical(body), **body)

    @property
    def condition_key(self) -> str:
        return ConditionPoint(
            self.selected_session_fatigue_target,
            self.sigma_multiplier,
        ).condition_key

    def identity_body(self) -> dict[str, Any]:
        values = asdict(self)
        values.pop("job_id")
        return values

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def jobs_for_phase(
    phase: SearchPhasePlan,
    *,
    base_master_seed: int,
    include_reference_arm: bool,
    code_fingerprint: str,
    versions: AutoSearchVersionMetadata,
) -> tuple[AutoSearchJob, ...]:
    jobs = [
        AutoSearchJob.create(
            phase=phase.phase,
            user_type_id=user_type_id,
            point=point,
            maximum_sessions=phase.maximum_sessions,
            replicate_index=replicate_index,
            base_master_seed=base_master_seed,
            arm="experimental",
            code_fingerprint=code_fingerprint,
            versions=versions,
        )
        for point in phase.conditions
        for user_type_id in phase.user_type_ids
        for replicate_index in range(phase.replicate_count)
    ]
    if include_reference_arm and phase.conditions:
        reference_point = ConditionPoint(0.0, 1.0)
        jobs.extend(
            AutoSearchJob.create(
                phase=phase.phase,
                user_type_id=user_type_id,
                point=reference_point,
                maximum_sessions=phase.maximum_sessions,
                replicate_index=replicate_index,
                base_master_seed=base_master_seed,
                arm="reference",
                code_fingerprint=code_fingerprint,
                versions=versions,
            )
            for user_type_id in phase.user_type_ids
            for replicate_index in range(phase.replicate_count)
        )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    if len({item.job_id for item in ordered}) != len(ordered):
        raise ValueError("duplicate auto-search job ID")
    return ordered


def reference_cache_key(job: AutoSearchJob) -> str:
    if job.arm != "reference":
        raise ValueError("reference cache keys require a reference job")
    return sha256_canonical(
        {
            "user_type_id": job.user_type_id,
            "maximum_sessions": job.maximum_sessions,
            "replicate_master_seed": job.replicate_master_seed,
            "code_fingerprint": job.code_fingerprint,
            "stage_08a1_model_version": job.stage_08a1_model_version,
            "profile_version": job.profile_version,
            "algorithm_version": job.algorithm_version,
            "state_schema_version": job.state_schema_version,
            "schema_version": REFERENCE_CACHE_SCHEMA_VERSION,
        }
    )


__all__ = [
    "AutoSearchJob",
    "canonical_json",
    "jobs_for_phase",
    "reference_cache_key",
    "sha256_canonical",
]
