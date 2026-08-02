"""Internal immutable touch intent produced by one connected Digital Life."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


@dataclass(frozen=True, slots=True)
class DigitalLifeTouchIntent:
    """Runtime-only intent; it is never delivered to the Garden boundary."""

    signal_index: int
    signal_time_us: int
    digital_life_id: str
    role: str
    b: tuple[float, float, float, float]
    tau: float | None
    touch_enabled: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "signal_index",
            _non_negative_int("signal_index", self.signal_index),
        )
        object.__setattr__(
            self,
            "signal_time_us",
            _non_negative_int("signal_time_us", self.signal_time_us),
        )
        object.__setattr__(
            self,
            "digital_life_id",
            _required_string("digital_life_id", self.digital_life_id),
        )
        role = _required_string("role", self.role)
        if role not in {"red", "green", "blue"}:
            raise ValueError("role must be red, green, or blue")
        if not isinstance(self.b, (tuple, list)) or len(self.b) != 4:
            raise ValueError("b must contain exactly four values")
        normalized_b = tuple(
            _unit(f"b[{index}]", value) for index, value in enumerate(self.b)
        )
        if not isinstance(self.touch_enabled, bool):
            raise TypeError("touch_enabled must be boolean")
        tau = None if self.tau is None else _unit("tau", self.tau)
        if self.touch_enabled and tau is None:
            raise ValueError("an enabled touch requires tau")
        if not self.touch_enabled and tau is not None:
            raise ValueError("a disabled touch cannot carry tau")
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "b", normalized_b)
        object.__setattr__(self, "tau", tau)

    @property
    def b_f(self) -> float:
        return self.b[0]

    @property
    def b_a(self) -> float:
        return self.b[1]

    @property
    def b_t(self) -> float:
        return self.b[2]

    @property
    def b_d(self) -> float:
        return self.b[3]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
