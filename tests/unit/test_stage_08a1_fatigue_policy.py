"""Selected-target conversion and component-owned session-end fatigue policy."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.digital_life.math import (
    ETA_E,
    RHO_E,
    calculate_e_next,
    calculate_e_next_with_coefficients,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    SelectedSessionFatiguePolicy,
    selected_session_eta,
)


@pytest.mark.parametrize("target", (0.0, 0.03, 0.05, 0.15, 0.20))
def test_selected_target_is_reached_from_zero_after_180_active_signals(
    target: float,
) -> None:
    policy = SelectedSessionFatiguePolicy(target)
    value = 0.0
    for _ in range(180):
        value = policy.calculate_e_next(value, 1, 1)
    assert value == pytest.approx(target, abs=2.0e-14)


def test_reference_target_has_the_exact_reference_eta_and_saturates_remaining_space() -> None:
    assert selected_session_eta(0.15) == ETA_E
    policy = SelectedSessionFatiguePolicy(0.15)
    initial = 0.4
    actual = initial
    for _ in range(180):
        actual = policy.calculate_e_next(actual, 1, 1)
    assert actual == pytest.approx(initial + 0.15 * (1.0 - initial), abs=2.0e-14)


@pytest.mark.parametrize(
    ("e", "s", "g"),
    ((0.0, 0, 0), (0.25, 0, 1), (0.4, 1, 0), (0.6, 1, 1)),
)
def test_existing_calculate_e_next_delegates_with_bit_exact_reference_result(
    e: float,
    s: int,
    g: int,
) -> None:
    actual = calculate_e_next(e, s, g)
    delegated = calculate_e_next_with_coefficients(
        e,
        s,
        g,
        eta_e=ETA_E,
        rho_e=RHO_E,
    )
    legacy_expression = min(
        1.0,
        max(
            0.0,
            e
            + ETA_E * (s * g) * (1.0 - e)
            - RHO_E * (1.0 - s * g) * e,
        ),
    )
    assert actual.hex() == delegated.hex() == legacy_expression.hex()


def test_baseline_closing_and_nonselected_active_all_retain_reference_recovery() -> None:
    policy = SelectedSessionFatiguePolicy(0.05)
    assert policy.calculate_e_next(0.4, 0, 0) == calculate_e_next(0.4, 0, 0)
    assert policy.calculate_e_next(0.4, 0, 1) == calculate_e_next(0.4, 0, 1)
    assert policy.calculate_e_next(0.4, 1, 0) == calculate_e_next(0.4, 1, 0)


def test_session_end_policy_resets_only_a_life_with_zero_selected_signals() -> None:
    policy = SelectedSessionFatiguePolicy(0.05)
    unselected = policy.decide_session_end(0.37, 0)
    selected = policy.decide_session_end(0.37, 1)
    assert unselected.full_recovery_applied
    assert unselected.e_after_policy == 0.0
    assert not selected.full_recovery_applied
    assert selected.e_after_policy == selected.e_before_policy == 0.37


@pytest.mark.parametrize(
    "invalid",
    (True, -0.01, 0.2000001, float("inf"), float("nan"), "0.05"),
)
def test_fatigue_target_rejects_bool_range_type_and_nonfinite(invalid: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        SelectedSessionFatiguePolicy(invalid)  # type: ignore[arg-type]


def test_unselected_recovery_fraction_is_exactly_one() -> None:
    with pytest.raises(ValueError, match="must equal 1.0"):
        SelectedSessionFatiguePolicy(
            0.05,
            unselected_session_end_recovery_fraction=math.nextafter(1.0, 0.0),
        )
