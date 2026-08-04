"""Pure Stage 8A.1 fatigue coefficient and session-end policy."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.digital_life.math import (
    RHO_E,
    calculate_e_next_with_coefficients,
)

from .config import (
    SELECTED_SESSION_FATIGUE_POLICY_VERSION,
    UNSELECTED_FULL_RECOVERY_POLICY_VERSION,
)

ACTIVE_SIGNAL_COUNT = 180
MIN_SELECTED_SESSION_FATIGUE_TARGET = 0.0
MAX_SELECTED_SESSION_FATIGUE_TARGET = 0.20
FULL_UNSELECTED_RECOVERY_FRACTION = 1.0


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _unit(name: str, value: object) -> float:
    converted = _finite(name, value)
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def _selected_target(value: object) -> float:
    target = _finite("selected_session_fatigue_target", value)
    if not MIN_SELECTED_SESSION_FATIGUE_TARGET <= target <= (
        MAX_SELECTED_SESSION_FATIGUE_TARGET
    ):
        raise ValueError("selected_session_fatigue_target must be between 0 and 0.20")
    return target


def _selected_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("selected_active_signal_count must be an integer")
    if not 0 <= value <= ACTIVE_SIGNAL_COUNT:
        raise ValueError(
            f"selected_active_signal_count must be between 0 and {ACTIVE_SIGNAL_COUNT}"
        )
    return value


def selected_session_eta(selected_session_fatigue_target: object) -> float:
    """Convert an E=0, 180-active-signal target into one-signal eta."""

    target = _selected_target(selected_session_fatigue_target)
    return 1.0 - (1.0 - target) ** (1.0 / ACTIVE_SIGNAL_COUNT)


@dataclass(frozen=True, slots=True)
class SessionEndFatigueDecision:
    """Pure decision made before an experimental final state is published."""

    e_before_policy: float
    e_after_policy: float
    selected_active_signal_count: int
    full_recovery_applied: bool
    recovery_fraction: float
    policy_version: str = UNSELECTED_FULL_RECOVERY_POLICY_VERSION

    def __post_init__(self) -> None:
        before = _unit("e_before_policy", self.e_before_policy)
        after = _unit("e_after_policy", self.e_after_policy)
        count = _selected_count(self.selected_active_signal_count)
        fraction = _unit("recovery_fraction", self.recovery_fraction)
        if fraction != FULL_UNSELECTED_RECOVERY_FRACTION:
            raise ValueError("Stage 8A.1 unselected recovery fraction must equal 1.0")
        if not isinstance(self.full_recovery_applied, bool):
            raise TypeError("full_recovery_applied must be boolean")
        expected_applied = count == 0
        if self.full_recovery_applied != expected_applied:
            raise ValueError("full recovery must be applied exactly when selected count is zero")
        expected_after = 0.0 if expected_applied else before
        if after != expected_after:
            raise ValueError("e_after_policy differs from the session-end fatigue policy")
        if self.policy_version != UNSELECTED_FULL_RECOVERY_POLICY_VERSION:
            raise ValueError(
                "policy_version must be "
                f"{UNSELECTED_FULL_RECOVERY_POLICY_VERSION}"
            )
        object.__setattr__(self, "e_before_policy", before)
        object.__setattr__(self, "e_after_policy", after)
        object.__setattr__(self, "selected_active_signal_count", count)
        object.__setattr__(self, "recovery_fraction", fraction)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SelectedSessionFatiguePolicy:
    """Experimental saturating accumulation with reference recovery unchanged."""

    selected_session_fatigue_target: float
    unselected_session_end_recovery_fraction: float = (
        FULL_UNSELECTED_RECOVERY_FRACTION
    )
    selected_policy_version: str = SELECTED_SESSION_FATIGUE_POLICY_VERSION
    session_end_policy_version: str = UNSELECTED_FULL_RECOVERY_POLICY_VERSION

    def __post_init__(self) -> None:
        target = _selected_target(self.selected_session_fatigue_target)
        recovery = _unit(
            "unselected_session_end_recovery_fraction",
            self.unselected_session_end_recovery_fraction,
        )
        if recovery != FULL_UNSELECTED_RECOVERY_FRACTION:
            raise ValueError("Stage 8A.1 unselected recovery fraction must equal 1.0")
        if self.selected_policy_version != SELECTED_SESSION_FATIGUE_POLICY_VERSION:
            raise ValueError(
                "selected_policy_version must be "
                f"{SELECTED_SESSION_FATIGUE_POLICY_VERSION}"
            )
        if self.session_end_policy_version != UNSELECTED_FULL_RECOVERY_POLICY_VERSION:
            raise ValueError(
                "session_end_policy_version must be "
                f"{UNSELECTED_FULL_RECOVERY_POLICY_VERSION}"
            )
        object.__setattr__(self, "selected_session_fatigue_target", target)
        object.__setattr__(
            self,
            "unselected_session_end_recovery_fraction",
            recovery,
        )

    @property
    def eta_selected(self) -> float:
        return selected_session_eta(self.selected_session_fatigue_target)

    @property
    def rho_reference(self) -> float:
        return RHO_E

    def calculate_e_next(self, e: object, s: object, g: object) -> float:
        return calculate_e_next_with_coefficients(
            e,
            s,
            g,
            eta_e=self.eta_selected,
            rho_e=RHO_E,
        )

    def decide_session_end(
        self,
        e_before_policy: object,
        selected_active_signal_count: object,
    ) -> SessionEndFatigueDecision:
        before = _unit("e_before_policy", e_before_policy)
        count = _selected_count(selected_active_signal_count)
        applied = count == 0
        return SessionEndFatigueDecision(
            e_before_policy=before,
            e_after_policy=0.0 if applied else before,
            selected_active_signal_count=count,
            full_recovery_applied=applied,
            recovery_fraction=self.unselected_session_end_recovery_fraction,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "eta_selected": self.eta_selected,
            "rho_reference": self.rho_reference,
        }


__all__ = [
    "ACTIVE_SIGNAL_COUNT",
    "FULL_UNSELECTED_RECOVERY_FRACTION",
    "MAX_SELECTED_SESSION_FATIGUE_TARGET",
    "MIN_SELECTED_SESSION_FATIGUE_TARGET",
    "SelectedSessionFatiguePolicy",
    "SessionEndFatigueDecision",
    "selected_session_eta",
]
