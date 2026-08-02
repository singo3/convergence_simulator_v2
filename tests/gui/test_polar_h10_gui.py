"""Offscreen behavior tests for the Stage 3 virtual Polar H10 GUI."""

from __future__ import annotations

import csv

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel

from symbiotic_sim_v2.devices.polar_h10.config import (
    POLAR_H10_MODEL_VERSION,
    RRI_EVENT_SCHEMA_VERSION,
)
from symbiotic_sim_v2.devices.polar_h10.diagnostics import H10_DIAGNOSTIC_CSV_FIELDS
from symbiotic_sim_v2.devices.polar_h10.scenario import create_polar_h10_simulation
from symbiotic_sim_v2.domain.event_types import (
    HEARTBEAT_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
)
from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.polar_h10_window import PolarH10MainWindow
from symbiotic_sim_v2.gui.timeline_widget import EVENT_STYLES
from symbiotic_sim_v2.simulation.clock import ClockState


@pytest.fixture
def stage_3_gui(qtbot):
    simulation = create_polar_h10_simulation()
    controller = SimulationController(simulation.engine)
    window = PolarH10MainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    yield controller, window
    window.close()


def click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def plot_point_count(item) -> int:
    return 0 if item.xData is None else len(item.xData)


def test_stage_3_window_has_required_tabs_explanations_and_fixed_conditions(
    stage_3_gui,
) -> None:
    _controller, window = stage_3_gui
    panel = window.polar_h10_panel

    assert window.windowTitle().endswith("仮想Polar H10")
    assert window.tabs.count() == 3
    assert [window.tabs.tabText(index) for index in range(3)] == [
        "仮想ユーザー",
        "Polar H10",
        "時間・イベント診断",
    ]
    assert window.tabs.currentWidget() is panel
    assert window.virtual_user_panel is window.tabs.widget(0)
    assert window.time_diagnostics_tab is window.tabs.widget(2)

    description = panel.findChild(QLabel, "h10Description")
    responsibility = panel.findChild(QLabel, "h10ResponsibilityNotice")
    diagnostic_notice = panel.findChild(QLabel, "diagnosticNotice")
    boundary_notice = panel.findChild(QLabel, "h10BoundaryNotice")
    assert description is not None and "HeartbeatEventの時刻差からraw RRI" in description.text()
    assert responsibility is not None and "RMSSD、N、Nd、W" in responsibility.text()
    assert diagnostic_notice is not None and "RriMeasurementEventだけ" in diagnostic_notice.text()
    assert boundary_notice is not None and "次StageのGarden入力層" in boundary_notice.text()
    flow_nodes = {label.text() for label in panel.findChildren(QLabel, "flowNode")}
    assert flow_nodes == {
        "仮想ユーザー",
        "HeartbeatEvent",
        "仮想Polar H10",
        "RriMeasurementEvent",
        "将来のGarden入力層",
    }

    assert panel.model_version_label.text() == POLAR_H10_MODEL_VERSION
    assert panel.event_schema_version_label.text() == RRI_EVENT_SCHEMA_VERSION
    assert panel.device_id_label.text() == "polar-h10-sim-001"
    assert panel.expected_user_id_label.text() == "virtual-user-001"
    assert panel.measurement_mode_label.text() == "ideal heartbeat interval"
    assert panel.measurement_noise_label.text() == "none"
    assert panel.packet_loss_label.text() == "none"
    assert panel.latency_label.text() == "none"
    assert panel.artifact_filtering_label.text() == "none"
    assert panel.measurement_model.columnCount() == 10


