"""Offscreen behavior tests for the Stage 4 Garden input GUI."""

from __future__ import annotations

import csv
import math

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QScrollArea

from symbiotic_sim_v2.domain.event_types import GARDEN_PHASE_CHANGED_EVENT_TYPE
from symbiotic_sim_v2.garden.input_layer.diagnostics import (
    GARDEN_EVALUATION_CSV_FIELDS,
    GARDEN_RRI_CSV_FIELDS,
    GARDEN_SIGNAL_CSV_FIELDS,
)
from symbiotic_sim_v2.garden.input_layer.scenario import create_garden_input_simulation
from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.garden_input_window import GardenInputMainWindow
from symbiotic_sim_v2.gui.timeline_widget import EVENT_STYLES
from symbiotic_sim_v2.simulation.clock import ClockState


@pytest.fixture
def stage_4_gui(qtbot):
    simulation = create_garden_input_simulation()
    controller = SimulationController(simulation.engine)
    window = GardenInputMainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    yield controller, window
    window.close()


def click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def plot_point_count(item) -> int:
    return 0 if item.xData is None else len(item.xData)


def test_stage_4_window_has_exact_tabs_copy_flow_fixed_values_and_notices(
    stage_4_gui,
) -> None:
    _controller, window = stage_4_gui
    panel = window.garden_input_panel

    assert window.windowTitle() == "環境共生型デジタル生命シミュレーター v2 — Garden入力層"
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "Garden入力層",
        "仮想ユーザー",
        "Polar H10",
        "時間・イベント診断",
    ]
    assert window.tabs.currentWidget() is panel
    assert window.virtual_user_panel is window.tabs.widget(1)
    assert window.polar_h10_panel is window.tabs.widget(2)
    assert window.time_diagnostics_tab is window.tabs.widget(3)

    description = panel.findChild(QLabel, "gardenDescription")
    responsibility = panel.findChild(QLabel, "gardenResponsibilityNotice")
    assumptions = panel.findChild(QLabel, "gardenAssumptionNotice")
    policy = panel.findChild(QLabel, "gardenPolicyNotice")
    assert description is not None and "RriMeasurementEventだけ" in description.text()
    assert responsibility is not None and "Nd、W、デジタル生命、光" in responsibility.text()
    assert assumptions is not None and "NはRMSSDだけ" in assumptions.text()
    assert assumptions is not None and "baselineはNの式に入りません" in assumptions.text()
    assert policy is not None and "measurement end time" in policy.text()
    assert policy is not None and "最小安全方針" in policy.text()
    assert {label.text() for label in panel.findChildren(QLabel, "gardenFlowNode")} == {
        "仮想ユーザー",
        "HeartbeatEvent",
        "Polar H10",
        "RriMeasurementEvent",
        "Garden入力層",
        "N, S",
        "将来のデジタル生命",
    }

    assert panel.rri_range_label.text() == "300〜2000 ms"
    assert panel.median_history_start_label.text() == "5 件"
    assert panel.median_history_max_label.text() == "15 件"
    assert panel.median_deviation_label.text() == "20% 超"
    assert panel.low_confidence_label.text() == "artifact率 5% 超"
    assert panel.reject_label.text() == "artifact率 10% 超"
    assert panel.minimum_valid_label.text() == "5 件"
    assert panel.rmssd_mapping_label.text() == "15〜80 ms を N 0〜1 へ写像"
    assert panel.baseline_timing_label.text() == "30秒 discard＋30秒 evaluation"
    assert panel.bundle_timing_label.text() == "30秒 discard＋30秒 evaluation"
    assert panel.bundle_count_label.text() == "3 bundle"
    assert panel.signal_interval_label.text() == "1 秒"
    assert panel.timeline.phase_region_count == 8
    assert panel.rri_model.columnCount() == 12
    assert panel.evaluation_model.columnCount() == 11
    assert not window.virtual_user_panel.duration_spin.isEnabled()


