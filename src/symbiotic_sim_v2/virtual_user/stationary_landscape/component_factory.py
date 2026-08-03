"""Private Stage 7 preference seam adapters for Stage 8A sessions."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
)
from symbiotic_sim_v2.virtual_user.light_response.preference import LightPreferenceMatch

from .config import (
    STATIONARY_PREFERENCE_LANDSCAPE_VERSION,
    StationaryUserTypeProfile,
)
from .evaluator import evaluate_stationary_preference


@dataclass(frozen=True, slots=True)
class StationaryStage7PreferenceEvaluator:
    """Callable adapter exposing only the three values the Stage 7 core consumes."""

    profile: StationaryUserTypeProfile

    def __post_init__(self) -> None:
        if not isinstance(self.profile, StationaryUserTypeProfile):
            raise TypeError("profile must be a StationaryUserTypeProfile")

    @property
    def preference_model_version(self) -> str:
        return STATIONARY_PREFERENCE_LANDSCAPE_VERSION

    def __call__(self, stimulus: PhysicalLightStimulus) -> LightPreferenceMatch:
        if not isinstance(stimulus, PhysicalLightStimulus):
            raise TypeError("stimulus must be a PhysicalLightStimulus")
        evaluated = evaluate_stationary_preference(
            self.profile,
            active=stimulus.active,
            hue_degree=stimulus.render_hue_degree,
            blink_bpm=stimulus.blink_bpm,
        )
        return LightPreferenceMatch(
            hue_match=evaluated.winning_hue_match,
            bpm_match=evaluated.winning_bpm_match,
            preference_match=evaluated.preference_match,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class StationaryLandscapeLightResponseConfig(LightResponseConfig):
    """A base-compatible config carrying a private, immutable Stage 8A seam."""

    _stage8a_profile: StationaryUserTypeProfile

    def __post_init__(self) -> None:
        # Explicit base-class dispatch avoids zero-argument super's dataclass-slots
        # class replacement edge case while retaining every Stage 7 validation.
        LightResponseConfig.__post_init__(self)
        if not isinstance(self._stage8a_profile, StationaryUserTypeProfile):
            raise TypeError("_stage8a_profile must be a StationaryUserTypeProfile")

    @property
    def stationary_user_type_profile(self) -> StationaryUserTypeProfile:
        return self._stage8a_profile

    @property
    def _stage8a_preference_model_version(self) -> str:
        return STATIONARY_PREFERENCE_LANDSCAPE_VERSION

    def _stage8a_preference_evaluator(
        self,
        stimulus: PhysicalLightStimulus,
    ) -> LightPreferenceMatch:
        return stationary_preference_evaluator(self._stage8a_profile)(stimulus)

    def to_dict(self) -> dict[str, Any]:
        """Keep the inherited Stage 7 config document free of private callables."""

        return {
            field.name: getattr(self, field.name)
            for field in fields(LightResponseConfig)
        }


def stationary_preference_evaluator(
    profile: StationaryUserTypeProfile,
) -> StationaryStage7PreferenceEvaluator:
    if not isinstance(profile, StationaryUserTypeProfile):
        raise TypeError("profile must be a StationaryUserTypeProfile")
    return StationaryStage7PreferenceEvaluator(profile)


def stationary_light_response_config(
    profile: StationaryUserTypeProfile,
) -> StationaryLandscapeLightResponseConfig:
    """Carry fixed landscape physiology through the unchanged Stage 5C factory."""

    if not isinstance(profile, StationaryUserTypeProfile):
        raise TypeError("profile must be a StationaryUserTypeProfile")
    representative_peak = profile.peaks[0] if profile.peaks else None
    return StationaryLandscapeLightResponseConfig(
        _stage8a_profile=profile,
        preferred_hue_degree=(
            125.0 if representative_peak is None else representative_peak.preferred_hue_degree
        ),
        hue_sigma_degree=(
            5.0 if representative_peak is None else representative_peak.hue_sigma_degree
        ),
        preferred_blink_bpm=(
            87.5 if representative_peak is None else representative_peak.preferred_blink_bpm
        ),
        blink_sigma_bpm=(
            30.0 if representative_peak is None else representative_peak.blink_sigma_bpm
        ),
        maximum_respiratory_amplitude_gain_ms=(
            profile.maximum_respiratory_amplitude_gain_ms
        ),
        maximum_mean_rri_increase_ms=profile.maximum_mean_rri_increase_ms,
        response_onset_time_constant_seconds=profile.onset_time_constant_seconds,
        response_recovery_time_constant_seconds=profile.recovery_time_constant_seconds,
    )


__all__ = [
    "StationaryLandscapeLightResponseConfig",
    "StationaryStage7PreferenceEvaluator",
    "stationary_light_response_config",
    "stationary_preference_evaluator",
]
