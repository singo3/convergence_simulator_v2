"""Recurrent per-life BPM attractor diagnostics over the latest 18 votes."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from itertools import combinations

from .config import StructuredConvergenceConfig
from .records import (
    LifeAttractorRecord,
    MultiAttractorRecord,
    StructuredSessionObservation,
)


@dataclass(frozen=True, slots=True)
class _LifeCandidate:
    members: tuple[StructuredSessionObservation, ...]
    bpm_range: float
    median_bpm: float
    mean_absolute_deviation: float

    @property
    def indices(self) -> tuple[int, ...]:
        return tuple(sorted(item.session_index for item in self.members))


def _candidate_selection_key(candidate: _LifeCandidate) -> tuple[object, ...]:
    newest_first = tuple(sorted(candidate.indices, reverse=True))
    return (
        -len(candidate.members),
        candidate.bpm_range,
        candidate.mean_absolute_deviation,
        tuple(-index for index in newest_first),
        candidate.indices,
    )


def _candidate_for_members(
    members: tuple[StructuredSessionObservation, ...],
) -> _LifeCandidate:
    bpms = tuple(item.blink_bpm for item in members)
    if any(value is None for value in bpms):
        raise RuntimeError("valid per-life observation lost BPM")
    values = tuple(float(value) for value in bpms if value is not None)
    median = float(statistics.median(values))
    return _LifeCandidate(
        members=tuple(sorted(members, key=lambda item: item.session_index)),
        bpm_range=max(values) - min(values),
        median_bpm=median,
        mean_absolute_deviation=statistics.fmean(abs(value - median) for value in values),
    )


def _select_life_cluster(
    observations: tuple[StructuredSessionObservation, ...],
    config: StructuredConvergenceConfig,
) -> _LifeCandidate | None:
    """Enumerate all distinct closed BPM intervals, equivalent to best 1-D subsets."""

    if len(observations) < config.multi_minimum_cluster_support:
        return None
    ordered = tuple(sorted(observations, key=lambda item: (item.blink_bpm, item.session_index)))
    candidate_by_indices: dict[tuple[int, ...], _LifeCandidate] = {}
    for start in range(len(ordered)):
        for end in range(start + config.multi_minimum_cluster_support - 1, len(ordered)):
            first_bpm = ordered[start].blink_bpm
            last_bpm = ordered[end].blink_bpm
            assert first_bpm is not None and last_bpm is not None
            if last_bpm - first_bpm > config.multi_maximum_cluster_range:
                break
            candidate = _candidate_for_members(ordered[start : end + 1])
            candidate_by_indices[candidate.indices] = candidate
    if not candidate_by_indices:
        return None
    return min(candidate_by_indices.values(), key=_candidate_selection_key)


def _medoid(candidate: _LifeCandidate) -> StructuredSessionObservation:
    def key(item: StructuredSessionObservation) -> tuple[float, int, float]:
        assert item.blink_bpm is not None
        total = sum(
            abs(item.blink_bpm - other.blink_bpm)  # type: ignore[operator]
            for other in candidate.members
        )
        return total, -item.session_index, item.blink_bpm

    return min(candidate.members, key=key)


def _life_record(
    life_id: str,
    observations: tuple[StructuredSessionObservation, ...],
    config: StructuredConvergenceConfig,
) -> LifeAttractorRecord:
    selected = _select_life_cluster(observations, config)
    if selected is None:
        return LifeAttractorRecord(
            life_id=life_id,
            occurrence_count=len(observations),
            support=0,
            support_fraction=0.0,
            member_session_indices=(),
            outlier_session_indices=tuple(item.session_index for item in observations),
            medoid_bpm=None,
            median_bpm=None,
            bpm_range=None,
            mean_absolute_deviation=None,
            valid_attractor=False,
        )
    member_indices = selected.indices
    support = len(selected.members)
    fraction = support / len(observations)
    medoid = _medoid(selected)
    assert medoid.blink_bpm is not None
    valid = bool(
        len(observations) >= config.multi_minimum_life_occurrences
        and support >= config.multi_minimum_cluster_support
        and fraction >= config.multi_minimum_cluster_fraction
        and selected.bpm_range <= config.multi_maximum_cluster_range
    )
    return LifeAttractorRecord(
        life_id=life_id,
        occurrence_count=len(observations),
        support=support,
        support_fraction=fraction,
        member_session_indices=member_indices,
        outlier_session_indices=tuple(
            item.session_index
            for item in observations
            if item.session_index not in set(member_indices)
        ),
        medoid_bpm=medoid.blink_bpm,
        median_bpm=selected.median_bpm,
        bpm_range=selected.bpm_range,
        mean_absolute_deviation=selected.mean_absolute_deviation,
        valid_attractor=valid,
    )


def evaluate_multi_attractor(
    valid_observations: tuple[StructuredSessionObservation, ...],
    config: StructuredConvergenceConfig,
    *,
    first_confirmed_session_index: int | None = None,
) -> MultiAttractorRecord:
    window = valid_observations[-config.multi_window_sessions :]
    life_ids = tuple(sorted({item.holder_id for item in window if item.holder_id is not None}))
    records = tuple(
        _life_record(
            life_id,
            tuple(item for item in window if item.holder_id == life_id),
            config,
        )
        for life_id in life_ids
    )
    valid_records = tuple(record for record in records if record.valid_attractor)
    medoids = tuple(record.medoid_bpm for record in valid_records if record.medoid_bpm is not None)
    separation = (
        None
        if len(medoids) < 2
        else min(abs(first - second) for first, second in combinations(medoids, 2))
    )
    confirmed = bool(
        len(valid_records) >= 2
        and separation is not None
        and separation >= config.multi_minimum_attractor_separation
    )
    return MultiAttractorRecord(
        valid_window_session_indices=tuple(item.session_index for item in window),
        life_attractors=records,
        attractor_count=len(valid_records),
        attractor_separation=separation,
        two_attractor_flag=confirmed,
        three_attractor_flag=confirmed and len(valid_records) >= 3,
        confirmed=confirmed,
        first_confirmed_session_index=first_confirmed_session_index,
    )


__all__ = ["evaluate_multi_attractor"]
