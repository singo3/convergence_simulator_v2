"""Phase 2 bounded neighborhood generation."""

from __future__ import annotations

from .plan import ConditionPoint, local_neighborhood


def build_refine_conditions(
    seeds: tuple[ConditionPoint, ...],
    *,
    maximum_conditions: int,
) -> tuple[ConditionPoint, ...]:
    if len(seeds) > 4:
        raise ValueError("Phase 2 accepts at most four seed conditions")
    return local_neighborhood(seeds, maximum_conditions=maximum_conditions)


__all__ = ["build_refine_conditions"]
