"""Pure replayable Stage 8A.1 structured convergence evaluator."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from symbiotic_sim_v2.convergence.config import RollingConvergenceConfig
from symbiotic_sim_v2.convergence.evaluator import evaluate_convergence_history
from symbiotic_sim_v2.convergence.records import SessionPatternObservation

from .bpm_common import evaluate_bpm_common
from .classification import classify_structured_convergence
from .config import StructuredConvergenceConfig
from .life_dominance import evaluate_life_dominance
from .mechanical_rotation import evaluate_mechanical_rotation
from .multi_attractor import evaluate_multi_attractor
from .records import StructuredConvergenceRecord, StructuredSessionObservation


def _normalize(value: object) -> StructuredSessionObservation:
    return (
        value
        if isinstance(value, StructuredSessionObservation)
        else StructuredSessionObservation.from_outcome(value)
    )


def _early_signal(
    observations: tuple[StructuredSessionObservation, ...],
    config: StructuredConvergenceConfig,
) -> bool:
    legacy = tuple(
        SessionPatternObservation(
            session_index=item.session_index,
            valid_for_convergence=item.valid_for_convergence,
            invalid_reason=(
                None if item.valid_for_convergence else item.invalid_reason or "invalid_session"
            ),
            holder_id=item.holder_id,
            hue_degree=item.hue_degree,
            blink_bpm=item.blink_bpm,
            exploration_decision=item.exploration_decision,
            candidate_generated=item.candidate_generated,
            candidate_accepted=item.candidate_accepted,
        )
        for item in observations
    )
    if not legacy:
        return False
    records = evaluate_convergence_history(
        legacy,
        RollingConvergenceConfig(maximum_sessions=config.maximum_sessions),
    )
    return records[-1].currently_converged


def evaluate_structured_convergence_history(
    outcomes_or_observations: Sequence[object],
    config: StructuredConvergenceConfig | None = None,
) -> tuple[StructuredConvergenceRecord, ...]:
    """Recompute all records from immutable observations, without Core callbacks."""

    selected_config = StructuredConvergenceConfig() if config is None else config
    if not isinstance(selected_config, StructuredConvergenceConfig):
        raise TypeError("config must be a StructuredConvergenceConfig")
    if isinstance(outcomes_or_observations, (str, bytes)) or not isinstance(
        outcomes_or_observations,
        Sequence,
    ):
        raise TypeError("outcomes_or_observations must be a sequence")
    observations = tuple(_normalize(item) for item in outcomes_or_observations)
    indices = tuple(item.session_index for item in observations)
    if any(current <= previous for previous, current in zip(indices, indices[1:], strict=False)):
        raise ValueError("session indices must be strictly increasing")
    if len(observations) > selected_config.maximum_sessions:
        raise ValueError("observation count exceeds maximum_sessions")
    records: list[StructuredConvergenceRecord] = []
    first_life: int | None = None
    first_bpm: int | None = None
    first_multi: int | None = None
    for position, observation in enumerate(observations):
        history = observations[: position + 1]
        valid = tuple(item for item in history if item.valid_for_convergence)
        life = evaluate_life_dominance(
            valid,
            selected_config,
            first_confirmed_session_index=first_life,
        )
        if life.confirmed and first_life is None:
            first_life = observation.session_index
            life = replace(life, first_confirmed_session_index=first_life)
        bpm = evaluate_bpm_common(
            valid,
            selected_config,
            first_confirmed_session_index=first_bpm,
        )
        if bpm.confirmed and first_bpm is None:
            first_bpm = observation.session_index
            bpm = replace(bpm, first_confirmed_session_index=first_bpm)
        multi = evaluate_multi_attractor(
            valid,
            selected_config,
            first_confirmed_session_index=first_multi,
        )
        if multi.confirmed and first_multi is None:
            first_multi = observation.session_index
            multi = replace(multi, first_confirmed_session_index=first_multi)
        classification = classify_structured_convergence(
            sufficient_sessions=(
                len(valid)
                >= max(
                    selected_config.life_window_sessions,
                    selected_config.bpm_window_sessions,
                )
            ),
            life_dominant=life.confirmed,
            bpm_common=bpm.confirmed,
            multi_attractor=multi.confirmed,
            bpm_common_cross_life=bpm.cross_life,
        )
        mechanical = evaluate_mechanical_rotation(valid)
        life_window_count = len(life.valid_window_session_indices)
        bpm_window_count = len(bpm.valid_window_session_indices)
        one_gap_score = (
            0.0
            if life_window_count == 0
            else life.one_outlier_tolerant_longest_run / life_window_count
        )
        records.append(
            StructuredConvergenceRecord(
                evaluated_at_session_index=observation.session_index,
                valid_session_count=len(valid),
                early_single_life_pattern_signal=_early_signal(history, selected_config),
                life_dominance=life,
                bpm_common=bpm,
                multi_attractor=multi,
                mechanical_rotation=mechanical,
                life_dominance_score=life.share,
                bpm_common_score=(
                    0.0 if bpm_window_count == 0 else bpm.support / bpm_window_count
                ),
                multi_attractor_score=min(1.0, multi.attractor_count / 3.0),
                mechanical_rotation_score=max(
                    mechanical.three_distinct_life_window_rate,
                    mechanical.immediate_return_rate,
                    mechanical.three_life_cycle_rate,
                ),
                one_gap_tolerant_continuity_flag=bool(
                    life.sufficient_sessions
                    and life.one_outlier_tolerant_longest_run
                    >= selected_config.life_required_sessions
                ),
                one_gap_tolerant_continuity_score=one_gap_score,
                temporary_outlier_and_return_flag=bool(
                    life.return_opportunity_count > 0
                    and life.return_within_two_sessions_count > 0
                ),
                temporary_outlier_and_return_score=(
                    life.return_within_two_sessions_rate
                ),
                life_dominant_converged=life.confirmed,
                bpm_common_converged=bpm.confirmed,
                multi_attractor_converged=multi.confirmed,
                three_attractor_converged=multi.three_attractor_flag,
                summary_classification=classification,
            )
        )
    return tuple(records)


class StructuredConvergenceEvaluator:
    """Append-only convenience API for single-session and run-all execution."""

    def __init__(
        self,
        config: StructuredConvergenceConfig | None = None,
        outcomes_or_observations: Sequence[object] = (),
    ) -> None:
        self._config = StructuredConvergenceConfig() if config is None else config
        if not isinstance(self._config, StructuredConvergenceConfig):
            raise TypeError("config must be a StructuredConvergenceConfig")
        self._observations = tuple(_normalize(item) for item in outcomes_or_observations)
        self._records = evaluate_structured_convergence_history(
            self._observations,
            self._config,
        )

    @property
    def config(self) -> StructuredConvergenceConfig:
        return self._config

    def observations(self) -> tuple[StructuredSessionObservation, ...]:
        return self._observations

    def records(self) -> tuple[StructuredConvergenceRecord, ...]:
        return self._records

    def latest_record(self) -> StructuredConvergenceRecord | None:
        return None if not self._records else self._records[-1]

    current_record = latest_record

    @property
    def latest_classification(self) -> str:
        latest = self.latest_record()
        return "insufficient_sessions" if latest is None else latest.summary_classification

    def append(self, outcome_or_observation: object) -> StructuredConvergenceRecord:
        observation = _normalize(outcome_or_observation)
        if self._observations and observation.session_index <= self._observations[-1].session_index:
            raise ValueError("session indices must be appended in increasing order")
        if len(self._observations) >= self._config.maximum_sessions:
            raise RuntimeError("maximum_sessions has already been reached")
        self._observations = (*self._observations, observation)
        self._records = evaluate_structured_convergence_history(
            self._observations,
            self._config,
        )
        return self._records[-1]

    update = append


__all__ = [
    "StructuredConvergenceEvaluator",
    "evaluate_structured_convergence_history",
]
