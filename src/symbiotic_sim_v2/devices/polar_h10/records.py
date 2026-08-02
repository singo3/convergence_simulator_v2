"""Immutable raw measurement records observed by the ideal H10 device."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


def _require_nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class RriMeasurementRecord:
    """One device-visible heartbeat interval and its formal event identity."""

    measurement_index: int
    event_id: str
    device_id: str
    user_id: str
    previous_beat_index: int
    current_beat_index: int
    previous_heartbeat_time_us: int
    current_heartbeat_time_us: int
    rri_us: int
    rri_ms: float
    event_schema_version: str

    def __post_init__(self) -> None:
        for name in (
            "measurement_index",
            "previous_beat_index",
            "current_beat_index",
            "previous_heartbeat_time_us",
            "current_heartbeat_time_us",
            "rri_us",
        ):
            _require_nonnegative_int(name, getattr(self, name))
        for name in ("event_id", "device_id", "user_id", "event_schema_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.current_beat_index <= self.previous_beat_index:
            raise ValueError("current_beat_index must be greater than previous_beat_index")
        if self.current_heartbeat_time_us <= self.previous_heartbeat_time_us:
            raise ValueError("heartbeat times must be strictly increasing")
        if self.rri_us <= 0:
            raise ValueError("rri_us must be positive")
        if self.rri_us != self.current_heartbeat_time_us - self.previous_heartbeat_time_us:
            raise ValueError("rri_us must equal the observed heartbeat timestamp difference")
        expected_ms = self.rri_us / 1_000.0
        if isinstance(self.rri_ms, bool) or not isinstance(self.rri_ms, (int, float)):
            raise TypeError("rri_ms must be a number")
        if not math.isfinite(float(self.rri_ms)) or float(self.rri_ms) != expected_ms:
            raise ValueError("rri_ms must equal rri_us / 1000")
        object.__setattr__(self, "rri_ms", expected_ms)

    @property
    def event_time_us(self) -> int:
        """Return the formal output time, equal to the current heartbeat time."""

        return self.current_heartbeat_time_us

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-serializable record mapping."""

        return asdict(self)
