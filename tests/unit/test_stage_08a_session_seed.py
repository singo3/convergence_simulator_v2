"""Exact Stage 8A session physiology seed and aggregate-time contracts."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION,
    SESSION_DURATION_US,
    global_time_offset_us_for_session,
    global_time_us,
    physiology_root_seed_for_session,
)


def derive(
    session_index: int,
    *,
    master_seed: int = 20260802,
    user_type_id: str = "green_narrow_moderate",
    policy: str = DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
) -> int:
    return physiology_root_seed_for_session(
        master_seed=master_seed,
        stationary_user_type_id=user_type_id,
        session_index=session_index,
        policy=policy,
    )


def test_unsigned_sha256_first_32_bit_reference_values_are_exact() -> None:
    assert derive(0) == 2_264_431_022
    assert derive(1) == 4_010_189_130
    assert derive(2) == 1_890_941_505


def test_seed_changes_independently_with_session_user_type_and_master_seed() -> None:
    baseline = derive(0)
    assert derive(1) != baseline
    assert derive(0, user_type_id="green_broad_strong") != baseline
    assert derive(0, master_seed=20260803) != baseline
    assert derive(0) == baseline


def test_repeat_policy_uses_the_same_master_seed_for_every_session() -> None:
    assert {
        derive(index, policy=REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION)
        for index in range(24)
    } == {20260802}


@pytest.mark.parametrize(
    ("keyword", "value", "error"),
    (
        ("master_seed", True, TypeError),
        ("master_seed", -1, ValueError),
        ("master_seed", 2**32, ValueError),
        ("stationary_user_type_id", "", ValueError),
        ("session_index", True, TypeError),
        ("session_index", -1, ValueError),
        ("policy", "unknown", ValueError),
    ),
)
def test_invalid_seed_inputs_are_rejected(keyword, value, error) -> None:
    values = {
        "master_seed": 20260802,
        "stationary_user_type_id": "green_narrow_moderate",
        "session_index": 0,
        "policy": DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    }
    values[keyword] = value
    with pytest.raises(error):
        physiology_root_seed_for_session(**values)


def test_local_and_global_integer_microsecond_times_are_separate() -> None:
    assert global_time_offset_us_for_session(0) == 0
    assert global_time_offset_us_for_session(3) == 3 * SESSION_DURATION_US
    assert global_time_us(3, 0) == 720_000_000
    assert global_time_us(3, SESSION_DURATION_US) == 960_000_000
    with pytest.raises(ValueError):
        global_time_us(0, SESSION_DURATION_US + 1)
