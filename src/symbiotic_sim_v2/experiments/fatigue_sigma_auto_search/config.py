"""Strict immutable configuration and version declarations for Stage 8A.2."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    ALGORITHM_VERSION,
    BASE_PROFILE_VERSION,
    DOCUMENT_VERSION,
    RELATION_MEMORY_STATE_SCHEMA_VERSION,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import UINT32_MAX
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    stationary_user_type_v2_ids,
)

PROJECT_VERSION = "0.12.0"
AUTO_SEARCH_MODEL_VERSION = "fatigue_sigma_auto_search_v0_1"
SEARCH_STRATEGY_VERSION = "coarse_refine_confirm_search_v0_1"
SEARCH_PLAN_SCHEMA_VERSION = "fatigue_sigma_auto_search_plan_v1"
SEARCH_JOB_SCHEMA_VERSION = "fatigue_sigma_auto_search_job_v1"
CHECKPOINT_SCHEMA_VERSION = "fatigue_sigma_auto_search_checkpoint_v1"
CANDIDATE_GATE_VERSION = "balanced_robust_candidate_gate_v0_1"
COARSE_GATE_VERSION = "coarse_candidate_gate_v0_1"
PARETO_EVALUATOR_VERSION = "multi_objective_pareto_frontier_v0_1"
CANDIDATE_RANKING_VERSION = "uncertainty_aware_robust_candidate_ranking_v0_1"
RECOMMENDATION_SCHEMA_VERSION = "fatigue_sigma_recommendation_v1"
HTML_REPORT_VERSION = "fatigue_sigma_auto_search_report_v1"
RUN_MANIFEST_VERSION = "fatigue_sigma_auto_search_manifest_v1"
CODE_FINGERPRINT_VERSION = "auto_search_code_fingerprint_v0_1"
REFERENCE_CACHE_SCHEMA_VERSION = "fatigue_sigma_reference_cache_v1"
CONDITION_SUMMARY_SCHEMA_VERSION = "fatigue_sigma_cross_user_summary_v1"

NORMATIVE_SPEC_PATH = Path(
    "/Users/sawadashingo/ONTELOPE/21_RICOH/共同研究/自律確認MVP/"
    "symbiotic-digital-life-signal-loop-concept_v2.0.md"
)
NORMATIVE_SPEC_SIZE = 65_759
NORMATIVE_SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"

SEARCH_PRESETS = ("smoke", "quick", "standard", "robust")
SEARCH_PHASES = ("coarse", "refine", "confirm")
RETAIN_FULL_DETAILS_POLICIES = ("compact_summary", "phase3_full", "all_full")
ALL_USER_TYPE_IDS = (
    "green_hue_dominant_broad_bpm",
    "bpm_common_100_hue_neutral",
    "three_life_bpm_equal",
    "three_life_bpm_green_dominant",
    "green_single_peak_narrow",
    "flat_control",
)
NONFLAT_USER_TYPE_IDS = ALL_USER_TYPE_IDS[:-1]
SMOKE_USER_TYPE_IDS = ("green_hue_dominant_broad_bpm", "flat_control")

PRESET_MAXIMUM_SESSION_RUNS = {
    "smoke": 32,
    "quick": 1_296,
    "standard": 40_000,
    "robust": 130_000,
}
PRESET_DEFAULT_STOP_PHASE = {
    "smoke": "coarse",
    "quick": "coarse",
    "standard": "confirm",
    "robust": "confirm",
}


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _strict_int(name: str, value: object, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _strict_rate(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")
    return result


@dataclass(frozen=True, slots=True)
class CandidateGateConfig:
    """Versioned transparent coarse and final candidate thresholds."""

    failed_replicate_rate_max: float = 0.0
    valid_session_rate_min: float = 0.95
    flat_spurious_structure_rate_max: float = 0.25
    flat_mechanical_rotation_warning_rate_max: float = 0.25
    w_ceiling_blocked_rate_max: float = 0.50
    worst_nonflat_correct_structure_rate_min: float = 0.30
    mean_nonflat_diffuse_rate_max: float = 0.50
    coarse_failed_replicate_rate_max: float = 0.0
    coarse_valid_session_rate_min: float = 0.90
    coarse_flat_spurious_structure_rate_max: float = 0.75
    coarse_w_ceiling_blocked_rate_max: float = 0.90
    coarse_mean_nonflat_correct_structure_rate_min_exclusive: float = 0.0
    version: str = CANDIDATE_GATE_VERSION
    coarse_version: str = COARSE_GATE_VERSION

    def __post_init__(self) -> None:
        for field in fields(self):
            if field.name in {"version", "coarse_version"}:
                continue
            object.__setattr__(
                self,
                field.name,
                _strict_rate(field.name, getattr(self, field.name)),
            )
        if self.version != CANDIDATE_GATE_VERSION:
            raise ValueError(f"version must be {CANDIDATE_GATE_VERSION}")
        if self.coarse_version != COARSE_GATE_VERSION:
            raise ValueError(f"coarse_version must be {COARSE_GATE_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> CandidateGateConfig:
        if not isinstance(values, Mapping):
            raise TypeError("candidate gate config must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                "candidate gate fields differ; "
                f"missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> CandidateGateConfig:
        values = json.loads(encoded, object_pairs_hook=_strict_object_pairs)
        if not isinstance(values, dict):
            raise ValueError("candidate gate JSON must contain an object")
        return cls.from_dict(values)


@dataclass(frozen=True, slots=True)
class AutoSearchVersionMetadata:
    project_version: str = PROJECT_VERSION
    auto_search_model_version: str = AUTO_SEARCH_MODEL_VERSION
    search_strategy_version: str = SEARCH_STRATEGY_VERSION
    search_plan_schema_version: str = SEARCH_PLAN_SCHEMA_VERSION
    search_job_schema_version: str = SEARCH_JOB_SCHEMA_VERSION
    checkpoint_schema_version: str = CHECKPOINT_SCHEMA_VERSION
    candidate_gate_version: str = CANDIDATE_GATE_VERSION
    pareto_evaluator_version: str = PARETO_EVALUATOR_VERSION
    candidate_ranking_version: str = CANDIDATE_RANKING_VERSION
    recommendation_schema_version: str = RECOMMENDATION_SCHEMA_VERSION
    html_report_version: str = HTML_REPORT_VERSION
    run_manifest_version: str = RUN_MANIFEST_VERSION
    code_fingerprint_version: str = CODE_FINGERPRINT_VERSION
    document_version: str = DOCUMENT_VERSION
    profile_version: str = BASE_PROFILE_VERSION
    algorithm_version: str = ALGORITHM_VERSION
    state_schema_version: str = RELATION_MEMORY_STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        expected = {
            "project_version": PROJECT_VERSION,
            "auto_search_model_version": AUTO_SEARCH_MODEL_VERSION,
            "search_strategy_version": SEARCH_STRATEGY_VERSION,
            "search_plan_schema_version": SEARCH_PLAN_SCHEMA_VERSION,
            "search_job_schema_version": SEARCH_JOB_SCHEMA_VERSION,
            "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
            "candidate_gate_version": CANDIDATE_GATE_VERSION,
            "pareto_evaluator_version": PARETO_EVALUATOR_VERSION,
            "candidate_ranking_version": CANDIDATE_RANKING_VERSION,
            "recommendation_schema_version": RECOMMENDATION_SCHEMA_VERSION,
            "html_report_version": HTML_REPORT_VERSION,
            "run_manifest_version": RUN_MANIFEST_VERSION,
            "code_fingerprint_version": CODE_FINGERPRINT_VERSION,
            "document_version": DOCUMENT_VERSION,
            "profile_version": BASE_PROFILE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "state_schema_version": RELATION_MEMORY_STATE_SCHEMA_VERSION,
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("auto-search version metadata is fixed")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> AutoSearchVersionMetadata:
        if not isinstance(values, Mapping):
            raise TypeError("version metadata must be a mapping")
        expected = {field.name for field in fields(cls)}
        if set(values) != expected:
            raise ValueError("version metadata fields differ")
        return cls(**dict(values))


@dataclass(frozen=True, slots=True)
class AutoSearchConfig:
    """Complete immutable search configuration with strict JSON handling."""

    search_preset: str
    user_type_ids: tuple[str, ...]
    base_master_seed: int
    include_reference_arm: bool
    output_directory: str
    maximum_total_session_runs: int
    stop_after_phase: str
    retain_full_details_policy: str
    candidate_gate_config: CandidateGateConfig
    version_metadata: AutoSearchVersionMetadata

    def __post_init__(self) -> None:
        if self.search_preset not in SEARCH_PRESETS:
            raise ValueError(f"search_preset must be one of {SEARCH_PRESETS}")
        if not isinstance(self.user_type_ids, tuple) or not self.user_type_ids:
            raise ValueError("user_type_ids must be a non-empty tuple")
        if len(set(self.user_type_ids)) != len(self.user_type_ids):
            raise ValueError("user_type_ids must not contain duplicates")
        known = set(stationary_user_type_v2_ids())
        unknown = set(self.user_type_ids) - known
        if unknown:
            raise ValueError(f"unknown user type IDs: {sorted(unknown)}")
        _strict_int(
            "base_master_seed",
            self.base_master_seed,
            minimum=0,
            maximum=UINT32_MAX,
        )
        if not isinstance(self.include_reference_arm, bool):
            raise TypeError("include_reference_arm must be boolean")
        if not isinstance(self.output_directory, str) or not self.output_directory.strip():
            raise ValueError("output_directory must be a non-empty string")
        _strict_int(
            "maximum_total_session_runs",
            self.maximum_total_session_runs,
            minimum=1,
            maximum=10_000_000,
        )
        if self.stop_after_phase not in SEARCH_PHASES:
            raise ValueError(f"stop_after_phase must be one of {SEARCH_PHASES}")
        if self.search_preset in {"smoke", "quick"} and self.stop_after_phase != "coarse":
            raise ValueError(f"{self.search_preset} supports the coarse phase only")
        if self.retain_full_details_policy not in RETAIN_FULL_DETAILS_POLICIES:
            raise ValueError(
                f"retain_full_details_policy must be one of {RETAIN_FULL_DETAILS_POLICIES}"
            )
        if not isinstance(self.candidate_gate_config, CandidateGateConfig):
            raise TypeError("candidate_gate_config must be CandidateGateConfig")
        if not isinstance(self.version_metadata, AutoSearchVersionMetadata):
            raise TypeError("version_metadata must be AutoSearchVersionMetadata")

    @classmethod
    def create(
        cls,
        *,
        search_preset: str = "standard",
        user_type_ids: tuple[str, ...] | None = None,
        base_master_seed: int = 20260802,
        include_reference_arm: bool = False,
        output_directory: str = "artifacts/auto_search",
        maximum_total_session_runs: int | None = None,
        stop_after_phase: str | None = None,
        retain_full_details_policy: str = "phase3_full",
        candidate_gate_config: CandidateGateConfig | None = None,
    ) -> AutoSearchConfig:
        if search_preset not in SEARCH_PRESETS:
            raise ValueError(f"search_preset must be one of {SEARCH_PRESETS}")
        selected_users = SMOKE_USER_TYPE_IDS if search_preset == "smoke" else ALL_USER_TYPE_IDS
        return cls(
            search_preset=search_preset,
            user_type_ids=selected_users if user_type_ids is None else user_type_ids,
            base_master_seed=base_master_seed,
            include_reference_arm=include_reference_arm,
            output_directory=output_directory,
            maximum_total_session_runs=(
                PRESET_MAXIMUM_SESSION_RUNS[search_preset]
                if maximum_total_session_runs is None
                else maximum_total_session_runs
            ),
            stop_after_phase=(
                PRESET_DEFAULT_STOP_PHASE[search_preset]
                if stop_after_phase is None
                else stop_after_phase
            ),
            retain_full_details_policy=retain_full_details_policy,
            candidate_gate_config=candidate_gate_config or CandidateGateConfig(),
            version_metadata=AutoSearchVersionMetadata(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_preset": self.search_preset,
            "user_type_ids": list(self.user_type_ids),
            "base_master_seed": self.base_master_seed,
            "include_reference_arm": self.include_reference_arm,
            "output_directory": self.output_directory,
            "maximum_total_session_runs": self.maximum_total_session_runs,
            "stop_after_phase": self.stop_after_phase,
            "retain_full_details_policy": self.retain_full_details_policy,
            "candidate_gate_config": self.candidate_gate_config.to_dict(),
            "version_metadata": self.version_metadata.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> AutoSearchConfig:
        if not isinstance(values, Mapping):
            raise TypeError("auto-search config must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                "auto-search config fields differ; "
                f"missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        payload = dict(values)
        users = payload["user_type_ids"]
        if not isinstance(users, list):
            raise TypeError("user_type_ids must be a JSON array")
        payload["user_type_ids"] = tuple(users)
        payload["candidate_gate_config"] = CandidateGateConfig.from_dict(
            payload["candidate_gate_config"]
        )
        payload["version_metadata"] = AutoSearchVersionMetadata.from_dict(
            payload["version_metadata"]
        )
        return cls(**payload)

    @classmethod
    def from_json(cls, encoded: str) -> AutoSearchConfig:
        if not isinstance(encoded, str):
            raise TypeError("encoded config must be a string")
        values = json.loads(encoded, object_pairs_hook=_strict_object_pairs)
        if not isinstance(values, dict):
            raise ValueError("auto-search config JSON must contain an object")
        return cls.from_dict(values)


__all__ = [
    "ALL_USER_TYPE_IDS",
    "AUTO_SEARCH_MODEL_VERSION",
    "AutoSearchConfig",
    "AutoSearchVersionMetadata",
    "CandidateGateConfig",
    "NONFLAT_USER_TYPE_IDS",
    "NORMATIVE_SPEC_PATH",
    "NORMATIVE_SPEC_SHA256",
    "NORMATIVE_SPEC_SIZE",
    "PROJECT_VERSION",
    "SEARCH_PHASES",
    "SEARCH_PRESETS",
    "SMOKE_USER_TYPE_IDS",
]
