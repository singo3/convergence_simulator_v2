"""Offscreen acceptance tests for the Stage 7 eight-tab closed-loop GUI."""

from __future__ import annotations

import csv
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QScrollArea

from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.light_response_chart import (
    GARDEN_RESPONSE_CHART_MIN_HEIGHT,
    GARDEN_RESPONSE_PLOT_MIN_HEIGHT,
    LIGHT_RESPONSE_CHART_MIN_HEIGHT,
    LIGHT_RESPONSE_PLOT_MIN_HEIGHT,
    PHYSIOLOGY_CHART_MIN_HEIGHT,
    PHYSIOLOGY_PLOT_MIN_HEIGHT,
    LightStimulusResponseChart,
)
from symbiotic_sim_v2.gui.light_responsive_window import LightResponsiveMainWindow
from symbiotic_sim_v2.runtime.closed_loop.light_responsive_scenario import (
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.light_response.diagnostics import (
    LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FIELDS,
    LIGHT_RESPONSE_SAMPLES_CSV_FIELDS,
    LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS,
    LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS,
    LIGHT_STIMULUS_RECEIPTS_CSV_FIELDS,
)


@pytest.fixture
def stage_7_gui(qtbot):
    simulation = create_light_responsive_closed_loop_simulation()
    controller = SimulationController(simulation.engine)
    window = LightResponsiveMainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(1)
    yield controller, window
    window.close()


def click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_chart_distinguishes_more_physical_audit_splits_than_response_epochs(
    qtbot,
) -> None:
    chart = LightStimulusResponseChart()
    qtbot.addWidget(chart)
    receipts = (
        SimpleNamespace(
            event_time_us=10_000_000,
            active=True,
            hue_match=1.0,
            bpm_match=1.0,
            physical_parameters_changed=True,
            target_changed=True,
            audit_segment_index=1,
            response_dynamics_epoch_index=1,
        ),
        SimpleNamespace(
            event_time_us=20_000_000,
            active=True,
            hue_match=1.0,
            bpm_match=1.0,
            physical_parameters_changed=True,
            target_changed=False,
            audit_segment_index=2,
            response_dynamics_epoch_index=1,
        ),
    )
    audit_segments = tuple(
        SimpleNamespace(segment_index=index, start_time_us=start_time_us)
        for index, start_time_us in enumerate((0,))
    )
    response_epochs = tuple(
        SimpleNamespace(epoch_index=index, start_time_us=start_time_us)
        for index, start_time_us in enumerate((0,))
    )

    chart.set_records((), receipts, audit_segments, response_epochs, 20_000_000)

    assert chart.audit_segment_boundary_count == 3
    assert chart.response_epoch_boundary_count == 2
    assert len(chart._audit_segment_lines) == 3
    assert len(chart._response_epoch_lines) == 2
    assert all(line in chart.physical_plot.items for line in chart._audit_segment_lines)
    assert all(line in chart.response_plot.items for line in chart._response_epoch_lines)
    assert "physical audit segment: 3" in chart.boundary_summary_label.text()
    assert "response dynamics epoch: 2" in chart.boundary_summary_label.text()


def test_window_has_exact_tabs_copy_flow_settings_cards_tables_and_boundaries(
    stage_7_gui,
) -> None:
    _controller, window = stage_7_gui
    panel = window.light_response_user_panel

    assert window.windowTitle() == (
        "環境共生型デジタル生命シミュレーター v2 — 光応答仮想ユーザー閉ループ"
    )
    assert "Stage 07" in window.findChild(QLabel, "pageTitle").text()
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "光応答仮想ユーザー",
        "光点滅シミュレーター",
        "3生命・資格競争",
        "Garden出力資格層",
        "Garden入力層",
        "仮想ユーザー心拍",
        "Polar H10",
        "時間・イベント診断",
    ]
    assert window.tabs.currentWidget() is panel
    assert "固定された反応特性" in panel.description_label.text()
    assert "1run中に変化しません" in panel.stationary_notice.text()
    assert "RMSSDやNを直接変更せず" in panel.boundary_notice.text()
    assert "実データ未校正" in panel.assumption_notice.text()
    assert [
        label.text()
        for label in panel.findChildren(QLabel, "lightResponseFlowNode")
    ] == [
        "LightStimulusStateEvent",
        "物理光projection",
        "Hue/BPM適合度",
        "一次遅れ反応R(t)",
        "呼吸性RRI変動幅・平均RRI",
        "HeartbeatEvent",
        "H10",
        "RRI",
        "Garden RMSSD/N",
    ]
    assert panel.preset_combo.currentData() == "aligned_green_center"
    assert panel.preferred_hue_spin.value() == 125.0
    assert panel.preferred_bpm_spin.value() == 87.5
    assert panel.respiratory_gain_spin.value() == 30.0
    assert panel.mean_rri_gain_spin.value() == 15.0
    assert panel.onset_tau_spin.value() == 8.0
    assert panel.recovery_tau_spin.value() == 12.0
    assert set(panel.state_labels) == {
        "light_active",
        "hue",
        "bpm",
        "hue_match",
        "bpm_match",
        "preference_match",
        "response_target",
        "response_level",
        "base_respiratory",
        "effective_respiratory",
        "base_mean_rri",
        "effective_mean_rri",
        "latest_rri",
        "latest_hr",
        "heartbeat_count",
    }
    assert panel.receipt_model.columnCount() == 16
    assert panel.audit_segment_model.columnCount() == 22
    assert panel.response_epoch_model.columnCount() == 11
    assert panel.heartbeat_model.columnCount() == 13
    assert [
        panel.table_tabs.tabText(index)
        for index in range(panel.table_tabs.count())
    ] == [
        "light receipt",
        "physical audit segment",
        "response dynamics epoch",
        "responsive heartbeat",
    ]
    assert panel.garden_evaluation_chart.source_is_garden_evaluation_records
    assert window.virtual_user_panel._component is window.simulation.component
    assert window.polar_h10_panel._virtual_user_component is window.simulation.component

    light_panel = window.light_output_panel
    assert "LightStimulusStateEventだけ" in light_panel.no_response_notice.text()
    assert not light_panel.preview_checkbox.isChecked()
    assert not light_panel.preview_checkbox.isEnabled()
    assert light_panel.color_preview.display_color == QColor("#000000")

    with pytest.raises(ValueError, match="not silently clipped"):
        panel.set_config(replace(panel.config, blink_sigma_bpm=500.1))


