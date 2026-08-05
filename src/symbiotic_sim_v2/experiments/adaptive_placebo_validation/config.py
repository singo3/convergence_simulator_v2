"""Strict Stage 8A.3 arm, condition, participant, and run contracts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import (
    canonical_json,
    sha256_canonical,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import UINT32_MAX

PROJECT_VERSION = "0.13.0"
VALIDATION_MODEL_VERSION = "adaptive_placebo_rmssd_validation_v0_1"
ARM_CONTRACT_VERSION = "adaptive_placebo_arm_contract_v0_1"
AUTONOMOUS_ARM_VERSION = "autonomous_closed_loop_arm_v0_1"
YOKED_ARM_VERSION = "response_decoupled_yoked_replay_v0_1"
RANDOM_ARM_VERSION = "pure_random_open_loop_v0_1"
VALIDATION_PARTICIPANT_VERSION = "fixed_validation_participant_v0_1"
YOKE_MAPPING_VERSION = "cyclic_same_type_yoke_mapping_v0_1"
RANDOM_OUTPUT_VERSION = "deterministic_random_light_sequence_v0_1"
BUNDLE_OUTCOME_SCHEMA_VERSION = "validation_bundle_outcome_v1"
SESSION_OUTCOME_SCHEMA_VERSION = "validation_session_outcome_v1"
HISTORY_RESPONSE_MODEL_VERSION = "past_sessions_only_response_model_v0_1"
LAGGED_COUPLING_VERSION = "rmssd_to_future_output_coupling_v0_1"
PROSPECTIVE_ENRICHMENT_VERSION = "prospective_selection_enrichment_v0_1"
PARTICIPANT_EFFECT_VERSION = "participant_adaptive_effect_v0_1"
PARTICIPANT_CLASSIFICATION_POLICY_VERSION = (
    "participant_adaptive_effect_thresholds_v0_1"
)
VALIDATION_SUMMARY_VERSION = "adaptive_placebo_validation_summary_v1"
VALIDATION_REPORT_VERSION = "adaptive_placebo_validation_report_v0_1"
VALIDATION_PLAN_VERSION = "adaptive_placebo_validation_plan_v1"
VALIDATION_MANIFEST_VERSION = "adaptive_placebo_validation_manifest_v1"
VALIDATION_CHECKPOINT_VERSION = "adaptive_placebo_validation_checkpoint_v1"
VALIDATION_CODE_FINGERPRINT_VERSION = "adaptive_placebo_code_fingerprint_v0_1"

DOCUMENT_VERSION = "v2.0"
PROFILE_VERSION = "symbiotic_signal_loop_reference_v1_0"
ALGORITHM_VERSION = "adaptive_random_search_confirmed_v1"
STATE_SCHEMA_VERSION = "relation_memory_state_v2"

AUTONOMOUS_ARM = "autonomous_closed_loop"
YOKED_ARM = "response_decoupled_yoked_replay"
RANDOM_ARM = "pure_random_open_loop"
ARM_IDS = (AUTONOMOUS_ARM, YOKED_ARM, RANDOM_ARM)

V2_REFERENCE_CONDITION = "v2_reference"
PROVISIONAL_CONDITION = "provisional_f15_sigma050"
CONDITION_IDS = (V2_REFERENCE_CONDITION, PROVISIONAL_CONDITION)

ALL_USER_TYPE_IDS = (
    "red_hue_dominant_broad_bpm",
    "green_hue_dominant_broad_bpm",
    "blue_hue_dominant_broad_bpm",
    "bpm_common_100_hue_neutral",
    "three_life_bpm_equal",
    "three_life_bpm_green_dominant",
    "green_single_peak_narrow",
    "weak_bpm_common_100",
    "flat_control",
)
SMOKE_USER_TYPE_IDS = ("green_hue_dominant_broad_bpm", "flat_control")
QUICK_USER_TYPE_IDS = (
    "red_hue_dominant_broad_bpm",
    "green_hue_dominant_broad_bpm",
    "bpm_common_100_hue_neutral",
    "flat_control",
)

VALIDATION_PRESETS = ("smoke", "quick", "standard", "robust")
RETAIN_DETAILS_POLICIES = ("compact", "representative", "all")
PRESET_DEFAULTS: Mapping[str, Mapping[str, Any]] = {
    "smoke": {
        "condition_ids": (PROVISIONAL_CONDITION,),
        "user_type_ids": SMOKE_USER_TYPE_IDS,
        "participants_per_type": 2,
        "maximum_sessions": 4,
        "permutation_count": 20,
        "maximum_target_session_runs": 48,
    },
    "quick": {
        "condition_ids": (PROVISIONAL_CONDITION,),
        "user_type_ids": QUICK_USER_TYPE_IDS,
        "participants_per_type": 4,
        "maximum_sessions": 12,
        "permutation_count": 100,
        "maximum_target_session_runs": 576,
    },
    "standard": {
        "condition_ids": CONDITION_IDS,
        "user_type_ids": ALL_USER_TYPE_IDS,
        "participants_per_type": 10,
        "maximum_sessions": 24,
        "permutation_count": 500,
        "maximum_target_session_runs": 12_960,
    },
    "robust": {
        "condition_ids": CONDITION_IDS,
        "user_type_ids": ALL_USER_TYPE_IDS,
        "participants_per_type": 20,
        "maximum_sessions": 60,
        "permutation_count": 2_000,
        "maximum_target_session_runs": 64_800,
    },
}
ABSOLUTE_MAXIMUM_TARGET_SESSION_RUNS = 100_000
DEFAULT_BASE_MASTER_SEED = 20260806
DEFAULT_RESPONSE_STRENGTH_CYCLE = (1.0, 0.8, 0.6, 0.4, 0.2)


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _strict_int(name: str, value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _exact_fields(values: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(values)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


@dataclass(frozen=True, slots=True)
class ArmContract:
    arm_id: str
    output_source: str
    target_rmssd_used_for_future_output: bool
    adaptive_state_enabled: bool
    version: str
    schema_version: str = ARM_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.arm_id not in ARM_IDS:
            raise ValueError(f"unknown validation arm: {self.arm_id!r}")
        _required_text("output_source", self.output_source)
        for name in (
            "target_rmssd_used_for_future_output",
            "adaptive_state_enabled",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        expected = {
            AUTONOMOUS_ARM: ("target_closed_loop", True, True, AUTONOMOUS_ARM_VERSION),
            YOKED_ARM: ("other_participant_autonomous_replay", False, False, YOKED_ARM_VERSION),
            RANDOM_ARM: ("deterministic_random_sequence", False, False, RANDOM_ARM_VERSION),
        }[self.arm_id]
        actual = (
            self.output_source,
            self.target_rmssd_used_for_future_output,
            self.adaptive_state_enabled,
            self.version,
        )
        if actual != expected:
            raise ValueError("arm contract values differ from the fixed Stage 8A.3 contract")
        if self.schema_version != ARM_CONTRACT_VERSION:
            raise ValueError(f"schema_version must be {ARM_CONTRACT_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> ArmContract:
        _exact_fields(values, {field.name for field in fields(cls)}, "arm contract")
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> ArmContract:
        value = json.loads(encoded, object_pairs_hook=_strict_object_pairs)
        if not isinstance(value, Mapping):
            raise ValueError("arm contract JSON must contain an object")
        return cls.from_dict(value)


def arm_contract(arm_id: str) -> ArmContract:
    if arm_id == AUTONOMOUS_ARM:
        return ArmContract(arm_id, "target_closed_loop", True, True, AUTONOMOUS_ARM_VERSION)
    if arm_id == YOKED_ARM:
        return ArmContract(
            arm_id,
            "other_participant_autonomous_replay",
            False,
            False,
            YOKED_ARM_VERSION,
        )
    if arm_id == RANDOM_ARM:
        return ArmContract(
            arm_id,
            "deterministic_random_sequence",
            False,
            False,
            RANDOM_ARM_VERSION,
        )
    raise ValueError(f"unknown validation arm: {arm_id!r}")


@dataclass(frozen=True, slots=True)
class ValidationCondition:
    condition_id: str
    fatigue_policy: str
    selected_session_fatigue_target: float
    unselected_full_recovery: bool
    sigma_multiplier: float
    formal_spec_adoption: bool = False
    document_version: str = DOCUMENT_VERSION
    profile_version: str = PROFILE_VERSION
    algorithm_version: str = ALGORITHM_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION
    validation_model_version: str = VALIDATION_MODEL_VERSION

    def __post_init__(self) -> None:
        _required_text("condition_id", self.condition_id)
        _required_text("fatigue_policy", self.fatigue_policy)
        target = _finite(
            "selected_session_fatigue_target",
            self.selected_session_fatigue_target,
        )
        if not 0.0 <= target <= 0.20:
            raise ValueError("selected_session_fatigue_target must be within [0, 0.20]")
        multiplier = _finite("sigma_multiplier", self.sigma_multiplier)
        if not 0.25 <= multiplier <= 1.50:
            raise ValueError("sigma_multiplier must be within [0.25, 1.50]")
        for name in ("unselected_full_recovery", "formal_spec_adoption"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        if self.formal_spec_adoption:
            raise ValueError("Stage 8A.3 conditions must keep formal_spec_adoption=false")
        if self.fatigue_policy == "v2_reference":
            if (
                target != 0.0
                or self.unselected_full_recovery
                or multiplier != 1.0
            ):
                raise ValueError(
                    "v2_reference must use target=0, no unselected full recovery, "
                    "and sigma multiplier 1.0"
                )
        elif not self.unselected_full_recovery:
            raise ValueError(
                "non-reference Stage 8A.3 conditions require the reused "
                "Stage 8A.1 unselected-full-recovery policy"
            )
        expected_versions = {
            "document_version": DOCUMENT_VERSION,
            "profile_version": PROFILE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "validation_model_version": VALIDATION_MODEL_VERSION,
        }
        for name, expected in expected_versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")
        object.__setattr__(self, "selected_session_fatigue_target", target)
        object.__setattr__(self, "sigma_multiplier", multiplier)

    @property
    def is_reference(self) -> bool:
        return self.fatigue_policy == "v2_reference"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> ValidationCondition:
        _exact_fields(values, {field.name for field in fields(cls)}, "validation condition")
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> ValidationCondition:
        value = json.loads(encoded, object_pairs_hook=_strict_object_pairs)
        if not isinstance(value, Mapping):
            raise ValueError("condition JSON must contain an object")
        return cls.from_dict(value)


def default_validation_conditions() -> tuple[ValidationCondition, ValidationCondition]:
    return (
        ValidationCondition(
            condition_id=V2_REFERENCE_CONDITION,
            fatigue_policy="v2_reference",
            selected_session_fatigue_target=0.0,
            unselected_full_recovery=False,
            sigma_multiplier=1.0,
        ),
        ValidationCondition(
            condition_id=PROVISIONAL_CONDITION,
            fatigue_policy="experimental_selected_target_full_recovery",
            selected_session_fatigue_target=0.15,
            unselected_full_recovery=True,
            sigma_multiplier=0.50,
        ),
    )


def validation_condition(condition_id: str) -> ValidationCondition:
    try:
        return next(
            condition
            for condition in default_validation_conditions()
            if condition.condition_id == condition_id
        )
    except StopIteration as exc:
        raise ValueError(f"unknown validation condition: {condition_id!r}") from exc


def load_conditions_json(path: Path) -> tuple[ValidationCondition, ...]:
    if not path.is_file():
        raise ValueError(f"conditions JSON does not exist: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object_pairs)
    raw = loaded.get("conditions") if isinstance(loaded, Mapping) else loaded
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ValueError("conditions JSON must contain a list or a {'conditions': [...]} object")
    conditions = tuple(ValidationCondition.from_dict(item) for item in raw)
    if not conditions or len({item.condition_id for item in conditions}) != len(conditions):
        raise ValueError("conditions must be non-empty with unique condition IDs")
    return conditions


def _participant_seed(base_master_seed: int, user_type_id: str, index: int) -> int:
    key = (
        f"{base_master_seed}:stage8a3:participant-physiology:"
        f"{user_type_id}:{index}"
    ).encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big", signed=False)


@dataclass(frozen=True, slots=True)
class ValidationParticipant:
    participant_id: str
    user_type_id: str
    participant_index: int
    physiology_seed: int
    response_strength_scale: float
    profile_hash: str
    version: str = VALIDATION_PARTICIPANT_VERSION
    validation_model_version: str = VALIDATION_MODEL_VERSION

    def __post_init__(self) -> None:
        _required_text("participant_id", self.participant_id)
        if self.user_type_id not in ALL_USER_TYPE_IDS:
            raise ValueError(f"unknown validation user type: {self.user_type_id!r}")
        index = _strict_int("participant_index", self.participant_index, 0, 999_999)
        seed = _strict_int("physiology_seed", self.physiology_seed, 0, UINT32_MAX)
        scale = _finite("response_strength_scale", self.response_strength_scale)
        if not 0.0 <= scale <= 1.0:
            raise ValueError("response_strength_scale must be within [0, 1]")
        if self.user_type_id == "flat_control" and scale != 0.0:
            raise ValueError("flat_control response_strength_scale must be zero")
        if len(self.profile_hash) != 64:
            raise ValueError("profile_hash must be a SHA-256 hex digest")
        int(self.profile_hash, 16)
        if self.version != VALIDATION_PARTICIPANT_VERSION:
            raise ValueError(f"version must be {VALIDATION_PARTICIPANT_VERSION}")
        if self.validation_model_version != VALIDATION_MODEL_VERSION:
            raise ValueError(f"validation_model_version must be {VALIDATION_MODEL_VERSION}")
        object.__setattr__(self, "participant_index", index)
        object.__setattr__(self, "physiology_seed", seed)
        object.__setattr__(self, "response_strength_scale", scale)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> ValidationParticipant:
        _exact_fields(values, {field.name for field in fields(cls)}, "validation participant")
        return cls(**dict(values))


@dataclass(frozen=True, slots=True)
class ParticipantClassificationPolicy:
    """Versioned simulation-only thresholds for the secondary classification."""

    minimum_valid_sessions: int = 4
    late_positive_threshold_ms: float = 0.5
    late_negative_threshold_ms: float = -0.5
    selection_enrichment_threshold: float = 0.0
    slope_threshold: float = 0.0
    permutation_p_like_threshold: float = 0.20
    clear_positive_indicator_count: int = 3
    partial_indicator_count: int = 2
    formal_spec_adoption: bool = False
    version: str = PARTICIPANT_CLASSIFICATION_POLICY_VERSION

    def __post_init__(self) -> None:
        _strict_int("minimum_valid_sessions", self.minimum_valid_sessions, 1, 100)
        positive = _finite(
            "late_positive_threshold_ms",
            self.late_positive_threshold_ms,
        )
        negative = _finite(
            "late_negative_threshold_ms",
            self.late_negative_threshold_ms,
        )
        enrichment = _finite(
            "selection_enrichment_threshold",
            self.selection_enrichment_threshold,
        )
        slope = _finite("slope_threshold", self.slope_threshold)
        p_like = _finite(
            "permutation_p_like_threshold",
            self.permutation_p_like_threshold,
        )
        clear_count = _strict_int(
            "clear_positive_indicator_count",
            self.clear_positive_indicator_count,
            1,
            4,
        )
        partial_count = _strict_int(
            "partial_indicator_count",
            self.partial_indicator_count,
            1,
            4,
        )
        if negative >= positive:
            raise ValueError("negative threshold must be below positive threshold")
        if not 0.0 <= p_like <= 1.0:
            raise ValueError("permutation_p_like_threshold must be within [0,1]")
        if partial_count > clear_count:
            raise ValueError("partial indicator count cannot exceed clear count")
        if self.formal_spec_adoption:
            raise ValueError("classification policy must remain a simulation assumption")
        if self.version != PARTICIPANT_CLASSIFICATION_POLICY_VERSION:
            raise ValueError(
                f"version must be {PARTICIPANT_CLASSIFICATION_POLICY_VERSION}"
            )
        for name, value in {
            "late_positive_threshold_ms": positive,
            "late_negative_threshold_ms": negative,
            "selection_enrichment_threshold": enrichment,
            "slope_threshold": slope,
            "permutation_p_like_threshold": p_like,
        }.items():
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        values: Mapping[str, Any],
    ) -> ParticipantClassificationPolicy:
        _exact_fields(values, {item.name for item in fields(cls)}, "classification policy")
        return cls(**dict(values))


def build_participants(
    *,
    user_type_ids: Sequence[str],
    participants_per_type: int,
    base_master_seed: int,
    profile_payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[ValidationParticipant, ...]:
    count = _strict_int("participants_per_type", participants_per_type, 1, 100)
    seed = _strict_int("base_master_seed", base_master_seed, 0, UINT32_MAX)
    result: list[ValidationParticipant] = []
    for user_type_id in user_type_ids:
        if user_type_id not in ALL_USER_TYPE_IDS:
            raise ValueError(f"unknown validation user type: {user_type_id!r}")
        base_payload = profile_payloads[user_type_id]
        for index in range(count):
            scale = (
                0.0
                if user_type_id == "flat_control"
                else DEFAULT_RESPONSE_STRENGTH_CYCLE[index % len(DEFAULT_RESPONSE_STRENGTH_CYCLE)]
            )
            profile_hash = sha256_canonical(
                {
                    "profile": base_payload,
                    "response_strength_scale": scale,
                    "version": VALIDATION_PARTICIPANT_VERSION,
                }
            )
            result.append(
                ValidationParticipant(
                    participant_id=f"{user_type_id}__p{index + 1:03d}",
                    user_type_id=user_type_id,
                    participant_index=index,
                    physiology_seed=_participant_seed(seed, user_type_id, index),
                    response_strength_scale=scale,
                    profile_hash=profile_hash,
                )
            )
    if len({item.participant_id for item in result}) != len(result):
        raise RuntimeError("participant IDs are not unique")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    validation_preset: str
    conditions: tuple[ValidationCondition, ...]
    user_type_ids: tuple[str, ...]
    participants_per_type: int
    maximum_sessions: int
    permutation_count: int
    base_master_seed: int
    output_directory: str
    retain_details: str
    maximum_target_session_runs: int
    hue_bandwidth_degree: float = 5.0
    bpm_bandwidth: float = 15.0
    minimum_history_count: int = 3
    classification_policy: ParticipantClassificationPolicy = field(
        default_factory=ParticipantClassificationPolicy
    )
    validation_model_version: str = VALIDATION_MODEL_VERSION
    schema_version: str = VALIDATION_PLAN_VERSION

    def __post_init__(self) -> None:
        if self.validation_preset not in VALIDATION_PRESETS:
            raise ValueError(f"unknown validation preset: {self.validation_preset!r}")
        conditions = tuple(self.conditions)
        if not conditions or any(not isinstance(item, ValidationCondition) for item in conditions):
            raise TypeError("conditions must contain ValidationCondition values")
        if len({item.condition_id for item in conditions}) != len(conditions):
            raise ValueError("condition IDs must be unique")
        user_types = tuple(self.user_type_ids)
        if not user_types or any(item not in ALL_USER_TYPE_IDS for item in user_types):
            raise ValueError("user_type_ids contain an unknown or empty selection")
        if len(set(user_types)) != len(user_types):
            raise ValueError("user_type_ids must be unique")
        participants = _strict_int("participants_per_type", self.participants_per_type, 1, 100)
        sessions = _strict_int("maximum_sessions", self.maximum_sessions, 4, 100)
        permutations = _strict_int("permutation_count", self.permutation_count, 1, 10_000)
        seed = _strict_int("base_master_seed", self.base_master_seed, 0, UINT32_MAX)
        budget = _strict_int(
            "maximum_target_session_runs",
            self.maximum_target_session_runs,
            1,
            ABSOLUTE_MAXIMUM_TARGET_SESSION_RUNS,
        )
        _required_text("output_directory", self.output_directory)
        if self.retain_details not in RETAIN_DETAILS_POLICIES:
            raise ValueError(f"retain_details must be one of {RETAIN_DETAILS_POLICIES}")
        if self.retain_details == "all" and self.validation_preset != "smoke":
            raise ValueError(
                "retain_details=all is limited to the smoke preset to prevent a "
                "full-run event ledger"
            )
        hue = _finite("hue_bandwidth_degree", self.hue_bandwidth_degree)
        bpm = _finite("bpm_bandwidth", self.bpm_bandwidth)
        if hue <= 0.0 or bpm <= 0.0:
            raise ValueError("history bandwidths must be positive")
        minimum = _strict_int("minimum_history_count", self.minimum_history_count, 1, 1_000)
        if not isinstance(self.classification_policy, ParticipantClassificationPolicy):
            raise TypeError(
                "classification_policy must be ParticipantClassificationPolicy"
            )
        planned = len(conditions) * len(user_types) * participants * sessions * len(ARM_IDS)
        if planned > budget:
            raise ValueError(
                f"planned target session runs {planned} exceed configured limit {budget}; "
                "the plan is rejected rather than clipped"
            )
        if self.validation_model_version != VALIDATION_MODEL_VERSION:
            raise ValueError(f"validation_model_version must be {VALIDATION_MODEL_VERSION}")
        if self.schema_version != VALIDATION_PLAN_VERSION:
            raise ValueError(f"schema_version must be {VALIDATION_PLAN_VERSION}")
        for name, value in {
            "conditions": conditions,
            "user_type_ids": user_types,
            "participants_per_type": participants,
            "maximum_sessions": sessions,
            "permutation_count": permutations,
            "base_master_seed": seed,
            "maximum_target_session_runs": budget,
            "hue_bandwidth_degree": hue,
            "bpm_bandwidth": bpm,
            "minimum_history_count": minimum,
        }.items():
            object.__setattr__(self, name, value)

    @property
    def planned_target_session_runs(self) -> int:
        return (
            len(self.conditions)
            * len(self.user_type_ids)
            * self.participants_per_type
            * self.maximum_sessions
            * len(ARM_IDS)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "conditions": [condition.to_dict() for condition in self.conditions],
            "user_type_ids": list(self.user_type_ids),
            "arms": [arm_contract(arm).to_dict() for arm in ARM_IDS],
            "planned_target_session_runs": self.planned_target_session_runs,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def create(
        cls,
        *,
        validation_preset: str,
        conditions: Sequence[ValidationCondition] | None = None,
        participants_per_type: int | None = None,
        maximum_sessions: int | None = None,
        permutation_count: int | None = None,
        base_master_seed: int = DEFAULT_BASE_MASTER_SEED,
        output_directory: str = "artifacts/adaptive_placebo_validation",
        retain_details: str = "compact",
    ) -> ValidationConfig:
        if validation_preset not in PRESET_DEFAULTS:
            raise ValueError(f"unknown validation preset: {validation_preset!r}")
        defaults = PRESET_DEFAULTS[validation_preset]
        selected_conditions = (
            tuple(conditions)
            if conditions is not None
            else tuple(validation_condition(item) for item in defaults["condition_ids"])
        )
        return cls(
            validation_preset=validation_preset,
            conditions=selected_conditions,
            user_type_ids=tuple(defaults["user_type_ids"]),
            participants_per_type=(
                int(defaults["participants_per_type"])
                if participants_per_type is None
                else participants_per_type
            ),
            maximum_sessions=(
                int(defaults["maximum_sessions"])
                if maximum_sessions is None
                else maximum_sessions
            ),
            permutation_count=(
                int(defaults["permutation_count"])
                if permutation_count is None
                else permutation_count
            ),
            base_master_seed=base_master_seed,
            output_directory=output_directory,
            retain_details=retain_details,
            maximum_target_session_runs=int(defaults["maximum_target_session_runs"]),
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> ValidationConfig:
        values = dict(values)
        encoded_arms = values.pop("arms", None)
        encoded_planned = values.pop("planned_target_session_runs", None)
        expected = {field.name for field in fields(cls)}
        _exact_fields(values, expected, "validation config")
        normalized = dict(values)
        normalized["conditions"] = tuple(
            ValidationCondition.from_dict(item) for item in normalized["conditions"]
        )
        normalized["user_type_ids"] = tuple(normalized["user_type_ids"])
        normalized["classification_policy"] = ParticipantClassificationPolicy.from_dict(
            normalized["classification_policy"]
        )
        result = cls(**normalized)
        if encoded_arms is not None and encoded_arms != [
            arm_contract(arm).to_dict() for arm in ARM_IDS
        ]:
            raise ValueError("encoded arm contracts differ from Stage 8A.3")
        if (
            encoded_planned is not None
            and encoded_planned != result.planned_target_session_runs
        ):
            raise ValueError("encoded planned target session count differs")
        return result

    @classmethod
    def from_json(cls, encoded: str) -> ValidationConfig:
        loaded = json.loads(encoded, object_pairs_hook=_strict_object_pairs)
        if not isinstance(loaded, Mapping):
            raise ValueError("validation config JSON must contain an object")
        return cls.from_dict(loaded)


def validation_plan_projection(config: ValidationConfig) -> dict[str, Any]:
    return {
        "mode": "plan_only",
        "config": config.to_dict(),
        "condition_count": len(config.conditions),
        "user_type_count": len(config.user_type_ids),
        "participants_per_type": config.participants_per_type,
        "arm_count": len(ARM_IDS),
        "sessions_per_participant_arm": config.maximum_sessions,
        "total_planned_session_runs": config.planned_target_session_runs,
        "autonomous_donor_runs_reused": True,
        "simulation_jobs_executed": 0,
        "state_changed": False,
        "formal_spec_adoption": False,
    }


__all__ = [
    "ABSOLUTE_MAXIMUM_TARGET_SESSION_RUNS",
    "ALGORITHM_VERSION",
    "ALL_USER_TYPE_IDS",
    "ARM_CONTRACT_VERSION",
    "ARM_IDS",
    "AUTONOMOUS_ARM",
    "AUTONOMOUS_ARM_VERSION",
    "ArmContract",
    "BUNDLE_OUTCOME_SCHEMA_VERSION",
    "CONDITION_IDS",
    "DEFAULT_BASE_MASTER_SEED",
    "DOCUMENT_VERSION",
    "HISTORY_RESPONSE_MODEL_VERSION",
    "LAGGED_COUPLING_VERSION",
    "PARTICIPANT_EFFECT_VERSION",
    "PARTICIPANT_CLASSIFICATION_POLICY_VERSION",
    "ParticipantClassificationPolicy",
    "PROFILE_VERSION",
    "PROJECT_VERSION",
    "PROSPECTIVE_ENRICHMENT_VERSION",
    "PROVISIONAL_CONDITION",
    "QUICK_USER_TYPE_IDS",
    "RANDOM_ARM",
    "RANDOM_ARM_VERSION",
    "RANDOM_OUTPUT_VERSION",
    "RETAIN_DETAILS_POLICIES",
    "SESSION_OUTCOME_SCHEMA_VERSION",
    "SMOKE_USER_TYPE_IDS",
    "STATE_SCHEMA_VERSION",
    "VALIDATION_CHECKPOINT_VERSION",
    "VALIDATION_CODE_FINGERPRINT_VERSION",
    "VALIDATION_MANIFEST_VERSION",
    "VALIDATION_MODEL_VERSION",
    "VALIDATION_PARTICIPANT_VERSION",
    "VALIDATION_PLAN_VERSION",
    "VALIDATION_PRESETS",
    "VALIDATION_REPORT_VERSION",
    "VALIDATION_SUMMARY_VERSION",
    "V2_REFERENCE_CONDITION",
    "YOKED_ARM",
    "YOKED_ARM_VERSION",
    "YOKE_MAPPING_VERSION",
    "ValidationCondition",
    "ValidationConfig",
    "ValidationParticipant",
    "arm_contract",
    "build_participants",
    "default_validation_conditions",
    "load_conditions_json",
    "validation_condition",
    "validation_plan_projection",
]
