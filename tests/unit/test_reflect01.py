"""Continuous reflected-boundary mapping tests."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.digital_life.relation_memory.reflect import (
    reflect01,
    reflect01_vector,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    ((0.0, 0.0), (0.8, 0.8), (1.0, 1.0), (1.2, 0.8), (-0.2, 0.2), (2.2, 0.2)),
)
def test_reflect01_uses_positive_period_two_modulo(
    value: float,
    expected: float,
) -> None:
    assert reflect01(value) == pytest.approx(expected)


def test_reflect01_vector_is_elementwise_and_does_not_clip() -> None:
    assert reflect01_vector((-0.2, 0.8, 1.2, 2.2)) == pytest.approx(
        (0.2, 0.8, 0.8, 0.2)
    )


@pytest.mark.parametrize("invalid", (True, math.nan, math.inf, -math.inf, "0.5"))
def test_reflect01_rejects_bool_non_finite_and_non_numeric(invalid: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        reflect01(invalid)
