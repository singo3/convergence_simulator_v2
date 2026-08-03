"""Intrinsic curiosity, adaptive distance, and strict exploration decisions."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.digital_life.hash01 import hash01
from symbiotic_sim_v2.digital_life.relation_memory.intrinsic import (
    derive_relation_memory_intrinsic_profile,
    exploration_decision,
    exploration_probability,
    exploration_sigma,
    relation_search_radius,
    should_explore,
)


def test_intrinsic_profile_uses_exact_existing_hash_and_normative_formulas() -> None:
    profile = derive_relation_memory_intrinsic_profile("life-green")
    curiosity = hash01("life-green", "curiosity")

    assert profile.curiosity == curiosity
    assert profile.sigma_min == 0.02 + 0.04 * curiosity
    assert profile.sigma_max == 0.25 + 0.30 * curiosity
    assert profile.epsilon_accept == 0.07 - 0.04 * curiosity
    assert profile.p_explore_min == 0.10 + 0.20 * curiosity
    assert profile.algorithm_version == "adaptive_random_search_confirmed_v1"
    assert profile.to_dict()["digital_life_id"] == "life-green"


def test_intrinsic_profiles_are_id_dependent_and_fixed_across_derivations() -> None:
    profiles = [
        derive_relation_memory_intrinsic_profile(life_id)
        for life_id in ("life-red", "life-green", "life-blue")
    ]
    assert len({profile.curiosity for profile in profiles}) == 3
    assert profiles[1] == derive_relation_memory_intrinsic_profile("life-green")
    assert all(0.02 <= profile.sigma_min <= 0.06 for profile in profiles)
    assert all(0.25 <= profile.sigma_max <= 0.55 for profile in profiles)
    assert all(0.03 <= profile.epsilon_accept <= 0.07 for profile in profiles)
    assert all(0.10 <= profile.p_explore_min <= 0.30 for profile in profiles)


@pytest.mark.parametrize(
    ("weight", "expected"),
    ((0.0, 0.0), (0.5, 0.0), (0.75, 0.5), (1.0, 1.0)),
)
def test_relation_search_radius_boundaries(weight: float, expected: float) -> None:
    assert relation_search_radius(weight) == expected


def test_sigma_and_probability_reach_exact_profile_boundaries() -> None:
    profile = derive_relation_memory_intrinsic_profile("life-green")
    assert exploration_sigma(0.0, profile.sigma_min, profile.sigma_max) == (
        profile.sigma_max
    )
    assert exploration_sigma(0.5, profile.sigma_min, profile.sigma_max) == (
        profile.sigma_max
    )
    assert exploration_sigma(1.0, profile.sigma_min, profile.sigma_max) == (
        profile.sigma_min
    )
    assert exploration_probability(0.0, profile.p_explore_min) == 1.0
    assert exploration_probability(0.5, profile.p_explore_min) == 1.0
    assert exploration_probability(1.0, profile.p_explore_min) == (
        profile.p_explore_min
    )


def test_exploration_comparison_is_strict_and_equality_means_hold() -> None:
    assert should_explore(0.2, 0.3)
    assert exploration_decision(0.2, 0.3) == "explore"
    assert not should_explore(0.3, 0.3)
    assert exploration_decision(0.3, 0.3) == "hold"


@pytest.mark.parametrize("invalid", (True, math.nan, math.inf, -0.1, 1.1))
def test_radius_rejects_bool_non_finite_and_out_of_range(invalid: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        relation_search_radius(invalid)