def test_garden_diagnostics_use_scrollable_readable_layout(stage_4_gui, qtbot) -> None:
    _controller, window = stage_4_gui
    panel = window.garden_input_panel
    scroll = panel.diagnostics_scroll
    splitter = panel.chart_table_splitter

    qtbot.wait(10)
    assert isinstance(scroll, QScrollArea)
    assert panel.body_splitter.widget(0) is panel.fixed_scroll
    assert panel.body_splitter.widget(1) is scroll
    assert scroll is not panel.fixed_scroll
    assert scroll.widget() is panel.diagnostics_content
    assert scroll.widgetResizable()
    assert scroll.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.verticalScrollBar().value() == 0
    assert panel.chart.minimumHeight() >= 700
    assert panel.chart.tabs.minimumHeight() >= 650
    assert panel.table_tabs.minimumHeight() >= 280
    assert panel.timeline.minimumHeight() >= 180
    assert not splitter.isCollapsible(0)
    assert not splitter.isCollapsible(1)
    assert splitter.sizes()[0] > splitter.sizes()[1]
    assert splitter.handle(1).isEnabled()
    splitter.setSizes([10_000, 300])
    qtbot.wait(1)
    chart_favored_sizes = splitter.sizes()
    splitter.setSizes([720, 10_000])
    qtbot.wait(1)
    table_favored_sizes = splitter.sizes()
    assert chart_favored_sizes[0] > table_favored_sizes[0]
    assert chart_favored_sizes[1] < table_favored_sizes[1]
    splitter.setSizes([740, 330])
    assert panel.chart.rri_plot.minimumHeight() >= 400
    assert panel.chart.rmssd_plot.minimumHeight() >= 230
    assert panel.chart.n_evaluation_plot.minimumHeight() >= 230
    assert panel.chart.n_signal_plot.minimumHeight() >= 180
    assert panel.chart.s_signal_plot.minimumHeight() >= 180
    assert panel.chart.revision_plot.minimumHeight() >= 180

    panel.chart.tabs.setCurrentIndex(2)
    scroll_bar = scroll.verticalScrollBar()
    scroll_bar.setValue(400)
    target = panel.chart.signal_graphics.viewport()
    target_center = target.rect().center()
    wheel_event = QWheelEvent(
        QPointF(target_center),
        QPointF(target.mapToGlobal(target_center)),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    value_before_wheel = scroll_bar.value()
    QApplication.sendEvent(target, wheel_event)
    assert wheel_event.isAccepted()
    assert scroll_bar.value() > value_before_wheel

    trackpad_event = QWheelEvent(
        QPointF(target_center),
        QPointF(target.mapToGlobal(target_center)),
        QPoint(0, -24),
        QPoint(0, 0),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    value_before_trackpad = scroll_bar.value()
    QApplication.sendEvent(target, trackpad_event)
    assert trackpad_event.isAccepted()
    assert scroll_bar.value() > value_before_trackpad


@pytest.mark.parametrize(("width", "height"), ((1560, 980), (1280, 800)))
def test_garden_diagnostics_remain_reachable_at_supported_window_sizes(
    stage_4_gui,
    qtbot,
    width: int,
    height: int,
) -> None:
    _controller, window = stage_4_gui
    panel = window.garden_input_panel
    scroll = panel.diagnostics_scroll

    window.resize(width, height)
    qtbot.wait(20)
    assert window.isVisible()
    assert scroll.verticalScrollBar().maximum() > 0
    assert scroll.horizontalScrollBar().maximum() == 0
    assert panel.diagnostics_content.minimumSizeHint().height() > scroll.viewport().height()

    chart_tabs = panel.chart.tabs
    for tab_text in ("raw RRI / artifact", "評価窓RMSSD / N", "N / S step"):
        index = next(
            index
            for index in range(chart_tabs.count())
            if chart_tabs.tabText(index) == tab_text
        )
        chart_tabs.setCurrentIndex(index)
        qtbot.wait(1)
        assert chart_tabs.currentIndex() == index
        assert panel.chart.minimumHeight() >= 700

    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    scrolled_value = scroll.verticalScrollBar().value()
    chart_tabs.setCurrentIndex(1)
    qtbot.wait(1)
    assert scroll.verticalScrollBar().value() == scrolled_value

    panel.reset_views()
    assert scroll.verticalScrollBar().maximum() > 0
    assert panel.chart.minimumHeight() >= 700


def test_event_and_second_steps_update_phase_s_rri_plots_tables_and_event_lane(
    stage_4_gui,
    qtbot,
) -> None:
    _controller, window = stage_4_gui
    panel = window.garden_input_panel

    click(qtbot, window.step_event_button)
    assert window.log_model.rowCount() == 1
    assert window.log_model.event_at(0).event_type == GARDEN_PHASE_CHANGED_EVENT_TYPE
    assert EVENT_STYLES[GARDEN_PHASE_CHANGED_EVENT_TYPE][0] in window.timeline._executed_y

    click(qtbot, window.reset_button)
    click(qtbot, window.step_second_button)
    snapshot = window.simulation.garden_input_component.snapshot()
    assert window.simulation.engine.clock.current_time_us == 1_000_000
    assert snapshot.current_phase == "baseline_discard"
    assert snapshot.current_s == 0
    assert snapshot.received_rri_count == 1
    assert snapshot.signal_count == 2
    assert panel.phase_label.text() == "baseline_discard"
    assert panel.s_label.text() == "0"
    assert panel.received_rri_label.text() == "1 件"
    assert panel.rri_model.rowCount() == 1
    assert panel.evaluation_model.rowCount() == 0
    assert panel.chart.rri_count == 1
    assert panel.chart.valid_rri_count == 1
    assert panel.chart.artifact_count == 0
    assert panel.timeline.signal_count == 2
    assert plot_point_count(panel.chart.valid_rri_item) == 1
    assert plot_point_count(panel.chart.artifact_rri_item) == 0
    assert plot_point_count(panel.chart.s_signal_item) == 2


def test_speeds_state_locking_and_config_apply_rebind_all_three_components(
    stage_4_gui,
    qtbot,
) -> None:
    controller, window = stage_4_gui
    modes = (SpeedMode.REALTIME, SpeedMode.X10, SpeedMode.X100, SpeedMode.MAXIMUM)
    for index, mode in enumerate(modes):
        window.speed_combo.setCurrentIndex(index)
        assert controller.speed_mode is mode
        assert window.speed_label.text() == mode.label

    settings = window.virtual_user_panel.settings_group
    click(qtbot, window.start_button)
    assert window.simulation.engine.clock.state is ClockState.RUNNING
    assert not settings.isEnabled()
    click(qtbot, window.pause_button)
    assert window.simulation.engine.clock.state is ClockState.PAUSED
    assert not settings.isEnabled()
    click(qtbot, window.reset_button)
    assert settings.isEnabled()
    assert not window.virtual_user_panel.duration_spin.isEnabled()

    old_simulation = window.simulation
    window.virtual_user_panel.mean_hr_spin.setValue(76.0)
    click(qtbot, window.virtual_user_panel.apply_settings_button)
    new_simulation = window.simulation
    assert new_simulation is not old_simulation
    assert new_simulation.virtual_user_component is not old_simulation.virtual_user_component
    assert new_simulation.polar_h10_component is not old_simulation.polar_h10_component
    assert new_simulation.garden_input_component is not old_simulation.garden_input_component
    assert new_simulation.virtual_user_config.duration_seconds == 240
    assert new_simulation.virtual_user_config.mean_heart_rate_bpm == 76.0
    assert new_simulation.engine.clock.end_time_us == 240_000_000
    assert window.virtual_user_panel._component is new_simulation.virtual_user_component
    assert window.polar_h10_panel._polar_h10_component is new_simulation.polar_h10_component
    assert window.garden_input_panel._component is new_simulation.garden_input_component


def test_run_to_end_populates_all_garden_views_and_reset_clears_dynamic_data(
    stage_4_gui,
    qtbot,
) -> None:
    _controller, window = stage_4_gui
    panel = window.garden_input_panel

    click(qtbot, window.run_to_end_button)
    qtbot.waitUntil(
        lambda: window.simulation.engine.clock.state is ClockState.COMPLETED,
        timeout=5000,
    )
    qtbot.wait(1)

    snapshot = window.simulation.garden_input_component.snapshot()
    assert window.time_label.text() == "00:04:00.000"
    assert window.state_label.text() == "完了"
    assert window.log_model.rowCount() == 1059
    assert snapshot.current_phase == "outside"
    assert snapshot.current_s == 0
    assert snapshot.received_rri_count == 279
    assert snapshot.valid_rri_count == 279
    assert snapshot.artifact_rri_count == 0
    assert snapshot.signal_count == 241
    assert snapshot.evaluation_count == 4
    assert snapshot.n_baseline_session is not None
    assert snapshot.n_current is not None
    assert snapshot.valid_evaluation_revision == 4
    assert panel.phase_label.text() == "outside"
    assert panel.baseline_n_label.text() != "—"
    assert panel.current_n_label.text() != "—"
    assert panel.latest_rmssd_label.text().endswith("ms")
    assert panel.evaluation_quality_label.text() == "valid"
    assert panel.revision_label.text() == "4"
    assert panel.rri_model.rowCount() == 279
    assert panel.evaluation_model.rowCount() == 4
    assert panel.chart.rri_count == 279
    assert panel.chart.artifact_count == 0
    assert panel.chart.evaluation_count == 4
    assert panel.chart.signal_count == 241
    assert panel.timeline.signal_count == 241
    assert plot_point_count(panel.chart.valid_rri_item) == 279
    assert plot_point_count(panel.chart.artifact_rri_item) == 0
    assert plot_point_count(panel.chart.baseline_rmssd_item) == 1
    assert plot_point_count(panel.chart.bundle_rmssd_item) == 3
    assert plot_point_count(panel.chart.n_evaluation_item) == 4
    assert plot_point_count(panel.chart.rejected_evaluation_item) == 0
    assert plot_point_count(panel.chart.n_signal_item) == 241
    assert math.isnan(panel.chart.n_signal_item.yData[0])
    assert plot_point_count(panel.chart.s_signal_item) == 241
    assert plot_point_count(panel.chart.revision_item) == 241
    assert panel.rri_table.verticalScrollBar().value() == (
        panel.rri_table.verticalScrollBar().maximum()
    )
    assert panel.evaluation_table.verticalScrollBar().value() == (
        panel.evaluation_table.verticalScrollBar().maximum()
    )

    click(qtbot, window.reset_button)
    assert panel.rri_model.rowCount() == 0
    assert panel.evaluation_model.rowCount() == 0
    assert panel.chart.rri_count == 0
    assert panel.chart.evaluation_count == 0
    assert panel.chart.signal_count == 0
    assert panel.timeline.signal_count == 0
    assert panel.timeline.phase_region_count == 8
    assert panel.received_rri_label.text() == "0 件"
    assert panel.baseline_n_label.text() == "—"
    assert panel.current_n_label.text() == "—"
    assert window.log_model.rowCount() == 0


def test_three_csv_buttons_export_exact_schemas_counts_and_preserve_digests(
    stage_4_gui,
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    _controller, window = stage_4_gui
    simulation = window.simulation
    panel = window.garden_input_panel
    simulation.engine.run_until_end()
    panel.update_diagnostics(simulation.engine.snapshot())
    component = simulation.garden_input_component
    digests_before = (
        component.artifact_digest(),
        component.evaluation_digest(),
        component.signal_digest(),
    )
    destinations = (
        tmp_path / "rri.csv",
        tmp_path / "evaluations.csv",
        tmp_path / "signals.csv",
    )
    selected = iter(destinations)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(next(selected)), "CSV (*.csv)"),
    )

    click(qtbot, panel.export_rri_button)
    click(qtbot, panel.export_evaluation_button)
    click(qtbot, panel.export_signal_button)

    expected = (
        (GARDEN_RRI_CSV_FIELDS, 279),
        (GARDEN_EVALUATION_CSV_FIELDS, 4),
        (GARDEN_SIGNAL_CSV_FIELDS, 241),
    )
    for destination, (fields, row_count) in zip(destinations, expected, strict=True):
        with destination.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
        assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == row_count
    assert (
        component.artifact_digest(),
        component.evaluation_digest(),
        component.signal_digest(),
    ) == digests_before


def test_window_close_stops_controller_timer(stage_4_gui, qtbot) -> None:
    controller, window = stage_4_gui
    assert controller.timer_active
    window.close()
    qtbot.wait(1)
    assert not controller.timer_active
