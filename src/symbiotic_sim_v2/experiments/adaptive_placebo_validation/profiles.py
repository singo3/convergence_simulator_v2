"""Stage 8A.3-only fixed participant profiles and response-strength scaling."""

from __future__ import annotations

from dataclasses import replace

from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    StationaryPreferencePeakV2,
    StationaryUserTypeProfileV2,
    stationary_user_type_profile_v2,
)

from .config import ALL_USER_TYPE_IDS

_RSA_GAIN_MS = 16.0
_MEAN_GAIN_MS = 6.0
_ONSET_SECONDS = 8.0
_RECOVERY_SECONDS = 12.0


def _hue_profile(
    user_type_id: str,
    display_name: str,
    hue_degree: float,
    life_id: str,
) -> StationaryUserTypeProfileV2:
    peak = StationaryPreferencePeakV2(
        peak_id=f"{life_id}-hue",
        hue_axis_mode="gaussian",
        preferred_hue_degree=hue_degree,
        hue_sigma_degree=3.0,
        bpm_axis_mode="neutral",
        preferred_blink_bpm=None,
        blink_sigma_bpm=None,
        peak_weight=1.0,
    )
    return StationaryUserTypeProfileV2(
        user_type_id=user_type_id,
        display_name_ja=display_name,
        description_ja=(
            f"Stage 8A.3専用の固定{hue_degree:g}度Hue優勢・BPM中立profile。"
        ),
        peaks=(peak,),
        maximum_respiratory_amplitude_gain_ms=_RSA_GAIN_MS,
        maximum_mean_rri_increase_ms=_MEAN_GAIN_MS,
        onset_time_constant_seconds=_ONSET_SECONDS,
        recovery_time_constant_seconds=_RECOVERY_SECONDS,
        expected_structure="life_dominant",
        expected_dominant_life_id=life_id,
        expected_attractor_count=1,
    )


def red_hue_dominant_broad_bpm() -> StationaryUserTypeProfileV2:
    return _hue_profile(
        "red_hue_dominant_broad_bpm",
        "赤Hue優勢・BPM中立",
        5.0,
        "life-red",
    )


def blue_hue_dominant_broad_bpm() -> StationaryUserTypeProfileV2:
    return _hue_profile(
        "blue_hue_dominant_broad_bpm",
        "青Hue優勢・BPM中立",
        250.0,
        "life-blue",
    )


def weak_bpm_common_100() -> StationaryUserTypeProfileV2:
    peak = StationaryPreferencePeakV2(
        peak_id="weak-bpm-100",
        hue_axis_mode="neutral",
        preferred_hue_degree=None,
        hue_sigma_degree=None,
        bpm_axis_mode="gaussian",
        preferred_blink_bpm=100.0,
        blink_sigma_bpm=12.0,
        peak_weight=1.0,
    )
    return StationaryUserTypeProfileV2(
        user_type_id="weak_bpm_common_100",
        display_name_ja="BPM 100共通・弱反応",
        description_ja="Stage 8A.3専用の固定BPM 100弱反応profile。",
        peaks=(peak,),
        maximum_respiratory_amplitude_gain_ms=8.0,
        maximum_mean_rri_increase_ms=3.0,
        onset_time_constant_seconds=_ONSET_SECONDS,
        recovery_time_constant_seconds=_RECOVERY_SECONDS,
        expected_structure="bpm_common",
        expected_dominant_life_id=None,
        expected_attractor_count=1,
    )


def validation_user_type_profile(user_type_id: str) -> StationaryUserTypeProfileV2:
    if user_type_id not in ALL_USER_TYPE_IDS:
        raise ValueError(f"unknown Stage 8A.3 user type: {user_type_id!r}")
    special = {
        "red_hue_dominant_broad_bpm": red_hue_dominant_broad_bpm,
        "blue_hue_dominant_broad_bpm": blue_hue_dominant_broad_bpm,
        "weak_bpm_common_100": weak_bpm_common_100,
    }
    factory = special.get(user_type_id)
    return factory() if factory is not None else stationary_user_type_profile_v2(user_type_id)


def participant_profile(
    user_type_id: str,
    response_strength_scale: float,
) -> StationaryUserTypeProfileV2:
    if isinstance(response_strength_scale, bool) or not isinstance(
        response_strength_scale, (int, float)
    ):
        raise TypeError("response_strength_scale must be numeric")
    scale = float(response_strength_scale)
    if not 0.0 <= scale <= 1.0:
        raise ValueError("response_strength_scale must be within [0, 1]")
    profile = validation_user_type_profile(user_type_id)
    if user_type_id == "flat_control" and scale != 0.0:
        raise ValueError("flat_control response strength must remain zero")
    return replace(
        profile,
        maximum_respiratory_amplitude_gain_ms=(
            profile.maximum_respiratory_amplitude_gain_ms * scale
        ),
        maximum_mean_rri_increase_ms=(
            profile.maximum_mean_rri_increase_ms * scale
        ),
    )


def base_profile_payloads() -> dict[str, dict[str, object]]:
    return {
        user_type_id: validation_user_type_profile(user_type_id).to_dict()
        for user_type_id in ALL_USER_TYPE_IDS
    }


__all__ = [
    "base_profile_payloads",
    "blue_hue_dominant_broad_bpm",
    "participant_profile",
    "red_hue_dominant_broad_bpm",
    "validation_user_type_profile",
    "weak_bpm_common_100",
]
