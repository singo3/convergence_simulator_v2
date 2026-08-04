"""Stage 8A.1 neutral/Gaussian fixed-user landscape contracts."""

from __future__ import annotations

import dataclasses
import inspect
import math

import pytest

from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    DEFAULT_STATIONARY_USER_TYPE_V2,
    STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION,
    StationaryPreferencePeakV2,
    StationaryUserTypeProfileV2,
    evaluate_stationary_preference_v2,
    stationary_light_response_config_v2,
    stationary_user_type_profile_v2,
    stationary_user_type_v2_ids,
)


def test_all_six_v2_presets_are_exact_fixed_profiles() -> None:
    assert DEFAULT_STATIONARY_USER_TYPE_V2 == "green_hue_dominant_broad_bpm"
    assert stationary_user_type_v2_ids() == (
        "green_hue_dominant_broad_bpm",
        "bpm_common_100_hue_neutral",
        "three_life_bpm_equal",
        "three_life_bpm_green_dominant",
        "green_single_peak_narrow",
        "flat_control",
    )
    green = stationary_user_type_profile_v2("green_hue_dominant_broad_bpm")
    assert green.expected_structure == "life_dominant"
    assert green.expected_dominant_life_id == "life-green"
    assert green.peaks[0].to_dict() == {
        "peak_id": "green-hue",
        "hue_axis_mode": "gaussian",
        "preferred_hue_degree": 125.0,
        "hue_sigma_degree": 3.0,
        "bpm_axis_mode": "neutral",
        "preferred_blink_bpm": None,
        "blink_sigma_bpm": None,
        "peak_weight": 1.0,
    }
    common = stationary_user_type_profile_v2("bpm_common_100_hue_neutral")
    assert common.peaks[0].hue_axis_mode == "neutral"
    assert common.peaks[0].preferred_blink_bpm == 100.0
    assert common.peaks[0].blink_sigma_bpm == 12.0
    equal = stationary_user_type_profile_v2("three_life_bpm_equal")
    weighted = stationary_user_type_profile_v2("three_life_bpm_green_dominant")
    assert tuple(peak.preferred_blink_bpm for peak in equal.peaks) == (55.0, 100.0, 145.0)
    assert tuple(peak.peak_weight for peak in equal.peaks) == (1.0, 1.0, 1.0)
    assert tuple(peak.peak_weight for peak in weighted.peaks) == (0.75, 1.0, 0.75)
    narrow = stationary_user_type_profile_v2("green_single_peak_narrow")
    assert (narrow.peaks[0].preferred_hue_degree, narrow.peaks[0].hue_sigma_degree) == (
        129.0,
        1.5,
    )
    assert (narrow.peaks[0].preferred_blink_bpm, narrow.peaks[0].blink_sigma_bpm) == (
        125.0,
        10.0,
    )
    flat = stationary_user_type_profile_v2("flat_control")
    assert flat.peaks == ()
    assert flat.expected_structure == "no_preference"
    assert flat.maximum_respiratory_amplitude_gain_ms == 0.0


def test_profiles_are_frozen_strict_and_canonical_json_round_trippable() -> None:
    for user_type_id in stationary_user_type_v2_ids():
        profile = stationary_user_type_profile_v2(user_type_id)
        assert profile.landscape_version == STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION
        assert StationaryUserTypeProfileV2.from_json(profile.to_json()) == profile
        with pytest.raises(dataclasses.FrozenInstanceError):
            profile.user_type_id = "moving"  # type: ignore[misc]
    values = stationary_user_type_profile_v2(DEFAULT_STATIONARY_USER_TYPE_V2).to_dict()
    with pytest.raises(ValueError, match="missing"):
        StationaryUserTypeProfileV2.from_dict(
            {key: value for key, value in values.items() if key != "peaks"}
        )
    with pytest.raises(ValueError, match="unknown"):
        StationaryUserTypeProfileV2.from_dict({**values, "session_peak": 1})
    with pytest.raises(ValueError, match="duplicate"):
        StationaryUserTypeProfileV2.from_json('{"user_type_id":"a","user_type_id":"b"}')


@pytest.mark.parametrize(
    "values",
    (
        {
            "hue_axis_mode": "neutral",
            "preferred_hue_degree": 125.0,
            "hue_sigma_degree": None,
        },
        {
            "hue_axis_mode": "gaussian",
            "preferred_hue_degree": None,
            "hue_sigma_degree": 3.0,
        },
        {
            "bpm_axis_mode": "neutral",
            "preferred_blink_bpm": None,
            "blink_sigma_bpm": 12.0,
        },
        {"peak_weight": True},
        {"hue_sigma_degree": math.nan},
    ),
)
def test_axis_modes_reject_inconsistent_bool_and_nonfinite_values(
    values: dict[str, object],
) -> None:
    base = StationaryPreferencePeakV2(
        "peak",
        "gaussian",
        125.0,
        3.0,
        "gaussian",
        100.0,
        12.0,
        1.0,
    ).to_dict()
    with pytest.raises((TypeError, ValueError)):
        StationaryPreferencePeakV2.from_dict({**base, **values})


