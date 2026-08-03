"""Strict records confined to the simulation-only hidden-truth diagnostic."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.simulation.time_utils import (
    indexed_local_time_to_global_us,
)

from .records import STAGE8A_SESSION_DURATION_US

STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION = (
    "stationary_landscape_truth_alignment_v0_1"
)
TRUTH_CLASSIFICATIONS = frozenset(
    {
        "not_converged",
        "correct_convergence",
        "stable_suboptimal",
        "no_preference_control",
    }
)


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _optional_finite(name: str, value: object | None) -> float | None:
    return None if value is None else _finite(name, value)


def _optional_text(name: str, value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string or null")
    return value


def _strict_object(encoded: str) -> dict[str, Any]:
    if not isinstance(encoded, str):
        raise TypeError("encoded truth alignment must be a string")

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate truth alignment field: {key}")
            result[key] = value
        return result

    parsed = json.loads(encoded, object_pairs_hook=pairs)
    if not isinstance(parsed, dict):
        raise ValueError("truth alignment JSON must contain an object")
    return parsed


@dataclass(frozen=True, slots=True)
class TruthAlignmentRecord:
    evaluated_at_session_index: int
    local_time_us: int
    global_time_us: int
    primary_converged: bool
    truth_classification: str
    preference_match_at_medoid: float | None
    global_maximum_preference_match: float
    response_gap: float | None
    nearest_peak_id: str | None
    distance_to_nearest_peak_center: float | None
    medoid_hue_degree: float | None
    medoid_blink_bpm: float | None
    truth_alignment_version: str = STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.evaluated_at_session_index, bool)
            or not isinstance(self.evaluated_at_session_index, int)
        ):
            raise TypeError("evaluated_at_session_index must be an integer")
        if self.evaluated_at_session_index < 0:
            raise ValueError("evaluated_at_session_index must be non-negative")
        if isinstance(self.local_time_us, bool) or not isinstance(
            self.local_time_us,
            int,
        ):
            raise TypeError("local_time_us must be an integer")
        if isinstance(self.global_time_us, bool) or not isinstance(
            self.global_time_us,
            int,
        ):
            raise TypeError("global_time_us must be an integer")
        if self.local_time_us < 0 or self.global_time_us < 0:
            raise ValueError("truth alignment times must be non-negative")
        if self.global_time_us != indexed_local_time_to_global_us(
            self.evaluated_at_session_index,
            STAGE8A_SESSION_DURATION_US,
            self.local_time_us,
        ):
            raise ValueError("truth global_time_us differs from session local time")
        if not isinstance(self.primary_converged, bool):
            raise TypeError("primary_converged must be boolean")
        if self.truth_classification not in TRUTH_CLASSIFICATIONS:
            raise ValueError("truth_classification is not recognized")
        if self.truth_alignment_version != STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION:
            raise ValueError(
                "truth_alignment_version must be "
                f"{STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION}"
            )
        for name in (
            "preference_match_at_medoid",
            "response_gap",
            "distance_to_nearest_peak_center",
            "medoid_hue_degree",
            "medoid_blink_bpm",
        ):
            object.__setattr__(self, name, _optional_finite(name, getattr(self, name)))
        for name in ("preference_match_at_medoid", "response_gap"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.medoid_hue_degree is not None and not 0.0 <= self.medoid_hue_degree <= 360.0:
            raise ValueError("medoid_hue_degree must be between 0 and 360")
        if self.medoid_blink_bpm is not None and not 10.0 <= self.medoid_blink_bpm <= 165.0:
            raise ValueError("medoid_blink_bpm must be between 10 and 165")
        maximum = _finite(
            "global_maximum_preference_match",
            self.global_maximum_preference_match,
        )
        if not 0.0 <= maximum <= 1.0:
            raise ValueError("global maximum preference match must be between 0 and 1")
        object.__setattr__(self, "global_maximum_preference_match", maximum)
        object.__setattr__(
            self,
            "nearest_peak_id",
            _optional_text("nearest_peak_id", self.nearest_peak_id),
        )
        aligned = self.truth_classification in {
            "correct_convergence",
            "stable_suboptimal",
        }
        if aligned != self.primary_converged and self.truth_classification != (
            "no_preference_control"
        ):
            raise ValueError("truth classification differs from primary convergence")
        alignment_values = (
            self.preference_match_at_medoid,
            self.response_gap,
            self.nearest_peak_id,
            self.distance_to_nearest_peak_center,
            self.medoid_hue_degree,
            self.medoid_blink_bpm,
        )
        if aligned and any(value is None for value in alignment_values):
            raise ValueError("an aligned convergence requires complete truth diagnostics")
        if self.truth_classification == "not_converged" and any(
            value is not None for value in alignment_values
        ):
            raise ValueError("not_converged cannot carry medoid truth diagnostics")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> TruthAlignmentRecord:
        if not isinstance(values, Mapping):
            raise TypeError("truth alignment values must be a mapping")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(
                f"missing truth alignment fields: {', '.join(sorted(missing))}"
            )
        if unknown := actual - expected:
            raise ValueError(
                f"unknown truth alignment fields: {', '.join(sorted(unknown))}"
            )
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> TruthAlignmentRecord:
        return cls.from_dict(_strict_object(encoded))


__all__ = [
    "STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION",
    "TRUTH_CLASSIFICATIONS",
    "TruthAlignmentRecord",
]
