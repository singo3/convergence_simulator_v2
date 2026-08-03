"""Strict immutable contracts for Stage 8A stationary user landscapes."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

STATIONARY_PREFERENCE_LANDSCAPE_VERSION = "stationary_preference_landscape_v0_1"
STATIONARY_GAUSSIAN_PEAK_VERSION = "stationary_gaussian_peak_v0_1"
MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION = "maximum_weighted_peak_response_v0_1"
STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION = "stationary_user_type_profile_v1"


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _bounded(name: str, value: object, minimum: float, maximum: float) -> float:
    converted = _finite_number(name, value)
    if not minimum <= converted <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return converted


def _strict_json_object(encoded: str, *, label: str) -> dict[str, Any]:
    if not isinstance(encoded, str):
        raise TypeError(f"encoded {label} must be a string")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate {label} field: {key}")
            result[key] = value
        return result

    values = json.loads(encoded, object_pairs_hook=object_pairs)
    if not isinstance(values, dict):
        raise ValueError(f"{label} JSON must contain an object")
    return values


def _require_exact_fields(
    values: Mapping[str, Any],
    expected_fields: set[str],
    *,
    label: str,
) -> None:
    actual_fields = set(values)
    if missing := expected_fields - actual_fields:
        raise ValueError(f"missing {label} fields: {', '.join(sorted(missing))}")
    if unknown := actual_fields - expected_fields:
        raise ValueError(f"unknown {label} fields: {', '.join(sorted(unknown))}")


@dataclass(frozen=True, slots=True)
class StationaryPreferencePeak:
    """One fixed weighted Gaussian peak in circular-Hue/BPM space."""

    peak_id: str
    preferred_hue_degree: float
    hue_sigma_degree: float
    preferred_blink_bpm: float
    blink_sigma_bpm: float
    peak_weight: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "peak_id", _required_string("peak_id", self.peak_id))
        object.__setattr__(
            self,
            "preferred_hue_degree",
            _bounded("preferred_hue_degree", self.preferred_hue_degree, 0.0, 360.0),
        )
        hue_sigma = _bounded("hue_sigma_degree", self.hue_sigma_degree, 0.0, 180.0)
        if hue_sigma <= 0.0:
            raise ValueError("hue_sigma_degree must be positive")
        object.__setattr__(self, "hue_sigma_degree", hue_sigma)
        object.__setattr__(
            self,
            "preferred_blink_bpm",
            _bounded("preferred_blink_bpm", self.preferred_blink_bpm, 10.0, 165.0),
        )
        blink_sigma = _finite_number("blink_sigma_bpm", self.blink_sigma_bpm)
        if blink_sigma <= 0.0:
            raise ValueError("blink_sigma_bpm must be positive")
        object.__setattr__(self, "blink_sigma_bpm", blink_sigma)
        object.__setattr__(
            self,
            "peak_weight",
            _bounded("peak_weight", self.peak_weight, 0.0, 1.0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "peak_id": self.peak_id,
            "preferred_hue_degree": self.preferred_hue_degree,
            "hue_sigma_degree": self.hue_sigma_degree,
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
    def from_dict(cls, values: Mapping[str, Any]) -> StationaryPreferencePeak:
        if not isinstance(values, Mapping):
            raise TypeError("peak values must be a mapping")
        _require_exact_fields(
            values,
            set(cls.__dataclass_fields__),
            label="peak",
        )
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> StationaryPreferencePeak:
        return cls.from_dict(_strict_json_object(encoded, label="peak"))


@dataclass(frozen=True, slots=True)
class StationaryUserTypeProfile:
    """One immutable multi-session user type and its physiology coupling."""

    user_type_id: str
    display_name_ja: str
    description_ja: str
    peaks: tuple[StationaryPreferencePeak, ...]
    maximum_respiratory_amplitude_gain_ms: float
    maximum_mean_rri_increase_ms: float
    onset_time_constant_seconds: float
    recovery_time_constant_seconds: float
    landscape_version: str = STATIONARY_PREFERENCE_LANDSCAPE_VERSION
    peak_model_version: str = STATIONARY_GAUSSIAN_PEAK_VERSION
    multi_peak_combination_version: str = MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION
    schema_version: str = STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("user_type_id", "display_name_ja", "description_ja"):
            object.__setattr__(self, name, _required_string(name, getattr(self, name)))
        if isinstance(self.peaks, (str, bytes)) or not isinstance(self.peaks, Sequence):
            raise TypeError("peaks must be a sequence")
        peaks = tuple(self.peaks)
        if any(not isinstance(peak, StationaryPreferencePeak) for peak in peaks):
            raise TypeError("peaks must contain StationaryPreferencePeak values")
        peak_ids = tuple(peak.peak_id for peak in peaks)
        if len(set(peak_ids)) != len(peak_ids):
            raise ValueError("peak IDs must be unique within one user type")
        object.__setattr__(self, "peaks", peaks)

        versions = {
            "landscape_version": STATIONARY_PREFERENCE_LANDSCAPE_VERSION,
            "peak_model_version": STATIONARY_GAUSSIAN_PEAK_VERSION,
            "multi_peak_combination_version": MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION,
            "schema_version": STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION,
        }
        for name, expected in versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")
        for name in (
            "maximum_respiratory_amplitude_gain_ms",
            "maximum_mean_rri_increase_ms",
        ):
            value = _finite_number(name, getattr(self, name))
            if value < 0.0:
                raise ValueError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)
        for name in (
            "onset_time_constant_seconds",
            "recovery_time_constant_seconds",
        ):
            value = _finite_number(name, getattr(self, name))
            if value <= 0.0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_type_id": self.user_type_id,
            "display_name_ja": self.display_name_ja,
            "description_ja": self.description_ja,
            "peaks": [peak.to_dict() for peak in self.peaks],
            "maximum_respiratory_amplitude_gain_ms": (
                self.maximum_respiratory_amplitude_gain_ms
            ),
            "maximum_mean_rri_increase_ms": self.maximum_mean_rri_increase_ms,
            "onset_time_constant_seconds": self.onset_time_constant_seconds,
            "recovery_time_constant_seconds": self.recovery_time_constant_seconds,
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
    def from_dict(cls, values: Mapping[str, Any]) -> StationaryUserTypeProfile:
        if not isinstance(values, Mapping):
            raise TypeError("user type values must be a mapping")
        _require_exact_fields(
            values,
            set(cls.__dataclass_fields__),
            label="user type",
        )
        normalized = dict(values)
        raw_peaks = normalized["peaks"]
        if isinstance(raw_peaks, (str, bytes)) or not isinstance(raw_peaks, Sequence):
            raise TypeError("peaks must be a sequence")
        normalized["peaks"] = tuple(
            StationaryPreferencePeak.from_dict(value) for value in raw_peaks
        )
        return cls(**normalized)

    @classmethod
    def from_json(cls, encoded: str) -> StationaryUserTypeProfile:
        return cls.from_dict(_strict_json_object(encoded, label="user type"))


__all__ = [
    "MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION",
    "STATIONARY_GAUSSIAN_PEAK_VERSION",
    "STATIONARY_PREFERENCE_LANDSCAPE_VERSION",
    "STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION",
    "StationaryPreferencePeak",
    "StationaryUserTypeProfile",
]
