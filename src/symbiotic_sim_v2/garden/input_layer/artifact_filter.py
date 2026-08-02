"""Pure raw-RRI artifact classification for the Garden input boundary."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig


@dataclass(frozen=True, slots=True)
class ArtifactDecision:
    artifact: bool
    artifact_reason: str | None
    median_history_count_before: int
    median_rri_us_before: float | None
    relative_deviation: float | None


def classify_rri(
    rri_us: int,
    recent_valid_history_us: Sequence[int],
    config: GardenInputConfig,
) -> ArtifactDecision:
    """Classify without clipping, interpolation, or mutation of history."""

    if isinstance(rri_us, bool) or not isinstance(rri_us, int):
        raise TypeError("rri_us must be an integer")
    if rri_us <= 0:
        raise ValueError("rri_us must be positive")
    history = tuple(recent_valid_history_us[-config.median_history_max_valid_count :])
    for item in history:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError("valid history must contain positive integer RRI values")

    if rri_us < config.rri_min_us:
        return ArtifactDecision(True, "too_short", len(history), None, None)
    if rri_us > config.rri_max_us:
        return ArtifactDecision(True, "too_long", len(history), None, None)
    if len(history) < config.median_history_min_valid_count:
        return ArtifactDecision(False, None, len(history), None, None)

    median_us = float(statistics.median(history))
    relative_deviation = abs(rri_us - median_us) / median_us
    if relative_deviation > config.median_relative_deviation_limit:
        return ArtifactDecision(
            True,
            "median_deviation",
            len(history),
            median_us,
            relative_deviation,
        )
    return ArtifactDecision(False, None, len(history), median_us, relative_deviation)
