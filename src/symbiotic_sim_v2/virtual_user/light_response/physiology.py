"""Pure Stage 7 coupling of latent response into the shared heartbeat model."""

from __future__ import annotations

import math
from dataclasses import dataclass

from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.physiology import (
    RriComputation,
    calculate_next_rri,
    calculate_next_rri_with_effective_physiology,
    mean_rri_ms,
)


@dataclass(frozen=True, slots=True)
class LightResponsiveRriComputation:
    computation: RriComputation
    response_level: float
    base_mean_rri_ms: float
    effective_mean_rri_ms: float
    mean_rri_increase_ms: float
    base_respiratory_amplitude_ms: float
    effective_respiratory_amplitude_ms: float
    respiratory_amplitude_gain_ms: float


def effective_physiology(
    virtual_user_config: VirtualUserConfig,
    light_response_config: LightResponseConfig,
    response_level: float,
) -> tuple[float, float, float, float, float, float]:
    response = _response_level(response_level)
    base_mean = mean_rri_ms(virtual_user_config.mean_heart_rate_bpm)
    mean_increase = light_response_config.maximum_mean_rri_increase_ms * response
    effective_mean = base_mean + mean_increase
    base_amplitude = virtual_user_config.respiratory_amplitude_ms
    amplitude_gain = (
        light_response_config.maximum_respiratory_amplitude_gain_ms * response
    )
    effective_amplitude = base_amplitude + amplitude_gain
    return (
        base_mean,
        effective_mean,
        mean_increase,
        base_amplitude,
        effective_amplitude,
        amplitude_gain,
    )


def calculate_light_responsive_next_rri(
    virtual_user_config: VirtualUserConfig,
    light_response_config: LightResponseConfig,
    current_heartbeat_time_us: int,
    beat_index: int,
    previous_correlated_state: float,
    response_level: float,
) -> LightResponsiveRriComputation:
    """Apply only mean-RRI and RSA-amplitude coupling at heartbeat start."""

    response = _response_level(response_level)
    (
        base_mean,
        effective_mean,
        mean_increase,
        base_amplitude,
        effective_amplitude,
        amplitude_gain,
    ) = effective_physiology(virtual_user_config, light_response_config, response)
    if mean_increase == 0.0 and amplitude_gain == 0.0:
        computation = calculate_next_rri(
            virtual_user_config,
            current_heartbeat_time_us,
            beat_index,
            previous_correlated_state,
        )
    else:
        computation = calculate_next_rri_with_effective_physiology(
            virtual_user_config,
            current_heartbeat_time_us,
            beat_index,
            previous_correlated_state,
            effective_mean_rri_ms=effective_mean,
            effective_respiratory_amplitude_ms=effective_amplitude,
        )
    return LightResponsiveRriComputation(
        computation=computation,
        response_level=response,
        base_mean_rri_ms=base_mean,
        effective_mean_rri_ms=effective_mean,
        mean_rri_increase_ms=mean_increase,
        base_respiratory_amplitude_ms=base_amplitude,
        effective_respiratory_amplitude_ms=effective_amplitude,
        respiratory_amplitude_gain_ms=amplitude_gain,
    )


def _response_level(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError("response_level must be finite and between 0 and 1")
    return float(value)
