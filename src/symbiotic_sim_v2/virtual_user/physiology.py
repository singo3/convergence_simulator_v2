"""Explicit Stage 2 baseline physiology assumption for the next heartbeat interval."""

from __future__ import annotations

import math
from dataclasses import dataclass

from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.random_source import standard_normal

MICROSECONDS_PER_MILLISECOND = 1_000
CORRELATED_STREAM = "correlated_innovation"
JITTER_STREAM = "beat_jitter"


@dataclass(frozen=True, slots=True)
class RriComputation:
    """Immutable internal computation used to schedule one future heartbeat."""

    mean_rri_ms: float
    respiratory_component_ms: float
    slow_wave_component_ms: float
    correlated_component_ms: float
    beat_jitter_component_ms: float
    unclamped_rri_ms: float
    final_rri_ms: float
    rri_us: int
    next_correlated_state: float
    clamped: bool


def mean_rri_ms(mean_heart_rate_bpm: float) -> float:
    """Convert configured mean heart rate to its mean RRI in milliseconds."""

    return 60_000.0 / mean_heart_rate_bpm


def respiratory_component_ms(config: VirtualUserConfig, time_seconds: float) -> float:
    """Return deterministic respiratory sinus arrhythmia component."""

    frequency_hz = config.respiratory_rate_bpm / 60.0
    return config.respiratory_amplitude_ms * math.sin(
        2.0 * math.pi * frequency_hz * time_seconds
    )


def slow_wave_component_ms(config: VirtualUserConfig, time_seconds: float) -> float:
    """Return the deterministic slow sinusoidal component."""

    return config.slow_wave_amplitude_ms * math.sin(
        2.0 * math.pi * config.slow_wave_frequency_hz * time_seconds + math.pi / 3.0
    )


def correlated_state_update(
    persistence: float,
    previous_state: float,
    innovation: float,
) -> float:
    """Apply the specified variance-normalized AR(1) update."""

    return persistence * previous_state + math.sqrt(1.0 - persistence**2) * innovation


def round_positive_ms_to_us(milliseconds: float) -> int:
    """Round a positive millisecond duration half-up to integer microseconds."""

    if not math.isfinite(milliseconds) or milliseconds <= 0.0:
        raise ValueError("milliseconds must be finite and positive")
    return math.floor(milliseconds * MICROSECONDS_PER_MILLISECOND + 0.5)


def calculate_next_rri(
    config: VirtualUserConfig,
    current_heartbeat_time_us: int,
    beat_index: int,
    previous_correlated_state: float,
) -> RriComputation:
    """Calculate the interval following a heartbeat using only causal internal state."""

    if (
        isinstance(current_heartbeat_time_us, bool)
        or not isinstance(current_heartbeat_time_us, int)
        or current_heartbeat_time_us < 0
    ):
        raise ValueError("current_heartbeat_time_us must be a non-negative integer")
    if isinstance(beat_index, bool) or not isinstance(beat_index, int) or beat_index < 0:
        raise ValueError("beat_index must be a non-negative integer")
    if not math.isfinite(previous_correlated_state):
        raise ValueError("previous_correlated_state must be finite")

    time_seconds = current_heartbeat_time_us / 1_000_000
    mean_component = mean_rri_ms(config.mean_heart_rate_bpm)
    respiratory = respiratory_component_ms(config, time_seconds)
    slow_wave = slow_wave_component_ms(config, time_seconds)
    innovation = standard_normal(config.root_seed, CORRELATED_STREAM, beat_index)
    next_correlated_state = correlated_state_update(
        config.correlated_variability_persistence,
        previous_correlated_state,
        innovation,
    )
    correlated = config.correlated_variability_sd_ms * next_correlated_state
    jitter = config.beat_jitter_sd_ms * standard_normal(
        config.root_seed,
        JITTER_STREAM,
        beat_index,
    )
    unclamped = mean_component + respiratory + slow_wave + correlated + jitter
    final = min(config.max_rri_ms, max(config.min_rri_ms, unclamped))
    return RriComputation(
        mean_rri_ms=mean_component,
        respiratory_component_ms=respiratory,
        slow_wave_component_ms=slow_wave,
        correlated_component_ms=correlated,
        beat_jitter_component_ms=jitter,
        unclamped_rri_ms=unclamped,
        final_rri_ms=final,
        rri_us=round_positive_ms_to_us(final),
        next_correlated_state=next_correlated_state,
        clamped=final != unclamped,
    )
