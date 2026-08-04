"""Pure Stage 8A.1 scaling of the already-computed reference sigma."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.digital_life.relation_memory.intrinsic import (
    exploration_sigma,
)

from .config import SCALED_REFERENCE_SIGMA_POLICY_VERSION

MIN_SIGMA_MULTIPLIER = 0.25
MAX_SIGMA_MULTIPLIER = 1.50


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _multiplier(value: object) -> float:
    converted = _finite("sigma_multiplier", value)
    if not MIN_SIGMA_MULTIPLIER <= converted <= MAX_SIGMA_MULTIPLIER:
        raise ValueError("sigma_multiplier must be between 0.25 and 1.50")
    return converted


@dataclass(frozen=True, slots=True)
class ScaledSigmaDecision:
    """Audit the reference distance separately from its experimental scale."""

    reference_sigma: float
    multiplier: float
    effective_sigma: float
    policy_version: str = SCALED_REFERENCE_SIGMA_POLICY_VERSION

    def __post_init__(self) -> None:
        reference = _finite("reference_sigma", self.reference_sigma)
        if not 0.0 <= reference <= 1.0:
            raise ValueError("reference_sigma must be between 0 and 1")
        multiplier = _multiplier(self.multiplier)
        effective = _finite("effective_sigma", self.effective_sigma)
        if not 0.0 <= effective <= 1.0:
            raise ValueError("effective_sigma must be between 0 and 1")
        if effective != multiplier * reference:
            raise ValueError("effective_sigma must equal multiplier * reference_sigma")
        if self.policy_version != SCALED_REFERENCE_SIGMA_POLICY_VERSION:
            raise ValueError(
                "policy_version must be "
                f"{SCALED_REFERENCE_SIGMA_POLICY_VERSION}"
            )
        object.__setattr__(self, "reference_sigma", reference)
        object.__setattr__(self, "multiplier", multiplier)
        object.__setattr__(self, "effective_sigma", effective)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ScaledReferenceSigmaPolicy:
    """Multiply sigma only, retaining every reference exploration decision."""

    sigma_multiplier: float
    policy_version: str = SCALED_REFERENCE_SIGMA_POLICY_VERSION

    def __post_init__(self) -> None:
        multiplier = _multiplier(self.sigma_multiplier)
        if self.policy_version != SCALED_REFERENCE_SIGMA_POLICY_VERSION:
            raise ValueError(
                "policy_version must be "
                f"{SCALED_REFERENCE_SIGMA_POLICY_VERSION}"
            )
        object.__setattr__(self, "sigma_multiplier", multiplier)

    def scale(self, reference_sigma: object) -> ScaledSigmaDecision:
        reference = _finite("reference_sigma", reference_sigma)
        if not 0.0 <= reference <= 1.0:
            raise ValueError("reference_sigma must be between 0 and 1")
        return ScaledSigmaDecision(
            reference_sigma=reference,
            multiplier=self.sigma_multiplier,
            effective_sigma=self.sigma_multiplier * reference,
        )

    def at_w(
        self,
        w_anchor_session: object,
        sigma_min_reference: object,
        sigma_max_reference: object,
    ) -> ScaledSigmaDecision:
        reference = exploration_sigma(
            w_anchor_session,
            sigma_min_reference,
            sigma_max_reference,
        )
        return self.scale(reference)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "MAX_SIGMA_MULTIPLIER",
    "MIN_SIGMA_MULTIPLIER",
    "ScaledReferenceSigmaPolicy",
    "ScaledSigmaDecision",
]
