"""Exact immutable Stage 8A.1 fixed-user presets."""

from __future__ import annotations

from .config import StationaryPreferencePeakV2, StationaryUserTypeProfileV2

GREEN_HUE_DOMINANT_BROAD_BPM = "green_hue_dominant_broad_bpm"
BPM_COMMON_100_HUE_NEUTRAL = "bpm_common_100_hue_neutral"
THREE_LIFE_BPM_EQUAL = "three_life_bpm_equal"
THREE_LIFE_BPM_GREEN_DOMINANT = "three_life_bpm_green_dominant"
GREEN_SINGLE_PEAK_NARROW = "green_single_peak_narrow"
FLAT_CONTROL = "flat_control"

DEFAULT_STATIONARY_USER_TYPE_V2 = GREEN_HUE_DOMINANT_BROAD_BPM
STATIONARY_USER_TYPE_V2_IDS = (
    GREEN_HUE_DOMINANT_BROAD_BPM,
    BPM_COMMON_100_HUE_NEUTRAL,
    THREE_LIFE_BPM_EQUAL,
    THREE_LIFE_BPM_GREEN_DOMINANT,
    GREEN_SINGLE_PEAK_NARROW,
    FLAT_CONTROL,
)

_ONSET_SECONDS = 8.0
_RECOVERY_SECONDS = 12.0
_RSA_GAIN_MS = 16.0
_MEAN_RRI_GAIN_MS = 6.0


def _peak(
    peak_id: str,
    *,
    hue: float | None,
    hue_sigma: float | None,
    bpm: float | None,
    bpm_sigma: float | None,
    weight: float,
) -> StationaryPreferencePeakV2:
    return StationaryPreferencePeakV2(
        peak_id=peak_id,
        hue_axis_mode="neutral" if hue is None else "gaussian",
        preferred_hue_degree=hue,
        hue_sigma_degree=hue_sigma,
        bpm_axis_mode="neutral" if bpm is None else "gaussian",
        preferred_blink_bpm=bpm,
        blink_sigma_bpm=bpm_sigma,
        peak_weight=weight,
    )


def _profile(
    user_type_id: str,
    display_name_ja: str,
    description_ja: str,
    peaks: tuple[StationaryPreferencePeakV2, ...],
    *,
    expected_structure: str,
    expected_dominant_life_id: str | None = None,
    expected_attractor_count: int | None = None,
    rsa_gain_ms: float = _RSA_GAIN_MS,
    mean_gain_ms: float = _MEAN_RRI_GAIN_MS,
) -> StationaryUserTypeProfileV2:
    return StationaryUserTypeProfileV2(
        user_type_id=user_type_id,
        display_name_ja=display_name_ja,
        description_ja=description_ja,
        peaks=peaks,
        maximum_respiratory_amplitude_gain_ms=rsa_gain_ms,
        maximum_mean_rri_increase_ms=mean_gain_ms,
        onset_time_constant_seconds=_ONSET_SECONDS,
        recovery_time_constant_seconds=_RECOVERY_SECONDS,
        expected_structure=expected_structure,
        expected_dominant_life_id=expected_dominant_life_id,
        expected_attractor_count=expected_attractor_count,
    )


def green_hue_dominant_broad_bpm() -> StationaryUserTypeProfileV2:
    return _profile(
        GREEN_HUE_DOMINANT_BROAD_BPM,
        "緑Hue優勢・BPM中立",
        "125度近傍の緑Hueだけに反応し、BPM軸は中立な固定好み。",
        (_peak("green-hue", hue=125.0, hue_sigma=3.0, bpm=None, bpm_sigma=None, weight=1.0),),
        expected_structure="life_dominant",
        expected_dominant_life_id="life-green",
        expected_attractor_count=1,
    )


def bpm_common_100_hue_neutral() -> StationaryUserTypeProfileV2:
    return _profile(
        BPM_COMMON_100_HUE_NEUTRAL,
        "BPM 100共通・Hue中立",
        "Hueを問わず100 BPM近傍に反応する固定好み。",
        (_peak("bpm-100", hue=None, hue_sigma=None, bpm=100.0, bpm_sigma=12.0, weight=1.0),),
        expected_structure="bpm_common",
        expected_attractor_count=1,
    )


