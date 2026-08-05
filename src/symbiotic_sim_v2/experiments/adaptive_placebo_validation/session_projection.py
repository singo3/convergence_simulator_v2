"""Project existing closed/open-loop components into Stage 8A.3 records."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import asdict

from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
    light_stimulus_state_payload,
    parse_light_stimulus_state_event,
)
from symbiotic_sim_v2.devices.virtual_light.records import LightStimulusStateRecord
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import sha256_canonical
from symbiotic_sim_v2.garden.input_layer.records import GardenEvaluationRecord
from symbiotic_sim_v2.runtime.experimental_multi_session.session_outcome import (
    ExperimentalSessionOutcome,
)

from .config import AUTONOMOUS_ARM, YOKED_ARM, ValidationCondition
from .output_policy import RandomBundleOutput
from .records import BundleOutcome, ReplayLightState, SessionOutcome


def _evaluation_map(
    evaluations: Sequence[GardenEvaluationRecord],
) -> tuple[GardenEvaluationRecord | None, dict[int, GardenEvaluationRecord]]:
    baseline = next(
        (item for item in evaluations if item.evaluation_kind == "baseline"),
        None,
    )
    bundles = {
        item.bundle_index: item
        for item in evaluations
        if item.evaluation_kind == "bundle" and item.bundle_index is not None
    }
    return baseline, bundles


def _state_for_bundle(
    states: Sequence[LightStimulusStateRecord],
    bundle_index: int,
) -> LightStimulusStateRecord | None:
    last_evaluation_signal = (119, 179, 239)[bundle_index]
    return next(
        (
            item
            for item in reversed(states)
            if item.active and item.source_signal_index <= last_evaluation_signal
        ),
        None,
    )


def _w_from_n(baseline_n: float | None, bundle_n: float | None) -> float | None:
    if baseline_n is None or bundle_n is None:
        return None
    return max(0.0, min(1.0, 0.5 + (bundle_n - baseline_n) / 0.2))


def _anchor_or_trial(
    arm: str,
    bundle_index: int,
    outcome: ExperimentalSessionOutcome | None,
) -> str | None:
    if arm != AUTONOMOUS_ARM or outcome is None:
        return "replay" if arm == YOKED_ARM else "random"
    if bundle_index == 0:
        return "anchor"
    if not outcome.candidate_generated:
        return "anchor_hold"
    if bundle_index == 1:
        return "trial"
    if outcome.adoption_result in {"accepted", "rejected_after_confirmation"}:
        return "trial_confirmation"
    if outcome.adoption_result == "unconfirmed_evaluation_reject":
        return "trial_unconfirmed"
    return "anchor_return"


def replay_states_from_device(
    *,
    session_index: int,
    source_participant_id: str,
    states: Sequence[LightStimulusStateRecord],
) -> tuple[ReplayLightState, ...]:
    result = tuple(
        ReplayLightState(
            session_index=session_index,
            source_participant_id=source_participant_id,
            source_bundle_index=(
                None
                if not 60 <= state.source_signal_index < 240
                else (state.source_signal_index - 60) // 60
            ),
            scheduled_time_us=state.effective_time_us,
            payload=light_stimulus_state_payload(state),
        )
        for state in states
    )
    if len(result) != 241:
        raise RuntimeError("autonomous donor light sequence must contain 241 formal states")
    return result


def light_state_records_from_replay(
    replay_states: Sequence[ReplayLightState],
) -> tuple[LightStimulusStateRecord, ...]:
    result: list[LightStimulusStateRecord] = []
    for index, state in enumerate(replay_states):
        parsed = parse_light_stimulus_state_event(
            SimulationEvent(
                event_id=f"stage8a3-replay-{index}",
                event_type=LIGHT_STIMULUS_STATE_EVENT_TYPE,
                source=LIGHT_STIMULUS_STATE_EVENT_SOURCE,
                scheduled_time_us=state.scheduled_time_us,
                priority=LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
                sequence=index,
                payload=dict(state.payload),
            )
        )
        result.append(LightStimulusStateRecord(state_index=index, **asdict(parsed)))
    return tuple(result)


def project_validation_session(
    *,
    participant_id: str,
    user_type_id: str,
    response_strength_scale: float,
    condition: ValidationCondition,
    arm: str,
    session_index: int,
    physiology_seed: int,
    evaluations: Sequence[GardenEvaluationRecord],
    states: Sequence[LightStimulusStateRecord],
    engine_digest: str,
    autonomous_outcome: ExperimentalSessionOutcome | None = None,
    source_participant_id: str | None = None,
    random_outputs: tuple[
        RandomBundleOutput,
        RandomBundleOutput,
        RandomBundleOutput,
    ]
    | None = None,
) -> tuple[tuple[BundleOutcome, BundleOutcome, BundleOutcome], SessionOutcome]:
    baseline, bundle_evaluations = _evaluation_map(evaluations)
    baseline_rmssd = None if baseline is None else baseline.rmssd_ms
    baseline_n = None if baseline is None else baseline.n
    bundle_rows: list[BundleOutcome] = []
    for bundle_index in range(3):
        evaluation = bundle_evaluations.get(bundle_index)
        state = _state_for_bundle(states, bundle_index)
        rmssd = None if evaluation is None else evaluation.rmssd_ms
        n = None if evaluation is None else evaluation.n
        valid = bool(
            baseline is not None
            and baseline.is_valid
            and evaluation is not None
            and evaluation.is_valid
            and baseline_rmssd is not None
            and rmssd is not None
        )
        delta = None if not valid else rmssd - baseline_rmssd
        displayed_b = None if state is None else state.source_b
        displayed_life = None if state is None else state.qualification_holder_id
        hue = None if state is None else state.hue_degree
        bpm = None if state is None else state.blink_bpm
        source_session = session_index if arm == YOKED_ARM else None
        source_bundle = bundle_index if arm == YOKED_ARM else None
        output_seed = (
            None if random_outputs is None else random_outputs[bundle_index].output_seed
        )
        data_projection = {
            "participant_id": participant_id,
            "condition_id": condition.condition_id,
            "arm": arm,
            "session_index": session_index,
            "bundle_index": bundle_index,
            "baseline_rmssd_ms": baseline_rmssd,
            "bundle_rmssd_ms": rmssd,
            "delta_rmssd_ms": delta,
            "displayed_life_id": displayed_life,
            "displayed_hue_degree": hue,
            "displayed_blink_bpm": bpm,
        }
        bundle_rows.append(
            BundleOutcome(
                participant_id=participant_id,
                user_type_id=user_type_id,
                response_strength_scale=response_strength_scale,
                condition_id=condition.condition_id,
                arm=arm,
                session_index=session_index,
                bundle_index=bundle_index,
                bundle_role=("anchor", "trial_or_hold", "confirmation_or_return")[
                    bundle_index
                ],
                evaluation_quality=(
                    "missing" if evaluation is None else evaluation.quality
                ),
                valid_for_analysis=valid,
                baseline_rmssd_ms=baseline_rmssd,
                bundle_rmssd_ms=rmssd,
                delta_rmssd_ms=delta,
                baseline_n=baseline_n,
                bundle_n=n,
                w=_w_from_n(baseline_n, n),
                w_anchor_session=(
                    None
                    if autonomous_outcome is None
                    else autonomous_outcome.holder_W_anchor_session
                ),
                displayed_life_id=displayed_life,
                displayed_hue_degree=hue,
                displayed_blink_bpm=bpm,
                displayed_b=displayed_b,
                anchor_or_trial=_anchor_or_trial(
                    arm,
                    bundle_index,
                    autonomous_outcome,
                ),
                adoption_result=(
                    None if autonomous_outcome is None else autonomous_outcome.adoption_result
                ),
                source_participant_id=source_participant_id,
                source_session_index=source_session,
                source_bundle_index=source_bundle,
                target_rmssd_used_for_future_output=(arm == AUTONOMOUS_ARM),
                physiology_seed=physiology_seed,
                output_seed=output_seed,
                event_digest=engine_digest,
                data_digest=sha256_canonical(data_projection),
            )
        )
    valid_deltas = [
        row.delta_rmssd_ms for row in bundle_rows if row.delta_rmssd_ms is not None
    ]
    representative = bundle_rows[2]
    representative_life_id = (
        autonomous_outcome.holder_id
        if autonomous_outcome is not None
        else representative.displayed_life_id
    )
    representative_hue_degree = (
        autonomous_outcome.holder_final_hue_degree
        if autonomous_outcome is not None
        else representative.displayed_hue_degree
    )
    representative_blink_bpm = (
        autonomous_outcome.holder_final_blink_bpm
        if autonomous_outcome is not None
        else representative.displayed_blink_bpm
    )
    invalid_reason = None
    if not valid_deltas:
        invalid_reason = "no_valid_bundle_evaluation"
    session = SessionOutcome(
        participant_id=participant_id,
        user_type_id=user_type_id,
        response_strength_scale=response_strength_scale,
        condition_id=condition.condition_id,
        arm=arm,
        session_index=session_index,
        physiology_seed=physiology_seed,
        baseline_rmssd_ms=baseline_rmssd,
        bundle_rmssd_ms=tuple(row.bundle_rmssd_ms for row in bundle_rows),
        bundle_delta_rmssd_ms=tuple(row.delta_rmssd_ms for row in bundle_rows),
        mean_valid_bundle_delta_rmssd_ms=(
            None if not valid_deltas else statistics.fmean(valid_deltas)
        ),
        median_valid_bundle_delta_rmssd_ms=(
            None if not valid_deltas else statistics.median(valid_deltas)
        ),
        holder_id=(
            representative.displayed_life_id
            if autonomous_outcome is None
            else autonomous_outcome.holder_id
        ),
        bundle_life_ids=tuple(row.displayed_life_id for row in bundle_rows),
        bundle_hue_degrees=tuple(row.displayed_hue_degree for row in bundle_rows),
        bundle_blink_bpms=tuple(row.displayed_blink_bpm for row in bundle_rows),
        representative_life_id=representative_life_id,
        representative_hue_degree=representative_hue_degree,
        representative_blink_bpm=representative_blink_bpm,
        actual_bundle2_evaluation_output={
            "displayed_life_id": representative.displayed_life_id,
            "hue_degree": representative.displayed_hue_degree,
            "blink_bpm": representative.displayed_blink_bpm,
            "source_b": representative.displayed_b,
        },
        final_committed_anchor=(
            None
            if autonomous_outcome is None
            else autonomous_outcome.holder_final_k_anchor
        ),
        exploration_decision=(
            None
            if autonomous_outcome is None
            else autonomous_outcome.exploration_decision
        ),
        candidate_generated=(
            False
            if autonomous_outcome is None
            else autonomous_outcome.candidate_generated
        ),
        adoption_result=(
            None if autonomous_outcome is None else autonomous_outcome.adoption_result
        ),
        valid_bundle_count=len(valid_deltas),
        session_valid=bool(valid_deltas),
        invalid_reason=invalid_reason,
        source_participant_id=source_participant_id,
        output_sequence_digest=sha256_canonical(
            [state.to_dict() for state in states]
        ),
    )
    return tuple(bundle_rows), session  # type: ignore[return-value]


__all__ = [
    "light_state_records_from_replay",
    "project_validation_session",
    "replay_states_from_device",
]
