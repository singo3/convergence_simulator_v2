"""Deterministic intrinsic profile derivation for one Digital Life."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.digital_life.hash01 import hash01
from symbiotic_sim_v2.digital_life.math import intrinsic_b_mapping


@dataclass(frozen=True, slots=True)
class IntrinsicProfile:
    p_intrinsic: float
    birth_phase: float
    initial_b: tuple[float, float, float, float]


def derive_intrinsic_profile(config: DigitalLifeConfig) -> IntrinsicProfile:
    """Derive all immutable ID/role-dependent Stage 5A values."""

    if not isinstance(config, DigitalLifeConfig):
        raise TypeError("config must be a DigitalLifeConfig")
    return IntrinsicProfile(
        p_intrinsic=0.35 + 0.30 * hash01(config.digital_life_id, "handle-distance"),
        birth_phase=0.000001 * hash01(config.digital_life_id, "birth-phase"),
        initial_b=intrinsic_b_mapping(
            config.initial_k_anchor,
            f_min=config.f_min,
            f_max=config.f_max,
            a_fixed=config.a_fixed,
            t_min=config.t_min,
            t_max=config.t_max,
            d_fixed=config.d_fixed,
        ),
    )
