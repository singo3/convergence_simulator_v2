"""Strict immutable Stage 5C persistent-state contract."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .config import ALGORITHM_VERSION, PROFILE_VERSION, STATE_SCHEMA_VERSION


def _required_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("digital_life_id must be a non-empty string")
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


def _unit_vector(name: str, values: object) -> tuple[float, float, float, float]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be a four-element sequence")
    if len(values) != 4:
        raise ValueError(f"{name} must contain four values")
    return tuple(
        _unit(f"{name}[{index}]", value) for index, value in enumerate(values)
    )  # type: ignore[return-value]


def _counter(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _strict_json_object(encoded: str) -> dict[str, Any]:
    if not isinstance(encoded, str):
        raise TypeError("encoded state must be a string")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate state field: {key}")
            result[key] = value
        return result

    values = json.loads(encoded, object_pairs_hook=object_pairs)
    if not isinstance(values, dict):
        raise ValueError("persistent state JSON must contain an object")
    return values


@dataclass(frozen=True, slots=True)
class RelationMemoryPersistentState:
    """State retained across sessions; q/E scopes remain explicitly distinct."""

    digital_life_id: str
    k_anchor: tuple[float, float, float, float]
    q: float
    e: float
    trial_count: int
    session_count: int
    profile_version: str
    algorithm_version: str
    state_schema_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "digital_life_id", _required_id(self.digital_life_id))
        object.__setattr__(self, "k_anchor", _unit_vector("k_anchor", self.k_anchor))
        object.__setattr__(self, "q", _unit("q", self.q))
        object.__setattr__(self, "e", _unit("e", self.e))
        object.__setattr__(
            self,
            "trial_count",
            _counter("trial_count", self.trial_count),
        )
        object.__setattr__(
            self,
            "session_count",
            _counter("session_count", self.session_count),
        )
        versions = {
            "profile_version": PROFILE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
        }
        for name, expected in versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")

    @classmethod
    def fresh(cls, digital_life_id: object) -> RelationMemoryPersistentState:
        return cls(
            digital_life_id=_required_id(digital_life_id),
            k_anchor=(0.5, 0.5, 0.5, 0.5),
            q=0.5,
            e=0.0,
            trial_count=0,
            session_count=0,
            profile_version=PROFILE_VERSION,
            algorithm_version=ALGORITHM_VERSION,
            state_schema_version=STATE_SCHEMA_VERSION,
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
    def from_dict(
        cls,
        values: Mapping[str, Any],
        *,
        expected_digital_life_id: str | None = None,
    ) -> RelationMemoryPersistentState:
        if not isinstance(values, Mapping):
            raise TypeError("persistent state values must be a mapping")
        expected_fields = set(cls.__dataclass_fields__)
        actual_fields = set(values)
        if missing := expected_fields - actual_fields:
            raise ValueError(
                f"missing persistent state fields: {', '.join(sorted(missing))}"
            )
        if unknown := actual_fields - expected_fields:
            raise ValueError(
                f"unknown persistent state fields: {', '.join(sorted(unknown))}"
            )
        state = cls(**dict(values))
        if (
            expected_digital_life_id is not None
            and state.digital_life_id != _required_id(expected_digital_life_id)
        ):
            raise ValueError("persistent state digital_life_id does not match")
        return state

    @classmethod
    def from_json(
        cls,
        encoded: str,
        *,
        expected_digital_life_id: str | None = None,
    ) -> RelationMemoryPersistentState:
        return cls.from_dict(
            _strict_json_object(encoded),
            expected_digital_life_id=expected_digital_life_id,
        )


__all__ = ["RelationMemoryPersistentState"]
