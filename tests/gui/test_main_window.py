"""Offscreen interaction tests for the Stage 1 main window."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from symbiotic_sim_v2.gui.controller import SimulationController, SpeedMode
from symbiotic_sim_v2.gui.main_window import MainWindow
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine


@pytest.fixture
def gui(qtbot):
    engine = create_demo_engine()
    controller = SimulationController(engine)
    window = MainWindow(controller)
    qtbot.addWidget(window)
    window.show()
    yield engine, controller, window
    window.close()


def click(qtbot, button) -> None:
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_window_constructs_offscreen_with_initial_state(gui) -> None:
    engine, _controller, window = gui
    assert window.windowTitle().endswith("時間シミュレーター")
    assert window.time_label.text() == "00:00:00.000"
    assert window.state_label.text() == "停止"
    assert window.pending_label.text() == "26"
    assert window.log_model.rowCount() == 0
    assert window.timeline.current_time_us == 0
    assert engine.clock.state is ClockState.STOPPED


def test_start_pause_and_resume_buttons(gui, qtbot) -> None:
    engine, _controller, window = gui
    click(qtbot, window.start_button)
    assert engine.clock.state is ClockState.RUNNING
    assert window.pause_button.isEnabled()
    click(qtbot, window.pause_button)
    assert engine.clock.state is ClockState.PAUSED
    assert window.resume_button.isEnabled()
    click(qtbot, window.resume_button)
    assert engine.clock.state is ClockState.RUNNING


def test_one_second_updates_time_log_and_timeline(gui, qtbot) -> None:
    engine, _controller, window = gui
    click(qtbot, window.step_second_button)
    assert engine.clock.current_time_us == 1_000_000
    assert window.time_label.text() == "00:00:01.000"
    assert window.log_model.rowCount() == 2
    assert window.timeline.current_time_us == 1_000_000


def test_next_event_is_exactly_one_and_reset_clears_views(gui, qtbot) -> None:
    engine, _controller, window = gui
    click(qtbot, window.step_event_button)
    assert len(engine.executed_events()) == 1
    assert window.log_model.rowCount() == 1
    assert window.reset_button.isEnabled()
    click(qtbot, window.reset_button)
    assert engine.clock.state is ClockState.STOPPED
    assert window.log_model.rowCount() == 0
    assert window.timeline.current_time_us == 0


def test_speed_selection_changes_policy_only(gui) -> None:
    engine, controller, window = gui
    initial_plan = [event.to_dict() for event in engine.planned_events()]
    modes = (SpeedMode.REALTIME, SpeedMode.X10, SpeedMode.X100, SpeedMode.MAXIMUM)
    for index, mode in enumerate(modes):
        window.speed_combo.setCurrentIndex(index)
        assert controller.speed_mode is mode
        assert window.speed_label.text() == mode.label
        assert [event.to_dict() for event in engine.planned_events()] == initial_plan


def test_run_to_end_updates_completed_controls_and_full_log(gui, qtbot) -> None:
    engine, _controller, window = gui
    click(qtbot, window.run_to_end_button)
    assert engine.clock.state is ClockState.COMPLETED
    assert window.time_label.text() == "00:00:20.000"
    assert window.state_label.text() == "完了"
    assert window.log_model.rowCount() == 26
    assert window.pending_label.text() == "0"
    assert not window.start_button.isEnabled()
    assert not window.pause_button.isEnabled()
    assert not window.resume_button.isEnabled()
    assert not window.step_second_button.isEnabled()
    assert not window.step_event_button.isEnabled()
    assert not window.run_to_end_button.isEnabled()
    assert window.reset_button.isEnabled()


def test_window_close_stops_controller_timer(gui, qtbot) -> None:
    _engine, controller, window = gui
    assert controller.timer_active
    window.close()
    qtbot.wait(1)
    assert not controller.timer_active
