"""Stage 2 main window combining virtual-user and Stage 1 time diagnostics."""

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
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.controller import (
    ControllerSnapshot,
    SimulationController,
    SpeedMode,
)
from symbiotic_sim_v2.gui.event_log_model import EventLogModel
from symbiotic_sim_v2.gui.main_window import STATE_LABELS, MainWindow
from symbiotic_sim_v2.gui.timeline_widget import TimelineWidget
from symbiotic_sim_v2.gui.virtual_user_panel import VirtualUserPanel
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.time_utils import format_time_us
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.scenario import (
    VirtualUserSimulation,
    create_virtual_user_simulation,
)

WINDOW_TITLE = "環境共生型デジタル生命シミュレーター v2 — 外部刺激なし仮想ユーザー"


class VirtualUserMainWindow(QMainWindow):
    """Default Stage 2 GUI while retaining a complete time/event diagnostic tab."""

    def __init__(
        self,
        controller: SimulationController,
        simulation: VirtualUserSimulation,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.simulation = simulation
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1360, 900)
        self.setMinimumSize(1120, 760)
        self._build_ui()
        self._connect_signals()
        self.timeline.set_scenario_events(self.controller.planned_events())
        self._update_snapshot(self.controller.current_snapshot())

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(9)

        title = QLabel("外部刺激なし仮想ユーザー  ·  Stage 02", central)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        status_frame = QFrame(central)
        status_frame.setObjectName("statusFrame")
        status_layout = QGridLayout(status_frame)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setHorizontalSpacing(18)
        self.time_label = MainWindow._add_status(
            status_layout, 0, "仮想時刻", "00:00:00.000"
        )
        self.time_label.setObjectName("virtualTimeLabel")
        self.state_label = MainWindow._add_status(status_layout, 1, "実行状態", "停止")
        self.speed_label = MainWindow._add_status(status_layout, 2, "選択速度", "等速")
        self.next_time_label = MainWindow._add_status(
            status_layout, 3, "次イベント時刻", "00:00:00.000"
        )
        self.pending_label = MainWindow._add_status(status_layout, 4, "pending", "2")
        self.executed_label = MainWindow._add_status(status_layout, 5, "executed", "0")
        root.addWidget(status_frame)

        controls = QHBoxLayout()
        controls.setSpacing(7)
        self.start_button = MainWindow._button("開始", "startButton")
        self.pause_button = MainWindow._button("一時停止", "pauseButton")
        self.resume_button = MainWindow._button("再開", "resumeButton")
        self.reset_button = MainWindow._button("リセット", "resetButton")
        self.step_second_button = MainWindow._button("1秒進む", "stepSecondButton")
        self.step_event_button = MainWindow._button("次イベント", "stepEventButton")
        self.run_to_end_button = MainWindow._button(
            "最後まで実行", "runToEndButton", primary=True
        )
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
        controls.addSpacing(10)
        controls.addWidget(QLabel("速度:"))
        self.speed_combo = QComboBox(central)
        self.speed_combo.setObjectName("speedCombo")
        for mode in SpeedMode:
            self.speed_combo.addItem(mode.label, mode.value)
        controls.addWidget(self.speed_combo)
        controls.addStretch(1)
        speed_note = QLabel("速度は実時間上の進み方だけを変え、心拍系列は変えません。")
        speed_note.setObjectName("speedNote")
        controls.addWidget(speed_note)
        root.addLayout(controls)

        self.tabs = QTabWidget(central)
        self.tabs.setObjectName("mainTabs")
        self.virtual_user_panel = VirtualUserPanel(
            self.simulation.config,
            self.simulation.component,
            self.tabs,
        )
        self.tabs.addTab(self.virtual_user_panel, "仮想ユーザー")
        self.time_diagnostics_tab = self._build_time_diagnostics_tab()
        self.tabs.addTab(self.time_diagnostics_tab, "時間・イベント診断")
        root.addWidget(self.tabs, stretch=1)

        self.setCentralWidget(central)
        self.setStyleSheet(
            MainWindow._style_sheet()
            + """
                QLabel#stimulusNotice, QLabel#diagnosticNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A; border-radius: 6px;
                    color: #6B4B16; padding: 6px 10px;
                }
                QLabel#sectionTitle { font-size: 17px; font-weight: 700; color: #17324D; }
                QLabel#settingExplanation { color: #6B778C; font-size: 10px; }
                QSpinBox, QDoubleSpinBox {
                    background: white; border: 1px solid #C8D2DF; border-radius: 5px;
                    padding: 4px 6px;
                }
                QTabWidget::pane { border: 1px solid #DCE3EC; border-radius: 6px; }
                QTabBar::tab { padding: 7px 16px; background: #E8EDF4; }
                QTabBar::tab:selected { background: white; color: #1D4ED8; font-weight: 700; }
            """
        )

    def _build_time_diagnostics_tab(self) -> QWidget:
        tab = QWidget(self.tabs)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        note = QLabel(
            "Stage 1のinteger-microseconds時計、deterministic event ordering、"
            "実行済みevent logを、現在のVirtualUserScenarioで確認します。",
            tab,
        )
        note.setWordWrap(True)
        note.setObjectName("stageDescription")
        layout.addWidget(note)

        splitter = QSplitter(Qt.Orientation.Vertical, tab)
        timeline_group = QGroupBox("イベント・タイムライン", splitter)
        timeline_layout = QVBoxLayout(timeline_group)
        self.timeline = TimelineWidget(timeline_group)
        self.timeline.setMinimumHeight(220)
        timeline_layout.addWidget(self.timeline)
        splitter.addWidget(timeline_group)

        log_group = QGroupBox("実行済みイベントログ", splitter)
        log_layout = QVBoxLayout(log_group)
        self.log_model = EventLogModel(self)
        self.event_table = QTableView(log_group)
        self.event_table.setObjectName("eventLogTable")
        self.event_table.setModel(self.log_model)
        self.event_table.setAlternatingRowColors(True)
        self.event_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.event_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self.event_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        log_layout.addWidget(self.event_table)
        splitter.addWidget(log_group)
        splitter.setSizes([300, 270])
        layout.addWidget(splitter, stretch=1)

        diagnostics = QGroupBox("実行診断", tab)
        diagnostic_layout = QGridLayout(diagnostics)
        self.real_elapsed_label = MainWindow._add_diagnostic(
            diagnostic_layout, 0, "実時間経過", "0.000 秒"
        )
        self.virtual_elapsed_label = MainWindow._add_diagnostic(
            diagnostic_layout, 1, "仮想時間経過", "0.000 秒"
        )
        self.effective_speed_label = MainWindow._add_diagnostic(
            diagnostic_layout, 2, "実効速度", "—"
        )
        self.queue_count_label = MainWindow._add_diagnostic(
            diagnostic_layout, 3, "queue内イベント数", "2"
        )
        self.last_event_label = MainWindow._add_diagnostic(
            diagnostic_layout, 4, "最終実行イベント", "—"
        )
        self.next_event_label = MainWindow._add_diagnostic(
            diagnostic_layout, 5, "次実行イベント", "heartbeat"
        )
        layout.addWidget(diagnostics)
        return tab

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self.controller.start)
        self.pause_button.clicked.connect(self.controller.pause)
        self.resume_button.clicked.connect(self.controller.resume)
        self.reset_button.clicked.connect(self.controller.reset)
        self.step_second_button.clicked.connect(self.controller.step_one_second)
        self.step_event_button.clicked.connect(self.controller.step_one_event)
        self.run_to_end_button.clicked.connect(self.controller.run_to_end)
        self.speed_combo.currentIndexChanged.connect(self._speed_selected)
        self.virtual_user_panel.config_applied.connect(self._apply_config)
        self.controller.snapshot_changed.connect(self._update_snapshot)
        self.controller.events_executed.connect(self._append_events)
        self.controller.scenario_reset.connect(self._reset_scenario_view)

    def _speed_selected(self, _index: int) -> None:
        value = self.speed_combo.currentData()
        if value is not None:
            self.controller.set_speed(SpeedMode(value))

    def _apply_config(self, config: VirtualUserConfig) -> None:
        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            return
        simulation = create_virtual_user_simulation(config)
        self.simulation = simulation
        self.virtual_user_panel.set_component(simulation.component)
        self.virtual_user_panel.set_config(config)
        self.virtual_user_panel.reset_views()
        self.controller.replace_engine(simulation.engine)

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
        self.virtual_user_panel.update_diagnostics(engine)

        self.real_elapsed_label.setText(f"{snapshot.real_elapsed_ns / 1_000_000_000:.3f} 秒")
        self.virtual_elapsed_label.setText(f"{engine.virtual_elapsed_us / 1_000_000:.3f} 秒")
        self.effective_speed_label.setText(
            "—" if snapshot.effective_speed is None else f"{snapshot.effective_speed:.2f}×"
        )
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
        self.virtual_user_panel.reset_views()

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
        """Stop the GUI wake-up timer before accepting close."""

        self.controller.shutdown()
        event.accept()

    @staticmethod
    def _event_summary(event) -> str:
        return f"{format_time_us(event.scheduled_time_us)}  {event.event_type}"
