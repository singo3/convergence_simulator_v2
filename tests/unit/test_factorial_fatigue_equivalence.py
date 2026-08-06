"""Reference eta/rho and independently injected session-end fatigue policies."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.digital_life.math import ETA_E, RHO_E
from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    GRADUAL_REFERENCE_ONLY_SESSION_END_POLICY_VERSION,
    UNSELECTED_FULL_RECOVERY_POLICY_VERSION,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    NO_SESSION_END_RECOVERY_FRACTION,
    SelectedSessionFatiguePolicy,
    SessionEndFatigueDecision,
    selected_session_eta,
)


def test_selected_target_015_eta_is_bit_exact_v2_reference_eta() -> None:
    assert selected_session_eta(0.15).hex() == ETA_E.hex()
    assert ETA_E == 1.0 - 0.85 ** (1.0 / 180.0)
    assert RHO_E == 1.0 - 0.90 ** (1.0 / 180.0)


@pytest.mark.parametrize("selected_count", (0, 1, 90, 180))
def test_gradual_reference_policy_never_applies_session_end_full_recovery(
    selected_count: int,
) -> None:
    policy = SelectedSessionFatiguePolicy(
        0.15,
        NO_SESSION_END_RECOVERY_FRACTION,
        session_end_policy_version=(
            GRADUAL_REFERENCE_ONLY_SESSION_END_POLICY_VERSION
        ),
    )
    decision = policy.decide_session_end(0.37, selected_count)
    assert not decision.full_recovery_applied
    assert decision.e_after_policy == decision.e_before_policy == 0.37
    assert policy.eta_selected == ETA_E
    assert policy.rho_reference == RHO_E


@pytest.mark.parametrize(
    ("selected_count", "expected_e"),
    ((0, 0.0), (1, 0.37), (180, 0.37)),
)
def test_full_recovery_policy_resets_only_nonselected_life(
    selected_count: int,
    expected_e: float,
) -> None:
    decision = SelectedSessionFatiguePolicy(0.15).decide_session_end(
        0.37,
        selected_count,
    )
    assert decision.e_after_policy == expected_e
    assert decision.full_recovery_applied is (selected_count == 0)


@pytest.mark.parametrize(
    ("policy_version", "fraction"),
    (
        (GRADUAL_REFERENCE_ONLY_SESSION_END_POLICY_VERSION, 1.0),
        (UNSELECTED_FULL_RECOVERY_POLICY_VERSION, 0.0),
        ("unknown", 0.0),
    ),
)
def test_policy_version_and_fraction_cannot_silently_disagree(
    policy_version: str,
    fraction: float,
) -> None:
    with pytest.raises(ValueError):
        SelectedSessionFatiguePolicy(
            0.15,
            fraction,
            session_end_policy_version=policy_version,
        )


def test_decision_rejects_nonfinite_and_wrong_policy_flag() -> None:
    with pytest.raises(ValueError):
        SessionEndFatigueDecision(
            e_before_policy=0.3,
            e_after_policy=0.0,
            selected_active_signal_count=0,
            full_recovery_applied=True,
            recovery_fraction=0.0,
            policy_version=GRADUAL_REFERENCE_ONLY_SESSION_END_POLICY_VERSION,
        )
    with pytest.raises(ValueError):
        SelectedSessionFatiguePolicy(
            0.15,
            math.nan,
            session_end_policy_version=(
                GRADUAL_REFERENCE_ONLY_SESSION_END_POLICY_VERSION
            ),
        )
