"""Condition-independent Stage 8A.3 random comparator cache contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    RANDOM_OUTPUT_VERSION,
    ValidationParticipant,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import sha256_canonical

from .config import SHARED_RANDOM_COMPARATOR_VERSION

SHARED_RANDOM_CACHE_KEY_VERSION = "shared_random_cache_key_v1"


@dataclass(frozen=True, slots=True)
class SharedRandomCacheKey:
    participant_id: str
    user_type_id: str
    physiology_seed: int
    maximum_sessions: int
    random_output_version: str
    code_fingerprint: str
    version: str = SHARED_RANDOM_CACHE_KEY_VERSION

    def __post_init__(self) -> None:
        for name in ("participant_id", "user_type_id", "code_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if len(self.code_fingerprint) != 64:
            raise ValueError("code_fingerprint must be a SHA-256 digest")
        int(self.code_fingerprint, 16)
        if isinstance(self.physiology_seed, bool) or not isinstance(self.physiology_seed, int):
            raise TypeError("physiology_seed must be an integer")
        if not 0 <= self.physiology_seed <= 0xFFFFFFFF:
            raise ValueError("physiology_seed must be unsigned 32-bit")
        if isinstance(self.maximum_sessions, bool) or not isinstance(self.maximum_sessions, int):
            raise TypeError("maximum_sessions must be an integer")
        if not 4 <= self.maximum_sessions <= 100:
            raise ValueError("maximum_sessions must be between 4 and 100")
        if self.random_output_version != RANDOM_OUTPUT_VERSION:
            raise ValueError(f"random_output_version must be {RANDOM_OUTPUT_VERSION}")
        if self.version != SHARED_RANDOM_CACHE_KEY_VERSION:
            raise ValueError(f"version must be {SHARED_RANDOM_CACHE_KEY_VERSION}")

    @property
    def digest(self) -> str:
        return sha256_canonical(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def shared_random_cache_key(
    participant: ValidationParticipant,
    *,
    maximum_sessions: int,
    code_fingerprint: str,
) -> SharedRandomCacheKey:
    return SharedRandomCacheKey(
        participant_id=participant.participant_id,
        user_type_id=participant.user_type_id,
        physiology_seed=participant.physiology_seed,
        maximum_sessions=maximum_sessions,
        random_output_version=RANDOM_OUTPUT_VERSION,
        code_fingerprint=code_fingerprint,
    )


def _bundle_random_value(row: BundleOutcome) -> dict[str, Any]:
    return {
        "participant_id": row.participant_id,
        "user_type_id": row.user_type_id,
        "response_strength_scale": row.response_strength_scale,
        "arm": row.arm,
        "session_index": row.session_index,
        "bundle_index": row.bundle_index,
        "physiology_seed": row.physiology_seed,
        "output_seed": row.output_seed,
        "displayed_life_id": row.displayed_life_id,
        "displayed_hue_degree": row.displayed_hue_degree,
        "displayed_blink_bpm": row.displayed_blink_bpm,
        "displayed_b": row.displayed_b,
        "baseline_rmssd_ms": row.baseline_rmssd_ms,
        "bundle_rmssd_ms": row.bundle_rmssd_ms,
        "delta_rmssd_ms": row.delta_rmssd_ms,
        "event_digest": row.event_digest,
    }


def _session_random_value(row: SessionOutcome) -> dict[str, Any]:
    return {
        "participant_id": row.participant_id,
        "user_type_id": row.user_type_id,
        "response_strength_scale": row.response_strength_scale,
        "arm": row.arm,
        "session_index": row.session_index,
        "physiology_seed": row.physiology_seed,
        "baseline_rmssd_ms": row.baseline_rmssd_ms,
        "bundle_rmssd_ms": row.bundle_rmssd_ms,
        "bundle_delta_rmssd_ms": row.bundle_delta_rmssd_ms,
        "mean_valid_bundle_delta_rmssd_ms": (row.mean_valid_bundle_delta_rmssd_ms),
        "bundle_life_ids": row.bundle_life_ids,
        "bundle_hue_degrees": row.bundle_hue_degrees,
        "bundle_blink_bpms": row.bundle_blink_bpms,
        "output_sequence_digest": row.output_sequence_digest,
    }


def shared_random_result_checksum(
    bundles: tuple[BundleOutcome, ...],
    sessions: tuple[SessionOutcome, ...],
) -> str:
    """Checksum physical/random/physiology results without a condition label."""

    return sha256_canonical(
        {
            "bundles": [_bundle_random_value(item) for item in bundles],
            "sessions": [_session_random_value(item) for item in sessions],
            "shared_random_comparator_version": SHARED_RANDOM_COMPARATOR_VERSION,
        }
    )


def clone_shared_random_for_condition(
    bundles: tuple[BundleOutcome, ...],
    sessions: tuple[SessionOutcome, ...],
    *,
    condition_id: str,
) -> tuple[tuple[BundleOutcome, ...], tuple[SessionOutcome, ...]]:
    if not isinstance(condition_id, str) or not condition_id.strip():
        raise ValueError("condition_id must be a non-empty string")
    projected_bundles = tuple(
        replace(
            item,
            condition_id=condition_id,
            data_digest=sha256_canonical(
                {
                    "participant_id": item.participant_id,
                    "condition_id": condition_id,
                    "arm": item.arm,
                    "session_index": item.session_index,
                    "bundle_index": item.bundle_index,
                    "baseline_rmssd_ms": item.baseline_rmssd_ms,
                    "bundle_rmssd_ms": item.bundle_rmssd_ms,
                    "delta_rmssd_ms": item.delta_rmssd_ms,
                    "displayed_life_id": item.displayed_life_id,
                    "displayed_hue_degree": item.displayed_hue_degree,
                    "displayed_blink_bpm": item.displayed_blink_bpm,
                }
            ),
        )
        for item in bundles
    )
    projected_sessions = tuple(replace(item, condition_id=condition_id) for item in sessions)
    if shared_random_result_checksum(projected_bundles, projected_sessions) != (
        shared_random_result_checksum(bundles, sessions)
    ):
        raise RuntimeError("condition projection changed the shared random result")
    return projected_bundles, projected_sessions


__all__ = [
    "SHARED_RANDOM_CACHE_KEY_VERSION",
    "SharedRandomCacheKey",
    "clone_shared_random_for_condition",
    "shared_random_cache_key",
    "shared_random_result_checksum",
]