def test_event_steps_show_first_beat_without_rri_then_second_beat_with_rri_and_timeline(
    stage_3_gui,
    qtbot,
) -> None:
    _controller, window = stage_3_gui
    simulation = window.simulation
    panel = window.polar_h10_panel

    click(qtbot, window.step_event_button)
    first_snapshot = simulation.polar_h10_component.snapshot()
    assert simulation.engine.clock.current_time_us == 0
    assert first_snapshot.observed_heartbeat_count == 1
    assert first_snapshot.rri_measurement_count == 0
    assert panel.heartbeat_count_label.text() == "1 拍"
    assert panel.rri_count_label.text() == "0 件"
    assert panel.measurement_model.rowCount() == 0

    click(qtbot, window.step_event_button)
    second_snapshot = simulation.polar_h10_component.snapshot()
    assert second_snapshot.observed_heartbeat_count == 2
    assert second_snapshot.rri_measurement_count == 1
    assert panel.rri_count_label.text() == "1 件"
    assert panel.latest_rri_label.text().endswith("ms")
    assert panel.latest_error_label.text() == "0 µs"
    assert panel.measurement_model.rowCount() == 1
    assert panel.chart.measurement_count == 1
    assert simulation.engine.snapshot().next_event.event_type == RRI_MEASUREMENT_EVENT_TYPE

    click(qtbot, window.step_event_button)
    event_types = [
        window.log_model.event_at(row).event_type
        for row in range(window.log_model.rowCount())
    ]
    assert event_types == [
        HEARTBEAT_EVENT_TYPE,
        HEARTBEAT_EVENT_TYPE,
        RRI_MEASUREMENT_EVENT_TYPE,
    ]
    heartbeat_lane = EVENT_STYLES[HEARTBEAT_EVENT_TYPE][0]
    rri_lane = EVENT_STYLES[RRI_MEASUREMENT_EVENT_TYPE][0]
    assert heartbeat_lane in window.timeline._executed_y
    assert rri_lane in window.timeline._executed_y


def test_one_second_step_updates_counts_cards_comparison_error_and_table(
    stage_3_gui,
    qtbot,
) -> None:
    _controller, window = stage_3_gui
    panel = window.polar_h10_panel

    click(qtbot, window.step_second_button)
    snapshot = window.simulation.polar_h10_component.snapshot()
    assert window.simulation.engine.clock.current_time_us == 1_000_000
    assert snapshot.observed_heartbeat_count == 2
    assert snapshot.rri_measurement_count == 1
    assert panel.heartbeat_count_label.text() == "2 拍"
    assert panel.rri_count_label.text() == "1 件"
    assert panel.latest_rri_label.text() != "—"
    assert panel.latest_measurement_time_label.text() != "—"
    assert panel.latest_error_label.text() == "0 µs"
    assert panel.max_error_label.text() == "0 µs"
    assert panel.measurement_model.rowCount() == 1
    assert panel.measurement_model.record_at(0).match
    assert plot_point_count(panel.chart.true_rri_item) == 1
    assert plot_point_count(panel.chart.measured_rri_item) == 1
    assert plot_point_count(panel.chart.error_item) == 1
    assert panel.chart.error_item.yData[0] == 0


def test_four_speed_modes_change_controller_policy_without_replacing_components(
    stage_3_gui,
) -> None:
    controller, window = stage_3_gui
    simulation = window.simulation
    virtual_user = simulation.virtual_user_component
    polar_h10 = simulation.polar_h10_component
    modes = (SpeedMode.REALTIME, SpeedMode.X10, SpeedMode.X100, SpeedMode.MAXIMUM)

    assert window.speed_combo.count() == 4
    for index, mode in enumerate(modes):
        window.speed_combo.setCurrentIndex(index)
        assert controller.speed_mode is mode
        assert window.speed_label.text() == mode.label
        assert window.simulation.virtual_user_component is virtual_user
        assert window.simulation.polar_h10_component is polar_h10


def test_stage_2_settings_are_disabled_while_stage_3_runs_or_is_paused(
    stage_3_gui,
    qtbot,
) -> None:
    _controller, window = stage_3_gui
    settings = window.virtual_user_panel.settings_group

    assert settings.isEnabled()
    click(qtbot, window.start_button)
    assert window.simulation.engine.clock.state is ClockState.RUNNING
    assert not settings.isEnabled()
    click(qtbot, window.pause_button)
    assert window.simulation.engine.clock.state is ClockState.PAUSED
    assert not settings.isEnabled()
    click(qtbot, window.reset_button)
    assert window.simulation.engine.clock.state is ClockState.STOPPED
    assert settings.isEnabled()


