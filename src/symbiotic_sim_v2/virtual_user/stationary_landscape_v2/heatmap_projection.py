"""Simulation-only immutable projection for the Stage 8A.1 preference map."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .config import StationaryUserTypeProfileV2
from .evaluator import evaluate_stationary_preference_v2

STATIONARY_PREFERENCE_HEATMAP_SCHEMA_VERSION = (
    "stationary_preference_heatmap_projection_v1"
)
DEFAULT_HUE_GRID_STEP_DEGREE = 1.0
DEFAULT_BPM_GRID_STEP = 2.5

# These are the standard Digital Life fixture's output-capable F ranges after
# the formal Stage 6 Hue=360F mapping. They are visualization metadata only.
STANDARD_LIFE_HUE_BANDS = (
    ("life-red", 0.0, 10.0),
    ("life-green", 120.0, 130.0),
    ("life-blue", 245.0, 255.0),
)


@dataclass(frozen=True, slots=True)
class StationaryPreferenceHeatmapProjectionV2:
    """Core-computed values consumed read-only by GUI and other diagnostics."""

    user_type_id: str
    hue_values_degree: tuple[float, ...]
    blink_bpm_values: tuple[float, ...]
    preference_match_rows: tuple[tuple[float, ...], ...]
    life_hue_bands: tuple[tuple[str, float, float], ...]
    schema_version: str = STATIONARY_PREFERENCE_HEATMAP_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.user_type_id, str) or not self.user_type_id:
            raise ValueError("user_type_id must be a non-empty string")
        if self.schema_version != STATIONARY_PREFERENCE_HEATMAP_SCHEMA_VERSION:
            raise ValueError(
                "schema_version must be "
                f"{STATIONARY_PREFERENCE_HEATMAP_SCHEMA_VERSION}"
            )
        if len(self.hue_values_degree) < 2 or len(self.blink_bpm_values) < 2:
            raise ValueError("heatmap axes must each contain at least two values")
        _validate_axis(
            "hue_values_degree",
            self.hue_values_degree,
            minimum=0.0,
            maximum=360.0,
        )
        _validate_axis(
            "blink_bpm_values",
            self.blink_bpm_values,
            minimum=10.0,
            maximum=165.0,
        )
        if len(self.preference_match_rows) != len(self.blink_bpm_values):
            raise ValueError("preference rows must match the BPM axis")
        for row in self.preference_match_rows:
            if len(row) != len(self.hue_values_degree):
                raise ValueError("preference columns must match the Hue axis")
            for value in row:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError("preference matches must be numbers")
                if not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                    raise ValueError("preference matches must be finite values in [0, 1]")
        for life_id, lower, upper in self.life_hue_bands:
            if not isinstance(life_id, str) or not life_id:
                raise ValueError("life Hue band IDs must be non-empty strings")
            if not (0.0 <= lower <= upper <= 360.0):
                raise ValueError("life Hue bands must be within [0, 360]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_type_id": self.user_type_id,
            "hue_values_degree": list(self.hue_values_degree),
            "blink_bpm_values": list(self.blink_bpm_values),
            "preference_match_rows": [
                list(row) for row in self.preference_match_rows
            ],
            "life_hue_bands": [list(band) for band in self.life_hue_bands],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> StationaryPreferenceHeatmapProjectionV2:
        if not isinstance(values, dict):
            raise TypeError("heatmap projection must be a dictionary")
        expected = set(cls.__dataclass_fields__)
        if missing := expected - set(values):
            raise ValueError(f"missing heatmap fields: {', '.join(sorted(missing))}")
        if unknown := set(values) - expected:
            raise ValueError(f"unknown heatmap fields: {', '.join(sorted(unknown))}")
        return cls(
            user_type_id=values["user_type_id"],
            hue_values_degree=tuple(values["hue_values_degree"]),
            blink_bpm_values=tuple(values["blink_bpm_values"]),
            preference_match_rows=tuple(
                tuple(row) for row in values["preference_match_rows"]
            ),
            life_hue_bands=tuple(
                (str(band[0]), band[1], band[2])
                for band in values["life_hue_bands"]
            ),
            schema_version=values["schema_version"],
        )


def project_stationary_preference_heatmap_v2(
    profile: StationaryUserTypeProfileV2,
    *,
    hue_step_degree: float = DEFAULT_HUE_GRID_STEP_DEGREE,
    bpm_step: float = DEFAULT_BPM_GRID_STEP,
) -> StationaryPreferenceHeatmapProjectionV2:
    """Evaluate a fixed profile on a deterministic grid outside the GUI layer."""

    if not isinstance(profile, StationaryUserTypeProfileV2):
        raise TypeError("profile must be a StationaryUserTypeProfileV2")
    hue_step = _positive_finite("hue_step_degree", hue_step_degree)
    bpm_grid_step = _positive_finite("bpm_step", bpm_step)
    hue_values = _inclusive_grid(0.0, 360.0, hue_step)
    bpm_values = _inclusive_grid(10.0, 165.0, bpm_grid_step)
    rows = tuple(
        tuple(
            evaluate_stationary_preference_v2(
                profile,
                active=True,
                hue_degree=hue,
                blink_bpm=bpm,
            ).preference_match
            for hue in hue_values
        )
        for bpm in bpm_values
    )
    return StationaryPreferenceHeatmapProjectionV2(
        user_type_id=profile.user_type_id,
        hue_values_degree=hue_values,
        blink_bpm_values=bpm_values,
        preference_match_rows=rows,
        life_hue_bands=STANDARD_LIFE_HUE_BANDS,
    )


def _positive_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return converted


def _inclusive_grid(start: float, stop: float, step: float) -> tuple[float, ...]:
    count = int(math.floor((stop - start) / step))
    values = tuple(start + index * step for index in range(count + 1))
    if math.isclose(values[-1], stop, rel_tol=0.0, abs_tol=1e-12):
        return (*values[:-1], stop)
    return (*values, stop)


def _validate_axis(
    name: str,
    values: tuple[float, ...],
    *,
    minimum: float,
    maximum: float,
) -> None:
    previous: float | None = None
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} values must be numbers")
        converted = float(value)
        if not math.isfinite(converted) or not minimum <= converted <= maximum:
            raise ValueError(f"{name} values must be finite and in range")
        if previous is not None and converted <= previous:
            raise ValueError(f"{name} values must be strictly increasing")
        previous = converted


__all__ = [
    "DEFAULT_BPM_GRID_STEP",
    "DEFAULT_HUE_GRID_STEP_DEGREE",
    "STANDARD_LIFE_HUE_BANDS",
    "STATIONARY_PREFERENCE_HEATMAP_SCHEMA_VERSION",
    "StationaryPreferenceHeatmapProjectionV2",
    "project_stationary_preference_heatmap_v2",
]
