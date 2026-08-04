"""Cross-life exhaustive common-BPM concentration diagnostic."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from itertools import combinations

from .config import StructuredConvergenceConfig
from .records import BpmCommonRecord, StructuredSessionObservation


@dataclass(frozen=True, slots=True)
class _BpmCandidate:
    members: tuple[StructuredSessionObservation, ...]
    bpm_range: float
    median_bpm: float
    mean_absolute_deviation: float

    @property
    def indices(self) -> tuple[int, ...]:
        return tuple(item.session_index for item in self.members)


def _candidate(
    members: tuple[StructuredSessionObservation, ...],
    maximum_range: float,
) -> _BpmCandidate | None:
    bpms = tuple(item.blink_bpm for item in members)
    if any(value is None for value in bpms):
        raise RuntimeError("valid observation lost BPM")
    values = tuple(float(value) for value in bpms if value is not None)
    spread = max(values) - min(values)
    if spread > maximum_range:
        return None
    median = float(statistics.median(values))
    return _BpmCandidate(
        members=members,
        bpm_range=spread,
        median_bpm=median,
        mean_absolute_deviation=statistics.fmean(abs(value - median) for value in values),
    )


def _selection_key(candidate: _BpmCandidate) -> tuple[object, ...]:
    newest_first = tuple(sorted(candidate.indices, reverse=True))
    return (
        -len(candidate.members),
        candidate.bpm_range,
        candidate.mean_absolute_deviation,
        tuple(-index for index in newest_first),
        candidate.indices,
    )


def _medoid(candidate: _BpmCandidate) -> StructuredSessionObservation:
    def key(item: StructuredSessionObservation) -> tuple[float, int, float]:
        assert item.blink_bpm is not None
        total = sum(
            abs(item.blink_bpm - other.blink_bpm)  # type: ignore[operator]
            for other in candidate.members
        )
        return total, -item.session_index, item.blink_bpm

    return min(candidate.members, key=key)


def evaluate_bpm_common(
    valid_observations: tuple[StructuredSessionObservation, ...],
    config: StructuredConvergenceConfig,
    *,
    first_confirmed_session_index: int | None = None,
) -> BpmCommonRecord:
    """Evaluate every bounded subset without using holder ID in selection."""

    window = valid_observations[-config.bpm_window_sessions :]
    sufficient = len(window) == config.bpm_window_sessions
    candidates = (
        tuple(
            candidate
            for size in range(config.bpm_required_sessions, len(window) + 1)
            for subset in combinations(window, size)
            for candidate in (_candidate(subset, config.bpm_maximum_range),)
            if candidate is not None
        )
        if sufficient
        else ()
    )
    if not candidates:
        return BpmCommonRecord(
            valid_window_session_indices=tuple(item.session_index for item in window),
            sufficient_sessions=sufficient,
            support=0,
            member_session_indices=(),
            outlier_session_indices=tuple(item.session_index for item in window),
            medoid_bpm=None,
            median_bpm=None,
            bpm_range=None,
            mean_absolute_deviation=None,
            participating_life_ids=(),
            cross_life=False,
            confirmed=False,
            first_confirmed_session_index=first_confirmed_session_index,
        )
    selected = min(candidates, key=_selection_key)
    member_indices = selected.indices
    medoid = _medoid(selected)
    assert medoid.blink_bpm is not None
    life_ids = tuple(
        sorted({item.holder_id for item in selected.members if item.holder_id is not None})
    )
    return BpmCommonRecord(
        valid_window_session_indices=tuple(item.session_index for item in window),
        sufficient_sessions=True,
        support=len(selected.members),
        member_session_indices=member_indices,
        outlier_session_indices=tuple(
            item.session_index for item in window if item.session_index not in set(member_indices)
        ),
        medoid_bpm=medoid.blink_bpm,
        median_bpm=selected.median_bpm,
        bpm_range=selected.bpm_range,
        mean_absolute_deviation=selected.mean_absolute_deviation,
        participating_life_ids=life_ids,
        cross_life=len(life_ids) >= 2,
        confirmed=True,
        first_confirmed_session_index=first_confirmed_session_index,
    )


__all__ = ["evaluate_bpm_common"]
