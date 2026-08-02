"""Offscreen behavior tests for the Stage 2 virtual-user GUI."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.virtual_user_window import VirtualUserMainWindow
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.scenario import create_virtual_user_simulation


@pytest.fixture
def stage_2_gui(qtbot):
    simulation = create_virtual_user_simulation()
    controller = SimulationController(simulation.engine)
    window = VirtualUserMainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    yield controller, window
    window.close()


def click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def run_to_end(qtbot, window) -> None:
    click(qtbot, window.run_to_end_button)
    qtbot.waitUntil(
        lambda: window.simulation.engine.clock.state is ClockState.COMPLETED,
        timeout=5000,
    )


def test_stage_2_window_constructs_with_both_tabs_and_standard_settings(stage_2_gui) -> None:
    _controller, window = stage_2_gui
    panel = window.virtual_user_panel
    assert window.windowTitle().endswith("外部刺激なし仮想ユーザー")
    assert window.tabs.count() == 2
    assert window.tabs.tabText(0) == "仮想ユーザー"
    assert window.tabs.tabText(1) == "時間・イベント診断"
    assert panel.duration_spin.value() == 180
    assert panel.mean_hr_spin.value() == 70.0
    assert panel.respiratory_amplitude_spin.value() == 35.0
    assert panel.seed_spin.value() == 20260802
    assert window.time_label.text() == "00:00:00.000"


def test_settings_apply_rebuilds_stopped_scenario_and_clears_views(stage_2_gui, qtbot) -> None:
    _controller, window = stage_2_gui
    panel = window.virtual_user_panel
    panel.duration_spin.setValue(60)
    panel.mean_hr_spin.setValue(80.0)
    click(qtbot, panel.apply_settings_button)
    assert window.simulation.config.duration_seconds == 60
    assert window.simulation.config.mean_heart_rate_bpm == 80.0
    assert window.simulation.engine.clock.end_time_us == 60_000_000
    assert panel.heartbeat_model.rowCount() == 0
    assert panel.chart.record_count == 0
    assert window.log_model.rowCount() == 0


def test_restore_standard_values_rebuilds_default_config(stage_2_gui, qtbot) -> None:
    _controller, window = stage_2_gui
    panel = window.virtual_user_panel
    panel.mean_hr_spin.setValue(100.0)
    click(qtbot, panel.apply_settings_button)
    assert window.simulation.config.mean_heart_rate_bpm == 100.0
    click(qtbot, panel.restore_defaults_button)
    assert window.simulation.config == VirtualUserConfig()
    assert panel.mean_hr_spin.value() == 70.0


def test_settings_are_disabled_while_running_and_paused_then_enabled_after_reset(
    stage_2_gui,
    qtbot,
) -> None:
    _controller, window = stage_2_gui
    panel = window.virtual_user_panel
    click(qtbot, window.start_button)
    assert window.simulation.engine.clock.state is ClockState.RUNNING
    assert not panel.settings_group.isEnabled()
    click(qtbot, window.pause_button)
    assert window.simulation.engine.clock.state is ClockState.PAUSED
    assert not panel.settings_group.isEnabled()
    click(qtbot, window.reset_button)
    assert window.simulation.engine.clock.state is ClockState.STOPPED
    assert panel.settings_group.isEnabled()


def test_one_second_step_updates_heartbeats_table_and_all_primary_charts(
    stage_2_gui,
    qtbot,
) -> None:
    _controller, window = stage_2_gui
    panel = window.virtual_user_panel
    click(qtbot, window.step_second_button)
    assert window.simulation.engine.clock.current_time_us == 1_000_000
    assert window.simulation.component.snapshot().heartbeat_count == 2
    assert panel.heartbeat_model.rowCount() == 2
    assert panel.chart.record_count == 2
    assert len(panel.chart.heartbeat_item.xData) == 2
    assert len(panel.chart.rri_item.xData) == 1
    assert len(panel.chart.hr_item.xData) == 1
    assert panel.latest_rri_label.text().endswith("ms")


def test_next_event_executes_only_first_heartbeat(stage_2_gui, qtbot) -> None:
    _controller, window = stage_2_gui
    click(qtbot, window.step_event_button)
    assert window.simulation.component.snapshot().heartbeat_count == 1
    assert window.simulation.engine.clock.current_time_us == 0
    assert window.virtual_user_panel.heartbeat_model.rowCount() == 1


def test_four_speed_selections_change_policy_not_config(stage_2_gui) -> None:
    controller, window = stage_2_gui
    original_config = window.simulation.config
    modes = (SpeedMode.REALTIME, SpeedMode.X10, SpeedMode.X100, SpeedMode.MAXIMUM)
    for index, mode in enumerate(modes):
        window.speed_combo.setCurrentIndex(index)
        assert controller.speed_mode is mode
        assert window.speed_label.text() == mode.label
        assert window.simulation.config == original_config


def test_run_to_end_populates_rmssd_components_table_and_time_diagnostics(
    stage_2_gui,
    qtbot,
) -> None:
    _controller, window = stage_2_gui
    panel = window.virtual_user_panel
    run_to_end(qtbot, window)
    assert window.simulation.engine.clock.state is ClockState.COMPLETED
    assert window.time_label.text() == "00:03:00.000"
    assert panel.heartbeat_model.rowCount() == 211
    assert panel.chart.record_count == 211
    assert len(panel.chart.rri_item.xData) == 210
    assert len(panel.chart.hr_item.xData) == 210
    assert len(panel.chart.rmssd_item.xData) > 100
    assert len(panel.chart.respiratory_item.xData) == 210
    assert panel.rolling_rmssd_label.text() != "—"
    assert panel.full_rmssd_label.text() != "—"
    assert window.log_model.rowCount() == 212
    assert not panel.settings_group.isEnabled()
    assert not window.run_to_end_button.isEnabled()


def test_reset_clears_charts_tables_logs_and_reproduces_series(stage_2_gui, qtbot) -> None:
    _controller, window = stage_2_gui
    run_to_end(qtbot, window)
    first_digest = window.simulation.component.heartbeat_digest()
    click(qtbot, window.reset_button)
    panel = window.virtual_user_panel
    assert panel.heartbeat_model.rowCount() == 0
    assert panel.chart.record_count == 0
    assert window.log_model.rowCount() == 0
    assert window.simulation.component.heartbeat_records() == ()
    run_to_end(qtbot, window)
    assert window.simulation.component.heartbeat_digest() == first_digest


def test_time_diagnostic_tab_remains_available_after_execution(stage_2_gui, qtbot) -> None:
    _controller, window = stage_2_gui
    run_to_end(qtbot, window)
    window.tabs.setCurrentIndex(1)
    assert window.tabs.currentWidget() is window.time_diagnostics_tab
    assert window.timeline.current_time_us == 180_000_000
    assert window.event_table.model().rowCount() == 212


def test_window_close_stops_qtimer(stage_2_gui, qtbot) -> None:
    controller, window = stage_2_gui
    assert controller.timer_active
    window.close()
    qtbot.wait(1)
    assert not controller.timer_active
