"""Immutable Stage 8A.1 stationary preference diagnostic values."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StationaryPeakMatchV2:
    peak_id: str
    hue_axis_mode: str
    hue_distance_degree: float | None
    hue_match: float
    bpm_axis_mode: str
    blink_bpm_distance: float | None
    bpm_match: float
    weighted_match: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StationaryPreferenceMatchV2:
    active: bool
    hue_degree: float | None
    blink_bpm: float | None
    preference_match: float
    winning_peak_id: str | None
    winning_hue_match: float | None
    winning_bpm_match: float | None
    peak_matches: tuple[StationaryPeakMatchV2, ...]
    landscape_version: str
    combination_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["StationaryPeakMatchV2", "StationaryPreferenceMatchV2"]
