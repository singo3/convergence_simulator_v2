"""Condition-independent paired-replicate physiology seed policy."""

from __future__ import annotations

import hashlib

from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    UINT32_MAX,
    physiology_root_seed_for_session,
)

from .config import PAIRED_REPLICATE_SEED_POLICY_VERSION


def paired_replicate_master_seed(base_master_seed: int, replicate_index: int) -> int:
    if isinstance(base_master_seed, bool) or not isinstance(base_master_seed, int):
        raise TypeError("base_master_seed must be an integer")
    if not 0 <= base_master_seed <= UINT32_MAX:
        raise ValueError(f"base_master_seed must be between 0 and {UINT32_MAX}")
    if isinstance(replicate_index, bool) or not isinstance(replicate_index, int):
        raise TypeError("replicate_index must be an integer")
    if replicate_index < 0:
        raise ValueError("replicate_index must be non-negative")
    key = f"{base_master_seed}:stage8a1:replicate:{replicate_index}"
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:4], "big")


def paired_physiology_root_seed(
    *,
    base_master_seed: int,
    replicate_index: int,
    user_type_id: str,
    session_index: int,
) -> int:
    """Use no condition, fatigue, sigma, or convergence value in the seed."""

    return physiology_root_seed_for_session(
        master_seed=paired_replicate_master_seed(base_master_seed, replicate_index),
        stationary_user_type_id=user_type_id,
        session_index=session_index,
        policy=DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    )


__all__ = [
    "PAIRED_REPLICATE_SEED_POLICY_VERSION",
    "paired_physiology_root_seed",
    "paired_replicate_master_seed",
]
