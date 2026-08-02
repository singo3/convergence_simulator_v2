"""Single pure half-open time classification for all Garden consumers."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.phases import (
    GardenEvaluationKind,
    GardenPhase,
    GardenWindowRole,
)
from symbiotic_sim_v2.simulation.time_utils import seconds_to_us


@dataclass(frozen=True, slots=True)
class GardenPhaseDescriptor:
    phase: GardenPhase
    bundle_index: int | None
    window_role: GardenWindowRole
    nominal_s: int
    evaluation_id: str | None
    window_start_us: int | None
    window_end_us: int | None


@dataclass(frozen=True, slots=True)
class GardenEvaluationWindow:
    evaluation_id: str
    evaluation_kind: GardenEvaluationKind
    bundle_index: int | None
    window_start_us: int
    window_end_us: int


def phase_at(time_us: int, config: GardenInputConfig) -> GardenPhaseDescriptor:
    """Classify a measurement end time with the Stage 4 half-open policy."""

    if isinstance(time_us, bool) or not isinstance(time_us, int):
        raise TypeError("time_us must be an integer")
    if time_us < 0:
        raise ValueError("time_us must be non-negative")

    baseline_discard_end = seconds_to_us(config.baseline_discard_seconds)
    baseline_end = seconds_to_us(
        config.baseline_discard_seconds + config.baseline_evaluation_seconds
    )
    if time_us < baseline_discard_end:
        return GardenPhaseDescriptor(
            GardenPhase.BASELINE_DISCARD,
            None,
            GardenWindowRole.DISCARD,
            0,
            None,
            None,
            None,
        )
    if time_us < baseline_end:
        return GardenPhaseDescriptor(
            GardenPhase.BASELINE_EVALUATION,
            None,
            GardenWindowRole.EVALUATION,
            0,
            "session-001-baseline",
            baseline_discard_end,
            baseline_end,
        )

    bundle_duration_us = seconds_to_us(
        config.bundle_discard_seconds + config.bundle_evaluation_seconds
    )
    main_end = baseline_end + seconds_to_us(config.main_session_seconds)
    if time_us >= main_end:
        return GardenPhaseDescriptor(
            GardenPhase.OUTSIDE,
            None,
            GardenWindowRole.OUTSIDE,
            0,
            None,
            None,
            None,
        )

    offset_us = time_us - baseline_end
    bundle_index = offset_us // bundle_duration_us
    bundle_start_us = baseline_end + bundle_index * bundle_duration_us
    evaluation_start_us = bundle_start_us + seconds_to_us(config.bundle_discard_seconds)
    evaluation_end_us = bundle_start_us + bundle_duration_us
    is_evaluation = time_us >= evaluation_start_us
    phase = GardenPhase(f"bundle_{bundle_index}_{'evaluation' if is_evaluation else 'discard'}")
    return GardenPhaseDescriptor(
        phase,
        bundle_index,
        GardenWindowRole.EVALUATION if is_evaluation else GardenWindowRole.DISCARD,
        1,
        f"session-001-bundle-{bundle_index}" if is_evaluation else None,
        evaluation_start_us if is_evaluation else None,
        evaluation_end_us if is_evaluation else None,
    )


def phase_change_times_us(config: GardenInputConfig) -> tuple[int, ...]:
    """Return all nine formal phase boundaries, including closing time."""

    boundaries_seconds = [0, config.baseline_discard_seconds]
    baseline_total = config.baseline_discard_seconds + config.baseline_evaluation_seconds
    boundaries_seconds.append(baseline_total)
    for bundle_index in range(config.bundle_count):
        bundle_start = baseline_total + bundle_index * (
            config.bundle_discard_seconds + config.bundle_evaluation_seconds
        )
        boundaries_seconds.extend(
            (
                bundle_start + config.bundle_discard_seconds,
                bundle_start + config.bundle_discard_seconds + config.bundle_evaluation_seconds,
            )
        )
    return tuple(dict.fromkeys(seconds_to_us(value) for value in boundaries_seconds))


def evaluation_windows(config: GardenInputConfig) -> tuple[GardenEvaluationWindow, ...]:
    """Return baseline plus the three bundle evaluation windows."""

    baseline_start = seconds_to_us(config.baseline_discard_seconds)
    baseline_end = seconds_to_us(
        config.baseline_discard_seconds + config.baseline_evaluation_seconds
    )
    windows = [
        GardenEvaluationWindow(
            "session-001-baseline",
            GardenEvaluationKind.BASELINE,
            None,
            baseline_start,
            baseline_end,
        )
    ]
    bundle_duration_seconds = config.bundle_discard_seconds + config.bundle_evaluation_seconds
    for bundle_index in range(config.bundle_count):
        start_seconds = (
            config.baseline_discard_seconds
            + config.baseline_evaluation_seconds
            + bundle_index * bundle_duration_seconds
            + config.bundle_discard_seconds
        )
        windows.append(
            GardenEvaluationWindow(
                f"session-001-bundle-{bundle_index}",
                GardenEvaluationKind.BUNDLE,
                bundle_index,
                seconds_to_us(start_seconds),
                seconds_to_us(start_seconds + config.bundle_evaluation_seconds),
            )
        )
    return tuple(windows)
