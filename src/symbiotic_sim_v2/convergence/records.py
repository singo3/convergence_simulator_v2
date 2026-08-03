"""Immutable observable convergence and separate hidden-truth records."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.simulation.time_utils import (
    indexed_local_time_to_global_us,
)

ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION = "rolling_convergence_record_v1"
STAGE8A_SESSION_DURATION_US = 240_000_000

CONVERGENCE_STATES = frozenset(
    {
        "searching",
        "converged_monitoring",
        "converged_monitoring_latest_outlier",
        "convergence_lost",
        "insufficient_valid_sessions",
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


def _strict_object(encoded: str, label: str) -> dict[str, Any]:
    if not isinstance(encoded, str):
        raise TypeError(f"encoded {label} must be a string")

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate {label} field: {key}")
            result[key] = value
        return result

    parsed = json.loads(encoded, object_pairs_hook=pairs)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} JSON must contain an object")
    return parsed


def _exact_fields(values: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(values)
    if missing := expected - actual:
        raise ValueError(f"missing {label} fields: {', '.join(sorted(missing))}")
    if unknown := actual - expected:
        raise ValueError(f"unknown {label} fields: {', '.join(sorted(unknown))}")


def _non_empty_optional(name: str, value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string or null")
    return value


@dataclass(frozen=True, slots=True)
class SessionPatternObservation:
    """The complete primary evaluator input; no hidden preference is present."""

    session_index: int
    valid_for_convergence: bool
    invalid_reason: str | None
    holder_id: str | None
    hue_degree: float | None
    blink_bpm: float | None
    exploration_decision: str | None
    candidate_generated: bool
    candidate_accepted: bool
    local_time_us: int = STAGE8A_SESSION_DURATION_US
    global_time_us: int | None = None

    def __post_init__(self) -> None:
        index = _counter("session_index", self.session_index)
        local_time_us = _counter("local_time_us", self.local_time_us)
        expected_global_time_us = indexed_local_time_to_global_us(
            index,
            STAGE8A_SESSION_DURATION_US,
            local_time_us,
        )
        global_time_us = (
            expected_global_time_us
            if self.global_time_us is None
            else _counter("global_time_us", self.global_time_us)
        )
        if global_time_us != expected_global_time_us:
            raise ValueError("global_time_us differs from session local time")
        object.__setattr__(self, "session_index", index)
        object.__setattr__(self, "local_time_us", local_time_us)
        object.__setattr__(self, "global_time_us", global_time_us)
        for name in (
            "valid_for_convergence",
            "candidate_generated",
            "candidate_accepted",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        reason = _non_empty_optional("invalid_reason", self.invalid_reason)
        holder = _non_empty_optional("holder_id", self.holder_id)
        if self.exploration_decision not in {None, "hold", "explore"}:
            raise ValueError("exploration_decision must be hold, explore, or null")
        hue = _optional_finite("hue_degree", self.hue_degree)
        bpm = _optional_finite("blink_bpm", self.blink_bpm)
        if hue is not None and not 0.0 <= hue <= 360.0:
            raise ValueError("hue_degree must be between 0 and 360")
        if bpm is not None and not 10.0 <= bpm <= 165.0:
            raise ValueError("blink_bpm must be between 10 and 165")
        if self.valid_for_convergence:
            if reason is not None:
                raise ValueError("a valid observation cannot have invalid_reason")
            if holder is None or hue is None or bpm is None:
                raise ValueError("a valid observation requires holder, Hue, and BPM")
        elif reason is None:
            raise ValueError("an invalid observation requires invalid_reason")
        if self.candidate_accepted and not self.candidate_generated:
            raise ValueError("candidate_accepted requires candidate_generated")
        object.__setattr__(self, "invalid_reason", reason)
        object.__setattr__(self, "holder_id", holder)
        object.__setattr__(self, "hue_degree", hue)
        object.__setattr__(self, "blink_bpm", bpm)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> SessionPatternObservation:
        if not isinstance(values, Mapping):
            raise TypeError("observation values must be a mapping")
        _exact_fields(values, set(cls.__dataclass_fields__), "observation")
        return cls(**dict(values))

    @classmethod
    def from_outcome(cls, outcome: object) -> SessionPatternObservation:
        """Detach the observable fields from a runtime SessionOutcome-like value."""

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
            invalid_reason=read("invalid_reason"),  # type: ignore[arg-type]
            holder_id=read("holder_id"),  # type: ignore[arg-type]
            hue_degree=read("holder_final_hue_degree"),  # type: ignore[arg-type]
            blink_bpm=read("holder_final_blink_bpm"),  # type: ignore[arg-type]
            exploration_decision=read("exploration_decision"),  # type: ignore[arg-type]
            candidate_generated=read("candidate_generated"),  # type: ignore[arg-type]
            candidate_accepted=read("candidate_accepted"),  # type: ignore[arg-type]
            local_time_us=read("local_time_us"),  # type: ignore[arg-type]
            global_time_us=read("global_time_us"),  # type: ignore[arg-type]
        )


@dataclass(frozen=True, slots=True)
class RollingConvergenceRecord:
    evaluated_at_session_index: int
    local_time_us: int
    global_time_us: int
    window_session_indices: tuple[int, ...]
    valid_window_session_indices: tuple[int, ...]
    support_count: int
    window_size: int
    required_sessions: int
    holder_id: str | None
    member_session_indices: tuple[int, ...]
    outlier_session_indices: tuple[int, ...]
    maximum_pairwise_distance: float | None
    mean_pairwise_distance: float | None
    medoid_session_index: int | None
    medoid_hue_degree: float | None
    medoid_blink_bpm: float | None
    circular_mean_hue_degree: float | None
    median_blink_bpm: float | None
    currently_converged: bool
    convergence_state: str
    first_convergence_session_index: int | None
    latest_valid_session_is_outlier: bool
    total_sessions_after_first_convergence: int
    post_convergence_cluster_member_count: int
    post_convergence_outlier_count: int
    latest_outlier_count: int
    convergence_lost_count: int
    reconvergence_count: int
    dominant_cluster_switch_count: int
    outlier_return_within_one_session_count: int
    outlier_return_within_two_sessions_count: int
    post_convergence_exploration_count: int
    post_convergence_candidate_accepted_count: int
    evaluator_version: str
    schema_version: str = ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        evaluated_index = _counter(
            "evaluated_at_session_index",
            self.evaluated_at_session_index,
        )
        local_time_us = _counter("local_time_us", self.local_time_us)
        global_time_us = _counter("global_time_us", self.global_time_us)
        if global_time_us != indexed_local_time_to_global_us(
            evaluated_index,
            STAGE8A_SESSION_DURATION_US,
            local_time_us,
        ):
            raise ValueError("convergence global_time_us differs from local time")
        object.__setattr__(self, "evaluated_at_session_index", evaluated_index)
        object.__setattr__(self, "local_time_us", local_time_us)
        object.__setattr__(self, "global_time_us", global_time_us)
        for name in (
            "support_count",
            "window_size",
            "required_sessions",
            "total_sessions_after_first_convergence",
            "post_convergence_cluster_member_count",
            "post_convergence_outlier_count",
            "latest_outlier_count",
            "convergence_lost_count",
            "reconvergence_count",
            "dominant_cluster_switch_count",
            "outlier_return_within_one_session_count",
            "outlier_return_within_two_sessions_count",
            "post_convergence_exploration_count",
            "post_convergence_candidate_accepted_count",
        ):
            object.__setattr__(self, name, _counter(name, getattr(self, name)))
        for name in (
            "window_session_indices",
            "valid_window_session_indices",
            "member_session_indices",
            "outlier_session_indices",
        ):
            raw = getattr(self, name)
            if isinstance(raw, (str, bytes)):
                raise TypeError(f"{name} must be a sequence of integers")
            normalized = tuple(_counter(name, value) for value in raw)
            if normalized != tuple(sorted(set(normalized))):
                raise ValueError(f"{name} must be unique and sorted")
            object.__setattr__(self, name, normalized)
        if not isinstance(self.currently_converged, bool):
            raise TypeError("currently_converged must be boolean")
        if not isinstance(self.latest_valid_session_is_outlier, bool):
            raise TypeError("latest_valid_session_is_outlier must be boolean")
        if self.convergence_state not in CONVERGENCE_STATES:
            raise ValueError("convergence_state is not recognized")
        if self.schema_version != ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION}"
            )
        if not isinstance(self.evaluator_version, str) or not self.evaluator_version:
            raise ValueError("evaluator_version must be a non-empty string")
        holder = _non_empty_optional("holder_id", self.holder_id)
        object.__setattr__(self, "holder_id", holder)
        for name in (
            "maximum_pairwise_distance",
            "mean_pairwise_distance",
            "medoid_hue_degree",
            "medoid_blink_bpm",
            "circular_mean_hue_degree",
            "median_blink_bpm",
        ):
            object.__setattr__(self, name, _optional_finite(name, getattr(self, name)))
        for name in ("medoid_session_index", "first_convergence_session_index"):
            value = getattr(self, name)
            object.__setattr__(self, name, None if value is None else _counter(name, value))
        if self.support_count != len(self.member_session_indices):
            raise ValueError("support_count must equal member_session_indices length")
        if self.window_size != len(self.window_session_indices):
            raise ValueError("window_size must equal window_session_indices length")
        if not set(self.valid_window_session_indices).issubset(
            self.window_session_indices
        ):
            raise ValueError("valid window indices must belong to the selected window")
        if not set(self.member_session_indices).issubset(self.valid_window_session_indices):
            raise ValueError("cluster members must belong to the valid window")
        if set(self.member_session_indices) & set(self.outlier_session_indices):
            raise ValueError("cluster members and outliers must be disjoint")
        cluster_optionals = (
            self.holder_id,
            self.maximum_pairwise_distance,
            self.mean_pairwise_distance,
            self.medoid_session_index,
            self.medoid_hue_degree,
            self.medoid_blink_bpm,
            self.circular_mean_hue_degree,
            self.median_blink_bpm,
        )
        if self.support_count == 0 and any(value is not None for value in cluster_optionals):
            raise ValueError("an empty cluster cannot carry cluster diagnostics")
        if self.support_count > 0 and any(value is None for value in cluster_optionals):
            raise ValueError("a non-empty cluster requires every cluster diagnostic")
        if self.support_count > 0 and set(
            (*self.member_session_indices, *self.outlier_session_indices)
        ) != set(self.valid_window_session_indices):
            raise ValueError("cluster members and outliers must partition the valid window")
        if self.currently_converged != (self.support_count >= self.required_sessions):
            raise ValueError("currently_converged differs from cluster support")
        converged_states = {
            "converged_monitoring",
            "converged_monitoring_latest_outlier",
        }
        if self.currently_converged != (self.convergence_state in converged_states):
            raise ValueError("convergence state differs from currently_converged")

    @property
    def post_convergence_valid_session_count(self) -> int:
        """Count valid primary observations after first convergence."""

        return (
            self.post_convergence_cluster_member_count
            + self.post_convergence_outlier_count
        )

    @property
    def post_convergence_outlier_rate(self) -> float:
        """Exclude invalid sessions from the monitoring-rate denominator."""

        count = self.post_convergence_valid_session_count
        return 0.0 if count == 0 else self.post_convergence_outlier_count / count

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
    def from_dict(cls, values: Mapping[str, Any]) -> RollingConvergenceRecord:
        if not isinstance(values, Mapping):
            raise TypeError("convergence record values must be a mapping")
        _exact_fields(values, set(cls.__dataclass_fields__), "convergence record")
        normalized = dict(values)
        for name in (
            "window_session_indices",
            "valid_window_session_indices",
            "member_session_indices",
            "outlier_session_indices",
        ):
            normalized[name] = tuple(normalized[name])
        return cls(**normalized)

    @classmethod
    def from_json(cls, encoded: str) -> RollingConvergenceRecord:
        return cls.from_dict(_strict_object(encoded, "convergence record"))


__all__ = [
    "CONVERGENCE_STATES",
    "ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION",
    "RollingConvergenceRecord",
    "SessionPatternObservation",
]
