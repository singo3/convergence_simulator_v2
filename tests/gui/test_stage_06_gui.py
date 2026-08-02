"""Offscreen behavior tests for the Stage 6 seven-tab light GUI."""

from __future__ import annotations

import csv

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QWheelEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QScrollArea

from symbiotic_sim_v2.devices.virtual_light.diagnostics import (
    LIGHT_COMMAND_CSV_FIELDS,
    LIGHT_STIMULUS_SEGMENT_CSV_FIELDS,
    LIGHT_STIMULUS_STATE_CSV_FIELDS,
    LIGHT_WAVEFORM_SAMPLE_CSV_FIELDS,
)
from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.light_simulation_window import LightSimulationMainWindow
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    create_light_feedback_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState


@pytest.fixture
def stage_6_gui(qtbot):
    simulation = create_light_feedback_simulation()
    controller = SimulationController(simulation.engine)
    window = LightSimulationMainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(1)
    yield controller, window
    window.close()


def click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_window_has_exact_seven_tabs_copy_flow_cards_preview_and_models(
    stage_6_gui,
) -> None:
    _controller, window = stage_6_gui
    panel = window.light_output_panel

    assert window.windowTitle() == (
        "環境共生型デジタル生命シミュレーター v2 — 光点滅シミュレーター"
    )
    assert "Stage 06" in window.findChild(QLabel, "pageTitle").text()
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "光点滅シミュレーター",
        "3生命・資格競争",
        "Garden出力資格層",
        "Garden入力層",
        "仮想ユーザー",
        "Polar H10",
        "時間・イベント診断",
    ]
    assert window.tabs.currentWidget() is panel
    assert "資格生命のBをHue" in panel.description_label.text()
    assert "GUIの描画fpsは正式な点滅位相ではありません" in (
        panel.virtual_clock_notice.text()
    )
    assert "心拍へ作用させません" in panel.no_response_notice.text()
    assert {label.text() for label in panel.findChildren(QLabel, "lightFlowNode")} == {
        "GardenQualifiedBEvent v2",
        "Garden Light Mapper",
        "LightCommandEvent = I",
        "Virtual PC Light Device",
        "LightStimulusStateEvent",
        "将来の光応答VirtualUser",
    }
    assert set(panel.state_labels) == {
        "active",
        "holder",
        "source_signal",
        "source_b",
        "hue",
        "render_hue",
        "bpm",
        "saturation",
        "value",
        "phase",
        "waveform",
        "effective_time",
        "command_age",
        "command_count",
        "segment_count",
        "phase_reset_count",
        "phase_continuation_count",
    }
    assert not panel.preview_checkbox.isChecked()
    assert not panel.preview_checkbox.isEnabled()
    assert "点滅表示を含みます" in panel.preview_warning_label.text()
    assert panel.color_preview.display_color == QColor("#000000")
    assert panel.command_model.columnCount() == 15
    assert panel.segment_model.columnCount() == 13
    assert panel.table_tabs.tabText(0) == "B→I / command履歴"
    assert panel.table_tabs.tabText(1) == "stimulus segment"

    no_light = window.garden_output_panel.findChild(
        QLabel,
        "gardenOutputNoLightNotice",
    )
    assert no_light is not None
    assert "GardenQualifiedBEvent v2だけ" in no_light.text()


@pytest.mark.parametrize(("width", "height"), ((1560, 980), (1280, 800)))
def test_light_diagnostics_are_scrollable_readable_and_wheel_scrolls_page(
    stage_6_gui,
    qtbot,
    width: int,
    height: int,
) -> None:
    _controller, window = stage_6_gui
    panel = window.light_output_panel
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
    assert panel.color_preview.minimumHeight() >= 240
    assert panel.waveform_chart.minimumHeight() >= 350
    assert panel.parameter_chart.minimumHeight() >= 500
    assert panel.table_tabs.minimumHeight() >= 300
    assert not panel.top_splitter.isCollapsible(0)
    assert not panel.top_splitter.isCollapsible(1)
    for index in range(3):
        assert not panel.chart_table_splitter.isCollapsible(index)

    scroll.verticalScrollBar().setValue(300)
    target = panel.waveform_chart.graphics.viewport()
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


def test_one_second_step_updates_light_records_tables_and_state_at(stage_6_gui, qtbot) -> None:
    _controller, window = stage_6_gui
    panel = window.light_output_panel
    click(qtbot, window.step_second_button)

    assert window.simulation.engine.clock.current_time_us == 1_000_000
    assert panel.command_model.rowCount() == 2
    assert panel.segment_model.rowCount() == 1
    assert panel.parameter_chart.command_count == 2
    assert panel.waveform_chart.sample_count == 51
    assert panel.active_label.text() == "inactive"
    assert panel.current_value_label.text() == "0.000000"
    assert panel.command_count_label.text() == "2"
    assert panel.segment_count_label.text() == "1"


