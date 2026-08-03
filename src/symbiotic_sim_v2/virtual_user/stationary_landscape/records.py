"""Immutable diagnostic values for the private Stage 8A preference model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StationaryPeakMatch:
    peak_id: str
    hue_distance_degree: float
    hue_match: float
    blink_bpm_distance: float
    bpm_match: float
    weighted_match: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StationaryPreferenceMatch:
    active: bool
    hue_degree: float | None
    blink_bpm: float | None
    preference_match: float
    winning_peak_id: str | None
    winning_hue_match: float | None
    winning_bpm_match: float | None
    peak_matches: tuple[StationaryPeakMatch, ...]
    landscape_version: str
    combination_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["StationaryPeakMatch", "StationaryPreferenceMatch"]
