"""Immutable configuration for the ideal Stage 3 Polar H10 model."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

POLAR_H10_MODEL_VERSION = "ideal_polar_h10_rri_device_v0_1"
RRI_EVENT_SCHEMA_VERSION = "rri_measurement_event_v1"


@dataclass(frozen=True, slots=True)
class PolarH10Config:
    """Fixed identity and schema contract for one ideal RRI input device."""

    device_id: str = "polar-h10-sim-001"
    expected_user_id: str = "virtual-user-001"
    model_version: str = POLAR_H10_MODEL_VERSION
    event_schema_version: str = RRI_EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("device_id", "expected_user_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.model_version != POLAR_H10_MODEL_VERSION:
            raise ValueError(f"model_version must be {POLAR_H10_MODEL_VERSION}")
        if self.event_schema_version != RRI_EVENT_SCHEMA_VERSION:
            raise ValueError(f"event_schema_version must be {RRI_EVENT_SCHEMA_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-serializable mapping."""

        return asdict(self)

    def to_json(self) -> str:
        """Serialize deterministically for configuration round trips."""

        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> PolarH10Config:
        """Construct only from the exact four-field Stage 3 schema."""

        if not isinstance(values, dict):
            raise TypeError("config values must be a dictionary")
        expected_fields = set(cls.__dataclass_fields__)
        actual_fields = set(values)
        if missing := expected_fields - actual_fields:
            raise ValueError(f"missing config fields: {', '.join(sorted(missing))}")
        if unknown := actual_fields - expected_fields:
            raise ValueError(f"unknown config fields: {', '.join(sorted(unknown))}")
        return cls(**values)

    @classmethod
    def from_json(cls, encoded: str) -> PolarH10Config:
        """Deserialize one exact JSON object without implicit defaults."""

        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("config JSON must contain an object")
        return cls.from_dict(values)
