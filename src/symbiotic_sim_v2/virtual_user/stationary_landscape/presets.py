"""Fixed Stage 8A diagnostic user-type presets."""

from __future__ import annotations

from .config import StationaryPreferencePeak, StationaryUserTypeProfile

GREEN_BROAD_STRONG = "green_broad_strong"
GREEN_NARROW_MODERATE = "green_narrow_moderate"
RED_BROAD_MODERATE = "red_broad_moderate"
BLUE_BROAD_WEAK = "blue_broad_weak"
RED_BLUE_DUAL_PEAK = "red_blue_dual_peak"
FLAT_CONTROL = "flat_control"
DEFAULT_STATIONARY_USER_TYPE = GREEN_NARROW_MODERATE
STATIONARY_USER_TYPE_IDS = (
    GREEN_BROAD_STRONG,
    GREEN_NARROW_MODERATE,
    RED_BROAD_MODERATE,
    BLUE_BROAD_WEAK,
    RED_BLUE_DUAL_PEAK,
    FLAT_CONTROL,
)

_DEFAULT_ONSET_SECONDS = 8.0
_DEFAULT_RECOVERY_SECONDS = 12.0


def _profile(
    user_type_id: str,
    display_name_ja: str,
    description_ja: str,
    peaks: tuple[StationaryPreferencePeak, ...],
    rsa_gain_ms: float,
    mean_gain_ms: float,
) -> StationaryUserTypeProfile:
    return StationaryUserTypeProfile(
        user_type_id=user_type_id,
        display_name_ja=display_name_ja,
        description_ja=description_ja,
        peaks=peaks,
        maximum_respiratory_amplitude_gain_ms=rsa_gain_ms,
        maximum_mean_rri_increase_ms=mean_gain_ms,
        onset_time_constant_seconds=_DEFAULT_ONSET_SECONDS,
        recovery_time_constant_seconds=_DEFAULT_RECOVERY_SECONDS,
    )


def green_broad_strong() -> StationaryUserTypeProfile:
    return _profile(
        GREEN_BROAD_STRONG,
        "緑・広域・強反応",
        "緑の狭いHue帯と広い点滅速度帯に強く反応する固定好み。",
        (StationaryPreferencePeak("green", 129.0, 5.0, 125.0, 35.0, 1.0),),
        30.0,
        15.0,
    )


def green_narrow_moderate() -> StationaryUserTypeProfile:
    return _profile(
        GREEN_NARROW_MODERATE,
        "緑・狭域・中反応",
        "緑の狭いHue/BPM近傍に中程度に反応する固定好み。",
        (StationaryPreferencePeak("green", 129.0, 1.5, 125.0, 12.0, 1.0),),
        16.0,
        6.0,
    )


def red_broad_moderate() -> StationaryUserTypeProfile:
    return _profile(
        RED_BROAD_MODERATE,
        "赤・広域・中反応",
        "赤のHue帯と広い点滅速度帯に中程度に反応する固定好み。",
        (StationaryPreferencePeak("red", 7.0, 4.0, 70.0, 35.0, 1.0),),
        18.0,
        7.0,
    )


def blue_broad_weak() -> StationaryUserTypeProfile:
    return _profile(
        BLUE_BROAD_WEAK,
        "青・広域・弱反応",
        "青のHue帯と広い点滅速度帯に弱く反応する固定好み。",
        (StationaryPreferencePeak("blue", 252.0, 5.0, 120.0, 40.0, 1.0),),
        8.0,
        3.0,
    )


def red_blue_dual_peak() -> StationaryUserTypeProfile:
    return _profile(
        RED_BLUE_DUAL_PEAK,
        "赤青・二峰",
        "赤の局所峰と、より高い青の大域峰を持つ固定二峰好み。",
        (
            StationaryPreferencePeak("red-local", 6.0, 2.5, 70.0, 25.0, 0.75),
            StationaryPreferencePeak("blue-global", 252.0, 2.5, 120.0, 20.0, 1.0),
        ),
        18.0,
        7.0,
    )


def flat_control() -> StationaryUserTypeProfile:
    return _profile(
        FLAT_CONTROL,
        "無反応対照",
        "光への固定好みと生理反応を持たない対照ユーザー。",
        (),
        0.0,
        0.0,
    )


def stationary_user_type_profile(user_type_id: str) -> StationaryUserTypeProfile:
    factories = {
        GREEN_BROAD_STRONG: green_broad_strong,
        GREEN_NARROW_MODERATE: green_narrow_moderate,
        RED_BROAD_MODERATE: red_broad_moderate,
        BLUE_BROAD_WEAK: blue_broad_weak,
        RED_BLUE_DUAL_PEAK: red_blue_dual_peak,
        FLAT_CONTROL: flat_control,
    }
    if not isinstance(user_type_id, str):
        raise TypeError("user_type_id must be a string")
    try:
        factory = factories[user_type_id]
    except KeyError as exc:
        raise ValueError(f"unknown stationary user type: {user_type_id!r}") from exc
    return factory()


def stationary_user_type_ids() -> tuple[str, ...]:
    return STATIONARY_USER_TYPE_IDS


__all__ = [
    "BLUE_BROAD_WEAK",
    "DEFAULT_STATIONARY_USER_TYPE",
    "FLAT_CONTROL",
    "GREEN_BROAD_STRONG",
    "GREEN_NARROW_MODERATE",
    "RED_BLUE_DUAL_PEAK",
    "RED_BROAD_MODERATE",
    "STATIONARY_USER_TYPE_IDS",
    "blue_broad_weak",
    "flat_control",
    "green_broad_strong",
    "green_narrow_moderate",
    "red_blue_dual_peak",
    "red_broad_moderate",
    "stationary_user_type_ids",
    "stationary_user_type_profile",
]
