"""Main Qt Widgets window for the Stage 1 time simulator."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.controller import (
    ControllerSnapshot,
    SimulationController,
    SpeedMode,
)
from symbiotic_sim_v2.gui.event_log_model import EventLogModel
from symbiotic_sim_v2.gui.timeline_widget import TimelineWidget
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.time_utils import format_time_us

WINDOW_TITLE = "環境共生型デジタル生命シミュレーター v2 — 時間シミュレーター"
STAGE_DESCRIPTION = (
    "この画面は時間・イベント配送基盤だけを検証するStage 1です。"
    "仮想ユーザー、H10、Garden、デジタル生命、光刺激はまだ実装されていません。"
)

STATE_LABELS = {
    ClockState.STOPPED: "停止",
    ClockState.RUNNING: "実行中",
    ClockState.PAUSED: "一時停止",
    ClockState.COMPLETED: "完了",
}


class MainWindow(QMainWindow):
    """Render controller snapshots and forward user intent to the controller."""

    def __init__(self, controller: SimulationController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1280, 800)
        self.setMinimumSize(1050, 680)
        self._build_ui()
        self._connect_signals()
        self.timeline.set_scenario_events(self.controller.planned_events())
        self._update_snapshot(self.controller.current_snapshot())

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        title = QLabel("時間シミュレーター  ·  Stage 01", central)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        description = QLabel(STAGE_DESCRIPTION, central)
        description.setObjectName("stageDescription")
        description.setWordWrap(True)
        root.addWidget(description)

        status_frame = QFrame(central)
        status_frame.setObjectName("statusFrame")
        status_layout = QGridLayout(status_frame)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setHorizontalSpacing(18)
        self.time_label = self._add_status(status_layout, 0, "仮想時刻", "00:00:00.000")
        self.time_label.setObjectName("virtualTimeLabel")
        self.state_label = self._add_status(status_layout, 1, "実行状態", "停止")
        self.state_label.setObjectName("stateLabel")
        self.speed_label = self._add_status(status_layout, 2, "選択速度", "等速")
        self.next_time_label = self._add_status(status_layout, 3, "次イベント時刻", "00:00:00.000")
        self.pending_label = self._add_status(status_layout, 4, "pending", "26")
        self.executed_label = self._add_status(status_layout, 5, "executed", "0")
        root.addWidget(status_frame)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.start_button = self._button("開始", "startButton")
        self.pause_button = self._button("一時停止", "pauseButton")
        self.resume_button = self._button("再開", "resumeButton")
        self.reset_button = self._button("リセット", "resetButton")
        self.step_second_button = self._button("1秒進む", "stepSecondButton")
        self.step_event_button = self._button("次イベント", "stepEventButton")
        self.run_to_end_button = self._button("最後まで実行", "runToEndButton", primary=True)
        for button in (
            self.start_button,
            self.pause_button,
            self.resume_button,
            self.reset_button,
            self.step_second_button,
            self.step_event_button,
            self.run_to_end_button,
        ):
            controls.addWidget(button)

        controls.addSpacing(12)
        controls.addWidget(QLabel("速度:"))
        self.speed_combo = QComboBox(central)
        self.speed_combo.setObjectName("speedCombo")
        for mode in SpeedMode:
            self.speed_combo.addItem(mode.label, mode.value)
        controls.addWidget(self.speed_combo)
        controls.addStretch(1)
        speed_note = QLabel("速度は実時間上の進み方だけを変え、結果は変えません。", central)
        speed_note.setObjectName("speedNote")
        controls.addWidget(speed_note)
        root.addLayout(controls)

        splitter = QSplitter(Qt.Orientation.Vertical, central)
        timeline_group = QGroupBox("イベント・タイムライン（診断用Demo）", splitter)
        timeline_layout = QVBoxLayout(timeline_group)
        self.timeline = TimelineWidget(timeline_group)
        self.timeline.setMinimumHeight(230)
        timeline_layout.addWidget(self.timeline)
        splitter.addWidget(timeline_group)

        log_group = QGroupBox("実行済みイベントログ", splitter)
        log_layout = QVBoxLayout(log_group)
        self.log_model = EventLogModel(self)
        self.event_table = QTableView(log_group)
        self.event_table.setObjectName("eventLogTable")
        self.event_table.setModel(self.log_model)
        self.event_table.setAlternatingRowColors(True)
        self.event_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.event_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        header = self.event_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        log_layout.addWidget(self.event_table)
        splitter.addWidget(log_group)
        splitter.setSizes([300, 250])
        root.addWidget(splitter, stretch=1)

        diagnostics = QGroupBox("実行診断", central)
        diag_layout = QGridLayout(diagnostics)
        self.real_elapsed_label = self._add_diagnostic(diag_layout, 0, "実時間経過", "0.000 秒")
        self.virtual_elapsed_label = self._add_diagnostic(
            diag_layout, 1, "仮想時間経過", "0.000 秒"
        )
        self.effective_speed_label = self._add_diagnostic(diag_layout, 2, "実効速度", "—")
        self.queue_count_label = self._add_diagnostic(diag_layout, 3, "queue内イベント数", "26")
        self.last_event_label = self._add_diagnostic(diag_layout, 4, "最終実行イベント", "—")
        self.next_event_label = self._add_diagnostic(diag_layout, 5, "次実行イベント", "clock_tick")
        root.addWidget(diagnostics)

        self.setCentralWidget(central)
        self.setStyleSheet(self._style_sheet())

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self.controller.start)
        self.pause_button.clicked.connect(self.controller.pause)
        self.resume_button.clicked.connect(self.controller.resume)
        self.reset_button.clicked.connect(self.controller.reset)
        self.step_second_button.clicked.connect(self.controller.step_one_second)
        self.step_event_button.clicked.connect(self.controller.step_one_event)
        self.run_to_end_button.clicked.connect(self.controller.run_to_end)
        self.speed_combo.currentIndexChanged.connect(self._speed_selected)
        self.controller.snapshot_changed.connect(self._update_snapshot)
        self.controller.events_executed.connect(self._append_events)
        self.controller.scenario_reset.connect(self._reset_scenario_view)

    def _speed_selected(self, _index: int) -> None:
        value = self.speed_combo.currentData()
        if value is not None:
            self.controller.set_speed(SpeedMode(value))

    def _update_snapshot(self, snapshot: ControllerSnapshot) -> None:
        engine = snapshot.engine
        self.time_label.setText(format_time_us(engine.current_time_us))
        self.state_label.setText(STATE_LABELS[engine.state])
        self.speed_label.setText(snapshot.speed_mode.label)
        self.next_time_label.setText(
            format_time_us(engine.next_event.scheduled_time_us) if engine.next_event else "—"
        )
        self.pending_label.setText(str(engine.pending_event_count))
        self.executed_label.setText(str(engine.executed_event_count))
        self.timeline.set_current_time_us(engine.current_time_us)

        self.real_elapsed_label.setText(f"{snapshot.real_elapsed_ns / 1_000_000_000:.3f} 秒")
        self.virtual_elapsed_label.setText(f"{engine.virtual_elapsed_us / 1_000_000:.3f} 秒")
        effective = snapshot.effective_speed
        self.effective_speed_label.setText("—" if effective is None else f"{effective:.2f}×")
        self.queue_count_label.setText(str(engine.pending_event_count))
        self.last_event_label.setText(
            self._event_summary(engine.last_executed_event) if engine.last_executed_event else "—"
        )
        self.next_event_label.setText(
            self._event_summary(engine.next_event) if engine.next_event else "—"
        )
        self._update_button_state(engine.state, engine.pending_event_count)

    def _append_events(self, events) -> None:
        self.log_model.append_events(events)
        self.timeline.mark_executed(events)
        self.event_table.scrollToBottom()

    def _reset_scenario_view(self, events) -> None:
        self.log_model.reset_events()
        self.timeline.set_scenario_events(events)

    def _update_button_state(self, state: ClockState, pending_count: int) -> None:
        stopped = state is ClockState.STOPPED
        running = state is ClockState.RUNNING
        paused = state is ClockState.PAUSED
        completed = state is ClockState.COMPLETED
        self.start_button.setEnabled(stopped)
        self.pause_button.setEnabled(running)
        self.resume_button.setEnabled(paused)
        self.reset_button.setEnabled(not stopped or self.log_model.rowCount() > 0)
        self.step_second_button.setEnabled((stopped or paused) and not completed)
        self.step_event_button.setEnabled((stopped or paused) and pending_count > 0)
        self.run_to_end_button.setEnabled(not completed)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Stop QTimer deterministically before accepting window close."""

        self.controller.shutdown()
        event.accept()

    @staticmethod
    def _event_summary(event) -> str:
        return f"{format_time_us(event.scheduled_time_us)}  {event.event_type}"

    @staticmethod
    def _button(text: str, name: str, *, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("primaryButton" if primary else name)
        button.setProperty("testName", name)
        button.setMinimumHeight(34)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return button

    @staticmethod
    def _add_status(layout: QGridLayout, column: int, caption: str, value: str) -> QLabel:
        caption_label = QLabel(caption)
        caption_label.setObjectName("statusCaption")
        value_label = QLabel(value)
        value_label.setObjectName("statusValue")
        layout.addWidget(caption_label, 0, column)
        layout.addWidget(value_label, 1, column)
        return value_label

    @staticmethod
    def _add_diagnostic(layout: QGridLayout, column: int, caption: str, value: str) -> QLabel:
        container = QWidget()
        line = QHBoxLayout(container)
        line.setContentsMargins(4, 0, 12, 0)
        caption_label = QLabel(f"{caption}:")
        caption_label.setObjectName("diagnosticCaption")
        value_label = QLabel(value)
        value_label.setObjectName("diagnosticValue")
        line.addWidget(caption_label)
        line.addWidget(value_label)
        line.addStretch(1)
        layout.addWidget(container, 0, column)
        return value_label

    @staticmethod
    def _style_sheet() -> str:
        return """
            QMainWindow, QWidget { background: #F4F6FA; color: #172033; }
            QLabel#pageTitle { font-size: 23px; font-weight: 700; color: #102A43; }
            QLabel#stageDescription {
                background: #E8F1FF; border: 1px solid #B9D2F5; border-radius: 7px;
                color: #234A75; padding: 8px 12px;
            }
            QFrame#statusFrame {
                background: white; border: 1px solid #DCE3EC; border-radius: 9px;
            }
            QLabel#statusCaption { color: #66758A; font-size: 11px; }
            QLabel#statusValue { color: #14213D; font-size: 17px; font-weight: 700; }
            QLabel#speedNote { color: #66758A; font-size: 11px; }
            QGroupBox {
                background: white; border: 1px solid #DCE3EC; border-radius: 8px;
                margin-top: 9px; padding-top: 7px; font-weight: 600;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QPushButton {
                background: white; border: 1px solid #C8D2DF; border-radius: 6px;
                padding: 6px 12px; font-weight: 600;
            }
            QPushButton:hover { background: #EDF4FF; border-color: #7BA9E8; }
            QPushButton:disabled { color: #A8B0BC; background: #EEF1F5; }
            QPushButton#primaryButton { background: #2563EB; color: white; border-color: #2563EB; }
            QPushButton#primaryButton:hover { background: #1D4ED8; }
            QComboBox {
                background: white; border: 1px solid #C8D2DF; border-radius: 6px;
                padding: 6px 24px 6px 10px; min-width: 78px;
            }
            QTableView {
                background: white; alternate-background-color: #F5F8FC;
                gridline-color: #E3E8EF; border: 0;
            }
            QHeaderView::section {
                background: #EAF0F7; color: #31445D; padding: 5px;
                border: 0; border-right: 1px solid #D9E1EA; font-weight: 600;
            }
            QLabel#diagnosticCaption { color: #66758A; font-size: 11px; }
            QLabel#diagnosticValue { color: #172033; font-weight: 600; }
        """
