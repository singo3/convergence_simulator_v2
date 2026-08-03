"""Strict Stage 8A rolling-convergence diagnostic configuration."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

ROLLING_PATTERN_CONVERGENCE_CONFIG_SCHEMA_VERSION = (
    "rolling_pattern_convergence_config_v1"
)
ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION = (
    "rolling_majority_pattern_convergence_v0_1"
)
MAXIMUM_BOUNDED_WINDOW_SESSIONS = 12


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _strict_object(encoded: str) -> dict[str, Any]:
    if not isinstance(encoded, str):
        raise TypeError("encoded convergence config must be a string")

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate convergence config field: {key}")
            result[key] = value
        return result

    parsed = json.loads(encoded, object_pairs_hook=pairs)
    if not isinstance(parsed, dict):
        raise ValueError("convergence config JSON must contain an object")
    return parsed


@dataclass(frozen=True, slots=True)
class RollingConvergenceConfig:
    evaluator_version: str = ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION
    schema_version: str = ROLLING_PATTERN_CONVERGENCE_CONFIG_SCHEMA_VERSION
    window_sessions: int = 4
    required_sessions: int = 3
    hue_tolerance_degree: float = 2.0
    blink_bpm_tolerance: float = 20.0
    truth_response_gap_threshold: float = 0.05
    use_valid_sessions_only: bool = True
    continue_after_convergence: bool = True
    maximum_sessions: int = 24

    def __post_init__(self) -> None:
        versions = {
            "evaluator_version": ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION,
            "schema_version": ROLLING_PATTERN_CONVERGENCE_CONFIG_SCHEMA_VERSION,
        }
        for name, expected in versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")
        window = _positive_integer("window_sessions", self.window_sessions)
        required = _positive_integer("required_sessions", self.required_sessions)
        maximum = _positive_integer("maximum_sessions", self.maximum_sessions)
        if window < 2:
            raise ValueError("window_sessions must be at least 2")
        if window > MAXIMUM_BOUNDED_WINDOW_SESSIONS:
            raise ValueError(
                f"window_sessions must not exceed {MAXIMUM_BOUNDED_WINDOW_SESSIONS}"
            )
        if required < 2:
            raise ValueError("required_sessions must be at least 2")
        if required > window:
            raise ValueError("required_sessions must not exceed window_sessions")
        if maximum < window:
            raise ValueError("maximum_sessions must be at least window_sessions")
        object.__setattr__(self, "window_sessions", window)
        object.__setattr__(self, "required_sessions", required)
        object.__setattr__(self, "maximum_sessions", maximum)

        hue = _finite("hue_tolerance_degree", self.hue_tolerance_degree)
        bpm = _finite("blink_bpm_tolerance", self.blink_bpm_tolerance)
        gap = _finite(
            "truth_response_gap_threshold",
            self.truth_response_gap_threshold,
        )
        if not 0.0 < hue <= 180.0:
            raise ValueError("hue_tolerance_degree must be positive and at most 180")
        if bpm <= 0.0:
            raise ValueError("blink_bpm_tolerance must be positive")
        if not 0.0 <= gap <= 1.0:
            raise ValueError("truth_response_gap_threshold must be between 0 and 1")
        object.__setattr__(self, "hue_tolerance_degree", hue)
        object.__setattr__(self, "blink_bpm_tolerance", bpm)
        object.__setattr__(self, "truth_response_gap_threshold", gap)
        for name in ("use_valid_sessions_only", "continue_after_convergence"):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be boolean")
            if not value:
                raise ValueError(f"{name} is fixed to true in Stage 8A")

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
    def from_dict(cls, values: Mapping[str, Any]) -> RollingConvergenceConfig:
        if not isinstance(values, Mapping):
            raise TypeError("convergence config values must be a mapping")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(
                f"missing convergence config fields: {', '.join(sorted(missing))}"
            )
        if unknown := actual - expected:
            raise ValueError(
                f"unknown convergence config fields: {', '.join(sorted(unknown))}"
            )
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> RollingConvergenceConfig:
        return cls.from_dict(_strict_object(encoded))


__all__ = [
    "MAXIMUM_BOUNDED_WINDOW_SESSIONS",
    "ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION",
    "ROLLING_PATTERN_CONVERGENCE_CONFIG_SCHEMA_VERSION",
    "RollingConvergenceConfig",
]
