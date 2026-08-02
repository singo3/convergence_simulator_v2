"""Offscreen behavior tests for the Stage 5B three-life competition GUI."""

from __future__ import annotations

import csv

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QScrollArea

from symbiotic_sim_v2.digital_life.second_round_diagnostics import (
    SECOND_ROUND_CSV_FIELDS,
)
from symbiotic_sim_v2.garden.output_layer.diagnostics import (
    QUALIFICATION_CSV_FIELDS,
    QUALIFIED_B_CSV_FIELDS,
    TOUCH_CSV_FIELDS,
)
from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.three_life_window import ThreeDigitalLifeMainWindow
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    create_three_digital_life_competition_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState


@pytest.fixture
def stage_5b_gui(qtbot):
    simulation = create_three_digital_life_competition_simulation()
    controller = SimulationController(simulation.engine)
    window = ThreeDigitalLifeMainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    yield controller, window
    window.close()


def click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def plot_point_count(item) -> int:
    return 0 if item.xData is None else len(item.xData)


def test_window_has_exact_tabs_copy_three_cards_flow_tables_and_output_rules(
    stage_5b_gui,
) -> None:
    _controller, window = stage_5b_gui
    life_panel = window.multi_life_panel
    output_panel = window.garden_output_panel

    assert window.windowTitle() == (
        "環境共生型デジタル生命シミュレーター v2 — 3生命・資格競争・第2周"
    )
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "3生命・資格競争",
        "Garden出力資格層",
        "Garden入力層",
        "仮想ユーザー",
        "Polar H10",
        "時間・イベント診断",
    ]
    assert window.tabs.currentWidget() is life_panel
    assert window.garden_output_panel is window.tabs.widget(1)
    assert window.garden_input_panel is window.tabs.widget(2)
    assert window.virtual_user_panel is window.tabs.widget(3)
    assert window.polar_h10_panel is window.tabs.widget(4)
    assert window.time_diagnostics_tab is window.tabs.widget(5)
    assert not window.virtual_user_panel.duration_spin.isEnabled()

    assert "互いのP、V、B、tau、内部状態を参照せず" in life_panel.findChild(
        QLabel,
        "multiLifeDescription",
    ).text()
    assert "P/Vを比較せず" in life_panel.findChild(
        QLabel,
        "multiLifeRuntimeNotice",
    ).text()
    assert "実際に到着したID、Bだけ" in life_panel.findChild(
        QLabel,
        "multiLifeGardenNotice",
    ).text()
    assert set(life_panel.life_cards) == {"life-red", "life-green", "life-blue"}
    assert [life_panel.life_cards[life_id].title() for life_id in life_panel.life_cards] == [
        "red",
        "green",
        "blue",
    ]
    assert all(len(labels) == 17 for labels in life_panel.life_value_labels.values())
    assert {label.text() for label in life_panel.findChildren(QLabel, "multiLifeFlowNode")} == {
        "Garden入力層",
        "red / green / blue独立第1周",
        "各tauでID,B touch",
        "Garden出力資格層",
        "資格ID返送",
        "各生命G",
        "E/q第2周",
        "次signal",
    }
    assert life_panel.touch_model.columnCount() == 13
    assert life_panel.second_round_model.columnCount() == 15
    assert "P" not in life_panel.touch_model.HEADERS
    assert "V" not in life_panel.touch_model.HEADERS
    assert "tau" not in life_panel.touch_model.HEADERS

    rules = output_panel.findChild(QLabel, "gardenOutputRulesNotice")
    boundary = output_panel.findChild(QLabel, "gardenOutputBoundaryNotice")
    no_light = output_panel.findChild(QLabel, "gardenOutputNoLightNotice")
    assert rules is not None and "first touch when empty" in rules.text()
    assert rules is not None and "release after closing second round when S=0" in rules.text()
    assert boundary is not None and "ID/B only" in boundary.text()
    assert boundary is not None and "P、V、tau" in boundary.text()
    assert no_light is not None and "まだHue、BPM、光波形Iを生成しません" in no_light.text()
    assert output_panel.qualification_model.columnCount() == 16
    assert output_panel.current_holder_label.text() == "null"
    assert output_panel.assignment_signal_label.text() == "—"
    assert output_panel.total_touch_count_label.text() == "0"


