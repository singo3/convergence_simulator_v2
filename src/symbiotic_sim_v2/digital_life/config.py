"""Immutable Stage 5A configuration and authoritative role presets."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any

DIGITAL_LIFE_MODEL_VERSION = "single_digital_life_first_round_v0_1"
DIGITAL_LIFE_CONFIG_SCHEMA_VERSION = "digital_life_config_v1"
DOCUMENT_VERSION = "v2.0"
PROFILE_VERSION = "symbiotic_signal_loop_reference_v1_0"
ALGORITHM_VERSION = "adaptive_random_search_confirmed_v1"
STATE_SCHEMA_VERSION = "relation_memory_state_v2"

_ROLE_PRESETS: dict[str, tuple[str, float, float]] = {
    "red": ("life-red", 0.0 / 360.0, 10.0 / 360.0),
    "green": ("life-green", 120.0 / 360.0, 130.0 / 360.0),
    "blue": ("life-blue", 245.0 / 360.0, 255.0 / 360.0),
}


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _unit_interval(name: str, value: object) -> float:
    converted = _finite_number(name, value)
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


@dataclass(frozen=True, slots=True)
class DigitalLifeConfig:
    """The exact configuration contract for one first-round Digital Life."""

    digital_life_id: str = "life-green"
    role: str = "green"
    model_version: str = DIGITAL_LIFE_MODEL_VERSION
    config_schema_version: str = DIGITAL_LIFE_CONFIG_SCHEMA_VERSION
    document_version: str = DOCUMENT_VERSION
    profile_version: str = PROFILE_VERSION
    algorithm_version: str = ALGORITHM_VERSION
    state_schema_version: str = STATE_SCHEMA_VERSION
    delta_n: float = 0.10
    epsilon_tau: float = 0.000001
    initial_e: float = 0.0
    initial_q: float = 0.5
    initial_k_anchor: tuple[float, float, float, float] = (0.5, 0.5, 0.5, 0.5)
    f_min: float = 120.0 / 360.0
    f_max: float = 130.0 / 360.0
    a_fixed: float = 0.5
    t_min: float = 0.0
    t_max: float = 1.0
    d_fixed: float = 0.5

    def __post_init__(self) -> None:
        if not isinstance(self.digital_life_id, str) or not self.digital_life_id.strip():
            raise ValueError("digital_life_id must be a non-empty string")
        if self.role not in _ROLE_PRESETS:
            raise ValueError("role must be red, green, or blue")

        exact_versions = {
            "model_version": DIGITAL_LIFE_MODEL_VERSION,
            "config_schema_version": DIGITAL_LIFE_CONFIG_SCHEMA_VERSION,
            "document_version": DOCUMENT_VERSION,
            "profile_version": PROFILE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
        }
        for name, expected in exact_versions.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")

        delta_n = _finite_number("delta_n", self.delta_n)
        epsilon_tau = _finite_number("epsilon_tau", self.epsilon_tau)
        if delta_n <= 0.0:
            raise ValueError("delta_n must be positive")
        if epsilon_tau <= 0.0:
            raise ValueError("epsilon_tau must be positive")

        initial_e = _unit_interval("initial_e", self.initial_e)
        initial_q = _unit_interval("initial_q", self.initial_q)
        if not isinstance(self.initial_k_anchor, (tuple, list)):
            raise TypeError("initial_k_anchor must be a four-element sequence")
        if len(self.initial_k_anchor) != 4:
            raise ValueError("initial_k_anchor must contain four values")
        initial_k_anchor = tuple(
            _unit_interval(f"initial_k_anchor[{index}]", value)
            for index, value in enumerate(self.initial_k_anchor)
        )

        f_min = _unit_interval("f_min", self.f_min)
        f_max = _unit_interval("f_max", self.f_max)
        a_fixed = _unit_interval("a_fixed", self.a_fixed)
        t_min = _unit_interval("t_min", self.t_min)
        t_max = _unit_interval("t_max", self.t_max)
        d_fixed = _unit_interval("d_fixed", self.d_fixed)
        if f_min >= f_max:
            raise ValueError("f_min must be less than f_max")
        if t_min >= t_max:
            raise ValueError("t_min must be less than t_max")
        _, expected_f_min, expected_f_max = _ROLE_PRESETS[self.role]
        if f_min != expected_f_min or f_max != expected_f_max:
            raise ValueError("role and F range do not match the authoritative preset")

        object.__setattr__(self, "delta_n", delta_n)
        object.__setattr__(self, "epsilon_tau", epsilon_tau)
        object.__setattr__(self, "initial_e", initial_e)
        object.__setattr__(self, "initial_q", initial_q)
        object.__setattr__(self, "initial_k_anchor", initial_k_anchor)
        object.__setattr__(self, "f_min", f_min)
        object.__setattr__(self, "f_max", f_max)
        object.__setattr__(self, "a_fixed", a_fixed)
        object.__setattr__(self, "t_min", t_min)
        object.__setattr__(self, "t_max", t_max)
        object.__setattr__(self, "d_fixed", d_fixed)

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
    def from_dict(cls, values: dict[str, Any]) -> DigitalLifeConfig:
        if not isinstance(values, dict):
            raise TypeError("config values must be a dictionary")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(f"missing config fields: {', '.join(sorted(missing))}")
        if unknown := actual - expected:
            raise ValueError(f"unknown config fields: {', '.join(sorted(unknown))}")
        normalized = dict(values)
        if isinstance(normalized["initial_k_anchor"], list):
            normalized["initial_k_anchor"] = tuple(normalized["initial_k_anchor"])
        return cls(**normalized)

    @classmethod
    def from_json(cls, encoded: str) -> DigitalLifeConfig:
        if not isinstance(encoded, str):
            raise TypeError("encoded config must be a string")
        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("config JSON must contain an object")
        return cls.from_dict(values)


def digital_life_config_for_role(role: str) -> DigitalLifeConfig:
    """Return the authoritative immutable preset for one visible life role."""

    if not isinstance(role, str):
        raise TypeError("role must be a string")
    try:
        digital_life_id, f_min, f_max = _ROLE_PRESETS[role]
    except KeyError as exc:
        raise ValueError("role must be red, green, or blue") from exc
    return DigitalLifeConfig(
        digital_life_id=digital_life_id,
        role=role,
        f_min=f_min,
        f_max=f_max,
    )
