"""Read-only Stage 8A.1 W-ceiling exploration-identifiability diagnostic."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

W_CEILING_DIAGNOSTIC_VERSION = "w_ceiling_diagnostic_v0_1"
W_CEILING_CLASSIFICATIONS = frozenset(
    {
        "exploration_identifiable",
        "exploration_partly_saturated",
        "exploration_blocked_by_W_ceiling",
    }
)
_CEILING_ABSOLUTE_TOLERANCE = 1.0e-12


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def _optional_unit(name: str, value: object | None) -> float | None:
    return None if value is None else _unit(name, value)


@dataclass(frozen=True, slots=True)
class WCeilingObservation:
    session_index: int
    w_anchor_session: float
    epsilon_accept: float
    w_trial_1: float | None
    w_trial_2: float | None
    candidate_generated: bool
    candidate_accepted: bool

    def __post_init__(self) -> None:
        if isinstance(self.session_index, bool) or not isinstance(self.session_index, int):
            raise TypeError("session_index must be an integer")
        if self.session_index < 0:
            raise ValueError("session_index must be non-negative")
        for name in ("candidate_generated", "candidate_accepted"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        if self.candidate_accepted and not self.candidate_generated:
            raise ValueError("candidate_accepted requires candidate_generated")
        object.__setattr__(
            self,
            "w_anchor_session",
            _unit("w_anchor_session", self.w_anchor_session),
        )
        object.__setattr__(self, "epsilon_accept", _unit("epsilon_accept", self.epsilon_accept))
        object.__setattr__(self, "w_trial_1", _optional_unit("w_trial_1", self.w_trial_1))
        object.__setattr__(self, "w_trial_2", _optional_unit("w_trial_2", self.w_trial_2))
        if (self.w_trial_1 is not None or self.w_trial_2 is not None) and not (
            self.candidate_generated
        ):
            raise ValueError("trial W values require candidate generation")

    @classmethod
    def from_outcome(
        cls,
        outcome: object,
        *,
        epsilon_accept: object,
    ) -> WCeilingObservation | None:
        def read(name: str) -> object:
            if isinstance(outcome, Mapping):
                return outcome[name]
            return getattr(outcome, name)

        anchor = read("holder_W_anchor_session")
        if anchor is None:
            return None
        return cls(
            session_index=read("session_index"),  # type: ignore[arg-type]
            w_anchor_session=anchor,  # type: ignore[arg-type]
            epsilon_accept=epsilon_accept,  # type: ignore[arg-type]
            w_trial_1=read("holder_W_trial_1"),  # type: ignore[arg-type]
            w_trial_2=read("holder_W_trial_2"),  # type: ignore[arg-type]
            candidate_generated=read("candidate_generated"),  # type: ignore[arg-type]
            candidate_accepted=read("candidate_accepted"),  # type: ignore[arg-type]
        )

    @property
    def provisional_success(self) -> bool:
        return bool(
            self.w_trial_1 is not None
            and self.w_trial_1 > self.w_anchor_session + self.epsilon_accept
        )

    @property
    def confirmation_success(self) -> bool:
        return bool(
            self.w_trial_1 is not None
            and self.w_trial_2 is not None
            and self.w_trial_2 > self.w_anchor_session
            and (self.w_trial_1 + self.w_trial_2) / 2.0
            > self.w_anchor_session + self.epsilon_accept
        )

    @property
    def mathematically_impossible_provisional_adoption(self) -> bool:
        return self.w_anchor_session + self.epsilon_accept >= 1.0

    @property
    def best_observed_trial_gap(self) -> float | None:
        trials = tuple(value for value in (self.w_trial_1, self.w_trial_2) if value is not None)
        return None if not trials else max(trials) - self.w_anchor_session

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "provisional_success": self.provisional_success,
            "confirmation_success": self.confirmation_success,
            "mathematically_impossible_provisional_adoption": (
                self.mathematically_impossible_provisional_adoption
            ),
            "best_observed_trial_gap": self.best_observed_trial_gap,
        }


@dataclass(frozen=True, slots=True)
class WCeilingDiagnosticRecord:
    anchor_evaluation_count: int
    w_anchor_session_ceiling_count: int
    w_anchor_session_ge_one_minus_epsilon_count: int
    mathematically_impossible_provisional_adoption_count: int
    w_trial_ceiling_count: int
    candidate_generation_count: int
    provisional_success_count: int
    confirmation_success_count: int
    accepted_count: int
    best_observed_trial_w_gap: float | None
    classification: str
    version: str = W_CEILING_DIAGNOSTIC_VERSION

    def __post_init__(self) -> None:
        if self.classification not in W_CEILING_CLASSIFICATIONS:
            raise ValueError("W ceiling classification is not recognized")
        if self.version != W_CEILING_DIAGNOSTIC_VERSION:
            raise ValueError(f"version must be {W_CEILING_DIAGNOSTIC_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_w_ceiling(
    observations: Sequence[WCeilingObservation],
) -> WCeilingDiagnosticRecord:
    if isinstance(observations, (str, bytes)) or not isinstance(observations, Sequence):
        raise TypeError("observations must be a sequence")
    values = tuple(observations)
    if any(not isinstance(item, WCeilingObservation) for item in values):
        raise TypeError("observations must contain WCeilingObservation values")
    impossible = sum(item.mathematically_impossible_provisional_adoption for item in values)
    anchor_ceilings = sum(
        math.isclose(
            item.w_anchor_session,
            1.0,
            rel_tol=0.0,
            abs_tol=_CEILING_ABSOLUTE_TOLERANCE,
        )
        for item in values
    )
    trial_values = tuple(
        value for item in values for value in (item.w_trial_1, item.w_trial_2) if value is not None
    )
    trial_ceilings = sum(
        math.isclose(value, 1.0, rel_tol=0.0, abs_tol=_CEILING_ABSOLUTE_TOLERANCE)
        for value in trial_values
    )
    if values and impossible == len(values):
        classification = "exploration_blocked_by_W_ceiling"
    elif impossible > 0 or anchor_ceilings > 0 or trial_ceilings > 0:
        classification = "exploration_partly_saturated"
    else:
        classification = "exploration_identifiable"
    gaps = tuple(
        gap for item in values for gap in (item.best_observed_trial_gap,) if gap is not None
    )
    return WCeilingDiagnosticRecord(
        anchor_evaluation_count=len(values),
        w_anchor_session_ceiling_count=anchor_ceilings,
        w_anchor_session_ge_one_minus_epsilon_count=sum(
            item.w_anchor_session >= 1.0 - item.epsilon_accept for item in values
        ),
        mathematically_impossible_provisional_adoption_count=impossible,
        w_trial_ceiling_count=trial_ceilings,
        candidate_generation_count=sum(item.candidate_generated for item in values),
        provisional_success_count=sum(item.provisional_success for item in values),
        confirmation_success_count=sum(item.confirmation_success for item in values),
        accepted_count=sum(item.candidate_accepted for item in values),
        best_observed_trial_w_gap=None if not gaps else max(gaps),
        classification=classification,
    )


__all__ = [
    "W_CEILING_CLASSIFICATIONS",
    "W_CEILING_DIAGNOSTIC_VERSION",
    "WCeilingDiagnosticRecord",
    "WCeilingObservation",
    "evaluate_w_ceiling",
]