@pytest.mark.parametrize(("width", "height"), ((1560, 980), (1280, 800)))
def test_stage_5b_diagnostics_are_vertically_scrollable_and_graphs_readable(
    stage_5b_gui,
    qtbot,
    width: int,
    height: int,
) -> None:
    _controller, window = stage_5b_gui
    life_panel = window.multi_life_panel
    output_panel = window.garden_output_panel
    window.resize(width, height)
    qtbot.wait(20)

    for panel in (life_panel, output_panel):
        window.tabs.setCurrentWidget(panel)
        qtbot.wait(1)
        scroll = panel.diagnostics_scroll
        assert isinstance(scroll, QScrollArea)
        assert scroll.widget() is panel.diagnostics_content
        assert scroll.widgetResizable()
        assert scroll.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
        assert scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert scroll.verticalScrollBar().maximum() > 0
        assert scroll.horizontalScrollBar().maximum() == 0
        assert not panel.chart_table_splitter.isCollapsible(0)
        assert not panel.chart_table_splitter.isCollapsible(1)

    assert life_panel.chart.minimumHeight() >= 700
    assert output_panel.chart.minimumHeight() >= 700
    assert life_panel.table_tabs.minimumHeight() >= 300
    assert output_panel.table_frame.minimumHeight() >= 300
    for plot in (
        life_panel.chart.tau_touch_plot,
        life_panel.chart.g_holder_plot,
        life_panel.chart.e_q_plot,
        life_panel.chart.p_v_plot,
        life_panel.chart.b_plot,
    ):
        assert plot.minimumHeight() >= 180
    assert output_panel.chart.holder_plot.minimumHeight() >= 250
    assert output_panel.chart.qualified_b_plot.minimumHeight() >= 250

    for panel in (life_panel, output_panel):
        scroll_bar = panel.diagnostics_scroll.verticalScrollBar()
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


def test_event_and_second_steps_update_all_new_views(stage_5b_gui, qtbot) -> None:
    _controller, window = stage_5b_gui
    life_panel = window.multi_life_panel
    output_panel = window.garden_output_panel

    click(qtbot, window.step_event_button)
    assert window.log_model.rowCount() == 1
    click(qtbot, window.reset_button)
    click(qtbot, window.step_second_button)

    assert window.simulation.engine.clock.current_time_us == 1_000_000
    assert life_panel.touch_model.rowCount() == 0
    assert life_panel.second_round_model.rowCount() == 6
    assert output_panel.qualification_model.rowCount() == 2
    assert life_panel.chart.first_round_count == 6
    assert life_panel.chart.second_round_count == 6
    assert life_panel.chart.qualification_count == 2
    assert output_panel.chart.qualification_count == 2
    assert output_panel.chart.qualified_b_count == 2
    assert output_panel.inactive_output_count_label.text() == "2"
    assert output_panel.current_holder_label.text() == "null"
    for life_id, component in window.simulation.digital_life_components.items():
        assert plot_point_count(life_panel.chart.p_items[life_id]) == 2
        assert life_panel.life_value_labels[life_id]["role"].text() == (
            component.snapshot().role
        )


def test_speeds_and_config_apply_rebind_all_stage_5b_components(
    stage_5b_gui,
    qtbot,
) -> None:
    controller, window = stage_5b_gui
    for index, mode in enumerate(
        (SpeedMode.REALTIME, SpeedMode.X10, SpeedMode.X100, SpeedMode.MAXIMUM)
    ):
        window.speed_combo.setCurrentIndex(index)
        assert controller.speed_mode is mode
    window.speed_combo.setCurrentIndex(0)

    old = window.simulation
    window.virtual_user_panel.mean_hr_spin.setValue(76.0)
    click(qtbot, window.virtual_user_panel.apply_settings_button)
    new = window.simulation
    assert new is not old
    assert new.virtual_user_component is not old.virtual_user_component
    assert new.polar_h10_component is not old.polar_h10_component
    assert new.garden_input_component is not old.garden_input_component
    assert new.garden_output_component is not old.garden_output_component
    assert all(
        new.digital_life_components[life_id] is not old.digital_life_components[life_id]
        for life_id in new.digital_life_components
    )
    assert new.virtual_user_config.mean_heart_rate_bpm == 76.0
    assert new.digital_life_configs == old.digital_life_configs
    assert new.runtime_config == old.runtime_config
    assert new.garden_output_config == old.garden_output_config
    assert window.multi_life_panel._components == dict(new.digital_life_components)
    assert window.garden_output_panel._component is new.garden_output_component


