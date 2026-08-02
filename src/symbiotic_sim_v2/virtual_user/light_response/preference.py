"""Stationary Gaussian Hue/BPM preference functions for Stage 7."""

from __future__ import annotations

import math
from dataclasses import dataclass

from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
)


@dataclass(frozen=True, slots=True)
class LightPreferenceMatch:
    hue_match: float | None
    bpm_match: float | None
    preference_match: float


def circular_hue_distance(first_degree: float, second_degree: float) -> float:
    values = (first_degree, second_degree)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in values
    ):
        raise ValueError("Hue values must be finite numbers")
    if any(not 0.0 <= float(value) <= 360.0 for value in values):
        raise ValueError("Hue values must be between 0 and 360")
    raw_difference = abs(float(first_degree) - float(second_degree))
    return min(raw_difference, 360.0 - raw_difference)


def gaussian_match(distance: float, sigma: float) -> float:
    if (
        isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or not math.isfinite(float(distance))
        or float(distance) < 0.0
    ):
        raise ValueError("distance must be finite and non-negative")
    if (
        isinstance(sigma, bool)
        or not isinstance(sigma, (int, float))
        or not math.isfinite(float(sigma))
        or float(sigma) <= 0.0
    ):
        raise ValueError("sigma must be finite and positive")
    return math.exp(-0.5 * (float(distance) / float(sigma)) ** 2)


def evaluate_light_preference(
    stimulus: PhysicalLightStimulus,
    config: LightResponseConfig,
) -> LightPreferenceMatch:
    if not isinstance(stimulus, PhysicalLightStimulus):
        raise TypeError("stimulus must be a PhysicalLightStimulus")
    if not isinstance(config, LightResponseConfig):
        raise TypeError("config must be a LightResponseConfig")
    if not stimulus.active:
        return LightPreferenceMatch(None, None, 0.0)
    if stimulus.render_hue_degree is None or stimulus.blink_bpm is None:
        raise ValueError("active physical stimulus requires Hue and BPM")
    hue_match = gaussian_match(
        circular_hue_distance(
            stimulus.render_hue_degree,
            config.preferred_hue_degree,
        ),
        config.hue_sigma_degree,
    )
    bpm_match = gaussian_match(
        abs(stimulus.blink_bpm - config.preferred_blink_bpm),
        config.blink_sigma_bpm,
    )
    preference_match = hue_match * bpm_match
    if not 0.0 <= preference_match <= 1.0:
        raise RuntimeError("preference match escaped its analytical range")
    return LightPreferenceMatch(hue_match, bpm_match, preference_match)


def response_target_for(
    stimulus: PhysicalLightStimulus,
    preference: LightPreferenceMatch,
    config: LightResponseConfig,
) -> float:
    if not isinstance(stimulus, PhysicalLightStimulus):
        raise TypeError("stimulus must be a PhysicalLightStimulus")
    if not isinstance(preference, LightPreferenceMatch):
        raise TypeError("preference must be a LightPreferenceMatch")
    if not isinstance(config, LightResponseConfig):
        raise TypeError("config must be a LightResponseConfig")
    return preference.preference_match if config.enabled and stimulus.active else 0.0
