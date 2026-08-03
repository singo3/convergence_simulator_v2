"""Stage 8A fixed user-type and stationary landscape contracts."""

from __future__ import annotations

import dataclasses
import inspect
import math

import pytest

from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    STATIONARY_PREFERENCE_LANDSCAPE_VERSION,
    StationaryPreferencePeak,
    StationaryUserTypeProfile,
    evaluate_stationary_preference,
    stationary_light_response_config,
    stationary_preference_evaluator,
    stationary_user_type_ids,
    stationary_user_type_profile,
)


def active_stimulus(hue: float, bpm: float) -> PhysicalLightStimulus:
    return PhysicalLightStimulus(
        effective_time_us=0,
        active=True,
        render_hue_degree=hue,
        saturation=1.0,
        value_center=0.425,
        value_amplitude=0.075,
        value_min=0.35,
        value_max=0.5,
        blink_bpm=bpm,
        waveform="sine",
        phase_cycles_at_start=0.0,
    )


def test_all_six_presets_are_exact_immutable_and_json_round_trippable() -> None:
    expected = {
        "green_broad_strong": (129.0, 5.0, 125.0, 35.0, 1.0, 30.0, 15.0),
        "green_narrow_moderate": (129.0, 1.5, 125.0, 12.0, 1.0, 16.0, 6.0),
        "red_broad_moderate": (7.0, 4.0, 70.0, 35.0, 1.0, 18.0, 7.0),
        "blue_broad_weak": (252.0, 5.0, 120.0, 40.0, 1.0, 8.0, 3.0),
    }
    assert stationary_user_type_ids() == (
        "green_broad_strong",
        "green_narrow_moderate",
        "red_broad_moderate",
        "blue_broad_weak",
        "red_blue_dual_peak",
        "flat_control",
    )
    for user_type_id in stationary_user_type_ids():
        profile = stationary_user_type_profile(user_type_id)
        assert profile.user_type_id == user_type_id
        assert len({peak.peak_id for peak in profile.peaks}) == len(profile.peaks)
        assert StationaryUserTypeProfile.from_json(profile.to_json()) == profile
        with pytest.raises(dataclasses.FrozenInstanceError):
            profile.user_type_id = "moving"  # type: ignore[misc]
    for user_type_id, values in expected.items():
        profile = stationary_user_type_profile(user_type_id)
        peak = profile.peaks[0]
        assert (
            peak.preferred_hue_degree,
            peak.hue_sigma_degree,
            peak.preferred_blink_bpm,
            peak.blink_sigma_bpm,
            peak.peak_weight,
            profile.maximum_respiratory_amplitude_gain_ms,
            profile.maximum_mean_rri_increase_ms,
        ) == values
    dual = stationary_user_type_profile("red_blue_dual_peak")
    assert tuple(peak.peak_id for peak in dual.peaks) == ("red-local", "blue-global")
    assert tuple(peak.peak_weight for peak in dual.peaks) == (0.75, 1.0)
    flat = stationary_user_type_profile("flat_control")
    assert flat.peaks == ()
    assert flat.maximum_respiratory_amplitude_gain_ms == 0.0
    assert flat.maximum_mean_rri_increase_ms == 0.0


def test_peak_schema_has_exact_six_semantic_fields_and_is_strict() -> None:
    peak = StationaryPreferencePeak("peak", 0.0, 1.0, 10.0, 2.0, 0.5)
    # Peak model version belongs to the containing profile metadata; the peak
    # payload itself is exactly the six fields listed by the Stage 8A contract.
    assert set(peak.to_dict()) == {
        "peak_id",
        "preferred_hue_degree",
        "hue_sigma_degree",
        "preferred_blink_bpm",
        "blink_sigma_bpm",
        "peak_weight",
    }
    assert StationaryPreferencePeak.from_json(peak.to_json()) == peak
    values = peak.to_dict()
    with pytest.raises(ValueError, match="missing"):
        StationaryPreferencePeak.from_dict(
            {key: value for key, value in values.items() if key != "peak_id"}
        )
    with pytest.raises(ValueError, match="unknown"):
        StationaryPreferencePeak.from_dict({**values, "future": 1})
    with pytest.raises(ValueError, match="duplicate"):
        StationaryPreferencePeak.from_json('{"peak_id":"a","peak_id":"b"}')


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("preferred_hue_degree", True),
        ("hue_sigma_degree", 0.0),
        ("hue_sigma_degree", 180.1),
        ("preferred_blink_bpm", 9.9),
        ("blink_sigma_bpm", 0.0),
        ("peak_weight", 1.1),
        ("preferred_hue_degree", math.nan),
        ("blink_sigma_bpm", math.inf),
    ),
)
def test_peak_rejects_bool_nonfinite_and_out_of_range(field: str, value: object) -> None:
    values = StationaryPreferencePeak("peak", 20.0, 2.0, 80.0, 10.0, 1.0).to_dict()
    values[field] = value
    with pytest.raises((TypeError, ValueError)):
        StationaryPreferencePeak.from_dict(values)


