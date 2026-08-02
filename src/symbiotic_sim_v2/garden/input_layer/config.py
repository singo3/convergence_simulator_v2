"""Immutable Stage 4 Garden input-layer reference configuration."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any

GARDEN_MANIFEST_VERSION = "relax_with_light_garden_manifest_v0_1"
GARDEN_INPUT_MODEL_VERSION = "relax_with_light_garden_input_v0_1"
GARDEN_INPUT_SIGNAL_SCHEMA_VERSION = "garden_input_signal_event_v1"
GARDEN_EVALUATION_SCHEMA_VERSION = "garden_evaluation_finalized_event_v1"
GARDEN_PHASE_SCHEMA_VERSION = "garden_phase_event_v1"
RRI_WINDOW_MEMBERSHIP_POLICY = "measurement_end_time"
BASELINE_INVALID_POLICY = "keep_s_zero_and_skip_main_evaluations"
RRI_INPUT_SCHEMA_VERSION = "rri_measurement_event_v1"


def _require_int(name: str, value: object, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _require_finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


@dataclass(frozen=True, slots=True)
class GardenInputConfig:
    """The exact Relax with Light Stage 4 input-layer contract."""

    garden_id: str = "relax-with-light"
    garden_manifest_version: str = GARDEN_MANIFEST_VERSION
    model_version: str = GARDEN_INPUT_MODEL_VERSION
    signal_interval_us: int = 1_000_000
    baseline_discard_seconds: int = 30
    baseline_evaluation_seconds: int = 30
    main_session_seconds: int = 180
    bundle_count: int = 3
    bundle_discard_seconds: int = 30
    bundle_evaluation_seconds: int = 30
    rri_min_us: int = 300_000
    rri_max_us: int = 2_000_000
    median_history_min_valid_count: int = 5
    median_history_max_valid_count: int = 15
    median_relative_deviation_limit: float = 0.20
    low_confidence_artifact_rate: float = 0.05
    reject_artifact_rate: float = 0.10
    minimum_valid_rri_count: int = 5
    rmssd_min_ms: float = 15.0
    rmssd_max_ms: float = 80.0
    rri_window_membership_policy: str = RRI_WINDOW_MEMBERSHIP_POLICY
    baseline_invalid_policy: str = BASELINE_INVALID_POLICY
    signal_schema_version: str = GARDEN_INPUT_SIGNAL_SCHEMA_VERSION
    evaluation_schema_version: str = GARDEN_EVALUATION_SCHEMA_VERSION
    phase_schema_version: str = GARDEN_PHASE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "garden_id",
            "garden_manifest_version",
            "model_version",
            "rri_window_membership_policy",
            "baseline_invalid_policy",
            "signal_schema_version",
            "evaluation_schema_version",
            "phase_schema_version",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

        exact_versions = {
            "garden_manifest_version": GARDEN_MANIFEST_VERSION,
            "model_version": GARDEN_INPUT_MODEL_VERSION,
            "rri_window_membership_policy": RRI_WINDOW_MEMBERSHIP_POLICY,
            "baseline_invalid_policy": BASELINE_INVALID_POLICY,
            "signal_schema_version": GARDEN_INPUT_SIGNAL_SCHEMA_VERSION,
            "evaluation_schema_version": GARDEN_EVALUATION_SCHEMA_VERSION,
            "phase_schema_version": GARDEN_PHASE_SCHEMA_VERSION,
        }
        for name, expected in exact_versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")

        for name in (
            "signal_interval_us",
            "baseline_discard_seconds",
            "baseline_evaluation_seconds",
            "main_session_seconds",
            "bundle_count",
            "bundle_discard_seconds",
            "bundle_evaluation_seconds",
            "rri_min_us",
            "rri_max_us",
            "median_history_min_valid_count",
            "median_history_max_valid_count",
            "minimum_valid_rri_count",
        ):
            _require_int(name, getattr(self, name), positive=True)

        if self.baseline_discard_seconds + self.baseline_evaluation_seconds != 60:
            raise ValueError("baseline discard and evaluation must total 60 seconds")
        if self.main_session_seconds != 180:
            raise ValueError("main_session_seconds must be 180")
        if self.bundle_count != 3:
            raise ValueError("bundle_count must be 3")
        bundle_seconds = self.bundle_discard_seconds + self.bundle_evaluation_seconds
        if bundle_seconds != 60:
            raise ValueError("one bundle must total 60 seconds")
        if self.main_session_seconds != self.bundle_count * bundle_seconds:
            raise ValueError("main session must equal bundle_count times bundle duration")
        if self.rri_min_us >= self.rri_max_us:
            raise ValueError("rri_min_us must be less than rri_max_us")
        if self.median_history_min_valid_count != 5:
            raise ValueError("median_history_min_valid_count must be 5")
        if self.median_history_max_valid_count != 15:
            raise ValueError("median_history_max_valid_count must be 15")
        if self.median_history_max_valid_count < self.median_history_min_valid_count:
            raise ValueError("median history maximum must be at least its minimum")
        if self.minimum_valid_rri_count != 5:
            raise ValueError("minimum_valid_rri_count must be 5")

        deviation = _require_finite_number(
            "median_relative_deviation_limit", self.median_relative_deviation_limit
        )
        low_rate = _require_finite_number(
            "low_confidence_artifact_rate", self.low_confidence_artifact_rate
        )
        reject_rate = _require_finite_number("reject_artifact_rate", self.reject_artifact_rate)
        rmssd_min = _require_finite_number("rmssd_min_ms", self.rmssd_min_ms)
        rmssd_max = _require_finite_number("rmssd_max_ms", self.rmssd_max_ms)
        if not 0.0 <= deviation <= 1.0:
            raise ValueError("median_relative_deviation_limit must be between 0 and 1")
        if not 0.0 <= low_rate <= 1.0:
            raise ValueError("low_confidence_artifact_rate must be between 0 and 1")
        if not low_rate <= reject_rate <= 1.0:
            raise ValueError("reject_artifact_rate must be between low threshold and 1")
        if rmssd_min >= rmssd_max:
            raise ValueError("rmssd_min_ms must be less than rmssd_max_ms")

        object.__setattr__(self, "median_relative_deviation_limit", deviation)
        object.__setattr__(self, "low_confidence_artifact_rate", low_rate)
        object.__setattr__(self, "reject_artifact_rate", reject_rate)
        object.__setattr__(self, "rmssd_min_ms", rmssd_min)
        object.__setattr__(self, "rmssd_max_ms", rmssd_max)

    @property
    def total_duration_seconds(self) -> int:
        return (
            self.baseline_discard_seconds
            + self.baseline_evaluation_seconds
            + self.main_session_seconds
        )

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
    def from_dict(cls, values: dict[str, Any]) -> GardenInputConfig:
        if not isinstance(values, dict):
            raise TypeError("config values must be a dictionary")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(f"missing config fields: {', '.join(sorted(missing))}")
        if unknown := actual - expected:
            raise ValueError(f"unknown config fields: {', '.join(sorted(unknown))}")
        return cls(**values)

    @classmethod
    def from_json(cls, encoded: str) -> GardenInputConfig:
        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("config JSON must contain an object")
        return cls.from_dict(values)
