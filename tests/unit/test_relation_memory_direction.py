"""Exact Hash01 keying, normalization, and deterministic fallback."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.digital_life.hash01 import hash01
from symbiotic_sim_v2.digital_life.relation_memory import direction as module
from symbiotic_sim_v2.digital_life.relation_memory.config import (
    DIRECTION_FALLBACK_POLICY_VERSION,
)
from symbiotic_sim_v2.digital_life.relation_memory.direction import (
    derive_search_direction,
)


def test_direction_uses_pre_increment_trial_index_and_exact_hash_keys() -> None:
    direction = derive_search_direction("life-green", 0)
    expected_u_f = 2.0 * hash01("life-green", "C", "direction", 0, "F") - 1.0
    expected_u_t = 2.0 * hash01("life-green", "C", "direction", 0, "T") - 1.0

    assert direction.trial_index_used == 0
    assert direction.u_f == expected_u_f
    assert direction.u_t == expected_u_t
    assert direction.norm == math.hypot(expected_u_f, expected_u_t)
    assert math.hypot(direction.xi[0], direction.xi[2]) == pytest.approx(1.0)
    assert direction.xi[1] == direction.xi[3] == 0.0
    assert not direction.fallback_used


def test_near_zero_direction_uses_versioned_positive_f_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys: list[tuple[object, ...]] = []

    def zero_direction_hash(*parts: object) -> float:
        keys.append(parts)
        return 0.5

    monkeypatch.setattr(module, "hash01", zero_direction_hash)
    direction = module.derive_search_direction("life-blue", 7)

    assert keys == [
        ("life-blue", "C", "direction", 7, "F"),
        ("life-blue", "C", "direction", 7, "T"),
    ]
    assert direction.norm == 0.0
    assert direction.xi == (1.0, 0.0, 0.0, 0.0)
    assert direction.fallback_used
    assert direction.fallback_policy_version == DIRECTION_FALLBACK_POLICY_VERSION


@pytest.mark.parametrize("invalid_index", (True, -1, 0.5))
def test_direction_rejects_invalid_trial_indices(invalid_index: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        derive_search_direction("life-red", invalid_index)
