"""Offscreen behavior tests for the Stage 5A single-Digital-Life GUI."""

from __future__ import annotations

import csv
import math

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QScrollArea

from symbiotic_sim_v2.digital_life.diagnostics import (
    EVALUATION_UPDATE_CSV_FIELDS,
    FIRST_ROUND_CSV_FIELDS,
)
from symbiotic_sim_v2.digital_life.scenario import (
    create_single_digital_life_simulation,
)
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
)
from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.digital_life_window import SingleDigitalLifeMainWindow
from symbiotic_sim_v2.simulation.clock import ClockState


@pytest.fixture
def stage_5a_gui(qtbot):
    simulation = create_single_digital_life_simulation()
    controller = SimulationController(simulation.engine)
    window = SingleDigitalLifeMainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    yield controller, window
    window.close()


def click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def plot_point_count(item) -> int:
    return 0 if item.xData is None else len(item.xData)


def test_stage_5a_window_has_exact_tabs_copy_preset_flow_cards_and_tables(
    stage_5a_gui,
) -> None:
    _controller, window = stage_5a_gui
    panel = window.digital_life_panel

    assert window.windowTitle() == (
        "環境共生型デジタル生命シミュレーター v2 — 1体のデジタル生命・第1周"
    )
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "デジタル生命",
        "Garden入力層",
        "仮想ユーザー",
        "Polar H10",
        "時間・イベント診断",
    ]
    assert window.tabs.currentWidget() is panel
    assert window.garden_input_panel is window.tabs.widget(1)
    assert window.virtual_user_panel is window.tabs.widget(2)
    assert window.polar_h10_panel is window.tabs.widget(3)
    assert window.time_diagnostics_tab is window.tabs.widget(4)
    assert panel.role_combo.currentData() == "green"
    assert panel.role_combo.count() == 3
    assert panel.role_combo.isEnabled()

    description = panel.findChild(QLabel, "digitalLifeDescription")
    boundary = panel.findChild(QLabel, "digitalLifeBoundaryNotice")
    assert description is not None and "Nd、W、P、V、B、tau" in description.text()
    assert boundary is not None and "Garden出力層とGはまだ未接続" in boundary.text()
    assert {label.text() for label in panel.findChildren(QLabel, "digitalLifeFlowNode")} == {
        "Garden入力層",
        "N, S",
        "外受容系",
        "状態系: Nd, P, E",
        "情動系: W",
        "関係記憶: k",
        "修飾系: q, V",
        "制御系: B",
        "遠心系: tau",
        "将来のGarden出力層",
    }
    assert panel.life_id_label.text() == "life-green"
    assert panel.role_label.text() == "green"
    assert panel.delta_n_label.text() == "0.10"
    assert panel.w_mapping_label.text() == "W = Nd（別field）"
    assert panel.initial_e_label.text() == "0.0"
    assert panel.initial_q_label.text() == "0.5"
    assert panel.epsilon_tau_label.text() == "0.000001"
    assert panel.g_label.text() == "未接続"
    assert panel.second_round_label.text() == "未実装"
    assert panel.touch_dispatch_label.text() == "未実行"
    assert panel.signal_model.columnCount() == 20
    assert panel.evaluation_model.columnCount() == 13


@pytest.mark.parametrize(("width", "height"), ((1560, 980), (1280, 800)))
def test_digital_life_diagnostics_are_vertically_scrollable_and_readable(
    stage_5a_gui,
    qtbot,
    width: int,
    height: int,
) -> None:
    _controller, window = stage_5a_gui
    panel = window.digital_life_panel
    scroll = panel.diagnostics_scroll
    window.resize(width, height)
    qtbot.wait(20)

    assert isinstance(scroll, QScrollArea)
    assert panel.body_splitter.widget(0) is panel.fixed_scroll
    assert panel.body_splitter.widget(1) is scroll
    assert scroll.widget() is panel.diagnostics_content
    assert scroll.widgetResizable()
    assert scroll.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.verticalScrollBar().maximum() > 0
    assert scroll.horizontalScrollBar().maximum() == 0
    assert panel.chart.minimumHeight() >= 900
    assert panel.table_tabs.minimumHeight() >= 300
    for plot in (
        panel.chart.state_plot,
        panel.chart.activity_plot,
        panel.chart.holding_plot,
        panel.chart.relation_plot,
    ):
        assert plot.minimumHeight() >= 200
    assert not panel.chart_table_splitter.isCollapsible(0)
    assert not panel.chart_table_splitter.isCollapsible(1)

    scroll_bar = scroll.verticalScrollBar()
    scroll_bar.setValue(300)
    target = panel.chart.graphics.viewport()
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
    before = scroll_bar.value()
    QApplication.sendEvent(target, wheel_event)
    assert wheel_event.isAccepted()
    assert scroll_bar.value() > before


