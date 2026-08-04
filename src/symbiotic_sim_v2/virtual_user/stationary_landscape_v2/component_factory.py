"""Stage 7 private preference-seam adapters for fixed Stage 8A.1 profiles."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
)
from symbiotic_sim_v2.virtual_user.light_response.preference import LightPreferenceMatch

from .config import (
    STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION,
    StationaryUserTypeProfileV2,
)
from .evaluator import evaluate_stationary_preference_v2


@dataclass(frozen=True, slots=True)
class StationaryV2Stage7PreferenceEvaluator:
    profile: StationaryUserTypeProfileV2

    def __post_init__(self) -> None:
        if not isinstance(self.profile, StationaryUserTypeProfileV2):
            raise TypeError("profile must be a StationaryUserTypeProfileV2")

    @property
    def preference_model_version(self) -> str:
        return STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION

    def __call__(self, stimulus: PhysicalLightStimulus) -> LightPreferenceMatch:
        if not isinstance(stimulus, PhysicalLightStimulus):
            raise TypeError("stimulus must be a PhysicalLightStimulus")
        evaluated = evaluate_stationary_preference_v2(
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
class StationaryLandscapeV2LightResponseConfig(LightResponseConfig):
    """Base-compatible config carrying only the fixed private user seam."""

    _stage8a1_profile: StationaryUserTypeProfileV2

    def __post_init__(self) -> None:
        LightResponseConfig.__post_init__(self)
        if not isinstance(self._stage8a1_profile, StationaryUserTypeProfileV2):
            raise TypeError("_stage8a1_profile must be a StationaryUserTypeProfileV2")

    @property
    def stationary_user_type_profile_v2(self) -> StationaryUserTypeProfileV2:
        return self._stage8a1_profile

    @property
    def _stage8a_preference_model_version(self) -> str:
        # The unchanged Stage 7 component owns this private compatibility seam.
        return STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION

    def _stage8a_preference_evaluator(
        self,
        stimulus: PhysicalLightStimulus,
    ) -> LightPreferenceMatch:
        return stationary_preference_evaluator_v2(self._stage8a1_profile)(stimulus)

    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(LightResponseConfig)}


def stationary_preference_evaluator_v2(
    profile: StationaryUserTypeProfileV2,
) -> StationaryV2Stage7PreferenceEvaluator:
    if not isinstance(profile, StationaryUserTypeProfileV2):
        raise TypeError("profile must be a StationaryUserTypeProfileV2")
    return StationaryV2Stage7PreferenceEvaluator(profile)


def stationary_light_response_config_v2(
    profile: StationaryUserTypeProfileV2,
) -> StationaryLandscapeV2LightResponseConfig:
    """Use valid legacy placeholders only for fields bypassed by the private seam."""

    if not isinstance(profile, StationaryUserTypeProfileV2):
        raise TypeError("profile must be a StationaryUserTypeProfileV2")
    hue_peak = next(
        (peak for peak in profile.peaks if peak.hue_axis_mode == "gaussian"),
        None,
    )
    bpm_peak = next(
        (peak for peak in profile.peaks if peak.bpm_axis_mode == "gaussian"),
        None,
    )
    return StationaryLandscapeV2LightResponseConfig(
        _stage8a1_profile=profile,
        preferred_hue_degree=(125.0 if hue_peak is None else hue_peak.preferred_hue_degree),
        hue_sigma_degree=5.0 if hue_peak is None else hue_peak.hue_sigma_degree,
        preferred_blink_bpm=(87.5 if bpm_peak is None else bpm_peak.preferred_blink_bpm),
        blink_sigma_bpm=30.0 if bpm_peak is None else bpm_peak.blink_sigma_bpm,
        maximum_respiratory_amplitude_gain_ms=(profile.maximum_respiratory_amplitude_gain_ms),
        maximum_mean_rri_increase_ms=profile.maximum_mean_rri_increase_ms,
        response_onset_time_constant_seconds=profile.onset_time_constant_seconds,
        response_recovery_time_constant_seconds=profile.recovery_time_constant_seconds,
    )


__all__ = [
    "StationaryLandscapeV2LightResponseConfig",
    "StationaryV2Stage7PreferenceEvaluator",
    "stationary_light_response_config_v2",
    "stationary_preference_evaluator_v2",
]