def test_neutral_axes_are_exactly_one_and_gaussian_axes_remain_exact() -> None:
    green = stationary_user_type_profile_v2("green_hue_dominant_broad_bpm")
    at_low_bpm = evaluate_stationary_preference_v2(
        green,
        active=True,
        hue_degree=125.0,
        blink_bpm=10.0,
    )
    at_high_bpm = evaluate_stationary_preference_v2(
        green,
        active=True,
        hue_degree=125.0,
        blink_bpm=165.0,
    )
    one_hue_sigma = evaluate_stationary_preference_v2(
        green,
        active=True,
        hue_degree=128.0,
        blink_bpm=100.0,
    )
    assert at_low_bpm.preference_match == at_high_bpm.preference_match == 1.0
    assert at_low_bpm.peak_matches[0].blink_bpm_distance is None
    assert at_low_bpm.peak_matches[0].bpm_match == 1.0
    assert one_hue_sigma.preference_match == pytest.approx(math.exp(-0.5))

    common = stationary_user_type_profile_v2("bpm_common_100_hue_neutral")
    first_hue = evaluate_stationary_preference_v2(
        common,
        active=True,
        hue_degree=0.0,
        blink_bpm=112.0,
    )
    other_hue = evaluate_stationary_preference_v2(
        common,
        active=True,
        hue_degree=300.0,
        blink_bpm=112.0,
    )
    assert first_hue.preference_match == other_hue.preference_match
    assert first_hue.preference_match == pytest.approx(math.exp(-0.5))
    assert first_hue.peak_matches[0].hue_distance_degree is None


def test_multi_peak_is_maximum_weighted_and_flat_is_zero() -> None:
    weighted = stationary_user_type_profile_v2("three_life_bpm_green_dominant")
    at_red = evaluate_stationary_preference_v2(
        weighted,
        active=True,
        hue_degree=5.0,
        blink_bpm=55.0,
    )
    at_green = evaluate_stationary_preference_v2(
        weighted,
        active=True,
        hue_degree=125.0,
        blink_bpm=100.0,
    )
    assert at_red.preference_match == 0.75
    assert at_green.preference_match == 1.0
    assert at_red.preference_match == max(item.weighted_match for item in at_red.peak_matches)
    flat = evaluate_stationary_preference_v2(
        stationary_user_type_profile_v2("flat_control"),
        active=True,
        hue_degree=125.0,
        blink_bpm=100.0,
    )
    assert flat.preference_match == 0.0
    assert flat.winning_peak_id is None


def test_v2_evaluator_has_no_session_holder_state_or_history_inputs() -> None:
    parameters = set(inspect.signature(evaluate_stationary_preference_v2).parameters)
    assert parameters == {"profile", "active", "hue_degree", "blink_bpm"}
    assert parameters.isdisjoint(
        {"session_index", "holder_id", "source_b", "k", "w", "q", "e", "history"}
    )
    profile = stationary_user_type_profile_v2(DEFAULT_STATIONARY_USER_TYPE_V2)
    first = evaluate_stationary_preference_v2(
        profile,
        active=True,
        hue_degree=126.0,
        blink_bpm=50.0,
    )
    second = evaluate_stationary_preference_v2(
        profile,
        active=True,
        hue_degree=126.0,
        blink_bpm=50.0,
    )
    assert first == second


def test_stage7_private_adapter_uses_v2_evaluator_for_neutral_axis() -> None:
    profile = stationary_user_type_profile_v2("bpm_common_100_hue_neutral")
    config = stationary_light_response_config_v2(profile)
    stimulus = PhysicalLightStimulus(
        effective_time_us=0,
        active=True,
        render_hue_degree=300.0,
        saturation=1.0,
        value_center=0.425,
        value_amplitude=0.075,
        value_min=0.35,
        value_max=0.5,
        blink_bpm=100.0,
        waveform="sine",
        phase_cycles_at_start=0.0,
    )
    assert config._stage8a_preference_model_version == (STATIONARY_PREFERENCE_LANDSCAPE_V2_VERSION)
    assert config._stage8a_preference_evaluator(stimulus).preference_match == 1.0
    assert "_stage8a1_profile" not in config.to_dict()
