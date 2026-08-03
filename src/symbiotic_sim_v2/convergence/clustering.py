"""Bounded exhaustive same-life complete-link clustering for Stage 8A."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from itertools import combinations

from .config import RollingConvergenceConfig
from .pattern_distance import pattern_distance
from .records import SessionPatternObservation


@dataclass(frozen=True, slots=True)
class PatternCluster:
    support_count: int
    holder_id: str
    member_session_indices: tuple[int, ...]
    outlier_session_indices: tuple[int, ...]
    maximum_pairwise_distance: float
    mean_pairwise_distance: float
    medoid_session_index: int
    medoid_hue_degree: float
    medoid_blink_bpm: float
    circular_mean_hue_degree: float
    median_blink_bpm: float


@dataclass(frozen=True, slots=True)
class _Candidate:
    members: tuple[SessionPatternObservation, ...]
    distances: tuple[float, ...]
    maximum_distance: float
    mean_distance: float

    @property
    def holder_id(self) -> str:
        holder = self.members[0].holder_id
        if holder is None:
            raise RuntimeError("valid cluster member lost holder ID")
        return holder

    @property
    def indices(self) -> tuple[int, ...]:
        return tuple(member.session_index for member in self.members)


def _candidate(
    members: tuple[SessionPatternObservation, ...],
    config: RollingConvergenceConfig,
) -> _Candidate | None:
    if len({member.holder_id for member in members}) != 1:
        return None
    distances = tuple(
        pattern_distance(first, second, config)
        for first, second in combinations(members, 2)
    )
    if any(distance > 1.0 for distance in distances):
        return None
    return _Candidate(
        members=members,
        distances=distances,
        maximum_distance=max(distances),
        mean_distance=statistics.fmean(distances),
    )


def _selection_key(candidate: _Candidate) -> tuple[object, ...]:
    # Lower tuple wins. Negated descending indices implement the explicit
    # "more recent sessions" priority before lexical identity fallbacks.
    newest_first = tuple(sorted(candidate.indices, reverse=True))
    return (
        -len(candidate.members),
        candidate.maximum_distance,
        candidate.mean_distance,
        tuple(-index for index in newest_first),
        candidate.holder_id,
        candidate.indices,
    )


def _medoid(
    candidate: _Candidate,
    config: RollingConvergenceConfig,
) -> SessionPatternObservation:
    def key(member: SessionPatternObservation) -> tuple[float, int]:
        total = sum(
            0.0 if other is member else pattern_distance(member, other, config)
            for other in candidate.members
        )
        # A newest-session tie-break makes duplicated patterns deterministic.
        return total, -member.session_index

    return min(candidate.members, key=key)


def _circular_mean_hue(
    members: tuple[SessionPatternObservation, ...],
    *,
    fallback_hue_degree: float,
) -> float:
    radians = tuple(
        math.radians(member.hue_degree % 360.0)  # type: ignore[operator]
        for member in members
    )
    x = statistics.fmean(math.cos(value) for value in radians)
    y = statistics.fmean(math.sin(value) for value in radians)
    if math.hypot(x, y) <= 1.0e-12:
        return fallback_hue_degree % 360.0
    return math.degrees(math.atan2(y, x)) % 360.0


def select_dominant_cluster(
    valid_window: tuple[SessionPatternObservation, ...],
    config: RollingConvergenceConfig,
) -> PatternCluster | None:
    """Evaluate every bounded subset and return the uniquely ordered winner."""

    if not isinstance(config, RollingConvergenceConfig):
        raise TypeError("config must be a RollingConvergenceConfig")
    if any(not isinstance(item, SessionPatternObservation) for item in valid_window):
        raise TypeError("valid_window must contain SessionPatternObservation values")
    if any(not item.valid_for_convergence for item in valid_window):
        raise ValueError("valid_window cannot contain invalid observations")
    if len(valid_window) > config.window_sessions:
        raise ValueError("valid_window exceeds configured window_sessions")
    ordered = tuple(sorted(valid_window, key=lambda item: item.session_index))
    if len({item.session_index for item in ordered}) != len(ordered):
        raise ValueError("valid_window session indices must be unique")
    candidates = tuple(
        candidate
        for size in range(config.required_sessions, len(ordered) + 1)
        for subset in combinations(ordered, size)
        for candidate in (_candidate(subset, config),)
        if candidate is not None
    )
    if not candidates:
        return None
    selected = min(candidates, key=_selection_key)
    medoid = _medoid(selected, config)
    if medoid.hue_degree is None or medoid.blink_bpm is None:
        raise RuntimeError("valid medoid lost its physical pattern")
    member_indices = selected.indices
    valid_indices = tuple(item.session_index for item in ordered)
    bpm_values = tuple(
        item.blink_bpm for item in selected.members if item.blink_bpm is not None
    )
    return PatternCluster(
        support_count=len(selected.members),
        holder_id=selected.holder_id,
        member_session_indices=member_indices,
        outlier_session_indices=tuple(
            index for index in valid_indices if index not in set(member_indices)
        ),
        maximum_pairwise_distance=selected.maximum_distance,
        mean_pairwise_distance=selected.mean_distance,
        medoid_session_index=medoid.session_index,
        medoid_hue_degree=medoid.hue_degree,
        medoid_blink_bpm=medoid.blink_bpm,
        circular_mean_hue_degree=_circular_mean_hue(
            selected.members,
            fallback_hue_degree=medoid.hue_degree,
        ),
        median_blink_bpm=float(statistics.median(bpm_values)),
    )


__all__ = ["PatternCluster", "select_dominant_cluster"]