def test_live_preview_uses_device_state_freezes_when_paused_and_turns_off_at_speed(
    stage_6_gui,
    qtbot,
) -> None:
    controller, window = stage_6_gui
    panel = window.light_output_panel
    simulation = window.simulation
    simulation.engine.start()
    simulation.engine.advance_by_us(60_551_540)
    controller.set_speed(SpeedMode.REALTIME)

    assert simulation.engine.clock.state is ClockState.RUNNING
    assert panel.preview_checkbox.isEnabled()
    assert panel.active_label.text() == "active"
    assert panel.hue_label.text() == "125.000°"
    assert panel.blink_bpm_label.text() == "87.500 BPM"
    panel.preview_checkbox.click()
    assert panel.preview_checkbox.isChecked()
    assert panel.color_preview.live_preview_enabled
    assert panel.color_preview.display_color != QColor("#000000")
    state = simulation.virtual_light_device_component.state_at(
        simulation.engine.clock.current_time_us
    )
    assert float(panel.current_value_label.text()) == pytest.approx(state.current_value)

    click(qtbot, window.pause_button)
    assert simulation.engine.clock.state is ClockState.PAUSED
    frozen_color = panel.color_preview.display_color
    frozen_phase = panel.phase_cycles_label.text()
    qtbot.wait(20)
    assert panel.color_preview.display_color == frozen_color
    assert panel.phase_cycles_label.text() == frozen_phase

    window.speed_combo.setCurrentIndex(1)
    assert controller.speed_mode is SpeedMode.X10
    assert not panel.preview_checkbox.isChecked()
    assert not panel.preview_checkbox.isEnabled()
    assert panel.color_preview.display_color == QColor("#000000")


def test_run_to_end_populates_mapping_waveform_segments_csvs_and_reset(
    stage_6_gui,
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    controller, window = stage_6_gui
    simulation = window.simulation
    panel = window.light_output_panel
    simulation.engine.run_until_end()
    controller.set_speed(controller.speed_mode)

    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert simulation.engine.snapshot().executed_event_count == 3_287
    assert panel.command_model.rowCount() == 241
    assert panel.segment_model.rowCount() == 240
    assert panel.parameter_chart.command_count == 241
    assert panel.waveform_chart.sample_count == 751
    assert panel.waveform_chart.command_boundary_count >= 15
    assert len(panel.waveform_chart.value_reference_lines) == 3
    assert len(panel.waveform_chart.active_item.xData) == 751
    assert len(panel.parameter_chart.command_item.xData) == 241
    assert len(panel.parameter_chart.hue_item.xData) == 241
    assert len(panel.parameter_chart.bpm_item.xData) == 241
    assert len(panel.parameter_chart.holder_item.xData) == 241
    assert panel.active_label.text() == "inactive"
    assert panel.current_value_label.text() == "0.000000"
    assert panel.command_count_label.text() == "241"
    assert panel.segment_count_label.text() == "240"
    assert panel.state_labels["phase_reset_count"].text() == "1"
    assert panel.state_labels["phase_continuation_count"].text() == "179"
    assert panel.command_model.data(panel.command_model.index(60, 8)) == "125.000"
    assert panel.command_model.data(panel.command_model.index(60, 9)) == "87.500"
    assert panel.command_model.data(panel.command_model.index(60, 13)) == "no"
    assert panel.command_model.data(panel.command_model.index(60, 14)) == "yes"
    assert not panel.preview_checkbox.isChecked()
    assert not panel.preview_checkbox.isEnabled()

    digests_before = (
        simulation.garden_light_mapper_component.command_digest(),
        simulation.virtual_light_device_component.stimulus_state_digest(),
        simulation.virtual_light_device_component.segment_digest(),
        simulation.virtual_light_device_component.waveform_sample_digest(),
        simulation.engine.deterministic_digest(),
    )
    destinations = (
        tmp_path / "commands.csv",
        tmp_path / "states.csv",
        tmp_path / "segments.csv",
        tmp_path / "waveform.csv",
    )
    selected = iter(destinations)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(next(selected)), "CSV (*.csv)"),
    )
    for button in (
        panel.export_command_button,
        panel.export_state_button,
        panel.export_segment_button,
        panel.export_waveform_button,
    ):
        click(qtbot, button)

    expected = (
        (destinations[0], LIGHT_COMMAND_CSV_FIELDS, 241),
        (destinations[1], LIGHT_STIMULUS_STATE_CSV_FIELDS, 241),
        (destinations[2], LIGHT_STIMULUS_SEGMENT_CSV_FIELDS, 240),
        (destinations[3], LIGHT_WAVEFORM_SAMPLE_CSV_FIELDS, 12_001),
    )
    for path, fields, row_count in expected:
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
        assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == row_count
    assert (
        simulation.garden_light_mapper_component.command_digest(),
        simulation.virtual_light_device_component.stimulus_state_digest(),
        simulation.virtual_light_device_component.segment_digest(),
        simulation.virtual_light_device_component.waveform_sample_digest(),
        simulation.engine.deterministic_digest(),
    ) == digests_before

    controller.reset()
    assert panel.command_model.rowCount() == 0
    assert panel.segment_model.rowCount() == 0
    assert panel.waveform_chart.sample_count == 0
    assert panel.parameter_chart.command_count == 0
    assert panel.active_label.text() == "inactive"
    assert panel.diagnostics_scroll.verticalScrollBar().value() == 0


def test_stopped_config_apply_rebuilds_every_stage_including_light(stage_6_gui, qtbot) -> None:
    _controller, window = stage_6_gui
    old = window.simulation
    window.virtual_user_panel.mean_hr_spin.setValue(76.0)
    click(qtbot, window.virtual_user_panel.apply_settings_button)
    new = window.simulation

    assert new is not old
    assert new.upstream_simulation is not old.upstream_simulation
    assert new.garden_light_mapper_component is not old.garden_light_mapper_component
    assert new.virtual_light_device_component is not old.virtual_light_device_component
    assert new.upstream_simulation.virtual_user_config.mean_heart_rate_bpm == 76.0
    assert window.light_output_panel._mapper_component is (
        new.garden_light_mapper_component
    )
    assert window.light_output_panel._device_component is (
        new.virtual_light_device_component
    )
    assert window.light_output_panel.command_model.rowCount() == 0


def test_window_close_stops_controller_timer(stage_6_gui, qtbot) -> None:
    controller, window = stage_6_gui
    assert controller.timer_active
    window.close()
    qtbot.wait(1)
    assert not controller.timer_active
