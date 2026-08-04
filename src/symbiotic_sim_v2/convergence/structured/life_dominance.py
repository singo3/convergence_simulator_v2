"""Hue-independent Digital Life dominance with one-gap tolerance."""

from __future__ import annotations

from collections import Counter

from .config import StructuredConvergenceConfig
from .records import LifeDominanceRecord, StructuredSessionObservation


def _longest_boolean_run(values: tuple[bool, ...], *, target: bool) -> int:
    longest = current = 0
    for value in values:
        if value is target:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _one_outlier_tolerant_longest(values: tuple[bool, ...]) -> int:
    longest = start = outliers = 0
    for end, is_dominant in enumerate(values):
        if not is_dominant:
            outliers += 1
        while outliers > 1:
            if not values[start]:
                outliers -= 1
            start += 1
        longest = max(longest, end - start + 1)
    return longest


def _candidate_metrics(
    window: tuple[StructuredSessionObservation, ...],
    life_id: str,
) -> tuple[int, int, int]:
    flags = tuple(item.holder_id == life_id for item in window)
    count = sum(flags)
    tolerant = _one_outlier_tolerant_longest(flags)
    latest = max(item.session_index for item in window if item.holder_id == life_id)
    return count, tolerant, latest


def _dominant_life(window: tuple[StructuredSessionObservation, ...]) -> str | None:
    life_ids = tuple(sorted({item.holder_id for item in window if item.holder_id is not None}))
    if not life_ids:
        return None
    return min(
        life_ids,
        key=lambda life_id: (
            -_candidate_metrics(window, life_id)[0],
            -_candidate_metrics(window, life_id)[1],
            -_candidate_metrics(window, life_id)[2],
            life_id,
        ),
    )


def _return_metrics(
    flags: tuple[bool, ...],
) -> tuple[int, int, float, int, float]:
    opportunities = within_one = within_two = 0
    position = 0
    while position < len(flags):
        if flags[position]:
            position += 1
            continue
        start = position
        while position < len(flags) and not flags[position]:
            position += 1
        if start == 0 or not flags[start - 1]:
            continue
        opportunities += 1
        if position < len(flags):
            outlier_length = position - start
            if outlier_length <= 1:
                within_one += 1
            if outlier_length <= 2:
                within_two += 1
    one_rate = 0.0 if opportunities == 0 else within_one / opportunities
    two_rate = 0.0 if opportunities == 0 else within_two / opportunities
    return opportunities, within_one, one_rate, within_two, two_rate


def evaluate_life_dominance(
    valid_observations: tuple[StructuredSessionObservation, ...],
    config: StructuredConvergenceConfig,
    *,
    first_confirmed_session_index: int | None = None,
) -> LifeDominanceRecord:
    """Evaluate only holder identity; Hue and BPM are deliberately unused."""

    window = valid_observations[-config.life_window_sessions :]
    sufficient = len(window) == config.life_window_sessions
    dominant = _dominant_life(window)
    if dominant is None:
        return LifeDominanceRecord(
            valid_window_session_indices=(),
            sufficient_sessions=False,
            dominant_life_id=None,
            dominant_count=0,
            share=0.0,
            strict_consecutive_run=0,
            one_outlier_tolerant_longest_run=0,
            maximum_consecutive_outliers=0,
            latest_session_outlier=False,
            return_opportunity_count=0,
            return_within_one_session_count=0,
            return_within_one_session_rate=0.0,
            return_within_two_sessions_count=0,
            return_within_two_sessions_rate=0.0,
            confirmed=False,
            first_confirmed_session_index=first_confirmed_session_index,
        )
    flags = tuple(item.holder_id == dominant for item in window)
    count = Counter(item.holder_id for item in window)[dominant]
    non_dominant_count = len(window) - count
    maximum_outliers = _longest_boolean_run(flags, target=False)
    confirmed = bool(
        sufficient
        and count >= config.life_required_sessions
        and non_dominant_count <= config.life_window_sessions - config.life_required_sessions
        and maximum_outliers <= config.life_maximum_consecutive_outliers
    )
    opportunities, within_one, one_rate, within_two, two_rate = _return_metrics(flags)
    return LifeDominanceRecord(
        valid_window_session_indices=tuple(item.session_index for item in window),
        sufficient_sessions=sufficient,
        dominant_life_id=dominant,
        dominant_count=count,
        share=0.0 if not window else count / len(window),
        strict_consecutive_run=_longest_boolean_run(flags, target=True),
        one_outlier_tolerant_longest_run=_one_outlier_tolerant_longest(flags),
        maximum_consecutive_outliers=maximum_outliers,
        latest_session_outlier=not flags[-1],
        return_opportunity_count=opportunities,
        return_within_one_session_count=within_one,
        return_within_one_session_rate=one_rate,
        return_within_two_sessions_count=within_two,
        return_within_two_sessions_rate=two_rate,
        confirmed=confirmed,
        first_confirmed_session_index=first_confirmed_session_index,
    )


__all__ = ["evaluate_life_dominance"]
