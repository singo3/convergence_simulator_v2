"""Offscreen acceptance tests for the Stage 8A eleven-tab main window."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from symbiotic_sim_v2.convergence import RollingConvergenceConfig
from symbiotic_sim_v2.gui.controller import SimulationController
from symbiotic_sim_v2.gui.multi_session_convergence_window import (
    TAB_TITLES,
    WINDOW_TITLE,
    MultiSessionConvergenceMainWindow,
    create_stage8a_preview_simulation,
)
from symbiotic_sim_v2.runtime.multi_session import (
    MultiSessionRelationMemoryRunner,
    MultiSessionRunnerConfig,
)
from symbiotic_sim_v2.simulation.clock import ClockState


@pytest.fixture
def stage8a_window(qtbot):
    runner = MultiSessionRelationMemoryRunner(
        MultiSessionRunnerConfig(
            convergence_config=RollingConvergenceConfig(maximum_sessions=4)
        )
    )
    preview = create_stage8a_preview_simulation(runner)
    controller = SimulationController(preview.engine)
    window = MultiSessionConvergenceMainWindow(controller, preview, runner)
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(20)
    yield controller, window
    controller.shutdown()
    window.close()


def test_window_has_exact_title_tabs_fixed_profile_and_locked_retained_controls(
    stage8a_window,
) -> None:
    _controller, window = stage8a_window
    assert window.windowTitle() == WINDOW_TITLE
    assert tuple(
        window.tabs.tabText(index) for index in range(window.tabs.count())
    ) == TAB_TITLES
    assert window.tabs.currentWidget() is window.multi_session_panel
    assert window.runner.config.user_type_id == "green_narrow_moderate"
    assert window.stationary_user_type_panel.selected_user_type_id == (
        "green_narrow_moderate"
    )
    assert window.simulation.engine.clock.state is ClockState.STOPPED
    assert not window.start_button.isEnabled()
    assert not window.run_to_end_button.isEnabled()
    assert not window.light_response_user_panel.settings_frame.isEnabled()
    assert not window.virtual_user_panel.settings_group.isEnabled()
    assert window.virtual_user_panel.seed_spin.value() == 2_264_431_022


def test_next_session_binds_latest_nine_tabs_and_reset_restores_fresh_boundary(
    stage8a_window,
) -> None:
    _controller, window = stage8a_window
    window._run_one_session()
    state = window.runner.state()
    assert state.completed_session_count == state.valid_session_count == 1
    assert window.simulation.engine.clock.state is ClockState.COMPLETED
    assert window.multi_session_panel.session_history_model.rowCount() == 1
    assert window.multi_session_panel.convergence_history_model.rowCount() == 1
    assert window.relation_memory_panel.transition_model.rowCount() == 12
    assert window.light_response_user_panel.receipt_model.rowCount() == 241
    assert window.simulation.garden_input_component.snapshot().baseline_available
    assert all(
        persistent.session_count == 1
        for persistent in state.current_persistent_state_by_life.values()
    )

    window._reset_multi_session_run()
    reset = window.runner.state()
    assert reset.completed_session_count == reset.next_session_index == 0
    assert window.simulation.engine.clock.state is ClockState.STOPPED
    assert window.multi_session_panel.session_history_model.rowCount() == 0
    assert not window.simulation.garden_input_component.snapshot().baseline_available
    assert all(
        persistent.session_count == 0
        for persistent in reset.current_persistent_state_by_life.values()
    )


def test_four_sessions_render_three_of_four_cluster_and_separate_truth(
    stage8a_window,
) -> None:
    _controller, window = stage8a_window
    state = window.runner.run_all()
    window._install_session_simulation(window.runner.current_simulation)
    window._refresh_aggregate_views()
    latest = state.convergence_records[-1]
    truth = window.runner.truth_alignment_records()[-1]
    assert latest.member_session_indices == (0, 1, 3)
    assert latest.outlier_session_indices == (2,)
    assert latest.currently_converged
    assert truth.truth_classification == "stable_suboptimal"
    assert window.multi_session_panel.chart.session_count == 4
    assert window.multi_session_panel.chart.cluster_member_count == 3
    assert window.multi_session_panel.chart.outlier_count == 1
    assert window.multi_session_panel.state_labels["support"].text() == "3 / 4"
    assert window.multi_session_panel.state_labels[
        "truth_classification"
    ].text() == "stable_suboptimal"
    chart = window.multi_session_panel.chart
    presentation_count = sum(
        len(outcome.bundle_presentations) for outcome in state.session_outcomes
    )
    assert presentation_count == 19
    assert sum(
        0 if item.xData is None else len(item.xData)
        for item in chart.bundle_timeline_items.values()
    ) == presentation_count
    assert sum(
        0 if item.xData is None else len(item.xData)
        for item in chart.bundle_presentation_items.values()
    ) == presentation_count
    assert len(chart.rejected_k_item.xData) == 3
    assert len(chart.accepted_k_item.xData) == 1
    assert chart.window_line.value() == 4.0
    assert chart.nearest_peak_text.isVisible()
    assert "green" in window.multi_session_panel.state_labels["nearest_peak"].text()
    first_row = window.multi_session_panel.session_history_model.row_at(0)
    assert first_row["initial_hue_bpm"] == (125.0, 87.5)
    assert first_row["final_hue_bpm"] == (125.0, 87.5)


def test_pause_can_be_armed_before_run_all_and_stops_after_exactly_one_session(
    stage8a_window,
    qtbot,
) -> None:
    _controller, window = stage8a_window
    panel = window.multi_session_panel
    assert panel.pause_after_session_button.isEnabled()

    qtbot.mouseClick(
        panel.pause_after_session_button,
        Qt.MouseButton.LeftButton,
    )
    qtbot.mouseClick(panel.run_all_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.runner.state().next_session_index == 1, timeout=5_000)
    qtbot.waitUntil(lambda: not window._run_all_pending, timeout=5_000)

    assert window.runner.state().completed_session_count == 1
    assert not panel.pause_after_session_button.isChecked()
    assert panel.run_all_button.isEnabled()

    qtbot.mouseClick(panel.run_all_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.runner.state().next_session_index == 4, timeout=8_000)
    assert window.runner.state().completed_session_count == 4
