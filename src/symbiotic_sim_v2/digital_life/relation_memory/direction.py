"""Deterministic F/T-only Stage 5C search direction."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.digital_life.hash01 import hash01

from .config import (
    DIRECTION_FALLBACK_POLICY_VERSION,
    DIRECTION_NEAR_ZERO_NORM_THRESHOLD,
)


def _required_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("digital_life_id must be a non-empty string")
    return value


def _counter(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class RelationMemorySearchDirection:
    digital_life_id: str
    trial_index_used: int
    u_f: float
    u_t: float
    norm: float
    xi: tuple[float, float, float, float]
    fallback_used: bool
    fallback_policy_version: str = DIRECTION_FALLBACK_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "digital_life_id", _required_id(self.digital_life_id))
        object.__setattr__(
            self,
            "trial_index_used",
            _counter("trial_index_used", self.trial_index_used),
        )
        for name in ("u_f", "u_t", "norm"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")
            converted = float(value)
            if not math.isfinite(converted):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, converted)
        if not isinstance(self.fallback_used, bool):
            raise TypeError("fallback_used must be boolean")
        if self.fallback_policy_version != DIRECTION_FALLBACK_POLICY_VERSION:
            raise ValueError(
                "fallback_policy_version must be "
                f"{DIRECTION_FALLBACK_POLICY_VERSION}"
            )
        expected_norm = math.hypot(self.u_f, self.u_t)
        if self.norm != expected_norm:
            raise ValueError("norm must equal hypot(u_f, u_t)")
        if not isinstance(self.xi, tuple) or len(self.xi) != 4:
            raise ValueError("xi must be an immutable four-element tuple")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in self.xi
        ):
            raise ValueError("xi values must be finite numbers")
        expected_fallback = self.norm <= DIRECTION_NEAR_ZERO_NORM_THRESHOLD
        if self.fallback_used != expected_fallback:
            raise ValueError("fallback flag does not match the norm threshold")
        expected_xi = (
            (1.0, 0.0, 0.0, 0.0)
            if self.fallback_used
            else (self.u_f / self.norm, 0.0, self.u_t / self.norm, 0.0)
        )
        if self.xi != expected_xi:
            raise ValueError("xi does not match the normalized F/T direction")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def derive_search_direction(
    digital_life_id: object,
    trial_index_used: object,
) -> RelationMemorySearchDirection:
    """Use the pre-increment trial index and exact normative Hash01 keys."""

    life_id = _required_id(digital_life_id)
    trial_index = _counter("trial_index_used", trial_index_used)
    u_f = 2.0 * hash01(life_id, "C", "direction", trial_index, "F") - 1.0
    u_t = 2.0 * hash01(life_id, "C", "direction", trial_index, "T") - 1.0
    norm = math.hypot(u_f, u_t)
    fallback = norm <= DIRECTION_NEAR_ZERO_NORM_THRESHOLD
    xi = (
        (1.0, 0.0, 0.0, 0.0)
        if fallback
        else (u_f / norm, 0.0, u_t / norm, 0.0)
    )
    return RelationMemorySearchDirection(
        digital_life_id=life_id,
        trial_index_used=trial_index,
        u_f=u_f,
        u_t=u_t,
        norm=norm,
        xi=xi,
        fallback_used=fallback,
    )


__all__ = ["RelationMemorySearchDirection", "derive_search_direction"]