def test_second_step_updates_first_round_records_charts_and_table(stage_5a_gui, qtbot) -> None:
    _controller, window = stage_5a_gui
    panel = window.digital_life_panel
    click(qtbot, window.step_second_button)

    snapshot = window.simulation.digital_life_component.snapshot()
    assert window.simulation.engine.clock.current_time_us == 1_000_000
    assert snapshot.first_round_count == 2
    assert snapshot.n_current is None
    assert snapshot.p == 1.0
    assert snapshot.tau is None
    assert panel.signal_model.rowCount() == 2
    assert panel.evaluation_model.rowCount() == 0
    assert panel.chart.record_count == 2
    assert plot_point_count(panel.chart.n_item) == 2
    assert math.isnan(panel.chart.n_item.yData[0])
    assert plot_point_count(panel.chart.p_item) == 2
    assert plot_point_count(panel.chart.tau_item) == 2
    assert math.isnan(panel.chart.tau_item.yData[0])
    assert panel.g_label.text() == "未接続"
    assert panel.touch_dispatch_label.text() == "未実行"


def test_latest_evaluation_card_uses_snapshot_before_same_time_signal(
    stage_5a_gui,
) -> None:
    controller, window = stage_5a_gui
    panel = window.digital_life_panel

    for _event_index in range(2_000):
        controller.step_one_event()
        latest_event = window.simulation.engine.executed_events()[-1]
        if latest_event.event_type == GARDEN_EVALUATION_FINALIZED_EVENT_TYPE:
            break
    else:  # pragma: no cover - bounded guard for a malformed scenario
        pytest.fail("baseline evaluation event was not reached")

    snapshot = window.simulation.digital_life_component.snapshot()
    assert snapshot.latest_evaluation_id is not None
    assert snapshot.last_revision == 0
    assert panel.evaluation_model.rowCount() == 0
    assert panel.latest_evaluation_label.text() == snapshot.latest_evaluation_id


def test_role_is_locked_by_state_and_rebuilds_all_four_components_when_stopped(
    stage_5a_gui,
    qtbot,
) -> None:
    controller, window = stage_5a_gui
    panel = window.digital_life_panel
    modes = (SpeedMode.REALTIME, SpeedMode.X10, SpeedMode.X100, SpeedMode.MAXIMUM)
    for index, mode in enumerate(modes):
        window.speed_combo.setCurrentIndex(index)
        assert controller.speed_mode is mode
    window.speed_combo.setCurrentIndex(0)

    click(qtbot, window.start_button)
    assert window.simulation.engine.clock.state is ClockState.RUNNING
    assert not panel.role_combo.isEnabled()
    click(qtbot, window.pause_button)
    assert window.simulation.engine.clock.state is ClockState.PAUSED
    assert not panel.role_combo.isEnabled()
    click(qtbot, window.reset_button)
    assert panel.role_combo.isEnabled()

    old = window.simulation
    old_garden_digest = old.garden_input_component.signal_digest()
    panel.role_combo.setCurrentIndex(panel.role_combo.findData("red"))
    new = window.simulation
    assert new is not old
    assert new.virtual_user_component is not old.virtual_user_component
    assert new.polar_h10_component is not old.polar_h10_component
    assert new.garden_input_component is not old.garden_input_component
    assert new.digital_life_component is not old.digital_life_component
    assert new.digital_life_config.role == "red"
    assert new.virtual_user_config == old.virtual_user_config
    assert new.polar_h10_config == old.polar_h10_config
    assert new.garden_input_config == old.garden_input_config
    assert new.garden_input_component.signal_digest() == old_garden_digest
    assert panel._component is new.digital_life_component
    assert panel.role_combo.currentData() == "red"
    assert panel.life_id_label.text() == "life-red"