def test_run_to_end_populates_three_life_and_garden_output_then_reset_clears(
    stage_5b_gui,
    qtbot,
) -> None:
    controller, window = stage_5b_gui
    simulation = window.simulation
    life_panel = window.multi_life_panel
    output_panel = window.garden_output_panel

    simulation.engine.run_until_end()
    life_panel.update_diagnostics(simulation.engine.snapshot())
    output_panel.update_diagnostics(simulation.engine.snapshot())

    assert simulation.engine.clock.state is ClockState.COMPLETED
    assert life_panel.touch_model.rowCount() == 540
    assert life_panel.second_round_model.rowCount() == 723
    assert output_panel.qualification_model.rowCount() == 241
    assert life_panel.chart.first_round_count == 723
    assert life_panel.chart.second_round_count == 723
    assert life_panel.chart.touch_count == 540
    assert output_panel.chart.qualified_b_count == 241
    assert output_panel.chart.assignment_count == 1
    assert output_panel.chart.release_count == 1
    assert plot_point_count(output_panel.chart.qualified_holder_item) == 241
    assert output_panel.current_holder_label.text() == "null"
    assert output_panel.assignment_signal_label.text() == "60"
    assert output_panel.total_touch_count_label.text() == "540"
    assert output_panel.active_output_count_label.text() == "180"
    assert output_panel.inactive_output_count_label.text() == "61"
    assert output_panel.feedback_count_label.text() == "723"
    assert output_panel.assignment_count_label.text() == "1"
    assert output_panel.release_count_label.text() == "1"
    assert output_panel.latest_qualified_b_label.text() == "—"

    green = simulation.digital_life_components["life-green"].snapshot()
    assert green.q_update_count == 3
    assert green.e > 0.0
    for life_id, component in simulation.digital_life_components.items():
        snapshot = component.snapshot()
        assert snapshot.k_anchor == snapshot.k_current == (0.5, 0.5, 0.5, 0.5)
        assert snapshot.first_round_completed
        assert snapshot.second_round_completed
        assert plot_point_count(life_panel.chart.tau_items[life_id]) == 241
        assert plot_point_count(life_panel.chart.e_items[life_id]) == 241

    controller.reset()
    assert life_panel.touch_model.rowCount() == 0
    assert life_panel.second_round_model.rowCount() == 0
    assert output_panel.qualification_model.rowCount() == 0
    assert life_panel.chart.first_round_count == 0
    assert life_panel.chart.second_round_count == 0
    assert output_panel.chart.qualification_count == 0
    assert output_panel.current_holder_label.text() == "null"
    assert output_panel.total_touch_count_label.text() == "0"


def test_four_csv_buttons_write_exact_schemas_and_preserve_digests(
    stage_5b_gui,
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    _controller, window = stage_5b_gui
    simulation = window.simulation
    simulation.engine.run_until_end()
    window.multi_life_panel.update_diagnostics(simulation.engine.snapshot())
    window.garden_output_panel.update_diagnostics(simulation.engine.snapshot())
    garden = simulation.garden_output_component
    digests_before = (
        garden.touch_digest(),
        garden.qualification_digest(),
        garden.qualified_b_digest(),
        tuple(
            component.second_round_digest()
            for component in simulation.digital_life_components.values()
        ),
        simulation.engine.deterministic_digest(),
    )
    destinations = (
        tmp_path / "second-round.csv",
        tmp_path / "touch.csv",
        tmp_path / "qualification.csv",
        tmp_path / "qualified-b.csv",
    )
    selected = iter(destinations)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(next(selected)), "CSV (*.csv)"),
    )

    click(qtbot, window.multi_life_panel.export_second_round_button)
    click(qtbot, window.garden_output_panel.export_touch_button)
    click(qtbot, window.garden_output_panel.export_qualification_button)
    click(qtbot, window.garden_output_panel.export_qualified_b_button)
    for path, fields, row_count in (
        (destinations[0], SECOND_ROUND_CSV_FIELDS, 723),
        (destinations[1], TOUCH_CSV_FIELDS, 540),
        (destinations[2], QUALIFICATION_CSV_FIELDS, 241),
        (destinations[3], QUALIFIED_B_CSV_FIELDS, 241),
    ):
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
        assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == row_count

    assert (
        garden.touch_digest(),
        garden.qualification_digest(),
        garden.qualified_b_digest(),
        tuple(
            component.second_round_digest()
            for component in simulation.digital_life_components.values()
        ),
        simulation.engine.deterministic_digest(),
    ) == digests_before


def test_window_close_stops_controller_timer(stage_5b_gui, qtbot) -> None:
    controller, window = stage_5b_gui
    assert controller.timer_active
    window.close()
    qtbot.wait(1)
    assert not controller.timer_active
