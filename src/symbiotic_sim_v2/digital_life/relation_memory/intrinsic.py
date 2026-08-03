"""Pure intrinsic curiosity and adaptive-search parameter mappings."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.digital_life.hash01 import hash01
from symbiotic_sim_v2.digital_life.math import clip01

from .config import ALGORITHM_VERSION


def _required_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("digital_life_id must be a non-empty string")
    return value


def _finite_unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


@dataclass(frozen=True, slots=True)
class RelationMemoryIntrinsicProfile:
    """Immutable ID-derived parameters; no Garden or UI setting can modify them."""

    digital_life_id: str
    curiosity: float
    sigma_min: float
    sigma_max: float
    epsilon_accept: float
    p_explore_min: float
    algorithm_version: str = ALGORITHM_VERSION

    def __post_init__(self) -> None:
        life_id = _required_id(self.digital_life_id)
        curiosity = _finite_unit("curiosity", self.curiosity)
        expected = {
            "sigma_min": 0.02 + 0.04 * curiosity,
            "sigma_max": 0.25 + 0.30 * curiosity,
            "epsilon_accept": 0.07 - 0.04 * curiosity,
            "p_explore_min": 0.10 + 0.20 * curiosity,
        }
        for name, derived in expected.items():
            actual = _finite_unit(name, getattr(self, name))
            if actual != derived:
                raise ValueError(f"{name} must equal the intrinsic curiosity mapping")
            object.__setattr__(self, name, actual)
        if self.algorithm_version != ALGORITHM_VERSION:
            raise ValueError(f"algorithm_version must be {ALGORITHM_VERSION}")
        object.__setattr__(self, "digital_life_id", life_id)
        object.__setattr__(self, "curiosity", curiosity)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def derive_relation_memory_intrinsic_profile(
    digital_life_id: object,
) -> RelationMemoryIntrinsicProfile:
    """Derive the fixed Stage 5C profile from the existing normative Hash01."""

    life_id = _required_id(digital_life_id)
    curiosity = hash01(life_id, "curiosity")
    return RelationMemoryIntrinsicProfile(
        digital_life_id=life_id,
        curiosity=curiosity,
        sigma_min=0.02 + 0.04 * curiosity,
        sigma_max=0.25 + 0.30 * curiosity,
        epsilon_accept=0.07 - 0.04 * curiosity,
        p_explore_min=0.10 + 0.20 * curiosity,
    )


def relation_search_radius(w_anchor_session: object) -> float:
    """Return r(W)=clip01(2W-1) with strict finite/unit input validation."""

    weight = _finite_unit("w_anchor_session", w_anchor_session)
    return clip01(2.0 * weight - 1.0)


def exploration_sigma(
    w_anchor_session: object,
    sigma_min: object,
    sigma_max: object,
) -> float:
    """Return the adaptive candidate distance fixed at candidate generation."""

    minimum = _finite_unit("sigma_min", sigma_min)
    maximum = _finite_unit("sigma_max", sigma_max)
    if minimum > maximum:
        raise ValueError("sigma_min must not exceed sigma_max")
    radius = relation_search_radius(w_anchor_session)
    return minimum + (maximum - minimum) * (1.0 - radius)


def exploration_probability(
    w_anchor_session: object,
    p_explore_min: object,
) -> float:
    """Return the adaptive per-session exploration probability."""

    minimum = _finite_unit("p_explore_min", p_explore_min)
    radius = relation_search_radius(w_anchor_session)
    return minimum + (1.0 - minimum) * (1.0 - radius)


def should_explore(u_explore: object, p_explore: object) -> bool:
    """Apply the normative strict comparison; equality is always hold."""

    decision = _finite_unit("u_explore", u_explore)
    probability = _finite_unit("p_explore", p_explore)
    return decision < probability


def exploration_decision(u_explore: object, p_explore: object) -> str:
    """Return the fixed state-machine vocabulary for the strict decision."""

    return "explore" if should_explore(u_explore, p_explore) else "hold"


__all__ = [
    "RelationMemoryIntrinsicProfile",
    "derive_relation_memory_intrinsic_profile",
    "exploration_decision",
    "exploration_probability",
    "exploration_sigma",
    "relation_search_radius",
    "should_explore",
]
