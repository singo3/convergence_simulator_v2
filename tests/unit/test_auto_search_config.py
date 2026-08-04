"""Stage 8A.2 strict immutable config tests."""

from __future__ import annotations

import dataclasses
import json

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    ALL_USER_TYPE_IDS,
    AUTO_SEARCH_MODEL_VERSION,
    AutoSearchConfig,
    CandidateGateConfig,
)


@pytest.mark.parametrize(
    ("preset", "users", "stop", "budget"),
    (
        ("smoke", 2, "coarse", 32),
        ("quick", 6, "coarse", 1_296),
        ("standard", 6, "confirm", 40_000),
        ("robust", 6, "confirm", 130_000),
    ),
)
def test_preset_defaults(preset, users, stop, budget) -> None:
    config = AutoSearchConfig.create(search_preset=preset)
    assert len(config.user_type_ids) == users
    assert config.stop_after_phase == stop
    assert config.maximum_total_session_runs == budget
    assert config.version_metadata.auto_search_model_version == AUTO_SEARCH_MODEL_VERSION
    assert config.include_reference_arm is False
    assert config.retain_full_details_policy == "phase3_full"


@pytest.mark.parametrize("preset", ("smoke", "quick", "standard", "robust"))
def test_config_json_round_trip_is_exact(preset) -> None:
    config = AutoSearchConfig.create(search_preset=preset)
    assert AutoSearchConfig.from_json(config.to_json()) == config


def test_config_is_frozen() -> None:
    config = AutoSearchConfig.create(search_preset="smoke")
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.search_preset = "quick"  # type: ignore[misc]


@pytest.mark.parametrize("preset", ("", "SMOKE", "future"))
def test_unknown_preset_is_rejected(preset) -> None:
    with pytest.raises(ValueError, match="search_preset"):
        AutoSearchConfig.create(search_preset=preset)


def test_unknown_and_duplicate_user_types_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        AutoSearchConfig.create(user_type_ids=("future_user",))
    with pytest.raises(ValueError, match="duplicates"):
        AutoSearchConfig.create(user_type_ids=("flat_control", "flat_control"))


@pytest.mark.parametrize("seed", (True, False, -1, 2**32))
def test_master_seed_requires_uint32_not_bool(seed) -> None:
    with pytest.raises((TypeError, ValueError), match="base_master_seed"):
        AutoSearchConfig.create(base_master_seed=seed)


@pytest.mark.parametrize("value", ("", "   "))
def test_output_directory_must_not_be_empty(value) -> None:
    with pytest.raises(ValueError, match="output_directory"):
        AutoSearchConfig.create(output_directory=value)


@pytest.mark.parametrize("value", (True, False, 0, -3))
def test_session_budget_requires_positive_non_bool(value) -> None:
    with pytest.raises((TypeError, ValueError), match="maximum_total_session_runs"):
        AutoSearchConfig.create(maximum_total_session_runs=value)


@pytest.mark.parametrize("phase", ("", "phase1", "future"))
def test_unknown_stop_phase_is_rejected(phase) -> None:
    with pytest.raises(ValueError, match="stop_after_phase"):
        AutoSearchConfig.create(stop_after_phase=phase)


@pytest.mark.parametrize("preset", ("smoke", "quick"))
def test_single_phase_presets_reject_later_stop(preset) -> None:
    with pytest.raises(ValueError, match="coarse phase only"):
        AutoSearchConfig.create(search_preset=preset, stop_after_phase="confirm")


@pytest.mark.parametrize("policy", ("", "full", "future"))
def test_unknown_retain_policy_is_rejected(policy) -> None:
    with pytest.raises(ValueError, match="retain_full_details_policy"):
        AutoSearchConfig.create(retain_full_details_policy=policy)


def test_config_json_rejects_missing_unknown_and_duplicate_fields() -> None:
    config = AutoSearchConfig.create().to_dict()
    missing = dict(config)
    missing.pop("search_preset")
    with pytest.raises(ValueError, match="missing"):
        AutoSearchConfig.from_dict(missing)
    unknown = {**config, "future": 1}
    with pytest.raises(ValueError, match="unknown"):
        AutoSearchConfig.from_dict(unknown)
    encoded = AutoSearchConfig.create().to_json()
    duplicate = encoded[:-1] + ',"search_preset":"standard"}'
    with pytest.raises(ValueError, match="duplicate"):
        AutoSearchConfig.from_json(duplicate)


def test_gate_config_json_is_strict_and_configurable() -> None:
    values = CandidateGateConfig().to_dict()
    values["flat_spurious_structure_rate_max"] = 0.1
    gate = CandidateGateConfig.from_json(json.dumps(values))
    assert gate.flat_spurious_structure_rate_max == 0.1
    values["future"] = 1
    with pytest.raises(ValueError, match="unknown"):
        CandidateGateConfig.from_dict(values)


@pytest.mark.parametrize(
    "field",
    (
        "failed_replicate_rate_max",
        "valid_session_rate_min",
        "flat_spurious_structure_rate_max",
        "w_ceiling_blocked_rate_max",
    ),
)
def test_gate_rates_reject_out_of_range_values(field) -> None:
    values = CandidateGateConfig().to_dict()
    values[field] = 1.1
    with pytest.raises(ValueError, match=field):
        CandidateGateConfig.from_dict(values)


def test_all_required_user_types_are_stable() -> None:
    assert ALL_USER_TYPE_IDS == (
        "green_hue_dominant_broad_bpm",
        "bpm_common_100_hue_neutral",
        "three_life_bpm_equal",
        "three_life_bpm_green_dominant",
        "green_single_peak_narrow",
        "flat_control",
    )
