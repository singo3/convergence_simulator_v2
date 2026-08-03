"""Stage 8A observable pattern-distance boundary tests."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.convergence import (
    RollingConvergenceConfig,
    SessionPatternObservation,
    pattern_distance,
    patterns_are_near,
)


def observation(
    index: int,
    hue: float,
    bpm: float,
    holder: str = "life-green",
) -> SessionPatternObservation:
    return SessionPatternObservation(
        session_index=index,
        valid_for_convergence=True,
        invalid_reason=None,
        holder_id=holder,
        hue_degree=hue,
        blink_bpm=bpm,
        exploration_decision="hold",
        candidate_generated=False,
        candidate_accepted=False,
    )


def test_same_pattern_and_circular_hue_are_exact() -> None:
    config = RollingConvergenceConfig()
    assert pattern_distance(
        observation(0, 129.0, 125.0),
        observation(1, 129.0, 125.0),
        config,
    ) == 0.0
    wrapped = pattern_distance(
        observation(0, 359.0, 100.0),
        observation(1, 1.0, 100.0),
        config,
    )
    assert wrapped == 1.0
    assert patterns_are_near(
        observation(0, 359.0, 100.0),
        observation(1, 1.0, 100.0),
        config,
    )


def test_hue_bpm_and_ellipse_boundaries_are_inclusive() -> None:
    config = RollingConvergenceConfig()
    assert pattern_distance(
        observation(0, 100.0, 100.0),
        observation(1, 102.0, 100.0),
        config,
    ) == 1.0
    assert pattern_distance(
        observation(0, 100.0, 100.0),
        observation(1, 100.0, 120.0),
        config,
    ) == 1.0
    diagonal = pattern_distance(
        observation(0, 100.0, 100.0),
        observation(1, 102.0, 120.0),
        config,
    )
    assert diagonal == pytest.approx(math.sqrt(2.0))
    assert not patterns_are_near(
        observation(0, 100.0, 100.0),
        observation(1, 102.0, 120.0),
        config,
    )


def test_different_life_and_invalid_session_are_rejected() -> None:
    config = RollingConvergenceConfig()
    with pytest.raises(ValueError, match="same Digital Life"):
        pattern_distance(
            observation(0, 100.0, 100.0, "life-red"),
            observation(1, 100.0, 100.0, "life-blue"),
            config,
        )
    invalid = SessionPatternObservation(
        session_index=2,
        valid_for_convergence=False,
        invalid_reason="baseline_rejected",
        holder_id=None,
        hue_degree=None,
        blink_bpm=None,
        exploration_decision=None,
        candidate_generated=False,
        candidate_accepted=False,
    )
    with pytest.raises(ValueError, match="valid"):
        pattern_distance(observation(0, 100.0, 100.0), invalid, config)


@pytest.mark.parametrize("invalid", (True, math.nan, math.inf))
def test_observation_rejects_bool_and_nonfinite_pattern_values(invalid: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        observation(0, invalid, 100.0)  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        observation(0, 100.0, invalid)  # type: ignore[arg-type]
