"""Pure and boundary tests for one Stage 5B connected Digital Life."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.connected_component import (
    ConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.math import ETA_E, RHO_E, calculate_e_next
from symbiotic_sim_v2.digital_life.second_round import calculate_g, decide_q_update
from symbiotic_sim_v2.digital_life.touch_intent import DigitalLifeTouchIntent


def test_calculate_g_is_a_local_binary_id_comparison() -> None:
    assert calculate_g("life-green", "life-green") == 1
    assert calculate_g("life-green", "life-red") == 0
    assert calculate_g("life-green", None) == 0


@pytest.mark.parametrize("holder", [True, "", 3])
def test_calculate_g_rejects_invalid_holder_ids(holder: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        calculate_g("life-green", holder)


def test_e_accumulates_for_180_active_holder_rounds_then_recovers() -> None:
    e = 0.0
    for _ in range(180):
        e = calculate_e_next(e, 1, 1)
    assert e == pytest.approx(0.15)
    assert calculate_e_next(e, 0, 1) == pytest.approx(e * (1.0 - RHO_E))
    assert pytest.approx(1.0 - 0.85 ** (1.0 / 180.0)) == ETA_E


@pytest.mark.parametrize(
    ("w", "expected"),
    [
        (1.0, 0.6),
        (0.5, 0.5),
        (0.0, 0.4),
    ],
)
def test_q_bundle_update_vectors(w: float, expected: float) -> None:
    decision = decide_q_update(
        q=0.5,
        w=w,
        g=1,
        evaluation_present=True,
        is_new_valid_evaluation=True,
        evaluation_kind="bundle",
        evaluation_is_valid=True,
    )
    assert decision.applied
    assert decision.skip_reason == "applied"
    assert decision.q_after == pytest.approx(expected)


@pytest.mark.parametrize(
    ("arguments", "reason"),
    [
        (
            {
                "evaluation_present": False,
                "is_new_valid_evaluation": False,
                "evaluation_kind": None,
                "evaluation_is_valid": None,
                "g": 1,
            },
            "no_new_evaluation",
        ),
        (
            {
                "evaluation_present": True,
                "is_new_valid_evaluation": False,
                "evaluation_kind": "bundle",
                "evaluation_is_valid": False,
                "g": 1,
            },
            "evaluation_rejected",
        ),
        (
            {
                "evaluation_present": True,
                "is_new_valid_evaluation": True,
                "evaluation_kind": "baseline",
                "evaluation_is_valid": True,
                "g": 1,
            },
            "baseline_not_intervention_evaluation",
        ),
        (
            {
                "evaluation_present": True,
                "is_new_valid_evaluation": True,
                "evaluation_kind": "bundle",
                "evaluation_is_valid": True,
                "g": 0,
            },
            "g_zero",
        ),
    ],
)
def test_q_skip_contract(arguments: dict[str, object], reason: str) -> None:
    decision = decide_q_update(q=0.5, w=1.0, **arguments)
    assert not decision.applied
    assert decision.q_after == 0.5
    assert decision.skip_reason == reason


def test_touch_intent_is_immutable_and_requires_enabled_tau() -> None:
    intent = DigitalLifeTouchIntent(
        signal_index=60,
        signal_time_us=60_000_000,
        digital_life_id="life-green",
        role="green",
        b=(0.35, 0.5, 0.5, 0.5),
        tau=0.5,
        touch_enabled=True,
    )
    assert intent.b_f == 0.35
    with pytest.raises((AttributeError, TypeError)):
        intent.tau = 0.1  # type: ignore[misc]
    with pytest.raises(ValueError):
        DigitalLifeTouchIntent(
            signal_index=60,
            signal_time_us=60_000_000,
            digital_life_id="life-green",
            role="green",
            b=(0.35, 0.5, 0.5, 0.5),
            tau=None,
            touch_enabled=True,
        )


@pytest.mark.parametrize("tau", [math.nan, math.inf, -0.1, 1.1, True])
def test_touch_intent_rejects_invalid_tau(tau: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        DigitalLifeTouchIntent(
            signal_index=60,
            signal_time_us=60_000_000,
            digital_life_id="life-green",
            role="green",
            b=(0.35, 0.5, 0.5, 0.5),
            tau=tau,  # type: ignore[arg-type]
            touch_enabled=True,
        )


def test_connected_lives_own_distinct_state_and_k_objects() -> None:
    red = ConnectedDigitalLifeComponent(digital_life_config_for_role("red"))
    green = ConnectedDigitalLifeComponent(digital_life_config_for_role("green"))
    blue = ConnectedDigitalLifeComponent(digital_life_config_for_role("blue"))

    assert len({id(red._state), id(green._state), id(blue._state)}) == 3
    assert len(
        {
            id(red.snapshot().k_current),
            id(green.snapshot().k_current),
            id(blue.snapshot().k_current),
        }
    ) == 3
