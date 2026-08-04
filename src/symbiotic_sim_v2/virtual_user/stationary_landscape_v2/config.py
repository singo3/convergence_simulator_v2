"""Strict Stage 8A.1 stationary axis-mode preference contracts."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION = "stationary_preference_landscape_v0_2"
STATIONARY_AXIS_MODE_PEAK_VERSION = "stationary_axis_mode_peak_v0_1"
MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION = "maximum_weighted_peak_response_v0_1"
STATIONARY_USER_TYPE_PROFILE_V2_SCHEMA_VERSION = "stationary_user_type_profile_v2"

AXIS_MODES = frozenset({"gaussian", "neutral"})
EXPECTED_STRUCTURES = frozenset(
    {
        "life_dominant",
        "bpm_common",
        "life_specific_multi_attractor_equal",
        "life_specific_multi_attractor_weighted",
        "single_life_pattern",
        "no_preference",
    }
)


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_text(name: str, value: object | None) -> str | None:
    return None if value is None else _required_text(name, value)


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _optional_finite(name: str, value: object | None) -> float | None:
    return None if value is None else _finite(name, value)


def _strict_object(encoded: str, *, label: str) -> dict[str, Any]:
    if not isinstance(encoded, str):
        raise TypeError(f"encoded {label} must be a string")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate {label} field: {key}")
            result[key] = value
        return result

    parsed = json.loads(encoded, object_pairs_hook=pairs)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} JSON must contain an object")
    return parsed


def _exact_fields(values: Mapping[str, Any], expected: set[str], *, label: str) -> None:
    actual = set(values)
    if missing := expected - actual:
        raise ValueError(f"missing {label} fields: {', '.join(sorted(missing))}")
    if unknown := actual - expected:
        raise ValueError(f"unknown {label} fields: {', '.join(sorted(unknown))}")


def _axis_values(
    *,
    axis_name: str,
    mode: object,
    preferred: object | None,
    sigma: object | None,
    preferred_minimum: float,
    preferred_maximum: float,
    sigma_maximum: float | None,
) -> tuple[str, float | None, float | None]:
    if not isinstance(mode, str) or mode not in AXIS_MODES:
        raise ValueError(f"{axis_name}_axis_mode must be gaussian or neutral")
    normalized_preferred = _optional_finite(f"preferred_{axis_name}", preferred)
    normalized_sigma = _optional_finite(f"{axis_name}_sigma", sigma)
    if mode == "neutral":
        if normalized_preferred is not None or normalized_sigma is not None:
            raise ValueError(f"neutral {axis_name} axis requires null preferred value and sigma")
        return mode, None, None
    if normalized_preferred is None or normalized_sigma is None:
        raise ValueError(f"gaussian {axis_name} axis requires preferred value and sigma")
    if not preferred_minimum <= normalized_preferred <= preferred_maximum:
        raise ValueError(
            f"preferred_{axis_name} must be between {preferred_minimum} and {preferred_maximum}"
        )
    if normalized_sigma <= 0.0:
        raise ValueError(f"{axis_name}_sigma must be positive")
    if sigma_maximum is not None and normalized_sigma > sigma_maximum:
        raise ValueError(f"{axis_name}_sigma must not exceed {sigma_maximum}")
    return mode, normalized_preferred, normalized_sigma


@dataclass(frozen=True, slots=True)
class StationaryPreferencePeakV2:
    """One fixed weighted peak with independently neutral or Gaussian axes."""

    peak_id: str
    hue_axis_mode: str
    preferred_hue_degree: float | None
    hue_sigma_degree: float | None
    bpm_axis_mode: str
    preferred_blink_bpm: float | None
    blink_sigma_bpm: float | None
    peak_weight: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "peak_id", _required_text("peak_id", self.peak_id))
        hue_mode, preferred_hue, hue_sigma = _axis_values(
            axis_name="hue_degree",
            mode=self.hue_axis_mode,
            preferred=self.preferred_hue_degree,
            sigma=self.hue_sigma_degree,
            preferred_minimum=0.0,
            preferred_maximum=360.0,
            sigma_maximum=180.0,
        )
        bpm_mode, preferred_bpm, bpm_sigma = _axis_values(
            axis_name="blink_bpm",
            mode=self.bpm_axis_mode,
            preferred=self.preferred_blink_bpm,
            sigma=self.blink_sigma_bpm,
            preferred_minimum=10.0,
            preferred_maximum=165.0,
            sigma_maximum=None,
        )
        weight = _finite("peak_weight", self.peak_weight)
        if not 0.0 <= weight <= 1.0:
            raise ValueError("peak_weight must be between 0 and 1")
        for name, value in {
            "hue_axis_mode": hue_mode,
            "preferred_hue_degree": preferred_hue,
            "hue_sigma_degree": hue_sigma,
            "bpm_axis_mode": bpm_mode,
            "preferred_blink_bpm": preferred_bpm,
            "blink_sigma_bpm": bpm_sigma,
            "peak_weight": weight,
        }.items():
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "peak_id": self.peak_id,
            "hue_axis_mode": self.hue_axis_mode,
            "preferred_hue_degree": self.preferred_hue_degree,
            "hue_sigma_degree": self.hue_sigma_degree,
            "bpm_axis_mode": self.bpm_axis_mode,
            "preferred_blink_bpm": self.preferred_blink_bpm,
            "blink_sigma_bpm": self.blink_sigma_bpm,
            "peak_weight": self.peak_weight,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> StationaryPreferencePeakV2:
        if not isinstance(values, Mapping):
            raise TypeError("peak values must be a mapping")
        _exact_fields(values, set(cls.__dataclass_fields__), label="peak")
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> StationaryPreferencePeakV2:
        return cls.from_dict(_strict_object(encoded, label="peak"))


@dataclass(frozen=True, slots=True)
class StationaryUserTypeProfileV2:
    """One immutable Stage 8A.1 user landscape and simulation-only expectations."""

    user_type_id: str
    display_name_ja: str
    description_ja: str
    peaks: tuple[StationaryPreferencePeakV2, ...]
    maximum_respiratory_amplitude_gain_ms: float
    maximum_mean_rri_increase_ms: float
    onset_time_constant_seconds: float
    recovery_time_constant_seconds: float
    expected_structure: str
    expected_dominant_life_id: str | None
    expected_attractor_count: int | None
    landscape_version: str = STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION
    peak_model_version: str = STATIONARY_AXIS_MODE_PEAK_VERSION
    multi_peak_combination_version: str = MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION
    schema_version: str = STATIONARY_USER_TYPE_PROFILE_V2_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("user_type_id", "display_name_ja", "description_ja"):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        if isinstance(self.peaks, (str, bytes)) or not isinstance(self.peaks, Sequence):
            raise TypeError("peaks must be a sequence")
        peaks = tuple(self.peaks)
        if any(not isinstance(peak, StationaryPreferencePeakV2) for peak in peaks):
            raise TypeError("peaks must contain StationaryPreferencePeakV2 values")
        if len({peak.peak_id for peak in peaks}) != len(peaks):
            raise ValueError("peak IDs must be unique within one user type")
        object.__setattr__(self, "peaks", peaks)
        for name, expected in {
            "landscape_version": STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION,
            "peak_model_version": STATIONARY_AXIS_MODE_PEAK_VERSION,
            "multi_peak_combination_version": MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION,
            "schema_version": STATIONARY_USER_TYPE_PROFILE_V2_SCHEMA_VERSION,
        }.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")
        if self.expected_structure not in EXPECTED_STRUCTURES:
            raise ValueError("expected_structure is not recognized")
        dominant = _optional_text(
            "expected_dominant_life_id",
            self.expected_dominant_life_id,
        )
        object.__setattr__(self, "expected_dominant_life_id", dominant)
        attractor_count = self.expected_attractor_count
        if attractor_count is not None:
            if isinstance(attractor_count, bool) or not isinstance(attractor_count, int):
                raise TypeError("expected_attractor_count must be an integer or null")
            if attractor_count <= 0:
                raise ValueError("expected_attractor_count must be positive")
        for name in (
            "maximum_respiratory_amplitude_gain_ms",
            "maximum_mean_rri_increase_ms",
        ):
            value = _finite(name, getattr(self, name))
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)
        for name in ("onset_time_constant_seconds", "recovery_time_constant_seconds"):
            value = _finite(name, getattr(self, name))
            if value <= 0.0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        if self.expected_structure == "no_preference":
            if peaks:
                raise ValueError("no_preference profile must have no peaks")
            if any(
                value != 0.0
                for value in (
                    self.maximum_respiratory_amplitude_gain_ms,
                    self.maximum_mean_rri_increase_ms,
                )
            ):
                raise ValueError("no_preference profile must have zero physiology gains")
        elif not peaks:
            raise ValueError("a responsive profile requires at least one peak")

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_type_id": self.user_type_id,
            "display_name_ja": self.display_name_ja,
            "description_ja": self.description_ja,
            "peaks": [peak.to_dict() for peak in self.peaks],
            "maximum_respiratory_amplitude_gain_ms": (self.maximum_respiratory_amplitude_gain_ms),
            "maximum_mean_rri_increase_ms": self.maximum_mean_rri_increase_ms,
            "onset_time_constant_seconds": self.onset_time_constant_seconds,
            "recovery_time_constant_seconds": self.recovery_time_constant_seconds,
            "expected_structure": self.expected_structure,
            "expected_dominant_life_id": self.expected_dominant_life_id,
            "expected_attractor_count": self.expected_attractor_count,
            "landscape_version": self.landscape_version,
            "peak_model_version": self.peak_model_version,
            "multi_peak_combination_version": self.multi_peak_combination_version,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> StationaryUserTypeProfileV2:
        if not isinstance(values, Mapping):
            raise TypeError("user type values must be a mapping")
        _exact_fields(values, set(cls.__dataclass_fields__), label="user type")
        normalized = dict(values)
        raw_peaks = normalized["peaks"]
        if isinstance(raw_peaks, (str, bytes)) or not isinstance(raw_peaks, Sequence):
            raise TypeError("peaks must be a sequence")
        normalized["peaks"] = tuple(
            StationaryPreferencePeakV2.from_dict(value) for value in raw_peaks
        )
        return cls(**normalized)

    @classmethod
    def from_json(cls, encoded: str) -> StationaryUserTypeProfileV2:
        return cls.from_dict(_strict_object(encoded, label="user type"))


__all__ = [
    "AXIS_MODES",
    "EXPECTED_STRUCTURES",
    "MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION",
    "STATIONARY_AXIS_MODE_PEAK_VERSION",
    "STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION",
    "STATIONARY_USER_TYPE_PROFILE_V2_SCHEMA_VERSION",
    "StationaryPreferencePeakV2",
    "StationaryUserTypeProfileV2",
]

STATIONARY_PREFERENCE_LANDSCAPE_VERSION = STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION
STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION = STATIONARY_USER_TYPE_PROFILE_V2_SCHEMA_VERSION
__all__.extend(
    [
        "STATIONARY_PREFERENCE_LANDSCAPE_VERSION",
        "STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION",
    ]
)