@pytest.mark.parametrize(("width", "height"), ((1560, 980), (1280, 800)))
def test_response_page_is_scrollable_and_charts_tables_keep_readable_heights(
    stage_7_gui,
    qtbot,
    width: int,
    height: int,
) -> None:
    _controller, window = stage_7_gui
    panel = window.light_response_user_panel
    window.resize(width, height)
    qtbot.wait(20)

    scroll = panel.diagnostics_scroll
    assert isinstance(scroll, QScrollArea)
    assert scroll.widget() is panel.diagnostics_content
    assert scroll.widgetResizable()
    assert scroll.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.verticalScrollBar().maximum() > 0
    assert scroll.horizontalScrollBar().maximum() == 0
    assert panel.light_response_chart.minimumHeight() >= LIGHT_RESPONSE_CHART_MIN_HEIGHT
    assert panel.physiology_chart.minimumHeight() >= PHYSIOLOGY_CHART_MIN_HEIGHT
    assert panel.garden_evaluation_chart.minimumHeight() >= (
        GARDEN_RESPONSE_CHART_MIN_HEIGHT
    )
    assert panel.table_tabs.minimumHeight() >= 300
    assert all(
        plot.minimumHeight() >= LIGHT_RESPONSE_PLOT_MIN_HEIGHT
        for plot in panel.light_response_chart.plots
    )
    assert all(
        plot.minimumHeight() >= PHYSIOLOGY_PLOT_MIN_HEIGHT
        for plot in panel.physiology_chart.plots
    )
    assert all(
        plot.minimumHeight() >= GARDEN_RESPONSE_PLOT_MIN_HEIGHT
        for plot in panel.garden_evaluation_chart.plots
    )
    assert not panel.top_splitter.isCollapsible(0)
    assert not panel.top_splitter.isCollapsible(1)
    for index in range(4):
        assert not panel.chart_table_splitter.isCollapsible(index)

    scroll.verticalScrollBar().setValue(300)
    target = panel.light_response_chart.graphics.viewport()
    center = target.rect().center()
    wheel_event = QWheelEvent(
        QPointF(center),
        QPointF(target.mapToGlobal(center)),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    before = scroll.verticalScrollBar().value()
    QApplication.sendEvent(target, wheel_event)
    assert wheel_event.isAccepted()
    assert scroll.verticalScrollBar().value() > before


def test_preset_rebuild_and_settings_lock_cover_stopped_running_paused_completed_reset(
    stage_7_gui,
    qtbot,
) -> None:
    controller, window = stage_7_gui
    panel = window.light_response_user_panel
    original_engine = window.simulation.engine

    control_index = panel.preset_combo.findData("light_insensitive_control")
    panel.preset_combo.setCurrentIndex(control_index)
    panel.preset_combo.activated.emit(control_index)
    assert window.simulation.engine is not original_engine
    assert panel.preset_name == "light_insensitive_control"
    assert window.simulation.light_response_config.maximum_respiratory_amplitude_gain_ms == 0
    assert window.simulation.light_response_config.maximum_mean_rri_increase_ms == 0
    assert panel.settings_frame.isEnabled()

    click(qtbot, window.start_button)
    assert window.simulation.engine.clock.state is ClockState.RUNNING
    assert not panel.settings_frame.isEnabled()
    click(qtbot, window.pause_button)
    assert window.simulation.engine.clock.state is ClockState.PAUSED
    assert not panel.settings_frame.isEnabled()
    click(qtbot, window.reset_button)
    assert window.simulation.engine.clock.state is ClockState.STOPPED
    assert panel.settings_frame.isEnabled()

    aligned_index = panel.preset_combo.findData("aligned_green_center")
    panel.preset_combo.setCurrentIndex(aligned_index)
    panel.preset_combo.activated.emit(aligned_index)
    assert panel.preset_name == "aligned_green_center"
    assert window.simulation.light_response_config.maximum_respiratory_amplitude_gain_ms == 30

    window.simulation.engine.run_until_end()
    controller.set_speed(controller.speed_mode)
    assert window.simulation.engine.clock.state is ClockState.COMPLETED
    assert not panel.settings_frame.isEnabled()
    click(qtbot, window.reset_button)
    assert panel.settings_frame.isEnabled()

    panel.preferred_hue_spin.setValue(130.0)
    click(qtbot, panel.apply_settings_button)
    assert panel.preset_name == "custom"
    assert panel.preset_combo.currentData() == "custom"
    assert panel.preset_combo.currentText() == "custom (手動設定)"
    assert window.simulation.light_response_config.preferred_hue_degree == 130.0

    aligned_index = panel.preset_combo.findData("aligned_green_center")
    panel.preset_combo.setCurrentIndex(aligned_index)
    panel.preset_combo.activated.emit(aligned_index)
    assert panel.preset_name == "aligned_green_center"
    assert panel.preset_combo.findData("custom") == -1


def test_step_and_complete_populate_state_charts_garden_adapter_and_tables(
    stage_7_gui,
    qtbot,
) -> None:
    controller, window = stage_7_gui
    panel = window.light_response_user_panel
    click(qtbot, window.step_second_button)

    assert window.simulation.engine.clock.current_time_us == 1_000_000
    assert panel.heartbeat_model.rowCount() == 2
    assert panel.receipt_model.rowCount() == 2
    assert panel.light_response_chart.sample_count == 11
    assert panel.light_active_label.text() == "inactive"
    assert panel.response_level_label.text() == "0.000000"

    window.simulation.engine.resume()
    window.simulation.engine.advance_by_us(60_000_000)
    window.simulation.engine.pause()
    panel.update_diagnostics(window.simulation.engine.snapshot())
    assert len(window.simulation.component.response_segments()) == 1
    assert len(window.simulation.component.response_dynamics_epoch_records()) == 1
    assert panel.light_response_chart.audit_segment_boundary_count == 2
    assert panel.light_response_chart.response_epoch_boundary_count == 2

    window.simulation.engine.run_until_end()
    controller.set_speed(controller.speed_mode)
    component = window.simulation.component
    assert window.simulation.engine.clock.state is ClockState.COMPLETED
    assert panel.heartbeat_model.rowCount() == len(
        component.responsive_heartbeat_records()
    )
    assert panel.receipt_model.rowCount() == 241
    assert panel.light_response_chart.sample_count == 2_401
    assert panel.light_response_chart.receipt_count == 241
    audit_segments = component.response_segments()
    response_epochs = component.response_dynamics_epoch_records()
    assert panel.audit_segment_model.rowCount() == len(audit_segments)
    assert panel.response_epoch_model.rowCount() == len(response_epochs)
    assert panel.light_response_chart.audit_segment_boundary_count == len(
        audit_segments
    )
    assert panel.light_response_chart.response_epoch_boundary_count == len(
        response_epochs
    )
    assert panel.light_response_chart.segment_boundary_count == len(audit_segments)
    assert len(panel.light_response_chart._audit_segment_lines) == len(audit_segments)
    assert len(panel.light_response_chart._response_epoch_lines) == len(
        response_epochs
    )
    assert "physical audit segment" in (
        panel.light_response_chart.boundary_summary_label.text()
    )
    assert "response dynamics epoch" in (
        panel.light_response_chart.boundary_summary_label.text()
    )
    assert len(panel.light_response_chart._first_active_lines) == 1
    assert panel.physiology_chart.record_count == panel.heartbeat_model.rowCount()
    assert panel.garden_evaluation_chart.evaluation_count == 4
    assert len(panel.garden_evaluation_chart.baseline_item.xData) == 1
    assert [len(item.xData) for item in panel.garden_evaluation_chart.bundle_items] == [
        1,
        1,
        1,
    ]
    assert len(panel.garden_evaluation_chart.n_item.xData) == 4
    assert panel.receipt_model.data(panel.receipt_model.index(60, 3)) == "125.000°"
    assert panel.receipt_model.data(panel.receipt_model.index(60, 4)) == (
        "87.500 BPM"
    )
    assert panel.receipt_model.data(panel.receipt_model.index(60, 7)) == "1.000000"
    assert panel.receipt_model.data(panel.receipt_model.index(60, 10)) == "yes"
    assert panel.receipt_model.data(panel.receipt_model.index(60, 11)) == "yes"
    assert panel.receipt_model.data(panel.receipt_model.index(60, 12)) == "1"
    assert panel.receipt_model.data(panel.receipt_model.index(60, 13)) == "1"
    assert "physical_parameters" in panel.receipt_model.data(
        panel.receipt_model.index(60, 14)
    )
    assert panel.receipt_model.data(panel.receipt_model.index(60, 15)) == "no"
    assert panel.audit_segment_model.data(
        panel.audit_segment_model.index(1, 17)
    ) == "1"
    assert panel.response_epoch_model.data(
        panel.response_epoch_model.index(1, 4)
    ) == "1.000000"
    assert panel.state_labels["light_active"].text() == "inactive"
    assert panel.state_labels["response_target"].text() == "0.000000"
    assert float(panel.state_labels["response_level"].text()) > 0.99
    assert panel.state_labels["effective_respiratory"].text() == "65.000 ms"
    assert window.polar_h10_panel.measurement_model.rowCount() == (
        panel.heartbeat_model.rowCount() - 1
    )

    click(qtbot, window.reset_button)
    assert panel.receipt_model.rowCount() == 0
    assert panel.audit_segment_model.rowCount() == 0
    assert panel.response_epoch_model.rowCount() == 0
    assert panel.heartbeat_model.rowCount() == 0
    assert panel.light_response_chart.sample_count == 0
    assert panel.light_response_chart.audit_segment_boundary_count == 0
    assert panel.light_response_chart.response_epoch_boundary_count == 0
    assert panel.physiology_chart.record_count == 0
    assert panel.garden_evaluation_chart.evaluation_count == 0
    assert panel.diagnostics_scroll.verticalScrollBar().value() == 0


def test_all_stage_7_csv_buttons_use_core_exporters_without_mutating_digests(
    stage_7_gui,
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    controller, window = stage_7_gui
    panel = window.light_response_user_panel
    component = window.simulation.component
    window.simulation.engine.run_until_end()
    controller.set_speed(controller.speed_mode)
    digests_before = (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_dynamics_epoch_digest(),
        component.response_sample_digest(),
        window.simulation.engine.deterministic_digest(),
    )
    paths = [
        tmp_path / "receipts.csv",
        tmp_path / "segments.csv",
        tmp_path / "epochs.csv",
        tmp_path / "heartbeats.csv",
        tmp_path / "samples.csv",
    ]
    destinations = iter(paths)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(next(destinations)), "CSV (*.csv)"),
    )

    for button in (
        panel.export_receipt_button,
        panel.export_segment_button,
        panel.export_epoch_button,
        panel.export_heartbeat_button,
        panel.export_sample_button,
    ):
        click(qtbot, button)
    expected_headers = (
        LIGHT_STIMULUS_RECEIPTS_CSV_FIELDS,
        LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS,
        LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FIELDS,
        LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS,
        LIGHT_RESPONSE_SAMPLES_CSV_FIELDS,
    )
    for path, fields in zip(paths, expected_headers, strict=True):
        with path.open(encoding="utf-8", newline="") as handle:
            assert tuple(next(csv.reader(handle))) == fields

    assert (
        component.heartbeat_digest(),
        component.responsive_diagnostic_digest(),
        component.light_receipt_digest(),
        component.response_segment_digest(),
        component.response_dynamics_epoch_digest(),
        component.response_sample_digest(),
        window.simulation.engine.deterministic_digest(),
    ) == digests_before


def test_stage_6_live_preview_safety_is_preserved_in_stage_7(
    stage_7_gui,
    qtbot,
) -> None:
    controller, window = stage_7_gui
    light_panel = window.light_output_panel
    simulation = window.simulation
    simulation.engine.start()
    simulation.engine.advance_by_us(60_551_540)
    controller.set_speed(SpeedMode.REALTIME)

    assert simulation.engine.clock.state is ClockState.RUNNING
    assert light_panel.preview_checkbox.isEnabled()
    assert light_panel.active_label.text() == "active"
    click(qtbot, light_panel.preview_checkbox)
    assert light_panel.preview_checkbox.isChecked()
    assert light_panel.color_preview.display_color != QColor("#000000")

    window.speed_combo.setCurrentIndex(1)
    assert controller.speed_mode is SpeedMode.X10
    assert not light_panel.preview_checkbox.isChecked()
    assert not light_panel.preview_checkbox.isEnabled()
    assert light_panel.color_preview.display_color == QColor("#000000")