def test_profile_rejects_missing_unknown_duplicate_peak_and_nonfinite() -> None:
    profile = stationary_user_type_profile("green_narrow_moderate")
    values = profile.to_dict()
    with pytest.raises(ValueError, match="missing"):
        StationaryUserTypeProfile.from_dict(
            {key: value for key, value in values.items() if key != "description_ja"}
        )
    with pytest.raises(ValueError, match="unknown"):
        StationaryUserTypeProfile.from_dict({**values, "moving_peak": True})
    duplicate = dict(values)
    duplicate["peaks"] = [values["peaks"][0], values["peaks"][0]]
    with pytest.raises(ValueError, match="unique"):
        StationaryUserTypeProfile.from_dict(duplicate)
    invalid_gain = dict(values)
    invalid_gain["maximum_mean_rri_increase_ms"] = math.nan
    with pytest.raises(ValueError, match="finite"):
        StationaryUserTypeProfile.from_dict(invalid_gain)


def test_single_peak_formula_broad_narrow_and_inactive_flat_are_exact() -> None:
    broad = stationary_user_type_profile("green_broad_strong")
    narrow = stationary_user_type_profile("green_narrow_moderate")
    at_center = evaluate_stationary_preference(
        broad,
        active=True,
        hue_degree=129.0,
        blink_bpm=125.0,
    )
    assert at_center.preference_match == 1.0
    one_sigma = evaluate_stationary_preference(
        broad,
        active=True,
        hue_degree=134.0,
        blink_bpm=160.0,
    )
    assert one_sigma.preference_match == pytest.approx(math.exp(-1.0))
    same_offset_narrow = evaluate_stationary_preference(
        narrow,
        active=True,
        hue_degree=134.0,
        blink_bpm=160.0,
    )
    assert same_offset_narrow.preference_match < one_sigma.preference_match
    inactive = evaluate_stationary_preference(
        broad,
        active=False,
        hue_degree=None,
        blink_bpm=None,
    )
    assert inactive.preference_match == 0.0
    flat = evaluate_stationary_preference(
        stationary_user_type_profile("flat_control"),
        active=True,
        hue_degree=129.0,
        blink_bpm=125.0,
    )
    assert flat.preference_match == 0.0
    assert flat.winning_peak_id is None


def test_dual_peak_uses_maximum_weighted_response_not_sum() -> None:
    profile = stationary_user_type_profile("red_blue_dual_peak")
    red = evaluate_stationary_preference(
        profile,
        active=True,
        hue_degree=6.0,
        blink_bpm=70.0,
    )
    blue = evaluate_stationary_preference(
        profile,
        active=True,
        hue_degree=252.0,
        blink_bpm=120.0,
    )
    between = evaluate_stationary_preference(
        profile,
        active=True,
        hue_degree=129.0,
        blink_bpm=95.0,
    )
    assert red.preference_match == 0.75
    assert red.winning_peak_id == "red-local"
    assert blue.preference_match == 1.0
    assert blue.winning_peak_id == "blue-global"
    assert between.preference_match == max(
        match.weighted_match for match in between.peak_matches
    )


def test_evaluator_signature_has_no_session_holder_source_or_history_input() -> None:
    parameters = set(inspect.signature(evaluate_stationary_preference).parameters)
    assert parameters == {"profile", "active", "hue_degree", "blink_bpm"}
    assert parameters.isdisjoint(
        {"session_index", "time_us", "bundle", "holder_id", "source_b", "k", "w", "q", "e"}
    )
    profile = stationary_user_type_profile("green_narrow_moderate")
    first = evaluate_stationary_preference(
        profile,
        active=True,
        hue_degree=129.5,
        blink_bpm=120.0,
    )
    second = evaluate_stationary_preference(
        profile,
        active=True,
        hue_degree=129.5,
        blink_bpm=120.0,
    )
    assert first == second


def test_private_stage7_adapter_is_frozen_and_carries_profile_physiology() -> None:
    profile = stationary_user_type_profile("blue_broad_weak")
    config = stationary_light_response_config(profile)
    assert config.maximum_respiratory_amplitude_gain_ms == 8.0
    assert config.maximum_mean_rri_increase_ms == 3.0
    assert config.response_onset_time_constant_seconds == 8.0
    assert config.response_recovery_time_constant_seconds == 12.0
    assert config._stage8a_preference_model_version == (
        STATIONARY_PREFERENCE_LANDSCAPE_VERSION
    )
    expected = stationary_preference_evaluator(profile)(active_stimulus(252.0, 120.0))
    assert config._stage8a_preference_evaluator(active_stimulus(252.0, 120.0)) == expected
    assert expected.preference_match == 1.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        config._stage8a_profile = stationary_user_type_profile("flat_control")  # type: ignore[misc]
    assert "_stage8a_profile" not in config.to_dict()
