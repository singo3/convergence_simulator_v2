"""Exact component and control tests for the Stage 2 physiology assumption."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.physiology import (
    calculate_next_rri,
    correlated_state_update,
    mean_rri_ms,
    respiratory_component_ms,
    round_positive_ms_to_us,
    slow_wave_component_ms,
)
from symbiotic_sim_v2.virtual_user.random_source import standard_normal


def zero_variability_config(**overrides) -> VirtualUserConfig:
    values = {
        "mean_heart_rate_bpm": 60.0,
        "respiratory_amplitude_ms": 0.0,
        "slow_wave_amplitude_ms": 0.0,
        "correlated_variability_sd_ms": 0.0,
        "beat_jitter_sd_ms": 0.0,
    }
    values.update(overrides)
    return VirtualUserConfig(**values)


def test_mean_rri_formula() -> None:
    assert mean_rri_ms(60.0) == 1000.0
    assert mean_rri_ms(75.0) == 800.0


def test_respiratory_component_exact_quarter_cycle() -> None:
    config = VirtualUserConfig(respiratory_rate_bpm=12.0, respiratory_amplitude_ms=35.0)
    assert respiratory_component_ms(config, 1.25) == pytest.approx(35.0, abs=1e-12)
    assert respiratory_component_ms(config, 0.0) == 0.0


def test_slow_wave_component_has_specified_phase() -> None:
    config = VirtualUserConfig(slow_wave_frequency_hz=0.1, slow_wave_amplitude_ms=10.0)
    assert slow_wave_component_ms(config, 0.0) == pytest.approx(
        10.0 * math.sin(math.pi / 3.0)
    )


def test_ar1_update_matches_formula() -> None:
    expected = 0.85 * 0.4 + math.sqrt(1.0 - 0.85**2) * -0.2
    assert correlated_state_update(0.85, 0.4, -0.2) == pytest.approx(expected)


def test_persistence_zero_uses_only_current_innovation() -> None:
    assert correlated_state_update(0.0, 99.0, -0.25) == pytest.approx(-0.25)


def test_high_persistence_retains_previous_state() -> None:
    with_memory = correlated_state_update(0.95, 1.0, 0.0)
    without_memory = correlated_state_update(0.0, 1.0, 0.0)
    assert with_memory == pytest.approx(0.95)
    assert without_memory == 0.0


def test_standard_calculation_components_are_exactly_separated() -> None:
    config = VirtualUserConfig()
    calculation = calculate_next_rri(config, 0, 0, 0.0)
    innovation = standard_normal(config.root_seed, "correlated_innovation", 0)
    expected_state = math.sqrt(1.0 - config.correlated_variability_persistence**2) * innovation
    assert calculation.mean_rri_ms == pytest.approx(60_000 / 70.0)
    assert calculation.respiratory_component_ms == 0.0
    assert calculation.slow_wave_component_ms == pytest.approx(10.0 * math.sin(math.pi / 3.0))
    assert calculation.next_correlated_state == pytest.approx(expected_state)
    assert calculation.correlated_component_ms == pytest.approx(8.0 * expected_state)
    assert calculation.beat_jitter_component_ms == pytest.approx(
        2.0 * standard_normal(config.root_seed, "beat_jitter", 0)
    )
    assert calculation.rri_us == 855_679


def test_lower_and_upper_clamps_are_explicit() -> None:
    lower_config = zero_variability_config(mean_heart_rate_bpm=200.0, min_rri_ms=400.0)
    lower = calculate_next_rri(lower_config, 0, 0, 0.0)
    assert lower.unclamped_rri_ms == 300.0
    assert lower.final_rri_ms == 400.0
    assert lower.clamped

    upper_config = zero_variability_config(mean_heart_rate_bpm=30.0, max_rri_ms=1500.0)
    upper = calculate_next_rri(upper_config, 0, 0, 0.0)
    assert upper.unclamped_rri_ms == 2000.0
    assert upper.final_rri_ms == 1500.0
    assert upper.clamped


@pytest.mark.parametrize(
    ("milliseconds", "expected_us"),
    [(1.2344, 1234), (1.2345, 1235), (855.679274, 855679), (1000.0, 1_000_000)],
)
def test_positive_microsecond_rounding_rule(milliseconds, expected_us) -> None:
    assert round_positive_ms_to_us(milliseconds) == expected_us


@pytest.mark.parametrize("value", [0.0, -1.0, math.inf, math.nan])
def test_rounding_rejects_non_positive_or_non_finite_values(value) -> None:
    with pytest.raises(ValueError):
        round_positive_ms_to_us(value)


def test_all_zero_variability_produces_constant_interval() -> None:
    config = zero_variability_config()
    calculations = [
        calculate_next_rri(config, second * 1_000_000, second, 0.0)
        for second in range(5)
    ]
    assert {calculation.rri_us for calculation in calculations} == {1_000_000}
    assert all(calculation.final_rri_ms == 1000.0 for calculation in calculations)


def test_zero_respiratory_amplitude_always_has_zero_component() -> None:
    config = VirtualUserConfig(respiratory_amplitude_ms=0.0)
    assert all(respiratory_component_ms(config, time) == 0.0 for time in (0.0, 1.2, 17.0))


def test_larger_respiratory_amplitude_scales_component() -> None:
    low = VirtualUserConfig(respiratory_amplitude_ms=10.0)
    high = VirtualUserConfig(respiratory_amplitude_ms=40.0)
    assert respiratory_component_ms(high, 1.25) == pytest.approx(
        4.0 * respiratory_component_ms(low, 1.25)
    )


def test_respiration_only_fixture_matches_manual_sum() -> None:
    config = zero_variability_config(
        respiratory_rate_bpm=12.0,
        respiratory_amplitude_ms=20.0,
    )
    calculation = calculate_next_rri(config, 1_250_000, 1, 0.0)
    assert calculation.respiratory_component_ms == pytest.approx(20.0)
    assert calculation.unclamped_rri_ms == pytest.approx(1020.0)
    assert calculation.rri_us == 1_020_000


def test_invalid_time_index_and_state_are_rejected() -> None:
    config = VirtualUserConfig()
    with pytest.raises(ValueError):
        calculate_next_rri(config, -1, 0, 0.0)
    with pytest.raises(ValueError):
        calculate_next_rri(config, 0, -1, 0.0)
    with pytest.raises(ValueError):
        calculate_next_rri(config, 0, 0, math.nan)