def three_life_bpm_equal() -> StationaryUserTypeProfileV2:
    return _profile(
        THREE_LIFE_BPM_EQUAL,
        "3生命・等重みBPM三峰",
        "赤55、緑100、青145 BPMに同じ高さの固定峰を持つ。",
        (
            _peak("red", hue=5.0, hue_sigma=3.0, bpm=55.0, bpm_sigma=10.0, weight=1.0),
            _peak("green", hue=125.0, hue_sigma=3.0, bpm=100.0, bpm_sigma=10.0, weight=1.0),
            _peak("blue", hue=250.0, hue_sigma=3.0, bpm=145.0, bpm_sigma=10.0, weight=1.0),
        ),
        expected_structure="life_specific_multi_attractor_equal",
        expected_attractor_count=3,
    )


def three_life_bpm_green_dominant() -> StationaryUserTypeProfileV2:
    return _profile(
        THREE_LIFE_BPM_GREEN_DOMINANT,
        "3生命・緑優勢BPM三峰",
        "赤55、緑100、青145 BPMの三峰を持ち、緑峰だけが高い固定好み。",
        (
            _peak("red", hue=5.0, hue_sigma=3.0, bpm=55.0, bpm_sigma=10.0, weight=0.75),
            _peak("green", hue=125.0, hue_sigma=3.0, bpm=100.0, bpm_sigma=10.0, weight=1.0),
            _peak("blue", hue=250.0, hue_sigma=3.0, bpm=145.0, bpm_sigma=10.0, weight=0.75),
        ),
        expected_structure="life_specific_multi_attractor_weighted",
        expected_dominant_life_id="life-green",
        expected_attractor_count=3,
    )


def green_single_peak_narrow() -> StationaryUserTypeProfileV2:
    return _profile(
        GREEN_SINGLE_PEAK_NARROW,
        "緑・単一狭域峰",
        "129度、125 BPM近傍だけに反応する固定好み。",
        (_peak("green", hue=129.0, hue_sigma=1.5, bpm=125.0, bpm_sigma=10.0, weight=1.0),),
        expected_structure="single_life_pattern",
        expected_dominant_life_id="life-green",
        expected_attractor_count=1,
    )


def flat_control() -> StationaryUserTypeProfileV2:
    return _profile(
        FLAT_CONTROL,
        "無反応対照",
        "光への固定好みも生理ゲインも持たない対照。",
        (),
        expected_structure="no_preference",
        rsa_gain_ms=0.0,
        mean_gain_ms=0.0,
    )


def stationary_user_type_profile_v2(user_type_id: str) -> StationaryUserTypeProfileV2:
    if not isinstance(user_type_id, str):
        raise TypeError("user_type_id must be a string")
    factories = {
        GREEN_HUE_DOMINANT_BROAD_BPM: green_hue_dominant_broad_bpm,
        BPM_COMMON_100_HUE_NEUTRAL: bpm_common_100_hue_neutral,
        THREE_LIFE_BPM_EQUAL: three_life_bpm_equal,
        THREE_LIFE_BPM_GREEN_DOMINANT: three_life_bpm_green_dominant,
        GREEN_SINGLE_PEAK_NARROW: green_single_peak_narrow,
        FLAT_CONTROL: flat_control,
    }
    try:
        return factories[user_type_id]()
    except KeyError as exc:
        raise ValueError(f"unknown stationary user type v2: {user_type_id!r}") from exc


def stationary_user_type_v2_ids() -> tuple[str, ...]:
    return STATIONARY_USER_TYPE_V2_IDS


DEFAULT_STATIONARY_USER_TYPE = DEFAULT_STATIONARY_USER_TYPE_V2


__all__ = [
    "BPM_COMMON_100_HUE_NEUTRAL",
    "DEFAULT_STATIONARY_USER_TYPE_V2",
    "DEFAULT_STATIONARY_USER_TYPE",
    "FLAT_CONTROL",
    "GREEN_HUE_DOMINANT_BROAD_BPM",
    "GREEN_SINGLE_PEAK_NARROW",
    "STATIONARY_USER_TYPE_V2_IDS",
    "THREE_LIFE_BPM_EQUAL",
    "THREE_LIFE_BPM_GREEN_DOMINANT",
    "bpm_common_100_hue_neutral",
    "flat_control",
    "green_hue_dominant_broad_bpm",
    "green_single_peak_narrow",
    "stationary_user_type_profile_v2",
    "stationary_user_type_v2_ids",
    "three_life_bpm_equal",
    "three_life_bpm_green_dominant",
]
