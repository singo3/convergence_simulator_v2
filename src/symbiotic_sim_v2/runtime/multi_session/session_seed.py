"""Deterministic Stage 8A physiology seeds and aggregate virtual time."""

from __future__ import annotations

import hashlib

from symbiotic_sim_v2.simulation.time_utils import (
    indexed_local_time_to_global_us,
)

DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION = (
    "deterministic_per_session_physiology_seed_v0_1"
)
REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION = (
    "repeat_same_physiology_seed_v0_1"
)
SESSION_SEED_POLICIES = (
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION,
)
DEFAULT_MASTER_SEED = 20260802
UINT32_MAX = 2**32 - 1
SESSION_DURATION_US = 240_000_000


def _uint32(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if not 0 <= value <= UINT32_MAX:
        raise ValueError(f"{name} must be between 0 and {UINT32_MAX}")
    return value


def _session_index(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("session_index must be an integer")
    if value < 0:
        raise ValueError("session_index must be non-negative")
    return value


def _user_type_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("stationary_user_type_id must be a non-empty string")
    return value


def physiology_root_seed_for_session(
    *,
    master_seed: object,
    stationary_user_type_id: object,
    session_index: object,
    policy: object = DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
) -> int:
    """Return the exact unsigned 32-bit seed selected for one session."""

    seed = _uint32("master_seed", master_seed)
    user_type_id = _user_type_id(stationary_user_type_id)
    index = _session_index(session_index)
    if not isinstance(policy, str) or policy not in SESSION_SEED_POLICIES:
        raise ValueError("session physiology seed policy is not recognized")
    if policy == REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION:
        return seed
    key = f"{seed}:stage8a:{user_type_id}:{index}".encode("utf-8")  # noqa: UP012
    return int.from_bytes(
        hashlib.sha256(key).digest()[:4],
        byteorder="big",
        signed=False,
    )


def global_time_offset_us_for_session(session_index: object) -> int:
    """Map one zero-based session index to its aggregate virtual-time offset."""

    return indexed_local_time_to_global_us(
        _session_index(session_index),
        SESSION_DURATION_US,
        0,
    )


def global_time_us(session_index: object, local_time_us: object) -> int:
    """Translate local integer-microsecond time without changing core clocks."""

    index = _session_index(session_index)
    if isinstance(local_time_us, bool) or not isinstance(local_time_us, int):
        raise TypeError("local_time_us must be an integer")
    if not 0 <= local_time_us <= SESSION_DURATION_US:
        raise ValueError(
            f"local_time_us must be between 0 and {SESSION_DURATION_US}"
        )
    return indexed_local_time_to_global_us(
        index,
        SESSION_DURATION_US,
        local_time_us,
    )


__all__ = [
    "DEFAULT_MASTER_SEED",
    "DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION",
    "REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION",
    "SESSION_DURATION_US",
    "SESSION_SEED_POLICIES",
    "UINT32_MAX",
    "global_time_offset_us_for_session",
    "global_time_us",
    "physiology_root_seed_for_session",
]