def test_run_to_end_populates_h10_views_auto_scrolls_and_reset_clears_them(
    stage_3_gui,
    qtbot,
) -> None:
    _controller, window = stage_3_gui
    panel = window.polar_h10_panel

    click(qtbot, window.run_to_end_button)
    qtbot.waitUntil(
        lambda: window.simulation.engine.clock.state is ClockState.COMPLETED,
        timeout=5000,
    )
    qtbot.wait(1)

    device_snapshot = window.simulation.polar_h10_component.snapshot()
    assert device_snapshot.state.value == "completed"
    assert device_snapshot.observed_heartbeat_count == 211
    assert device_snapshot.rri_measurement_count == 210
    assert window.state_label.text() == "完了"
    assert window.time_label.text() == "00:03:00.000"
    assert window.log_model.rowCount() == 422
    assert panel.heartbeat_count_label.text() == "211 拍"
    assert panel.rri_count_label.text() == "210 件"
    assert panel.connection_state_label.text().startswith("completed")
    assert panel.measurement_model.rowCount() == 210
    assert panel.measurement_model.record_at(209).match
    assert panel.chart.measurement_count == 210
    assert plot_point_count(panel.chart.true_rri_item) == 210
    assert plot_point_count(panel.chart.measured_rri_item) == 210
    assert plot_point_count(panel.chart.error_item) == 210
    assert all(value == 0 for value in panel.chart.error_item.yData)
    assert panel.max_error_label.text() == "0 µs"
    scroll_bar = panel.measurement_table.verticalScrollBar()
    assert scroll_bar.maximum() > 0
    assert scroll_bar.value() == scroll_bar.maximum()
    assert not window.virtual_user_panel.settings_group.isEnabled()
    assert not window.run_to_end_button.isEnabled()

    click(qtbot, window.reset_button)
    assert window.simulation.engine.clock.state is ClockState.STOPPED
    assert window.simulation.polar_h10_component.measurement_records() == ()
    assert panel.measurement_model.rowCount() == 0
    assert panel.chart.measurement_count == 0
    assert panel.heartbeat_count_label.text() == "0 拍"
    assert panel.rri_count_label.text() == "0 件"
    assert panel.latest_rri_label.text() == "—"
    assert panel.latest_error_label.text() == "—"
    assert window.log_model.rowCount() == 0
    assert window.timeline.current_time_us == 0


def test_h10_csv_button_uses_dialog_and_writes_raw_and_diagnostic_columns(
    stage_3_gui,
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    _controller, window = stage_3_gui
    panel = window.polar_h10_panel
    destination = tmp_path / "h10-diagnostics.csv"

    click(qtbot, window.step_second_button)
    digest_before = window.simulation.polar_h10_component.measurement_digest()
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(destination), "CSV (*.csv)"),
    )
    click(qtbot, panel.export_csv_button)

    assert destination.is_file()
    with destination.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
    assert tuple(reader.fieldnames or ()) == H10_DIAGNOSTIC_CSV_FIELDS
    assert len(rows) == 1
    assert rows[0]["rri_us"] == rows[0]["diagnostic_true_rri_us"]
    assert rows[0]["absolute_error_us"] == "0"
    assert rows[0]["match"] == "True"
    assert window.simulation.polar_h10_component.measurement_digest() == digest_before


def test_config_apply_replaces_both_components_and_rebinds_both_panels(
    stage_3_gui,
    qtbot,
) -> None:
    _controller, window = stage_3_gui
    old_simulation = window.simulation
    window.tabs.setCurrentWidget(window.virtual_user_panel)
    window.virtual_user_panel.duration_spin.setValue(60)

    click(qtbot, window.virtual_user_panel.apply_settings_button)
    new_simulation = window.simulation
    assert new_simulation is not old_simulation
    assert new_simulation.engine is not old_simulation.engine
    assert new_simulation.virtual_user_component is not old_simulation.virtual_user_component
    assert new_simulation.polar_h10_component is not old_simulation.polar_h10_component
    assert new_simulation.virtual_user_config.duration_seconds == 60
    assert new_simulation.engine.clock.end_time_us == 60_000_000
    assert window.virtual_user_panel._component is new_simulation.virtual_user_component
    assert window.polar_h10_panel._virtual_user_component is (
        new_simulation.virtual_user_component
    )
    assert window.polar_h10_panel._polar_h10_component is new_simulation.polar_h10_component
    assert window.polar_h10_panel.chart._duration_seconds == 60

    click(qtbot, window.step_second_button)
    assert new_simulation.virtual_user_component.snapshot().heartbeat_count == 2
    assert new_simulation.polar_h10_component.snapshot().rri_measurement_count == 1
    assert old_simulation.virtual_user_component.snapshot().heartbeat_count == 0
    assert old_simulation.polar_h10_component.snapshot().observed_heartbeat_count == 0


def test_window_close_stops_controller_timer(stage_3_gui, qtbot) -> None:
    controller, window = stage_3_gui
    assert controller.timer_active
    window.close()
    qtbot.wait(1)
    assert not controller.timer_active
