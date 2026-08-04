"""Offscreen contracts for the Stage 8A.1 record-backed Qt surface."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer

from symbiotic_sim_v2.convergence import RollingConvergenceConfig
from symbiotic_sim_v2.gui.controller import SimulationController
from symbiotic_sim_v2.gui.fatigue_sigma_grid_panel import (
    GRID_TABLE_MIN_HEIGHT,
    MAXIMUM_PLANNED_SESSIONS,
    FatigueSigmaGridPanel,
)
from symbiotic_sim_v2.gui.fatigue_sigma_lab_backend import (
    CoreFatigueSigmaLabBackend,
)
from symbiotic_sim_v2.gui.fatigue_sigma_lab_panel import (
    LAB_SUBTAB_TITLES,
    FatigueSigmaLabPanel,
)
from symbiotic_sim_v2.gui.fatigue_sigma_lab_window import (
    SCREENSHOT_TARGETS,
    TAB_TITLES,
    WINDOW_TITLE,
    FatigueSigmaLabMainWindow,
)
from symbiotic_sim_v2.gui.fatigue_sigma_single_run_panel import (
    DEFAULT_MASTER_SEED,
)
from symbiotic_sim_v2.gui.multi_session_convergence_window import (
    TAB_TITLES as STAGE8A_TAB_TITLES,
)
from symbiotic_sim_v2.gui.multi_session_convergence_window import (
    MultiSessionConvergenceMainWindow,
    create_stage8a_preview_simulation,
)
from symbiotic_sim_v2.runtime.multi_session import (
    MultiSessionRelationMemoryRunner,
    MultiSessionRunnerConfig,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    project_stationary_preference_heatmap_v2,
    stationary_user_type_profile_v2,
)

USER_TYPES = {
    "green_hue_dominant_broad_bpm": {
        "display_name_ja": "緑Hue優勢・BPM中立",
        "expected_structure": "life_dominant",
        "peaks": (
            {
                "peak_id": "green-hue",
                "hue_axis_mode": "gaussian",
                "preferred_hue_degree": 125.0,
                "hue_sigma_degree": 3.0,
                "bpm_axis_mode": "neutral",
                "preferred_blink_bpm": None,
                "blink_sigma_bpm": None,
                "peak_weight": 1.0,
            },
        ),
    },
    "flat_control": {
        "display_name_ja": "無反応対照",
        "expected_structure": "no_preference",
        "peaks": (),
    },
}


SINGLE_RESULT = {
    "sessions_completed": 2,
    "session_pattern_trajectory": (
        {
            "session_index": 0,
            "digital_life_id": "life-red",
            "hue_degree": 5.0,
            "blink_bpm": 55.0,
            "point_kind": "final",
            "cluster_member": True,
            "e": 0.04,
        },
        {
            "session_index": 0,
            "digital_life_id": "life-red",
            "hue_degree": 12.0,
            "blink_bpm": 60.0,
            "point_kind": "trial",
            "presentation_time_us": 120_000_000,
            "adoption_result": "rejected",
        },
        {
            "session_index": 1,
            "digital_life_id": "life-green",
            "hue_degree": 125.0,
            "blink_bpm": 100.0,
            "point_kind": "final",
            "outlier": True,
            "e": 0.05,
        },
        {
            "session_index": 2,
            "digital_life_id": "life-blue",
            "hue_degree": 250.0,
            "blink_bpm": 145.0,
            "point_kind": "final",
            "e": 0.02,
        },
    ),
    "fatigue_trajectory": (
        {
            "session_index": 0,
            "digital_life_id": "life-red",
            "e_at_session_start": 0.0,
            "e_after_baseline": 0.0,
            "e_after_active": 0.05,
            "e_before_session_end_policy": 0.049,
            "e_after_session_end_policy": 0.049,
            "full_recovery_applied": False,
        },
        {
            "session_index": 0,
            "digital_life_id": "life-green",
            "e_at_session_start": 0.03,
            "e_after_baseline": 0.029,
            "e_after_active": 0.029,
            "e_before_session_end_policy": 0.028,
            "e_after_session_end_policy": 0.0,
            "full_recovery_applied": True,
        },
    ),
    "sigma_trajectory": (
        {
            "session_index": 0,
            "w_anchor_session": 0.7,
            "reference_sigma_at_w": 0.20,
            "sigma_multiplier": 1.25,
            "effective_sigma": 0.25,
            "resulting_delta_hue": 12.0,
            "resulting_delta_bpm": 4.0,
            "candidate_accepted": False,
        },
    ),
    "structured_convergence": {
        "dominant_life_id": "life-green",
        "summary_classification": "mixed_structured_convergence",
        "early_single_life_pattern_signal": True,
    },
    "structured_convergence_history": (
        {
            "session_index": 1,
            "dominant_life_id": "life-green",
            "dominant_life_share": 0.75,
            "strict_consecutive_run": 4,
            "one_outlier_tolerant_longest_run": 6,
            "latest_session_outlier": True,
            "return_within_1_rate": 1.0,
            "bpm_common_support": 6,
            "bpm_common_medoid_bpm": 100.0,
            "bpm_common_range": 18.0,
            "bpm_common_participating_life_ids": ("life-red", "life-green"),
            "attractor_count": 2,
            "summary_classification": "mixed_structured_convergence",
            "early_single_life_pattern_signal": True,
        },
    ),
    "truth_alignment": {"truth_classification": "partially_correct_structure"},
    "mechanical_rotation_diagnostics": {
        "classification": "no_warning",
        "holder_switch_rate": 0.25,
    },
    "w_ceiling_diagnostics": {"classification": "exploration_identifiable"},
    "experiment_manifest": {
        "formal_spec_adoption": False,
        "stationary_preference": True,
        "moving_preference": False,
        "p_explore_modified": False,
        "epsilon_accept_modified": False,
        "experiment_manifest_digest": "manifest-digest",
    },
    "fatigue_trajectory_digest": "fatigue-digest",
    "sigma_trajectory_digest": "sigma-digest",
    "structured_convergence_digest": "convergence-digest",
}


GRID_RESULT = {
    "completed_conditions": 2,
    "failed_conditions": 0,
    "completed_session_runs": 240,
    "condition_summaries": (
        {
            "condition_id": "f003-s050",
            "selected_session_fatigue_target": 0.03,
            "sigma_multiplier": 0.50,
            "replicate_count": 5,
            "completed_replicate_count": 5,
            "failed_replicate_count": 0,
            "correct_structure_rate": 0.8,
            "life_dominant_convergence_rate": 0.8,
            "holder_switch_rate": 0.2,
        },
        {
            "condition_id": "f005-s100",
            "selected_session_fatigue_target": 0.05,
            "sigma_multiplier": 1.0,
            "replicate_count": 5,
            "completed_replicate_count": 4,
            "failed_replicate_count": 1,
            "correct_structure_rate": 0.4,
            "life_dominant_convergence_rate": 0.6,
            "holder_switch_rate": 0.4,
        },
    ),
}


class _FakeBackend:
    def __init__(self) -> None:
        self.actions: list[tuple[str, dict[str, object]]] = []
        self.block_run_all = False
        self.started = threading.Event()

    def create_single_operation(self, action, settings):
        self.actions.append((action, dict(settings)))

        def operation(progress, control):
            self.started.set()
            if action == "run_all" and self.block_run_all:
                for completed in range(1_000):
                    progress(
                        {
                            "completed_sessions": completed,
                            "total_sessions": 24,
                            "message": "running",
                        }
                    )
                    if control.cancel_requested or control.pause_requested:
                        return SINGLE_RESULT
                    time.sleep(0.001)
            progress({"completed_sessions": 2, "total_sessions": 24, "message": "done"})
            return SINGLE_RESULT

        return operation

    def create_grid_operation(self, settings):
        self.actions.append(("grid", dict(settings)))

        def operation(progress, _control):
            progress(
                {
                    "completed_session_runs": 240,
                    "total_planned_session_runs": 240,
                    "message": "done",
                }
            )
            return GRID_RESULT

        return operation

    def reset_single(self, _settings):
        return None

    def save_single_state(self, path):
        self.actions.append(("save", {"path": Path(path)}))

    def load_single_state(self, path):
        self.actions.append(("load", {"path": Path(path)}))
        return SINGLE_RESULT

    def export_csv(self, path):
        self.actions.append(("csv", {"path": Path(path)}))

    def current_simulation(self):
        return None


def _runner_and_preview():
    runner = MultiSessionRelationMemoryRunner(
        MultiSessionRunnerConfig(convergence_config=RollingConvergenceConfig(maximum_sessions=4))
    )
    return runner, create_stage8a_preview_simulation(runner)


def test_four_lab_subtabs_defaults_scroll_and_manifest_are_explicit(qtbot) -> None:
    panel = FatigueSigmaLabPanel(USER_TYPES)
    qtbot.addWidget(panel)
    panel.resize(1_280, 800)
    panel.show()
    qtbot.wait(20)

    assert (
        tuple(panel.subtabs.tabText(index) for index in range(panel.subtabs.count()))
        == LAB_SUBTAB_TITLES
    )
    single = panel.single_panel
    assert single.user_type_combo.currentData() == "green_hue_dominant_broad_bpm"
    assert single.fatigue_target_spin.value() == pytest.approx(0.05)
    assert single.sigma_multiplier_spin.value() == pytest.approx(1.0)
    assert single.maximum_sessions_spin.value() == 24
    assert int(single.master_seed_spin.value()) == DEFAULT_MASTER_SEED
    assert single.diagnostics_scroll.widgetResizable()
    assert single.diagnostics_scroll.verticalScrollBar().maximum() > 0
    assert not single.chart_splitter.isCollapsible(0)
    assert not single.chart_splitter.isCollapsible(1)
    assert panel.grid_panel.result_table.minimumHeight() == GRID_TABLE_MIN_HEIGHT
    assert panel.manifest_panel.flag_labels["moving_preference"].text() == "false"
    assert panel.manifest_panel.flag_labels["p_explore_modified"].text() == "false"
    assert "formal_spec_adoption=false" in panel.manifest_panel.formal_notice.text()


def test_record_views_keep_actual_hue_life_shape_and_independent_diagnostics(qtbot) -> None:
    panel = FatigueSigmaLabPanel(USER_TYPES)
    qtbot.addWidget(panel)
    panel.set_single_result(SINGLE_RESULT)
    chart = panel.single_panel.session_chart

    assert chart.final_point_count == 3
    assert chart.trial_point_count == 1
    assert chart.final_symbols == ("o", "t", "s")
    assert chart.final_hues == (5.0, 125.0, 250.0)
    assert chart.hover_payloads[1]["point_kind"] == "final"
    assert panel.single_panel.fatigue_chart.full_recovery_count == 1
    assert panel.single_panel.sigma_chart.record_count == 1
    assert panel.single_panel.sigma_chart.reference_item.yData.tolist() == [0.2]
    assert panel.single_panel.sigma_chart.effective_item.yData.tolist() == [0.25]
    assert panel.single_panel.sigma_chart.w_anchor_item.yData.tolist() == [0.7]
    assert panel.single_panel.sigma_chart.multiplier_item.yData.tolist() == [1.25]
    assert panel.single_panel.card_labels["early"].text() == "yes"
    assert panel.structured_panel.history_model.rowCount() == 1
    assert "mixed_structured_convergence" in (panel.structured_panel.card_labels["summary"].text())
    assert "strict=4" in panel.structured_panel.card_labels["life"].text()
    assert "latest-outlier=yes" in panel.structured_panel.card_labels["life"].text()
    assert not panel.single_panel.settings_frame.isEnabled() or all(
        not widget.isEnabled() for widget in panel.single_panel.settings_widgets
    )


def test_grid_metrics_reference_separation_and_budget_rejection(qtbot) -> None:
    panel = FatigueSigmaGridPanel(USER_TYPES)
    qtbot.addWidget(panel)
    panel.set_result(GRID_RESULT)

    assert panel.result_model.rowCount() == 2
    assert panel.heatmap.cell_count == 2
    assert panel.heatmap.reference_label.isVisible()
    assert "unselected full recoveryなし" in panel.reference_card.text()
    metric_index = panel.metric_combo.findData("holder_switch_rate")
    panel.metric_combo.setCurrentIndex(metric_index)
    assert panel.heatmap.metric == "holder_switch_rate"

    null_metric = panel.metric_combo.findData("median_first_convergence_session")
    panel.metric_combo.setCurrentIndex(null_metric)
    assert panel.heatmap.cell_count == 0
    panel.metric_combo.setCurrentIndex(metric_index)
    assert panel.heatmap.cell_count == 2

    panel.preset_combo.setCurrentIndex(panel.preset_combo.findData("detailed"))
    panel.fatigue_values_edit.setText(",".join(str(index / 100) for index in range(21)))
    panel.sigma_values_edit.setText(",".join(str(index / 100) for index in range(25, 151)))
    panel.maximum_sessions_spin.setValue(100)
    panel.replicates_spin.setValue(20)
    assert panel.total_planned_session_runs > MAXIMUM_PLANNED_SESSIONS
    assert not panel.run_button.isEnabled()
    assert "超えるため拒否" in panel.planned_label.text()


def test_fatigue_chart_expands_for_carried_selected_e(qtbot) -> None:
    panel = FatigueSigmaLabPanel(USER_TYPES)
    qtbot.addWidget(panel)
    result = {
        **SINGLE_RESULT,
        "fatigue_trajectory": (
            {
                **SINGLE_RESULT["fatigue_trajectory"][0],
                "e_after_active": 0.63,
                "e_before_session_end_policy": 0.62,
                "e_after_session_end_policy": 0.62,
            },
        ),
    }
    panel.set_single_result(result)

    assert panel.single_panel.fatigue_chart.display_y_max > 0.63


def test_reference_comparison_card_shows_separate_reference_diagnostics(qtbot) -> None:
    panel = FatigueSigmaLabPanel(USER_TYPES)
    qtbot.addWidget(panel)
    result = {
        **SINGLE_RESULT,
        "reference_arm_metadata": {"enabled": True, "available": True},
        "reference_arm_result": {
            "structured_convergence_history": (
                {"summary_classification": "bpm_common_convergence"},
            ),
            "truth_alignment_history": (
                {"truth_classification": "correct_structure"},
            ),
            "w_ceiling_diagnostics": {
                "classification": "exploration_identifiable"
            },
            "digest": "abcdef0123456789",
        },
    }
    panel.set_single_result(result)

    text = panel.single_panel.card_labels["reference"].text()
    assert "paired complete" in text
    assert "bpm_common_convergence" in text
    assert "correct_structure" in text
    assert "abcdef012345" in text


def test_loaded_state_condition_replaces_visible_settings_before_lock(qtbot) -> None:
    panel = FatigueSigmaLabPanel(USER_TYPES)
    qtbot.addWidget(panel)
    loaded = {
        **SINGLE_RESULT,
        "condition": {
            "user_type_id": "flat_control",
            "selected_session_fatigue_target": 0.15,
            "sigma_multiplier": 1.5,
            "maximum_sessions": 60,
            "master_seed": 42,
        },
        "reference_arm_metadata": {"enabled": True, "available": True},
    }
    single = panel.single_panel
    single.apply_loaded_result_settings(loaded)
    panel.set_single_result(loaded)

    assert single.user_type_combo.currentData() == "flat_control"
    assert single.fatigue_target_spin.value() == pytest.approx(0.15)
    assert single.sigma_multiplier_spin.value() == pytest.approx(1.5)
    assert single.maximum_sessions_spin.value() == 60
    assert int(single.master_seed_spin.value()) == 42
    assert single.compare_reference_checkbox.isChecked()
    assert all(not widget.isEnabled() for widget in single.settings_widgets)


def test_tab_first_window_retains_stage8a_widgets_and_worker_cancel_seam(qtbot) -> None:
    runner, preview = _runner_and_preview()
    controller = SimulationController(preview.engine)
    backend = _FakeBackend()
    window = FatigueSigmaLabMainWindow(
        controller,
        preview,
        runner,
        lab_backend=backend,
        user_types_v2=USER_TYPES,
    )
    qtbot.addWidget(window)
    window.resize(1_280, 800)
    window.show()
    qtbot.wait(20)
    try:
        assert window.windowTitle() == WINDOW_TITLE
        assert (
            tuple(window.tabs.tabText(index) for index in range(window.tabs.count())) == TAB_TITLES
        )
        assert len(STAGE8A_TAB_TITLES) == 11
        assert isinstance(window, MultiSessionConvergenceMainWindow)
        assert window.tabs.currentWidget() is window.fatigue_sigma_lab_panel
        assert window.tabs.indexOf(window.stationary_user_type_panel) == 1
        assert window.tabs.indexOf(window.multi_session_panel) == 2
        for target in SCREENSHOT_TARGETS:
            window.prepare_screenshot_target(target)
            assert window.screenshot_widget(target) is not None

        single = window.fatigue_sigma_lab_panel.single_panel
        qtbot.mouseClick(single.next_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: window._lab_thread is None, timeout=5_000)
        assert backend.actions[0][0] == "next_session"
        assert single.session_chart.final_point_count == 3
        assert not single.user_type_combo.isEnabled()

        backend.block_run_all = True
        backend.started.clear()
        qtbot.mouseClick(single.run_all_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(backend.started.is_set, timeout=2_000)
        assert window.lab_operation_active
        qtbot.mouseClick(single.cancel_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: window._lab_thread is None, timeout=5_000)
        assert "cancelled at safe boundary" in single.progress_label.text()
    finally:
        if window.lab_operation_active:
            window._request_lab_cancel()
            qtbot.waitUntil(lambda: window._lab_thread is None, timeout=5_000)
        controller.shutdown()
        window.close()


def test_production_backend_qthread_is_responsive_and_cancels_on_session_boundary(
    qtbot,
) -> None:
    runner, preview = _runner_and_preview()
    controller = SimulationController(preview.engine)
    backend = CoreFatigueSigmaLabBackend()
    window = FatigueSigmaLabMainWindow(
        controller,
        preview,
        runner,
        lab_backend=backend,
        user_types_v2=USER_TYPES,
    )
    qtbot.addWidget(window)
    window.resize(1_280, 800)
    window.show()
    qtbot.wait(20)
    event_loop_ticks: list[int] = []
    timer = QTimer(window)
    timer.setInterval(5)
    timer.timeout.connect(lambda: event_loop_ticks.append(time.monotonic_ns()))
    timer.start()
    try:
        single = window.fatigue_sigma_lab_panel.single_panel
        single.maximum_sessions_spin.setValue(60)
        ticks_before_run = len(event_loop_ticks)

        qtbot.mouseClick(single.run_all_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: single.progress_bar.value() >= 1, timeout=20_000)

        assert window.lab_operation_active
        assert len(event_loop_ticks) > ticks_before_run
        qtbot.mouseClick(single.cancel_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: window._lab_thread is None, timeout=20_000)

        completed = int(single.card_labels["sessions_completed"].text())
        assert 1 <= completed < 60
        assert single.progress_bar.value() == completed
        assert single.progress_label.text() == "cancelled at safe boundary"
        assert single.run_all_button.isEnabled()

        core_runner = backend._single_runner
        assert core_runner is not None
        result = core_runner.result()
        assert result.sessions_completed == completed
        assert len(result.session_outcomes) == completed
        assert core_runner.can_run_next_session
        assert not result.stopped_on_error
        assert all(
            state["session_count"] == completed
            for state in result.persistent_state.values()
        )
    finally:
        timer.stop()
        if window.lab_operation_active:
            window._request_lab_cancel()
            qtbot.waitUntil(lambda: window._lab_thread is None, timeout=20_000)
        controller.shutdown()
        window.close()


def test_zero_session_single_cancel_restores_both_profile_selectors(qtbot) -> None:
    runner, preview = _runner_and_preview()
    controller = SimulationController(preview.engine)
    profile_objects = {
        user_type_id: stationary_user_type_profile_v2(user_type_id)
        for user_type_id in USER_TYPES
    }
    window = FatigueSigmaLabMainWindow(
        controller,
        preview,
        runner,
        lab_backend=_FakeBackend(),
        user_types_v2={
            user_type_id: profile.to_dict()
            for user_type_id, profile in profile_objects.items()
        },
        user_type_heatmaps_v2={
            user_type_id: project_stationary_preference_heatmap_v2(
                profile,
                hue_step_degree=30.0,
                bpm_step=20.0,
            ).to_dict()
            for user_type_id, profile in profile_objects.items()
        },
    )
    qtbot.addWidget(window)
    try:
        single = window.fatigue_sigma_lab_panel.single_panel
        profile = window.stationary_user_type_v2_panel
        assert profile is not None
        assert single.user_type_combo.isEnabled()
        assert profile.user_type_combo.isEnabled()

        single.set_operation_active(True)
        window._sync_v2_profile_editability()
        assert not single.user_type_combo.isEnabled()
        assert not profile.user_type_combo.isEnabled()

        window._lab_operation_kind = "single"
        window._lab_cancelled(None)
        assert single.user_type_combo.isEnabled()
        assert profile.user_type_combo.isEnabled()
    finally:
        controller.shutdown()
        window.close()
