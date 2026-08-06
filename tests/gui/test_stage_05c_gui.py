"""Offscreen acceptance tests for the Stage 5C nine-tab main window."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from symbiotic_sim_v2.digital_life.relation_memory.adaptive_component import (
    AdaptiveConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.gui.adaptive_closed_loop_window import (
    OFF_CENTER_DIAGNOSTIC_OPTIMUM_FT,
    WINDOW_TITLE,
    AdaptiveClosedLoopMainWindow,
)
from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.relation_memory_chart import (
    RELATION_MEMORY_CHART_MIN_HEIGHT,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.light_response.presets import (
    light_response_config_for_preset,
)


@pytest.fixture
def stage_5c_gui(qtbot):
    simulation = create_adaptive_relation_memory_closed_loop_simulation()
    controller = SimulationController(simulation.engine)
    window = AdaptiveClosedLoopMainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(20)
    yield controller, window
    controller.shutdown()
    window.close()


def _click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def _select_preset(window: AdaptiveClosedLoopMainWindow, preset_name: str) -> None:
    combo = window.light_response_user_panel.preset_combo
    index = combo.findData(preset_name)
    assert index >= 0
    combo.setCurrentIndex(index)
    combo.activated.emit(index)


def test_window_title_exact_nine_tabs_and_adaptive_panel_binding(
    stage_5c_gui,
) -> None:
    _controller, window = stage_5c_gui
    panel = window.relation_memory_panel
    components = adaptive_digital_life_components(window.simulation)

    assert (
        window.windowTitle()
        == WINDOW_TITLE
        == ("環境共生型デジタル生命シミュレーター v2 — 3Bundle関係記憶探索")
    )
    assert "Stage 05C" in window.findChild(QLabel, "pageTitle").text()
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "関係記憶探索",
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
    assert panel.preset_name == "off_center_green"
    assert panel.diagnostic_optimum_ft == OFF_CENTER_DIAGNOSTIC_OPTIMUM_FT
    assert panel.chart.optimum_visible
    assert "探索計算には" in panel.optimum_notice.text()
    assert set(components) == {"life-red", "life-green", "life-blue"}
    assert all(
        isinstance(component, AdaptiveConnectedDigitalLifeComponent)
        for component in components.values()
    )
    assert all(panel._components[life_id] is component for life_id, component in components.items())


def test_run_to_end_populates_exact_relation_records_then_reset_clears(
    stage_5c_gui,
    qtbot,
) -> None:
    controller, window = stage_5c_gui
    panel = window.relation_memory_panel

    _click(qtbot, window.run_to_end_button)
    qtbot.waitUntil(
        lambda: window.simulation.engine.clock.state is ClockState.COMPLETED,
        timeout=20_000,
    )
    qtbot.waitUntil(lambda: panel.signal_model.rowCount() == 723, timeout=2_000)

    assert panel.transition_model.rowCount() == 12
    assert panel.signal_model.rowCount() == 723
    assert panel.persistent_model.rowCount() == 6
    assert panel.chart.transition_count == 12
    assert panel.chart.signal_count == 723
    assert panel.chart.qualified_b_change_count == 1
    assert panel.chart.hue_bpm_change_count == 1
    qualified_times, _ = panel.chart.qualified_b_items["life-green"].getData()
    command_times, _ = panel.chart.hue_bpm_items["life-green"].getData()
    assert tuple(qualified_times) == pytest.approx((60.55154,))
    assert tuple(command_times) == pytest.approx((60.55154,))
    assert panel.chart.optimum_visible
    assert window.simulation.engine.deterministic_digest() == (
        "97289a7bd4672edb5ffc7ecb56543a7602638c1a9b76a0859b81bbef332c67d2"
    )
    components = adaptive_digital_life_components(window.simulation)
    assert sum(len(value.adaptive_signal_records()) for value in components.values()) == 723
    assert (
        sum(len(value.relation_memory_transition_records()) for value in components.values()) == 12
    )
    assert all(value.final_persistent_state() is not None for value in components.values())

    _click(qtbot, window.reset_button)
    assert window.simulation.engine.clock.state is ClockState.STOPPED
    assert panel.transition_model.rowCount() == 0
    assert panel.signal_model.rowCount() == 0
    assert panel.persistent_model.rowCount() == 3
    assert panel.chart.transition_count == 0
    assert panel.chart.signal_count == 0
    assert panel.chart.qualified_b_change_count == 0
    assert panel.chart.hue_bpm_change_count == 0
    assert all(not value.adaptive_signal_records() for value in components.values())
    assert all(not value.relation_memory_transition_records() for value in components.values())
    assert all(value.final_persistent_state() is None for value in components.values())
    assert controller.current_snapshot().engine.current_time_us == 0


def test_preset_rebuild_retains_adaptive_factory_and_imported_initial_state(
    qtbot,
) -> None:
    initial_states = {
        life_id: replace(
            RelationMemoryPersistentState.fresh(life_id),
            k_anchor=(0.15, 0.25, 0.35, 0.45),
            q=0.61,
            e=0.12,
            trial_count=7,
            session_count=3,
        )
        for life_id in ("life-red", "life-green", "life-blue")
    }
    simulation = create_adaptive_relation_memory_closed_loop_simulation(
        initial_persistent_states_by_life_id=initial_states,
    )
    controller = SimulationController(simulation.engine)
    window = AdaptiveClosedLoopMainWindow(controller, simulation)
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(20)
    original_engine = window.simulation.engine

    _select_preset(window, "light_insensitive_control")
    assert window.simulation.engine is not original_engine
    assert window.relation_memory_panel.preset_name == "light_insensitive_control"
    assert window.relation_memory_panel.diagnostic_optimum_ft is None
    assert not window.relation_memory_panel.chart.optimum_visible
    rebuilt_components = adaptive_digital_life_components(window.simulation)
    assert {
        life_id: component.initial_persistent_state()
        for life_id, component in rebuilt_components.items()
    } == initial_states
    assert all(
        window.relation_memory_panel._components[life_id] is component
        for life_id, component in rebuilt_components.items()
    )

    control_engine = window.simulation.engine
    _select_preset(window, "off_center_green")
    assert window.simulation.engine is not control_engine
    assert window.relation_memory_panel.diagnostic_optimum_ft == (OFF_CENTER_DIAGNOSTIC_OPTIMUM_FT)
    assert window.relation_memory_panel.chart.optimum_visible
    assert {
        life_id: component.initial_persistent_state()
        for life_id, component in adaptive_digital_life_components(window.simulation).items()
    } == initial_states

    controller.shutdown()
    window.close()


def test_diagnostic_optimum_is_display_only_not_a_component_or_event_input(
    stage_5c_gui,
) -> None:
    controller, window = stage_5c_gui
    panel = window.relation_memory_panel
    panel.set_diagnostic_optimum("off_center_green", (0.01, 0.99))
    assert panel.diagnostic_optimum_ft == (0.01, 0.99)

    window.simulation.engine.run_until_end()
    controller.set_speed(controller.speed_mode)
    comparison = create_adaptive_relation_memory_closed_loop_simulation(
        light_response_config=light_response_config_for_preset("off_center_green")
    )
    comparison.engine.run_until_end()
    assert window.simulation.engine.deterministic_digest() == (
        comparison.engine.deterministic_digest()
    )
    window_components = adaptive_digital_life_components(window.simulation)
    comparison_components = adaptive_digital_life_components(comparison)
    assert {
        life_id: component.relation_memory_transition_records()
        for life_id, component in window_components.items()
    } == {
        life_id: component.relation_memory_transition_records()
        for life_id, component in comparison_components.items()
    }


def test_window_resize_keeps_vertical_scroll_preview_safe_and_closes_cleanly(
    stage_5c_gui,
    qtbot,
) -> None:
    controller, window = stage_5c_gui
    panel = window.relation_memory_panel
    for width, height in ((1_280, 800), (1_024, 700), (1_560, 980)):
        window.resize(width, height)
        qtbot.wait(20)
        assert isinstance(panel.diagnostics_scroll, QScrollArea)
        assert panel.diagnostics_scroll.verticalScrollBar().maximum() > 0
        assert panel.diagnostics_scroll.horizontalScrollBar().maximum() == 0
        assert panel.chart.minimumHeight() >= RELATION_MEMORY_CHART_MIN_HEIGHT

    preview = window.light_output_panel
    assert not preview.preview_checkbox.isChecked()
    assert not preview.preview_checkbox.isEnabled()
    assert preview.color_preview.display_color == QColor("#000000")
    controller.set_speed(SpeedMode.MAXIMUM)
    assert not preview.preview_checkbox.isChecked()
    assert not preview.preview_checkbox.isEnabled()

    window.close()
    QApplication.processEvents()
    controller.shutdown()
    assert not window.isVisible()
    assert not controller.timer_active
