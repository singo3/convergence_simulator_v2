"""F/T-only reflected candidate generation."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.digital_life.relation_memory.candidate import generate_candidate
from symbiotic_sim_v2.digital_life.relation_memory.direction import (
    derive_search_direction,
)


def test_candidate_changes_only_f_t_and_preserves_anchor_input() -> None:
    anchor = (0.99, 0.23, 0.01, 0.87)
    original = tuple(anchor)
    direction = derive_search_direction("life-green", 0)
    candidate = generate_candidate(anchor, 0.42, direction)

    assert anchor == original
    assert candidate[1] == anchor[1]
    assert candidate[3] == anchor[3]
    assert candidate[0] != anchor[0]
    assert candidate[2] != anchor[2]
    assert all(0.0 <= value <= 1.0 for value in candidate)


def test_candidate_is_continuous_and_not_rounded_to_twenty_five_cells() -> None:
    direction = derive_search_direction("life-red", 0)
    candidate = generate_candidate((0.5, 0.5, 0.5, 0.5), 0.31134787426039223, direction)
    assert candidate[0] * 4.0 != round(candidate[0] * 4.0)
    assert candidate[2] * 4.0 != round(candidate[2] * 4.0)


@pytest.mark.parametrize("invalid_sigma", (True, -0.1, math.nan, math.inf))
def test_candidate_rejects_invalid_sigma(invalid_sigma: object) -> None:
    direction = derive_search_direction("life-red", 0)
    with pytest.raises((TypeError, ValueError)):
        generate_candidate((0.5, 0.5, 0.5, 0.5), invalid_sigma, direction)


def test_candidate_rejects_out_of_range_anchor_without_silent_clip() -> None:
    direction = derive_search_direction("life-red", 0)
    with pytest.raises(ValueError):
        generate_candidate((1.1, 0.5, 0.5, 0.5), 0.2, direction)
