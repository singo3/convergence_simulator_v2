from __future__ import annotations

import hashlib

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma.condition import (
    FatigueSigmaCondition,
    FatigueSigmaGridConfig,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
    UNSELECTED_FULL_RECOVERY_POLICY_VERSION,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.replicate_seed import (
    paired_physiology_root_seed,
    paired_replicate_master_seed,
)


def test_default_condition_is_the_fixed_non_normative_experiment() -> None:
    condition = FatigueSigmaCondition.create()
    assert condition.user_type_id == "green_hue_dominant_broad_bpm"
    assert condition.selected_session_fatigue_target == 0.05
    assert condition.unselected_session_end_recovery_fraction == 1.0
    assert condition.sigma_multiplier == 1.0
    assert condition.maximum_sessions == 24
    assert condition.master_seed == 20260802
    assert condition.formal_spec_adoption is False
    assert condition.experiment_profile_version == FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION
    assert condition.fatigue_policy_version == UNSELECTED_FULL_RECOVERY_POLICY_VERSION


@pytest.mark.parametrize("target", [0.0, 0.20])
def test_fatigue_target_boundaries_are_accepted(target: float) -> None:
    assert (
        FatigueSigmaCondition.create(
            selected_session_fatigue_target=target
        ).selected_session_fatigue_target
        == target
    )


@pytest.mark.parametrize("target", [-0.0001, 0.2001, float("inf"), float("nan")])
def test_fatigue_target_rejects_outside_or_nonfinite(target: float) -> None:
    with pytest.raises(ValueError):
        FatigueSigmaCondition.create(selected_session_fatigue_target=target)


def test_unselected_recovery_is_exactly_one() -> None:
    values = FatigueSigmaCondition.create().to_dict()
    values["unselected_session_end_recovery_fraction"] = 0.999
    with pytest.raises(ValueError, match="must be 1.0"):
        FatigueSigmaCondition.from_dict(values)


def test_condition_json_round_trip_is_exact_and_strict() -> None:
    condition = FatigueSigmaCondition.create(
        selected_session_fatigue_target=0.15,
        sigma_multiplier=1.5,
        maximum_sessions=60,
        master_seed=2**32 - 1,
    )
    assert FatigueSigmaCondition.from_json(condition.to_json()) == condition
    duplicate = condition.to_json().replace(
        '"condition_id":', '"condition_id":"duplicate","condition_id":', 1
    )
    with pytest.raises(ValueError, match="duplicate condition field"):
        FatigueSigmaCondition.from_json(duplicate)
    extra = condition.to_dict() | {"unknown": 1}
    with pytest.raises(ValueError, match="unknown"):
        FatigueSigmaCondition.from_dict(extra)
    missing = condition.to_dict()
    missing.pop("schema_version")
    with pytest.raises(ValueError, match="missing"):
        FatigueSigmaCondition.from_dict(missing)

    wrong_seed_policy = condition.to_dict()
    wrong_seed_policy["session_seed_policy"] = "repeat_same_physiology_seed_v0_1"
    with pytest.raises(ValueError, match="session_seed_policy must be"):
        FatigueSigmaCondition.from_dict(wrong_seed_policy)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("selected_session_fatigue_target", True),
        ("sigma_multiplier", False),
        ("maximum_sessions", True),
        ("master_seed", False),
        ("formal_spec_adoption", 0),
    ],
)
def test_condition_rejects_boolean_coercion(field: str, value: object) -> None:
    values = FatigueSigmaCondition.create().to_dict()
    values[field] = value
    with pytest.raises((TypeError, ValueError)):
        FatigueSigmaCondition.from_dict(values)


def test_grid_order_is_canonical_and_budget_is_explicit() -> None:
    grid = FatigueSigmaGridConfig(
        fatigue_targets=(0.15, 0.03, 0.08),
        sigma_multipliers=(1.5, 0.5, 1.0),
        maximum_sessions=12,
        replicate_count=3,
    )
    assert grid.fatigue_targets == (0.03, 0.08, 0.15)
    assert grid.sigma_multipliers == (0.5, 1.0, 1.5)
    assert grid.total_planned_session_runs == 324


def test_grid_rejects_more_than_thirty_thousand_sessions() -> None:
    with pytest.raises(ValueError, match="exceed"):
        FatigueSigmaGridConfig(
            fatigue_targets=tuple(index / 100 for index in range(21)),
            sigma_multipliers=tuple(0.25 + index * 0.05 for index in range(20)),
            maximum_sessions=100,
            replicate_count=1,
        )


def test_paired_replicate_seed_uses_the_required_sha256_key() -> None:
    key = "20260802:stage8a1:replicate:4"
    expected = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big")
    assert paired_replicate_master_seed(20260802, 4) == expected


def test_paired_session_seed_has_no_condition_dimension() -> None:
    first = paired_physiology_root_seed(
        base_master_seed=20260802,
        replicate_index=2,
        user_type_id="green_hue_dominant_broad_bpm",
        session_index=7,
    )
    second = paired_physiology_root_seed(
        base_master_seed=20260802,
        replicate_index=2,
        user_type_id="green_hue_dominant_broad_bpm",
        session_index=7,
    )
    assert first == second
