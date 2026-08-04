from __future__ import annotations

import pytest

from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    STANDARD_LIFE_HUE_BANDS,
    StationaryPreferenceHeatmapProjectionV2,
    project_stationary_preference_heatmap_v2,
    stationary_user_type_profile_v2,
)


def test_core_heatmap_projection_is_strict_and_json_ready() -> None:
    profile = stationary_user_type_profile_v2("three_life_bpm_equal")
    projection = project_stationary_preference_heatmap_v2(
        profile,
        hue_step_degree=5.0,
        bpm_step=5.0,
    )

    assert projection.user_type_id == profile.user_type_id
    assert projection.hue_values_degree[0] == 0.0
    assert projection.hue_values_degree[-1] == 360.0
    assert projection.blink_bpm_values[0] == 10.0
    assert projection.blink_bpm_values[-1] == 165.0
    assert projection.life_hue_bands == STANDARD_LIFE_HUE_BANDS
    assert StationaryPreferenceHeatmapProjectionV2.from_dict(
        projection.to_dict()
    ) == projection

    unknown = projection.to_dict()
    unknown["condition_id"] = "must-not-enter-hidden-truth"
    with pytest.raises(ValueError, match="unknown heatmap fields"):
        StationaryPreferenceHeatmapProjectionV2.from_dict(unknown)


def test_neutral_axis_and_flat_control_are_precomputed_in_core() -> None:
    bpm_profile = stationary_user_type_profile_v2("bpm_common_100_hue_neutral")
    bpm_map = project_stationary_preference_heatmap_v2(
        bpm_profile,
        hue_step_degree=120.0,
        bpm_step=5.0,
    )
    row_100 = bpm_map.preference_match_rows[
        bpm_map.blink_bpm_values.index(100.0)
    ]
    assert row_100 == pytest.approx((1.0, 1.0, 1.0, 1.0))

    hue_profile = stationary_user_type_profile_v2("green_hue_dominant_broad_bpm")
    hue_map = project_stationary_preference_heatmap_v2(
        hue_profile,
        hue_step_degree=5.0,
        bpm_step=155.0,
    )
    hue_index = hue_map.hue_values_degree.index(125.0)
    assert hue_map.preference_match_rows[0][hue_index] == pytest.approx(1.0)
    assert hue_map.preference_match_rows[1][hue_index] == pytest.approx(1.0)

    flat_map = project_stationary_preference_heatmap_v2(
        stationary_user_type_profile_v2("flat_control"),
        hue_step_degree=120.0,
        bpm_step=155.0,
    )
    assert all(value == 0.0 for row in flat_map.preference_match_rows for value in row)


def test_heatmap_projection_rejects_bool_steps_and_mismatched_rows() -> None:
    profile = stationary_user_type_profile_v2("green_single_peak_narrow")
    with pytest.raises(TypeError, match="hue_step_degree"):
        project_stationary_preference_heatmap_v2(profile, hue_step_degree=True)

    projection = project_stationary_preference_heatmap_v2(
        profile,
        hue_step_degree=180.0,
        bpm_step=155.0,
    ).to_dict()
    projection["preference_match_rows"] = [[0.0]]
    with pytest.raises(ValueError, match="rows must match"):
        StationaryPreferenceHeatmapProjectionV2.from_dict(projection)
