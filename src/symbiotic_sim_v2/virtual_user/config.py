"""Immutable and JSON-round-trippable Stage 2 virtual-user configuration."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any

VIRTUAL_USER_MODEL_VERSION = "baseline_virtual_user_physiology_v0_1"
MAX_ROOT_SEED = 2**31 - 1


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _bounded(name: str, value: object, minimum: float, maximum: float) -> float:
    converted = _finite_number(name, value)
    if not minimum <= converted <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return converted


@dataclass(frozen=True, slots=True)
class VirtualUserConfig:
    """Validated parameters for the uncalibrated Stage 2 physiology assumption."""

    user_id: str = "virtual-user-001"
    duration_seconds: int = 180
    mean_heart_rate_bpm: float = 70.0
    respiratory_rate_bpm: float = 12.0
    respiratory_amplitude_ms: float = 35.0
    slow_wave_frequency_hz: float = 0.10
    slow_wave_amplitude_ms: float = 10.0
    correlated_variability_sd_ms: float = 8.0
    correlated_variability_persistence: float = 0.85
    beat_jitter_sd_ms: float = 2.0
    min_rri_ms: float = 300.0
    max_rri_ms: float = 2000.0
    root_seed: int = 20260802
    model_version: str = VIRTUAL_USER_MODEL_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        if isinstance(self.duration_seconds, bool) or not isinstance(self.duration_seconds, int):
            raise TypeError("duration_seconds must be an integer")
        if not 10 <= self.duration_seconds <= 3600:
            raise ValueError("duration_seconds must be between 10 and 3600")
        if isinstance(self.root_seed, bool) or not isinstance(self.root_seed, int):
            raise TypeError("root_seed must be an integer")
        if not 0 <= self.root_seed <= MAX_ROOT_SEED:
            raise ValueError(f"root_seed must be between 0 and {MAX_ROOT_SEED}")
        if self.model_version != VIRTUAL_USER_MODEL_VERSION:
            raise ValueError(f"model_version must be {VIRTUAL_USER_MODEL_VERSION}")

        ranges = {
            "mean_heart_rate_bpm": (30.0, 200.0),
            "respiratory_rate_bpm": (3.0, 40.0),
            "respiratory_amplitude_ms": (0.0, 200.0),
            "slow_wave_frequency_hz": (0.01, 0.20),
            "slow_wave_amplitude_ms": (0.0, 100.0),
            "correlated_variability_sd_ms": (0.0, 100.0),
            "beat_jitter_sd_ms": (0.0, 50.0),
            "min_rri_ms": (250.0, 2999.999999),
            "max_rri_ms": (250.0, 3000.0),
        }
        for name, (minimum, maximum) in ranges.items():
            object.__setattr__(self, name, _bounded(name, getattr(self, name), minimum, maximum))

        persistence = _finite_number(
            "correlated_variability_persistence",
            self.correlated_variability_persistence,
        )
        if not 0.0 <= persistence < 1.0:
            raise ValueError("correlated_variability_persistence must be >= 0 and < 1")
        object.__setattr__(self, "correlated_variability_persistence", persistence)
        if self.max_rri_ms <= self.min_rri_ms:
            raise ValueError("max_rri_ms must be greater than min_rri_ms")

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-serializable configuration mapping."""

        return asdict(self)

    def to_json(self) -> str:
        """Serialize with stable keys for logs and reproducible fixtures."""

        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> VirtualUserConfig:
        """Validate and construct a configuration from a JSON-like mapping."""

        if not isinstance(values, dict):
            raise TypeError("config values must be a dictionary")
        return cls(**values)

    @classmethod
    def from_json(cls, encoded: str) -> VirtualUserConfig:
        """Deserialize and validate a configuration JSON document."""

        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("config JSON must contain an object")
        return cls.from_dict(values)
