"""Frozen observable-only records for Stage 8A.1 structured diagnostics."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .config import STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION

STRUCTURED_SESSION_OBSERVATION_SCHEMA_VERSION = "structured_session_observation_v1"
STRUCTURED_CONVERGENCE_RECORD_SCHEMA_VERSION = "structured_convergence_record_v1"

SUMMARY_CLASSIFICATIONS = frozenset(
    {
        "insufficient_sessions",
        "single_life_pattern_convergence",
        "life_dominant_convergence",
        "bpm_common_convergence",
        "life_specific_multi_attractor_convergence",
        "mixed_structured_convergence",
        "diffuse_or_unresolved",
    }
)


def _counter(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _optional_finite(name: str, value: object | None) -> float | None:
    return None if value is None else _finite(name, value)


def _optional_text(name: str, value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string or null")
    return value


@dataclass(frozen=True, slots=True)
class StructuredSessionObservation:
    """The complete primary input: no hidden preference or internal Core state."""

    session_index: int
    valid_for_convergence: bool
    holder_id: str | None
    hue_degree: float | None
    blink_bpm: float | None
    exploration_decision: str | None = None
    candidate_generated: bool = False
    candidate_accepted: bool = False
    invalid_reason: str | None = None
    schema_version: str = STRUCTURED_SESSION_OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_index", _counter("session_index", self.session_index))
        if not isinstance(self.valid_for_convergence, bool):
            raise TypeError("valid_for_convergence must be boolean")
        for name in ("candidate_generated", "candidate_accepted"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        holder = _optional_text("holder_id", self.holder_id)
        reason = _optional_text("invalid_reason", self.invalid_reason)
        hue = _optional_finite("hue_degree", self.hue_degree)
        bpm = _optional_finite("blink_bpm", self.blink_bpm)
        if hue is not None and not 0.0 <= hue <= 360.0:
            raise ValueError("hue_degree must be between 0 and 360")
        if bpm is not None and not 10.0 <= bpm <= 165.0:
            raise ValueError("blink_bpm must be between 10 and 165")
        if self.valid_for_convergence:
            if holder is None or hue is None or bpm is None:
                raise ValueError("valid observation requires holder, Hue, and BPM")
            if reason is not None:
                raise ValueError("valid observation cannot carry invalid_reason")
        if self.exploration_decision not in {None, "hold", "explore"}:
            raise ValueError("exploration_decision must be hold, explore, or null")
        if self.candidate_generated and self.exploration_decision != "explore":
            raise ValueError("candidate_generated requires explore decision")
        if self.candidate_accepted and not self.candidate_generated:
            raise ValueError("candidate_accepted requires candidate_generated")
        if self.schema_version != STRUCTURED_SESSION_OBSERVATION_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {STRUCTURED_SESSION_OBSERVATION_SCHEMA_VERSION}"
            )
        for name, value in {
            "holder_id": holder,
            "invalid_reason": reason,
            "hue_degree": hue,
            "blink_bpm": bpm,
        }.items():
            object.__setattr__(self, name, value)

    @classmethod
    def from_outcome(cls, outcome: object) -> StructuredSessionObservation:
        def read(name: str) -> object:
            if isinstance(outcome, Mapping):
                if name not in outcome:
                    raise ValueError(f"session outcome is missing {name}")
                return outcome[name]
            try:
                return getattr(outcome, name)
            except AttributeError as exc:
                raise ValueError(f"session outcome is missing {name}") from exc

        return cls(
            session_index=read("session_index"),  # type: ignore[arg-type]
            valid_for_convergence=read("valid_for_convergence"),  # type: ignore[arg-type]
            holder_id=read("holder_id"),  # type: ignore[arg-type]
            hue_degree=read("holder_final_hue_degree"),  # type: ignore[arg-type]
            blink_bpm=read("holder_final_blink_bpm"),  # type: ignore[arg-type]
            exploration_decision=read("exploration_decision"),  # type: ignore[arg-type]
            candidate_generated=read("candidate_generated"),  # type: ignore[arg-type]
            candidate_accepted=read("candidate_accepted"),  # type: ignore[arg-type]
            invalid_reason=read("invalid_reason"),  # type: ignore[arg-type]
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
    def from_dict(cls, values: Mapping[str, Any]) -> StructuredSessionObservation:
        if not isinstance(values, Mapping):
            raise TypeError("structured observation values must be a mapping")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(f"missing observation fields: {', '.join(sorted(missing))}")
        if unknown := actual - expected:
            raise ValueError(f"unknown observation fields: {', '.join(sorted(unknown))}")
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> StructuredSessionObservation:
        if not isinstance(encoded, str):
            raise TypeError("encoded structured observation must be a string")
        parsed = json.loads(encoded)
        if not isinstance(parsed, dict):
            raise ValueError("structured observation JSON must contain an object")
        return cls.from_dict(parsed)


@dataclass(frozen=True, slots=True)
class LifeDominanceRecord:
    valid_window_session_indices: tuple[int, ...]
    sufficient_sessions: bool
    dominant_life_id: str | None
    dominant_count: int
    share: float
    strict_consecutive_run: int
    one_outlier_tolerant_longest_run: int
    maximum_consecutive_outliers: int
    latest_session_outlier: bool
    return_opportunity_count: int
    return_within_one_session_count: int
    return_within_one_session_rate: float
    return_within_two_sessions_count: int
    return_within_two_sessions_rate: float
    confirmed: bool
    first_confirmed_session_index: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BpmCommonRecord:
    valid_window_session_indices: tuple[int, ...]
    sufficient_sessions: bool
    support: int
    member_session_indices: tuple[int, ...]
    outlier_session_indices: tuple[int, ...]
    medoid_bpm: float | None
    median_bpm: float | None
    bpm_range: float | None
    mean_absolute_deviation: float | None
    participating_life_ids: tuple[str, ...]
    cross_life: bool
    confirmed: bool
    first_confirmed_session_index: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LifeAttractorRecord:
    life_id: str
    occurrence_count: int
    support: int
    support_fraction: float
    member_session_indices: tuple[int, ...]
    outlier_session_indices: tuple[int, ...]
    medoid_bpm: float | None
    median_bpm: float | None
    bpm_range: float | None
    mean_absolute_deviation: float | None
    valid_attractor: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MultiAttractorRecord:
    valid_window_session_indices: tuple[int, ...]
    life_attractors: tuple[LifeAttractorRecord, ...]
    attractor_count: int
    attractor_separation: float | None
    two_attractor_flag: bool
    three_attractor_flag: bool
    confirmed: bool
    first_confirmed_session_index: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MechanicalRotationRecord:
    valid_session_count: int
    dominant_life_id: str | None
    holder_switch_count: int
    holder_switch_opportunities: int
    holder_switch_rate: float
    three_distinct_life_window_count: int
    three_session_window_count: int
    three_distinct_life_window_rate: float
    immediate_return_count: int
    immediate_return_rate: float
    three_life_cycle_count: int
    four_session_window_count: int
    three_life_cycle_rate: float
    dominant_life_return_count: int
    dominant_life_return_opportunities: int
    dominant_life_return_rate: float
    mean_sessions_between_same_life_selections: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EDrivenSwitchRecord:
    holder_switch_count: int
    evaluable_switch_count: int
    lower_incoming_e_switch_count: int
    lower_incoming_e_switch_rate: float
    mean_incoming_e_advantage: float | None
    e_driven_switch_warning: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StructuredConvergenceRecord:
    evaluated_at_session_index: int
    valid_session_count: int
    early_single_life_pattern_signal: bool
    life_dominance: LifeDominanceRecord
    bpm_common: BpmCommonRecord
    multi_attractor: MultiAttractorRecord
    mechanical_rotation: MechanicalRotationRecord
    life_dominance_score: float
    bpm_common_score: float
    multi_attractor_score: float
    mechanical_rotation_score: float
    one_gap_tolerant_continuity_flag: bool
    one_gap_tolerant_continuity_score: float
    temporary_outlier_and_return_flag: bool
    temporary_outlier_and_return_score: float
    life_dominant_converged: bool
    bpm_common_converged: bool
    multi_attractor_converged: bool
    three_attractor_converged: bool
    summary_classification: str
    evaluator_version: str = STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION
    schema_version: str = STRUCTURED_CONVERGENCE_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evaluated_at_session_index",
            _counter("evaluated_at_session_index", self.evaluated_at_session_index),
        )
        object.__setattr__(
            self,
            "valid_session_count",
            _counter("valid_session_count", self.valid_session_count),
        )
        for name in (
            "early_single_life_pattern_signal",
            "one_gap_tolerant_continuity_flag",
            "temporary_outlier_and_return_flag",
            "life_dominant_converged",
            "bpm_common_converged",
            "multi_attractor_converged",
            "three_attractor_converged",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        for name in (
            "life_dominance_score",
            "bpm_common_score",
            "multi_attractor_score",
            "mechanical_rotation_score",
            "one_gap_tolerant_continuity_score",
            "temporary_outlier_and_return_score",
        ):
            score = _finite(name, getattr(self, name))
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
            object.__setattr__(self, name, score)
        if self.summary_classification not in SUMMARY_CLASSIFICATIONS:
            raise ValueError("summary_classification is not recognized")
        if self.evaluator_version != STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION:
            raise ValueError(
                f"evaluator_version must be {STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION}"
            )
        if self.schema_version != STRUCTURED_CONVERGENCE_RECORD_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {STRUCTURED_CONVERGENCE_RECORD_SCHEMA_VERSION}"
            )
        if self.life_dominant_converged != self.life_dominance.confirmed:
            raise ValueError("life dominance flag differs from its diagnostic")
        if self.bpm_common_converged != self.bpm_common.confirmed:
            raise ValueError("BPM common flag differs from its diagnostic")
        if self.multi_attractor_converged != self.multi_attractor.confirmed:
            raise ValueError("multi-attractor flag differs from its diagnostic")
        if self.three_attractor_converged != self.multi_attractor.three_attractor_flag:
            raise ValueError("three-attractor flag differs from its diagnostic")

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "dominant_life_id": self.dominant_life_id,
            "dominant_life_share": self.dominant_life_share,
            "strict_consecutive_run": self.strict_consecutive_run,
            "one_outlier_tolerant_longest_run": (self.one_outlier_tolerant_longest_run),
            "latest_session_outlier": self.latest_session_outlier,
            "return_within_1_rate": self.return_within_1_rate,
            "return_within_2_rate": self.return_within_2_rate,
            "bpm_common_support": self.bpm_common_support,
            "bpm_common_medoid_bpm": self.bpm_common_medoid_bpm,
            "bpm_common_range": self.bpm_common_range,
            "bpm_common_participating_life_ids": (self.bpm_common_participating_life_ids),
            "attractor_count": self.attractor_count,
            "attractor_medoid_bpm_by_life": self.attractor_medoid_bpm_by_life,
            "attractor_support_by_life": self.attractor_support_by_life,
            "attractor_separation": self.attractor_separation,
        }

    @property
    def dominant_life_id(self) -> str | None:
        return self.life_dominance.dominant_life_id

    @property
    def dominant_life_share(self) -> float:
        return self.life_dominance.share

    @property
    def strict_consecutive_run(self) -> int:
        return self.life_dominance.strict_consecutive_run

    @property
    def one_outlier_tolerant_longest_run(self) -> int:
        return self.life_dominance.one_outlier_tolerant_longest_run

    @property
    def latest_session_outlier(self) -> bool:
        return self.life_dominance.latest_session_outlier

    @property
    def return_within_1_rate(self) -> float:
        return self.life_dominance.return_within_one_session_rate

    @property
    def return_within_2_rate(self) -> float:
        return self.life_dominance.return_within_two_sessions_rate

    @property
    def bpm_common_support(self) -> int:
        return self.bpm_common.support

    @property
    def bpm_common_medoid_bpm(self) -> float | None:
        return self.bpm_common.medoid_bpm

    @property
    def bpm_common_range(self) -> float | None:
        return self.bpm_common.bpm_range

    @property
    def bpm_common_participating_life_ids(self) -> tuple[str, ...]:
        return self.bpm_common.participating_life_ids

    @property
    def attractor_count(self) -> int:
        return self.multi_attractor.attractor_count

    @property
    def attractor_medoid_bpm_by_life(self) -> dict[str, float | None]:
        return {item.life_id: item.medoid_bpm for item in self.multi_attractor.life_attractors}

    @property
    def attractor_support_by_life(self) -> dict[str, int]:
        return {item.life_id: item.support for item in self.multi_attractor.life_attractors}

    @property
    def attractor_separation(self) -> float | None:
        return self.multi_attractor.attractor_separation

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


__all__ = [
    "BpmCommonRecord",
    "EDrivenSwitchRecord",
    "LifeAttractorRecord",
    "LifeDominanceRecord",
    "MechanicalRotationRecord",
    "MultiAttractorRecord",
    "STRUCTURED_CONVERGENCE_RECORD_SCHEMA_VERSION",
    "STRUCTURED_SESSION_OBSERVATION_SCHEMA_VERSION",
    "SUMMARY_CLASSIFICATIONS",
    "StructuredConvergenceRecord",
    "StructuredSessionObservation",
]
