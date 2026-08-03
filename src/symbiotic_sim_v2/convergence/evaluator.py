"""Stateful and pure rolling-majority convergence diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from .clustering import PatternCluster, select_dominant_cluster
from .config import RollingConvergenceConfig
from .pattern_distance import pattern_distance
from .records import (
    ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION,
    RollingConvergenceRecord,
    SessionPatternObservation,
)


def _normalize_observation(value: object) -> SessionPatternObservation:
    return (
        value
        if isinstance(value, SessionPatternObservation)
        else SessionPatternObservation.from_outcome(value)
    )


def _window(
    observations: tuple[SessionPatternObservation, ...],
    config: RollingConvergenceConfig,
) -> tuple[
    tuple[SessionPatternObservation, ...],
    tuple[SessionPatternObservation, ...],
]:
    eligible = (
        tuple(item for item in observations if item.valid_for_convergence)
        if config.use_valid_sessions_only
        else observations
    )
    selected = eligible[-config.window_sessions :]
    valid = tuple(item for item in selected if item.valid_for_convergence)
    return selected, valid


def _empty_cluster_fields() -> dict[str, object]:
    return {
        "support_count": 0,
        "holder_id": None,
        "member_session_indices": (),
        "outlier_session_indices": (),
        "maximum_pairwise_distance": None,
        "mean_pairwise_distance": None,
        "medoid_session_index": None,
        "medoid_hue_degree": None,
        "medoid_blink_bpm": None,
        "circular_mean_hue_degree": None,
        "median_blink_bpm": None,
    }


def _cluster_fields(cluster: PatternCluster | None) -> dict[str, object]:
    if cluster is None:
        return _empty_cluster_fields()
    return {
        "support_count": cluster.support_count,
        "holder_id": cluster.holder_id,
        "member_session_indices": cluster.member_session_indices,
        "outlier_session_indices": cluster.outlier_session_indices,
        "maximum_pairwise_distance": cluster.maximum_pairwise_distance,
        "mean_pairwise_distance": cluster.mean_pairwise_distance,
        "medoid_session_index": cluster.medoid_session_index,
        "medoid_hue_degree": cluster.medoid_hue_degree,
        "medoid_blink_bpm": cluster.medoid_blink_bpm,
        "circular_mean_hue_degree": cluster.circular_mean_hue_degree,
        "median_blink_bpm": cluster.median_blink_bpm,
    }


def _initial_records(
    observations: tuple[SessionPatternObservation, ...],
    config: RollingConvergenceConfig,
) -> tuple[RollingConvergenceRecord, ...]:
    records: list[RollingConvergenceRecord] = []
    first_convergence: int | None = None
    for position, observation in enumerate(observations):
        history = observations[: position + 1]
        selected_window, valid_window = _window(history, config)
        window_is_complete = len(selected_window) == config.window_sessions
        enough_valid = len(valid_window) >= config.required_sessions
        sufficient = window_is_complete and enough_valid
        cluster = (
            select_dominant_cluster(valid_window, config)
            if sufficient
            else None
        )
        converged = cluster is not None
        if converged and first_convergence is None:
            first_convergence = observation.session_index
        latest_valid_index = (
            None if not valid_window else valid_window[-1].session_index
        )
        latest_is_outlier = bool(
            cluster is not None
            and latest_valid_index in cluster.outlier_session_indices
        )
        if not sufficient:
            state = "insufficient_valid_sessions"
        elif converged and latest_is_outlier:
            state = "converged_monitoring_latest_outlier"
        elif converged:
            state = "converged_monitoring"
        elif first_convergence is None:
            state = "searching"
        else:
            state = "convergence_lost"
        records.append(
            RollingConvergenceRecord(
                evaluated_at_session_index=observation.session_index,
                local_time_us=observation.local_time_us,
                global_time_us=observation.global_time_us,
                window_session_indices=tuple(
                    item.session_index for item in selected_window
                ),
                valid_window_session_indices=tuple(
                    item.session_index for item in valid_window
                ),
                window_size=len(selected_window),
                required_sessions=config.required_sessions,
                currently_converged=converged,
                convergence_state=state,
                first_convergence_session_index=first_convergence,
                latest_valid_session_is_outlier=latest_is_outlier,
                total_sessions_after_first_convergence=0,
                post_convergence_cluster_member_count=0,
                post_convergence_outlier_count=0,
                latest_outlier_count=0,
                convergence_lost_count=0,
                reconvergence_count=0,
                dominant_cluster_switch_count=0,
                outlier_return_within_one_session_count=0,
                outlier_return_within_two_sessions_count=0,
                post_convergence_exploration_count=0,
                post_convergence_candidate_accepted_count=0,
                evaluator_version=config.evaluator_version,
                schema_version=ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION,
                **_cluster_fields(cluster),
            )
        )
    return tuple(records)


def _same_dominant_region(
    first: RollingConvergenceRecord,
    second: RollingConvergenceRecord,
    config: RollingConvergenceConfig,
) -> bool:
    if first.holder_id != second.holder_id:
        return False
    if first.holder_id is None:
        return False
    values = (
        first.medoid_hue_degree,
        first.medoid_blink_bpm,
        second.medoid_hue_degree,
        second.medoid_blink_bpm,
    )
    if any(value is None for value in values):
        return False
    left = SessionPatternObservation(
        session_index=first.evaluated_at_session_index,
        valid_for_convergence=True,
        invalid_reason=None,
        holder_id=first.holder_id,
        hue_degree=first.medoid_hue_degree,
        blink_bpm=first.medoid_blink_bpm,
        exploration_decision=None,
        candidate_generated=False,
        candidate_accepted=False,
    )
    right = SessionPatternObservation(
        session_index=second.evaluated_at_session_index,
        valid_for_convergence=True,
        invalid_reason=None,
        holder_id=second.holder_id,
        hue_degree=second.medoid_hue_degree,
        blink_bpm=second.medoid_blink_bpm,
        exploration_decision=None,
        candidate_generated=False,
        candidate_accepted=False,
    )
    return pattern_distance(left, right, config) <= 1.0


def _returns_to_cluster(
    observation: SessionPatternObservation,
    cluster_record: RollingConvergenceRecord,
    config: RollingConvergenceConfig,
) -> bool:
    if not observation.valid_for_convergence:
        return False
    if observation.holder_id != cluster_record.holder_id:
        return False
    if cluster_record.holder_id is None:
        return False
    reference = SessionPatternObservation(
        session_index=cluster_record.evaluated_at_session_index,
        valid_for_convergence=True,
        invalid_reason=None,
        holder_id=cluster_record.holder_id,
        hue_degree=cluster_record.medoid_hue_degree,
        blink_bpm=cluster_record.medoid_blink_bpm,
        exploration_decision=None,
        candidate_generated=False,
        candidate_accepted=False,
    )
    return pattern_distance(observation, reference, config) <= 1.0


def _with_monitoring_counters(
    observations: tuple[SessionPatternObservation, ...],
    records: tuple[RollingConvergenceRecord, ...],
    config: RollingConvergenceConfig,
) -> tuple[RollingConvergenceRecord, ...]:
    if not records:
        return ()
    first = next(
        (
            record.first_convergence_session_index
            for record in records
            if record.first_convergence_session_index is not None
        ),
        None,
    )
    updated: list[RollingConvergenceRecord] = []
    total_after = member_count = outlier_count = latest_outliers = 0
    lost_count = reconvergence_count = switch_count = 0
    return_one_count = return_two_count = 0
    explore_count = accepted_count = 0
    previous: RollingConvergenceRecord | None = None
    last_converged: RollingConvergenceRecord | None = None
    pending_outliers: list[tuple[int, RollingConvergenceRecord]] = []

    for position, (observation, record) in enumerate(zip(observations, records, strict=True)):
        after_first = first is not None and observation.session_index > first
        if after_first:
            total_after += 1
            if observation.exploration_decision == "explore":
                explore_count += 1
            if observation.candidate_accepted:
                accepted_count += 1
            if observation.valid_for_convergence:
                if observation.session_index in record.member_session_indices:
                    member_count += 1
                else:
                    outlier_count += 1
                if (
                    record.currently_converged
                    and observation.session_index in record.outlier_session_indices
                ):
                    latest_outliers += 1
                    pending_outliers.append((position, record))

        if previous is not None:
            if previous.currently_converged and record.convergence_state == "convergence_lost":
                lost_count += 1
            if (
                first is not None
                and not previous.currently_converged
                and record.currently_converged
                and observation.session_index != first
            ):
                reconvergence_count += 1
        if record.currently_converged and observation.valid_for_convergence:
            if last_converged is not None and not _same_dominant_region(
                last_converged,
                record,
                config,
            ):
                switch_count += 1
            last_converged = record

        still_pending: list[tuple[int, RollingConvergenceRecord]] = []
        for outlier_position, cluster_record in pending_outliers:
            delta = position - outlier_position
            if delta <= 0:
                still_pending.append((outlier_position, cluster_record))
                continue
            returned = _returns_to_cluster(observation, cluster_record, config)
            if returned:
                if delta <= 1:
                    return_one_count += 1
                if delta <= 2:
                    return_two_count += 1
                continue
            if delta < 2:
                still_pending.append((outlier_position, cluster_record))
        pending_outliers = still_pending

        updated.append(
            replace(
                record,
                total_sessions_after_first_convergence=total_after,
                post_convergence_cluster_member_count=member_count,
                post_convergence_outlier_count=outlier_count,
                latest_outlier_count=latest_outliers,
                convergence_lost_count=lost_count,
                reconvergence_count=reconvergence_count,
                dominant_cluster_switch_count=switch_count,
                outlier_return_within_one_session_count=return_one_count,
                outlier_return_within_two_sessions_count=return_two_count,
                post_convergence_exploration_count=explore_count,
                post_convergence_candidate_accepted_count=accepted_count,
            )
        )
        previous = record
    return tuple(updated)


def evaluate_convergence_history(
    outcomes_or_observations: Sequence[object],
    config: RollingConvergenceConfig,
) -> tuple[RollingConvergenceRecord, ...]:
    """Recompute the complete diagnostic history from immutable observations."""

    if not isinstance(config, RollingConvergenceConfig):
        raise TypeError("config must be a RollingConvergenceConfig")
    if isinstance(outcomes_or_observations, (str, bytes)) or not isinstance(
        outcomes_or_observations, Sequence
    ):
        raise TypeError("outcomes_or_observations must be a sequence")
    observations = tuple(_normalize_observation(value) for value in outcomes_or_observations)
    indices = tuple(item.session_index for item in observations)
    if any(
        current <= previous
        for previous, current in zip(indices, indices[1:], strict=False)
    ):
        raise ValueError("session indices must be strictly increasing")
    if len(observations) > config.maximum_sessions:
        raise ValueError("observation count exceeds maximum_sessions")
    base = _initial_records(observations, config)
    return _with_monitoring_counters(observations, base, config)


def evaluate_rolling_convergence(
    outcomes_or_observations: Sequence[object],
    config: RollingConvergenceConfig,
) -> RollingConvergenceRecord:
    """Return the current record for one complete outcome history."""

    records = evaluate_convergence_history(outcomes_or_observations, config)
    if not records:
        raise ValueError("at least one session outcome is required")
    return records[-1]


class RollingConvergenceEvaluator:
    """Append-only convenience wrapper; every result remains pure and replayable."""

    def __init__(
        self,
        config: RollingConvergenceConfig,
        outcomes_or_observations: Sequence[object] = (),
        *,
        expected_records: Sequence[RollingConvergenceRecord] | None = None,
    ) -> None:
        if not isinstance(config, RollingConvergenceConfig):
            raise TypeError("config must be a RollingConvergenceConfig")
        self._config = config
        self._observations = tuple(
            _normalize_observation(value) for value in outcomes_or_observations
        )
        self._records = evaluate_convergence_history(self._observations, config)
        if expected_records is not None and tuple(expected_records) != self._records:
            raise ValueError("stored convergence records do not match replayed outcomes")

    @property
    def config(self) -> RollingConvergenceConfig:
        return self._config

    def observations(self) -> tuple[SessionPatternObservation, ...]:
        return self._observations

    def records(self) -> tuple[RollingConvergenceRecord, ...]:
        return self._records

    def current_record(self) -> RollingConvergenceRecord | None:
        return None if not self._records else self._records[-1]

    def update(self, outcome_or_observation: object) -> RollingConvergenceRecord:
        observation = _normalize_observation(outcome_or_observation)
        if self._observations and (
            observation.session_index <= self._observations[-1].session_index
        ):
            raise ValueError("session indices must be appended in increasing order")
        if len(self._observations) >= self._config.maximum_sessions:
            raise RuntimeError("maximum_sessions has already been reached")
        self._observations = (*self._observations, observation)
        self._records = evaluate_convergence_history(
            self._observations,
            self._config,
        )
        return self._records[-1]


__all__ = [
    "RollingConvergenceEvaluator",
    "evaluate_convergence_history",
    "evaluate_rolling_convergence",
]
