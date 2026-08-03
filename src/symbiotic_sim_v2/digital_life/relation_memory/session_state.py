"""Immutable session-local Stage 5C adaptation state."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .config import ADAPTATION_PHASES, ADOPTION_RESULTS, EXPLORATION_DECISIONS
from .intrinsic import derive_relation_memory_intrinsic_profile
from .persistent_state import RelationMemoryPersistentState


def _required_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("digital_life_id must be a non-empty string")
    return value


def _counter(name: str, value: object, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must not exceed {maximum}")
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


def _optional_unit(name: str, value: object | None) -> float | None:
    return None if value is None else _unit(name, value)


def _vector(
    name: str,
    value: object,
    *,
    unit: bool,
) -> tuple[float, float, float, float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a four-element sequence")
    if len(value) != 4:
        raise ValueError(f"{name} must contain four values")
    converted: list[float] = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(f"{name}[{index}] must be a number")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"{name}[{index}] must be finite")
        if unit and not 0.0 <= number <= 1.0:
            raise ValueError(f"{name}[{index}] must be between 0 and 1")
        converted.append(number)
    return tuple(converted)  # type: ignore[return-value]


def _optional_vector(
    name: str,
    value: object | None,
    *,
    unit: bool,
) -> tuple[float, float, float, float] | None:
    return None if value is None else _vector(name, value, unit=unit)


@dataclass(frozen=True, slots=True)
class RelationMemorySessionState:
    digital_life_id: str
    session_count_used: int
    initial_k_anchor: tuple[float, float, float, float]
    w_anchor_session: float | None
    anchor_evaluated: bool
    k_trial: tuple[float, float, float, float] | None
    w_trial_1: float | None
    w_trial_2: float | None
    adaptation_phase: str
    exploration_decision: str | None
    u_explore: float | None
    p_explore: float | None
    sigma: float | None
    direction_xi: tuple[float, float, float, float] | None
    epsilon_accept: float
    candidate_generated: bool
    candidate_generation_trial_index: int | None
    candidate_effective_signal_index: int | None
    adoption_result: str
    rollback_reason: str | None
    anchor_return_w: float | None
    valid_trial_evaluation_count: int
    session_finalized: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "digital_life_id", _required_id(self.digital_life_id))
        object.__setattr__(
            self,
            "session_count_used",
            _counter("session_count_used", self.session_count_used),
        )
        object.__setattr__(
            self,
            "initial_k_anchor",
            _vector("initial_k_anchor", self.initial_k_anchor, unit=True),
        )
        object.__setattr__(
            self,
            "w_anchor_session",
            _optional_unit("w_anchor_session", self.w_anchor_session),
        )
        if not isinstance(self.anchor_evaluated, bool):
            raise TypeError("anchor_evaluated must be boolean")
        object.__setattr__(
            self,
            "k_trial",
            _optional_vector("k_trial", self.k_trial, unit=True),
        )
        object.__setattr__(
            self,
            "w_trial_1",
            _optional_unit("w_trial_1", self.w_trial_1),
        )
        object.__setattr__(
            self,
            "w_trial_2",
            _optional_unit("w_trial_2", self.w_trial_2),
        )
        if self.adaptation_phase not in ADAPTATION_PHASES:
            raise ValueError("adaptation_phase is not recognized")
        if (
            self.exploration_decision is not None
            and self.exploration_decision not in EXPLORATION_DECISIONS
        ):
            raise ValueError("exploration_decision must be hold, explore, or null")
        for name in ("u_explore", "p_explore", "sigma"):
            object.__setattr__(self, name, _optional_unit(name, getattr(self, name)))
        direction = _optional_vector("direction_xi", self.direction_xi, unit=False)
        if direction is not None:
            if direction[1] != 0.0 or direction[3] != 0.0:
                raise ValueError("direction_xi may contain only F/T components")
            if not math.isclose(
                math.hypot(direction[0], direction[2]),
                1.0,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            ):
                raise ValueError("direction_xi F/T norm must equal one")
        object.__setattr__(self, "direction_xi", direction)
        object.__setattr__(
            self,
            "epsilon_accept",
            _unit("epsilon_accept", self.epsilon_accept),
        )
        if not isinstance(self.candidate_generated, bool):
            raise TypeError("candidate_generated must be boolean")
        for name in (
            "candidate_generation_trial_index",
            "candidate_effective_signal_index",
        ):
            value = getattr(self, name)
            if value is not None:
                value = _counter(name, value)
            object.__setattr__(self, name, value)
        if self.adoption_result not in ADOPTION_RESULTS:
            raise ValueError("adoption_result is not recognized")
        if self.rollback_reason is not None and (
            not isinstance(self.rollback_reason, str) or not self.rollback_reason.strip()
        ):
            raise ValueError("rollback_reason must be a non-empty string or null")
        object.__setattr__(
            self,
            "anchor_return_w",
            _optional_unit("anchor_return_w", self.anchor_return_w),
        )
        object.__setattr__(
            self,
            "valid_trial_evaluation_count",
            _counter(
                "valid_trial_evaluation_count",
                self.valid_trial_evaluation_count,
                maximum=2,
            ),
        )
        if not isinstance(self.session_finalized, bool):
            raise TypeError("session_finalized must be boolean")
        if self.anchor_evaluated != (self.w_anchor_session is not None):
            raise ValueError("anchor_evaluated and w_anchor_session are inconsistent")
        candidate_values = (
            self.k_trial,
            self.direction_xi,
            self.candidate_generation_trial_index,
            self.candidate_effective_signal_index,
        )
        required_candidate_values = (
            candidate_values[1:] if self.session_finalized else candidate_values
        )
        if self.candidate_generated and any(
            value is None for value in required_candidate_values
        ):
            raise ValueError("generated candidate requires direction and generation indices")
        if not self.candidate_generated and any(value is not None for value in candidate_values):
            raise ValueError("candidate fields require candidate_generated=true")

    @classmethod
    def fresh(
        cls,
        persistent_state: RelationMemoryPersistentState,
    ) -> RelationMemorySessionState:
        if not isinstance(persistent_state, RelationMemoryPersistentState):
            raise TypeError("persistent_state must be a RelationMemoryPersistentState")
        profile = derive_relation_memory_intrinsic_profile(
            persistent_state.digital_life_id
        )
        return cls(
            digital_life_id=persistent_state.digital_life_id,
            session_count_used=persistent_state.session_count,
            initial_k_anchor=persistent_state.k_anchor,
            w_anchor_session=None,
            anchor_evaluated=False,
            k_trial=None,
            w_trial_1=None,
            w_trial_2=None,
            adaptation_phase="anchor_evaluation",
            exploration_decision=None,
            u_explore=None,
            p_explore=None,
            sigma=None,
            direction_xi=None,
            epsilon_accept=profile.epsilon_accept,
            candidate_generated=False,
            candidate_generation_trial_index=None,
            candidate_effective_signal_index=None,
            adoption_result="pending",
            rollback_reason=None,
            anchor_return_w=None,
            valid_trial_evaluation_count=0,
            session_finalized=False,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["RelationMemorySessionState"]