def test_run_to_end_populates_all_life_views_and_reset_clears_them(
    stage_5a_gui,
    qtbot,
) -> None:
    _controller, window = stage_5a_gui
    panel = window.digital_life_panel
    click(qtbot, window.run_to_end_button)
    qtbot.waitUntil(
        lambda: window.simulation.engine.clock.state is ClockState.COMPLETED,
        timeout=5000,
    )
    qtbot.wait(1)

    snapshot = window.simulation.digital_life_component.snapshot()
    assert window.time_label.text() == "00:04:00.000"
    assert window.state_label.text() == "完了"
    assert snapshot.first_round_count == 241
    assert snapshot.evaluation_update_count == 4
    assert snapshot.new_valid_evaluation_count == 4
    assert snapshot.baseline_initialized
    assert snapshot.last_revision == 4
    assert snapshot.latest_s == 0
    assert snapshot.p == 1.0
    assert snapshot.tau is None
    assert snapshot.e == 0.0
    assert snapshot.q == 0.5
    assert snapshot.k_anchor == snapshot.k_current == (0.5, 0.5, 0.5, 0.5)
    assert snapshot.g_status == "not_connected"
    assert not snapshot.second_round_connected
    assert snapshot.touch_dispatched_count == 0
    assert window.simulation.digital_life_component.first_round_digest() == (
        "661c2c74942d6b217a635fb4f2cb142bee8cff2e0e842cd21ccdd511682028b8"
    )
    assert window.simulation.digital_life_component.evaluation_update_digest() == (
        "f7bf973cc20a2af77ccd7b38fa0e2407801353890a23cc1b3e30e9d7feeba4c3"
    )
    assert window.simulation.engine.deterministic_digest() == (
        "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72"
    )
    assert not panel.role_combo.isEnabled()
    assert panel.signal_model.rowCount() == 241
    assert panel.evaluation_model.rowCount() == 4
    assert panel.chart.record_count == 241
    assert panel.chart.evaluation_point_count == 4
    for item in (
        panel.chart.n_item,
        panel.chart.baseline_n_item,
        panel.chart.nd_item,
        panel.chart.w_item,
        panel.chart.p_item,
        panel.chart.v_item,
        panel.chart.tau_item,
        panel.chart.e_item,
        panel.chart.q_item,
        panel.chart.k_f_item,
        panel.chart.b_f_item,
    ):
        assert plot_point_count(item) == 241
    assert math.isnan(panel.chart.tau_item.yData[-1])
    assert panel.g_label.text() == "未接続"
    assert panel.second_round_label.text() == "未実装"
    assert panel.touch_dispatch_label.text() == "未実行"
    assert panel.signal_table.verticalScrollBar().value() == (
        panel.signal_table.verticalScrollBar().maximum()
    )

    click(qtbot, window.reset_button)
    assert panel.role_combo.isEnabled()
    assert panel.signal_model.rowCount() == 0
    assert panel.evaluation_model.rowCount() == 0
    assert panel.chart.record_count == 0
    assert panel.chart.evaluation_point_count == 0
    assert panel.n_label.text() == "—"
    assert panel.tau_label.text() == "—"
    assert panel.g_label.text() == "未接続"


def test_two_csv_buttons_write_exact_schemas_and_preserve_digests(
    stage_5a_gui,
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    _controller, window = stage_5a_gui
    simulation = window.simulation
    component = simulation.digital_life_component
    simulation.engine.run_until_end()
    window.digital_life_panel.update_diagnostics(simulation.engine.snapshot())
    digests_before = (
        component.first_round_digest(),
        component.evaluation_update_digest(),
    )
    destinations = (tmp_path / "first-round.csv", tmp_path / "evaluations.csv")
    selected = iter(destinations)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(next(selected)), "CSV (*.csv)"),
    )

    click(qtbot, window.digital_life_panel.export_first_round_button)
    click(qtbot, window.digital_life_panel.export_evaluation_button)
    for path, fields, count in (
        (destinations[0], FIRST_ROUND_CSV_FIELDS, 241),
        (destinations[1], EVALUATION_UPDATE_CSV_FIELDS, 4),
    ):
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
        assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == count
    assert (
        component.first_round_digest(),
        component.evaluation_update_digest(),
    ) == digests_before


def test_window_close_stops_controller_timer(stage_5a_gui, qtbot) -> None:
    controller, window = stage_5a_gui
    assert controller.timer_active
    window.close()
    qtbot.wait(1)
    assert not controller.timer_active
