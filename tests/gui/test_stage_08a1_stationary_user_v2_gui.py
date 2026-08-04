from __future__ import annotations

from pathlib import Path

import pytest

from symbiotic_sim_v2.convergence import RollingConvergenceConfig
from symbiotic_sim_v2.gui.controller import SimulationController
from symbiotic_sim_v2.gui.fatigue_sigma_lab_window import FatigueSigmaLabMainWindow
from symbiotic_sim_v2.gui.multi_session_convergence_window import (
    create_stage8a_preview_simulation,
)
from symbiotic_sim_v2.gui.stationary_user_type_v2_panel import (
    STAGE8A1_USER_TYPE_TABLE_MIN_HEIGHT,
    StationaryUserTypeV2Panel,
)
from symbiotic_sim_v2.runtime.multi_session import (
    MultiSessionRelationMemoryRunner,
    MultiSessionRunnerConfig,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    project_stationary_preference_heatmap_v2,
    stationary_user_type_profile_v2,
    stationary_user_type_v2_ids,
)


@pytest.fixture(scope="module")
def v2_profiles_and_maps():
    profiles = {
        user_type_id: stationary_user_type_profile_v2(user_type_id)
        for user_type_id in stationary_user_type_v2_ids()
    }
    maps = {
        user_type_id: project_stationary_preference_heatmap_v2(
            profile,
            hue_step_degree=5.0,
            bpm_step=5.0,
        )
        for user_type_id, profile in profiles.items()
    }
    return profiles, maps


def test_v2_profile_panel_shows_modes_physiology_truth_map_and_attractors(
    qtbot,
    v2_profiles_and_maps,
) -> None:
    profiles, maps = v2_profiles_and_maps
    panel = StationaryUserTypeV2Panel(profiles, maps)
    qtbot.addWidget(panel)
    panel.resize(1_280, 800)
    panel.show()
    qtbot.wait(20)

    assert panel.selected_user_type_id == "green_hue_dominant_broad_bpm"
    assert panel.profile_labels["expected_structure"].text() == "life_dominant"
    assert panel.profile_labels["expected_dominant_life_id"].text() == "life-green"
    assert "16.000 ms" in panel.profile_labels["physiology"].text()
    assert "6.000 ms" in panel.profile_labels["physiology"].text()
    assert panel.peak_model.rowCount() == 1
    assert panel.peak_model.index(0, 1).data() == "gaussian"
    assert panel.peak_model.index(0, 4).data() == "neutral"
    assert panel.peak_model.index(0, 5).data() == "—"
    assert panel.peak_model.index(0, 6).data() == "—"
    assert panel.peak_table.minimumHeight() == STAGE8A1_USER_TYPE_TABLE_MIN_HEIGHT
    assert panel.heatmap_shape == (32, 73)
    assert panel.heatmap_maximum == pytest.approx(1.0)
    assert len(panel._band_items) == 3
    assert len(panel._attractor_lines) == 1
    assert "Digital Life、Runtime、Garden" in panel.hidden_truth_notice.text()
    assert panel.diagnostics_scroll.verticalScrollBar().maximum() > 0

    panel.set_selected_user_type("bpm_common_100_hue_neutral")
    assert panel.peak_model.index(0, 1).data() == "neutral"
    assert panel.peak_model.index(0, 4).data() == "gaussian"
    assert "Hue neutral / BPM 100.0" in panel.attractor_summary.text()
    assert len(panel._attractor_lines) == 1

    panel.set_selected_user_type("three_life_bpm_equal")
    assert panel.peak_model.rowCount() == 3
    assert panel.expected_attractor_points.xData.tolist() == [5.0, 125.0, 250.0]
    assert panel.expected_attractor_points.yData.tolist() == [55.0, 100.0, 145.0]

    panel.set_selected_user_type("flat_control")
    assert panel.peak_model.rowCount() == 0
    assert panel.heatmap_maximum == 0.0
    assert panel.attractor_summary.text() == "expected attractor: none"


def test_v2_profile_panel_has_no_preference_formula_or_evaluator_import() -> None:
    source = Path(
        "src/symbiotic_sim_v2/gui/stationary_user_type_v2_panel.py"
    ).read_text(encoding="utf-8")
    assert "evaluate_stationary_preference" not in source
    assert "gaussian_match" not in source
    assert "math.exp" not in source
    assert "preference_match_rows" in source


def test_stage8a1_window_nests_v2_and_v1_profiles_and_syncs_presets(
    qtbot,
    v2_profiles_and_maps,
) -> None:
    profiles, maps = v2_profiles_and_maps
    runner = MultiSessionRelationMemoryRunner(
        MultiSessionRunnerConfig(
            convergence_config=RollingConvergenceConfig(maximum_sessions=4)
        )
    )
    preview = create_stage8a_preview_simulation(runner)
    controller = SimulationController(preview.engine)
    window = FatigueSigmaLabMainWindow(
        controller,
        preview,
        runner,
        user_types_v2={key: value.to_dict() for key, value in profiles.items()},
        user_type_heatmaps_v2={key: value.to_dict() for key, value in maps.items()},
    )
    qtbot.addWidget(window)
    window.resize(1_280, 800)
    window.show()
    qtbot.wait(20)
    try:
        v2_panel = window.stationary_user_type_v2_panel
        assert v2_panel is not None
        nested = window.stationary_user_type_panel.stage8a1_profile_tabs
        assert nested is not None
        assert nested.count() == 2
        assert nested.widget(0) is v2_panel
        assert nested.widget(1) is window.stationary_user_type_panel.diagnostics_scroll
        assert window.tabs.indexOf(window.stationary_user_type_panel) == 1

        v2_panel.set_selected_user_type("three_life_bpm_green_dominant")
        assert (
            window.fatigue_sigma_lab_panel.single_panel.user_type_combo.currentData()
            == "three_life_bpm_green_dominant"
        )
        single = window.fatigue_sigma_lab_panel.single_panel
        single.set_result({"sessions_completed": 1})
        window._sync_v2_profile_editability()
        assert not v2_panel.user_type_combo.isEnabled()
        v2_panel.user_type_selected.emit("flat_control")
        assert single.user_type_combo.currentData() == "three_life_bpm_green_dominant"

        single.reset_views()
        window._sync_v2_profile_editability()
        assert v2_panel.user_type_combo.isEnabled()
        index = single.user_type_combo.findData("flat_control")
        single.user_type_combo.setCurrentIndex(index)
        assert v2_panel.selected_user_type_id == "flat_control"
    finally:
        controller.shutdown()
        window.close()
