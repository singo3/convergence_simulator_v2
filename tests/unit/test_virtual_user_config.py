"""Validation and serialization tests for Stage 2 configuration."""

from __future__ import annotations

import dataclasses
import math

import pytest

from symbiotic_sim_v2.virtual_user.config import (
    MAX_ROOT_SEED,
    VIRTUAL_USER_MODEL_VERSION,
    VirtualUserConfig,
)


def test_standard_config_values_and_version() -> None:
    config = VirtualUserConfig()
    assert config.user_id == "virtual-user-001"
    assert config.duration_seconds == 180
    assert config.mean_heart_rate_bpm == 70.0
    assert config.root_seed == 20260802
    assert config.model_version == VIRTUAL_USER_MODEL_VERSION


def test_config_json_round_trip_is_exact() -> None:
    config = VirtualUserConfig(root_seed=17, mean_heart_rate_bpm=68.5)
    assert VirtualUserConfig.from_json(config.to_json()) == config
    assert VirtualUserConfig.from_dict(config.to_dict()) == config


def test_config_is_immutable() -> None:
    config = VirtualUserConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.root_seed = 3  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "exception"),
    [
        ("user_id", "", ValueError),
        ("user_id", "   ", ValueError),
        ("user_id", 4, ValueError),
        ("duration_seconds", 10.5, TypeError),
        ("root_seed", 2.2, TypeError),
        ("mean_heart_rate_bpm", "70", TypeError),
        ("respiratory_rate_bpm", None, TypeError),
    ],
)
def test_invalid_types_are_rejected(field, value, exception) -> None:
    with pytest.raises(exception):
        VirtualUserConfig(**{field: value})


@pytest.mark.parametrize(
    "field",
    [
        "duration_seconds",
        "mean_heart_rate_bpm",
        "respiratory_rate_bpm",
        "respiratory_amplitude_ms",
        "slow_wave_frequency_hz",
        "slow_wave_amplitude_ms",
        "correlated_variability_sd_ms",
        "correlated_variability_persistence",
        "beat_jitter_sd_ms",
        "min_rri_ms",
        "max_rri_ms",
        "root_seed",
    ],
)
def test_bool_is_never_accepted_as_numeric(field) -> None:
    with pytest.raises((TypeError, ValueError)):
        VirtualUserConfig(**{field: True})


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
@pytest.mark.parametrize(
    "field",
    [
        "mean_heart_rate_bpm",
        "respiratory_rate_bpm",
        "respiratory_amplitude_ms",
        "slow_wave_frequency_hz",
        "slow_wave_amplitude_ms",
        "correlated_variability_sd_ms",
        "correlated_variability_persistence",
        "beat_jitter_sd_ms",
        "min_rri_ms",
        "max_rri_ms",
    ],
)
def test_non_finite_float_is_rejected(field, value) -> None:
    with pytest.raises(ValueError, match="finite"):
        VirtualUserConfig(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("duration_seconds", 9),
        ("duration_seconds", 3601),
        ("mean_heart_rate_bpm", 29.9),
        ("mean_heart_rate_bpm", 200.1),
        ("respiratory_rate_bpm", 2.9),
        ("respiratory_rate_bpm", 40.1),
        ("respiratory_amplitude_ms", -0.1),
        ("respiratory_amplitude_ms", 200.1),
        ("slow_wave_frequency_hz", 0.009),
        ("slow_wave_frequency_hz", 0.201),
        ("slow_wave_amplitude_ms", -0.1),
        ("slow_wave_amplitude_ms", 100.1),
        ("correlated_variability_sd_ms", -0.1),
        ("correlated_variability_sd_ms", 100.1),
        ("correlated_variability_persistence", -0.01),
        ("correlated_variability_persistence", 1.0),
        ("beat_jitter_sd_ms", -0.1),
        ("beat_jitter_sd_ms", 50.1),
        ("min_rri_ms", 249.9),
        ("max_rri_ms", 3000.1),
        ("root_seed", -1),
        ("root_seed", MAX_ROOT_SEED + 1),
    ],
)
def test_each_range_is_enforced_without_silent_clipping(field, value) -> None:
    with pytest.raises(ValueError):
        VirtualUserConfig(**{field: value})


def test_minimum_rri_must_be_less_than_maximum() -> None:
    with pytest.raises(ValueError, match="greater"):
        VirtualUserConfig(min_rri_ms=1000.0, max_rri_ms=1000.0)
    with pytest.raises(ValueError, match="greater"):
        VirtualUserConfig(min_rri_ms=1200.0, max_rri_ms=1000.0)


def test_model_version_cannot_be_substituted() -> None:
    with pytest.raises(ValueError, match="model_version"):
        VirtualUserConfig(model_version="future_model")
