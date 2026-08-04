"""Versioned immutable Stage 8A.1 structured-convergence thresholds."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION = "structured_convergence_diagnostics_v0_1"
STRUCTURED_CONVERGENCE_CONFIG_SCHEMA_VERSION = "structured_convergence_config_v1"
STRUCTURED_CONVERGENCE_CONFIG_VERSION = STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION


def _integer(name: str, value: object, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


@dataclass(frozen=True, slots=True)
class StructuredConvergenceConfig:
    config_version: str = STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION
    schema_version: str = STRUCTURED_CONVERGENCE_CONFIG_SCHEMA_VERSION
    life_window_sessions: int = 8
    life_required_sessions: int = 6
    life_maximum_consecutive_outliers: int = 1
    bpm_window_sessions: int = 8
    bpm_required_sessions: int = 6
    bpm_maximum_range: float = 20.0
    multi_window_sessions: int = 18
    multi_minimum_life_occurrences: int = 3
    multi_minimum_cluster_support: int = 3
    multi_minimum_cluster_fraction: float = 0.70
    multi_maximum_cluster_range: float = 20.0
    multi_minimum_attractor_separation: float = 20.0
    truth_recent_window_sessions: int = 18
    truth_response_gap_threshold: float = 0.05
    truth_peak_hit_radius: float = 1.0
    mechanical_warning_rate_threshold: float = 0.50
    mechanical_warning_minimum_windows: int = 3
    maximum_sessions: int = 100

    def __post_init__(self) -> None:
        if self.config_version != STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION:
            raise ValueError(f"config_version must be {STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION}")
        if self.schema_version != STRUCTURED_CONVERGENCE_CONFIG_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {STRUCTURED_CONVERGENCE_CONFIG_SCHEMA_VERSION}"
            )
        integer_fields = {
            "life_window_sessions": (self.life_window_sessions, 2),
            "life_required_sessions": (self.life_required_sessions, 2),
            "life_maximum_consecutive_outliers": (
                self.life_maximum_consecutive_outliers,
                0,
            ),
            "bpm_window_sessions": (self.bpm_window_sessions, 2),
            "bpm_required_sessions": (self.bpm_required_sessions, 2),
            "multi_window_sessions": (self.multi_window_sessions, 3),
            "multi_minimum_life_occurrences": (
                self.multi_minimum_life_occurrences,
                1,
            ),
            "multi_minimum_cluster_support": (
                self.multi_minimum_cluster_support,
                1,
            ),
            "truth_recent_window_sessions": (self.truth_recent_window_sessions, 1),
            "mechanical_warning_minimum_windows": (
                self.mechanical_warning_minimum_windows,
                1,
            ),
            "maximum_sessions": (self.maximum_sessions, 4),
        }
        for name, (value, minimum) in integer_fields.items():
            object.__setattr__(self, name, _integer(name, value, minimum=minimum))
        if self.maximum_sessions > 100:
            raise ValueError("maximum_sessions must not exceed 100")
        if self.life_required_sessions > self.life_window_sessions:
            raise ValueError("life_required_sessions exceeds its window")
        if self.bpm_required_sessions > self.bpm_window_sessions:
            raise ValueError("bpm_required_sessions exceeds its window")
        if self.multi_minimum_cluster_support > self.multi_minimum_life_occurrences:
            raise ValueError("multi cluster support cannot exceed minimum occurrences")
        positive_fields = (
            "bpm_maximum_range",
            "multi_maximum_cluster_range",
            "multi_minimum_attractor_separation",
            "truth_peak_hit_radius",
        )
        for name in positive_fields:
            value = _finite(name, getattr(self, name))
            if value <= 0.0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        unit_fields = (
            "multi_minimum_cluster_fraction",
            "truth_response_gap_threshold",
            "mechanical_warning_rate_threshold",
        )
        for name in unit_fields:
            value = _finite(name, getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
            object.__setattr__(self, name, value)

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
    def from_dict(cls, values: Mapping[str, Any]) -> StructuredConvergenceConfig:
        if not isinstance(values, Mapping):
            raise TypeError("structured convergence config must be a mapping")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(f"missing config fields: {', '.join(sorted(missing))}")
        if unknown := actual - expected:
            raise ValueError(f"unknown config fields: {', '.join(sorted(unknown))}")
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> StructuredConvergenceConfig:
        if not isinstance(encoded, str):
            raise TypeError("encoded structured convergence config must be a string")

        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in items:
                if key in result:
                    raise ValueError(f"duplicate structured config field: {key}")
                result[key] = value
            return result

        parsed = json.loads(encoded, object_pairs_hook=pairs)
        if not isinstance(parsed, dict):
            raise ValueError("structured convergence config JSON must contain an object")
        return cls.from_dict(parsed)


__all__ = [
    "STRUCTURED_CONVERGENCE_CONFIG_SCHEMA_VERSION",
    "STRUCTURED_CONVERGENCE_CONFIG_VERSION",
    "STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION",
    "StructuredConvergenceConfig",
]
