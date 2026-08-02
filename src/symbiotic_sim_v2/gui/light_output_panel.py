"""Scrollable Stage 6 Garden light mapper and virtual-device diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.controller import SpeedMode
from symbiotic_sim_v2.gui.light_color_preview import LightColorPreview
from symbiotic_sim_v2.gui.light_command_table_model import LightCommandTableModel
from symbiotic_sim_v2.gui.light_segment_table_model import LightSegmentTableModel
from symbiotic_sim_v2.gui.light_waveform_chart import (
    WAVEFORM_WINDOW_SECONDS,
    LightParameterChart,
    LightWaveformChart,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.engine import EngineSnapshot
from symbiotic_sim_v2.simulation.time_utils import format_time_us

LIGHT_DESCRIPTION = (
    "Garden Light Mapperは、資格生命のBをHue、点滅BPM、正弦波の"
    "明るさparameterへ変換します。"
)
VIRTUAL_CLOCK_NOTICE = (
    "Virtual Light Deviceは仮想時計から光状態を解析的に計算します。"
    "GUIの描画fpsは正式な点滅位相ではありません。"
)
NO_RESPONSE_NOTICE = (
    "このStageでは光を仮想ユーザーの心拍へ作用させません。"
)
PREVIEW_WARNING = (
    "点滅表示を含みます。体調に不安がある場合は有効にしないでください。"
    "この表示は校正済みの物理光刺激ではありません。"
)

LIGHT_TOP_SPLITTER_MIN_HEIGHT = 430
LIGHT_DIAGNOSTIC_SPLITTER_MIN_HEIGHT = 1_480
LIGHT_TABLE_TABS_MIN_HEIGHT = 330
LIGHT_DIAGNOSTIC_INITIAL_SIZES = (540, 570, 370)

LIGHT_COMMAND_CSV_FILENAME = "stage_06_light_commands.csv"
LIGHT_STATE_CSV_FILENAME = "stage_06_light_stimulus_states.csv"
LIGHT_SEGMENT_CSV_FILENAME = "stage_06_light_stimulus_segments.csv"
LIGHT_WAVEFORM_CSV_FILENAME = "stage_06_light_waveform_samples_20ms.csv"


@dataclass(frozen=True, slots=True)
class _DisplaySample:
    time_us: int
    active: bool
    source_signal_index: int | None
    holder_id: str | None
    hue_degree: float | None
    render_hue_degree: float | None
    saturation: float
    blink_bpm: float | None
    phase_cycles: float | None
    value: float


class LightOutputPanel(QWidget):
    """Read mapper/device records and state_at without reproducing core logic."""

    def __init__(
        self,
        mapper_config: Any,
        mapper_component: Any,
        device_config: Any,
        device_component: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mapper_config = mapper_config
        self._mapper_component = mapper_component
        self._device_config = device_config
        self._device_component = device_component
        self._speed_mode = SpeedMode.REALTIME
        self._engine_state = ClockState.STOPPED
        self._last_state: Any | None = None
        self._record_revision = (-1, -1, -1)
        self._waveform_cache: dict[int, _DisplaySample] = {}
        self._build_ui()
        self.reset_views()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("lightDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("lightDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(4, 4, 4, 4)
        content.setSpacing(7)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.description_label = self._notice(
            LIGHT_DESCRIPTION,
            "lightDescription",
            self.diagnostics_content,
        )
        content.addWidget(self.description_label)
        self.virtual_clock_notice = self._notice(
            VIRTUAL_CLOCK_NOTICE,
            "lightVirtualClockNotice",
            self.diagnostics_content,
        )
        content.addWidget(self.virtual_clock_notice)
        self.no_response_notice = self._notice(
            NO_RESPONSE_NOTICE,
            "lightNoResponseNotice",
            self.diagnostics_content,
        )
        content.addWidget(self.no_response_notice)
        content.addWidget(self._build_flow())

        self.top_splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.diagnostics_content,
        )
        self.top_splitter.setObjectName("lightStatePreviewSplitter")
        self.top_splitter.setMinimumHeight(LIGHT_TOP_SPLITTER_MIN_HEIGHT)
        self.top_splitter.addWidget(self._build_state_frame())
        self.top_splitter.addWidget(self._build_preview_frame())
        self.top_splitter.setCollapsible(0, False)
        self.top_splitter.setCollapsible(1, False)
        self.top_splitter.setStretchFactor(0, 2)
        self.top_splitter.setStretchFactor(1, 1)
        self.top_splitter.setSizes([900, 480])
        content.addWidget(self.top_splitter)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("lightChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(
            LIGHT_DIAGNOSTIC_SPLITTER_MIN_HEIGHT
        )
        self.waveform_chart = LightWaveformChart(self.chart_table_splitter)
        self.parameter_chart = LightParameterChart(self.chart_table_splitter)
        self.table_tabs = self._build_table_tabs()
        for widget in (self.waveform_chart, self.parameter_chart, self.table_tabs):
            self.chart_table_splitter.addWidget(widget)
        for index in range(3):
            self.chart_table_splitter.setCollapsible(index, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 1)
        self.chart_table_splitter.setStretchFactor(2, 0)
        self.chart_table_splitter.setSizes(list(LIGHT_DIAGNOSTIC_INITIAL_SIZES))
        content.addWidget(self.chart_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self._diagnostic_scroll_wheel_targets = (
            self.waveform_chart.graphics.viewport(),
            self.parameter_chart.graphics.viewport(),
        )
        for target in self._diagnostic_scroll_wheel_targets:
            target.installEventFilter(self)
        root.addWidget(self.diagnostics_scroll)

        self.setStyleSheet(
            """
                QLabel#lightDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5;
                    border-radius: 6px; color: #234A75; padding: 7px 10px;
                }
                QLabel#lightVirtualClockNotice, QLabel#lightNoResponseNotice,
                QLabel#lightPreviewWarning {
                    background: #FFF7E6; border: 1px solid #F5D28A;
                    border-radius: 6px; color: #6B4B16; padding: 7px 10px;
                }
                QFrame#lightFlowFrame {
                    background: #ECFDF5; border: 1px solid #A7F3D0;
                    border-radius: 7px;
                }
                QLabel#lightFlowNode {
                    background: white; border: 1px solid #6EE7B7;
                    border-radius: 5px; color: #065F46; font-weight: 700;
                    padding: 5px 4px;
                }
                QLabel#lightFlowArrow {
                    color: #059669; font-size: 17px; font-weight: 700;
                }
                QFrame#lightStateFrame, QFrame#lightPreviewFrame {
                    background: #F8FAFC; border: 1px solid #CBD5E1;
                    border-radius: 8px;
                }
                QLabel#lightStateCaption { color: #64748B; font-size: 10px; }
                QLabel#lightStateValue { color: #172033; font-weight: 700; }
                QCheckBox#liveLightPreviewCheck { font-weight: 700; }
            """
        )

    @staticmethod
    def _notice(text: str, name: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setObjectName(name)
        label.setWordWrap(True)
        return label

    def _build_flow(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("lightFlowFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)
        nodes = (
            "GardenQualifiedBEvent v2",
            "Garden Light Mapper",
            "LightCommandEvent = I",
            "Virtual PC Light Device",
            "LightStimulusStateEvent",
            "将来の光応答VirtualUser",
        )
        for index, text in enumerate(nodes):
            if index:
                arrow = QLabel("→", frame)
                arrow.setObjectName("lightFlowArrow")
                layout.addWidget(arrow)
            node = QLabel(text, frame)
            node.setObjectName("lightFlowNode")
            node.setAlignment(Qt.AlignmentFlag.AlignCenter)
            node.setWordWrap(True)
            layout.addWidget(node, stretch=1)
        return frame

    def _build_state_frame(self) -> QFrame:
        frame = QFrame(self.top_splitter)
        frame.setObjectName("lightStateFrame")
        grid = QGridLayout(frame)
        grid.setContentsMargins(10, 9, 10, 9)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        fields = (
            ("active", "active / inactive"),
            ("holder", "holder ID"),
            ("source_signal", "source signal"),
            ("source_b", "source B=[F,A,T,D]"),
            ("hue", "Hue degree"),
            ("render_hue", "render Hue"),
            ("bpm", "blink BPM"),
            ("saturation", "Saturation"),
            ("value", "current HSV Value"),
            ("phase", "phase cycles"),
            ("waveform", "waveform"),
            ("effective_time", "command effective time"),
            ("command_age", "command age"),
            ("command_count", "command count"),
            ("segment_count", "segment count"),
            ("phase_reset_count", "phase reset count"),
            ("phase_continuation_count", "phase continuation count"),
        )
        self.state_labels: dict[str, QLabel] = {}
        for index, (key, caption) in enumerate(fields):
            cell = QWidget(frame)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(3, 2, 3, 2)
            cell_layout.setSpacing(1)
            caption_label = QLabel(caption, cell)
            caption_label.setObjectName("lightStateCaption")
            caption_label.setWordWrap(True)
            value_label = QLabel("—", cell)
            value_label.setObjectName("lightStateValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            cell_layout.addWidget(caption_label)
            cell_layout.addWidget(value_label)
            grid.addWidget(cell, index // 4, index % 4)
            self.state_labels[key] = value_label

        self.active_label = self.state_labels["active"]
        self.holder_label = self.state_labels["holder"]
        self.source_signal_label = self.state_labels["source_signal"]
        self.source_b_label = self.state_labels["source_b"]
        self.hue_label = self.state_labels["hue"]
        self.render_hue_label = self.state_labels["render_hue"]
        self.blink_bpm_label = self.state_labels["bpm"]
        self.current_value_label = self.state_labels["value"]
        self.phase_cycles_label = self.state_labels["phase"]
        self.command_count_label = self.state_labels["command_count"]
        self.segment_count_label = self.state_labels["segment_count"]
        return frame

    def _build_preview_frame(self) -> QFrame:
        frame = QFrame(self.top_splitter)
        frame.setObjectName("lightPreviewFrame")
        frame.setMinimumWidth(350)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        title = QLabel("仮想PC光プレビュー", frame)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.color_preview = LightColorPreview(frame)
        self.light_color_preview = self.color_preview
        layout.addWidget(self.color_preview, stretch=1)
        self.preview_checkbox = QCheckBox("実光プレビューを有効にする", frame)
        self.preview_checkbox.setObjectName("liveLightPreviewCheck")
        self.preview_checkbox.setChecked(False)
        self.preview_checkbox.toggled.connect(self._preview_toggled)
        layout.addWidget(self.preview_checkbox)
        warning = QLabel(PREVIEW_WARNING, frame)
        warning.setObjectName("lightPreviewWarning")
        warning.setWordWrap(True)
        self.preview_warning_label = warning
        layout.addWidget(warning)
        return frame

    def _build_table_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self.chart_table_splitter)
        tabs.setObjectName("lightHistoryTableTabs")
        tabs.setMinimumHeight(LIGHT_TABLE_TABS_MIN_HEIGHT)

        command_page = QWidget(tabs)
        command_layout = QVBoxLayout(command_page)
        command_layout.setContentsMargins(4, 4, 4, 4)
        self.command_model = LightCommandTableModel(self)
        self.command_table = QTableView(command_page)
        self.command_table.setObjectName("lightCommandTable")
        self._configure_table(self.command_table, self.command_model)
        command_layout.addWidget(self.command_table)
        command_buttons = QHBoxLayout()
        self.export_command_button = QPushButton("Light command CSVを保存", command_page)
        self.export_command_button.setObjectName("exportLightCommandCsvButton")
        self.export_state_button = QPushButton("stimulus state CSVを保存", command_page)
        self.export_state_button.setObjectName("exportLightStateCsvButton")
        command_buttons.addWidget(self.export_command_button)
        command_buttons.addWidget(self.export_state_button)
        command_buttons.addStretch(1)
        command_layout.addLayout(command_buttons)
        tabs.addTab(command_page, "B→I / command履歴")

        segment_page = QWidget(tabs)
        segment_layout = QVBoxLayout(segment_page)
        segment_layout.setContentsMargins(4, 4, 4, 4)
        self.segment_model = LightSegmentTableModel(self)
        self.segment_table = QTableView(segment_page)
        self.segment_table.setObjectName("lightSegmentTable")
        self._configure_table(self.segment_table, self.segment_model)
        segment_layout.addWidget(self.segment_table)
        segment_buttons = QHBoxLayout()
        self.export_segment_button = QPushButton("stimulus segment CSVを保存", segment_page)
        self.export_segment_button.setObjectName("exportLightSegmentCsvButton")
        self.export_waveform_button = QPushButton("20ms波形CSVを保存", segment_page)
        self.export_waveform_button.setObjectName("exportLightWaveformCsvButton")
        segment_buttons.addWidget(self.export_segment_button)
        segment_buttons.addWidget(self.export_waveform_button)
        segment_buttons.addStretch(1)
        segment_layout.addLayout(segment_buttons)
        tabs.addTab(segment_page, "stimulus segment")

        self.export_command_button.clicked.connect(self._export_commands)
        self.export_state_button.clicked.connect(self._export_states)
        self.export_segment_button.clicked.connect(self._export_segments)
        self.export_waveform_button.clicked.connect(self._export_waveform)
        return tabs

    @staticmethod
    def _configure_table(table: QTableView, model: Any) -> None:
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched in self._diagnostic_scroll_wheel_targets and event.type() is QEvent.Type.Wheel:
            scroll_delta = event.pixelDelta().y()
            angle_delta = event.angleDelta().y()
            if scroll_delta == 0 and angle_delta:
                scroll_delta = round(
                    (angle_delta / 120.0)
                    * 3
                    * self.diagnostics_scroll.verticalScrollBar().singleStep()
                )
            if scroll_delta:
                bar = self.diagnostics_scroll.verticalScrollBar()
                bar.setValue(bar.value() - scroll_delta)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def set_components(
        self,
        mapper_config: Any,
        mapper_component: Any,
        device_config: Any,
        device_component: Any,
    ) -> None:
        self._mapper_config = mapper_config
        self._mapper_component = mapper_component
        self._device_config = device_config
        self._device_component = device_component

    def set_speed_mode(self, speed_mode: SpeedMode | str) -> None:
        self._speed_mode = (
            speed_mode if isinstance(speed_mode, SpeedMode) else SpeedMode(speed_mode)
        )
        if not self._preview_eligible():
            self._set_preview_checked(False)
        self._update_preview_availability()
        self._paint_preview()

    def update_diagnostics(
        self,
        engine_snapshot: EngineSnapshot,
        speed_mode: SpeedMode | str = SpeedMode.REALTIME,
    ) -> None:
        self._engine_state = engine_snapshot.state
        self.set_speed_mode(speed_mode)
        current_time_us = engine_snapshot.current_time_us
        state = self._device_component.state_at(current_time_us)
        self._last_state = state
        summary = self._device_snapshot(current_time_us)

        commands = tuple(self._mapper_component.command_records())
        states = tuple(self._device_component.stimulus_state_records())
        segments = tuple(self._device_component.stimulus_segments())
        self._update_state_labels(state, summary, commands, states, segments)
        self._paint_preview()

        revision = (len(commands), len(states), len(segments))
        if revision != self._record_revision:
            previous_command_rows = self.command_model.rowCount()
            previous_segment_rows = self.segment_model.rowCount()
            self.command_model.set_records(commands, states)
            self.segment_model.set_records(segments)
            self.parameter_chart.set_records(commands, current_time_us)
            if self.command_model.rowCount() > previous_command_rows:
                self.command_table.scrollToBottom()
            if self.segment_model.rowCount() > previous_segment_rows:
                self.segment_table.scrollToBottom()
            self._record_revision = revision
        else:
            self.parameter_chart.set_current_time_us(current_time_us)

        samples = (
            ()
            if engine_snapshot.state is ClockState.STOPPED and not commands
            else self._visible_waveform_samples(current_time_us)
        )
        self.waveform_chart.set_records(samples, commands, current_time_us)
        self._set_export_enabled(
            commands,
            states,
            segments,
            waveform_ready=engine_snapshot.state is ClockState.COMPLETED,
        )

    def reset_views(self) -> None:
        self._engine_state = ClockState.STOPPED
        self._last_state = None
        self._record_revision = (-1, -1, -1)
        self._waveform_cache.clear()
        self.command_model.clear()
        self.segment_model.clear()
        self.waveform_chart.clear()
        self.parameter_chart.clear()
        for label in self.state_labels.values():
            label.setText("—")
        self.state_labels["active"].setText("inactive")
        self.state_labels["command_count"].setText("0")
        self.state_labels["segment_count"].setText("0")
        self.state_labels["phase_reset_count"].setText("0")
        self.state_labels["phase_continuation_count"].setText("0")
        self._set_preview_checked(False)
        self.color_preview.clear()
        self._update_preview_availability()
        self._set_export_enabled((), (), (), waveform_ready=False)
        self.diagnostics_scroll.verticalScrollBar().setValue(0)

    def _device_snapshot(self, current_time_us: int) -> Any:
        try:
            return self._device_component.snapshot(current_time_us)
        except TypeError:
            return self._device_component.snapshot()

    def _update_state_labels(
        self,
        state: Any,
        summary: Any,
        commands: tuple[Any, ...],
        states: tuple[Any, ...],
        segments: tuple[Any, ...],
    ) -> None:
        active = bool(_field(state, "active", default=False))
        source_b = _field(state, "source_b", "b", default=None)
        command_count = _field(summary, "command_count", default=len(commands))
        segment_count = _field(
            summary,
            "closed_segment_count",
            "segment_count",
            default=len(segments),
        )
        phase_reset_count = _field(
            summary,
            "phase_reset_count",
            default=sum(bool(_field(item, "phase_reset", default=False)) for item in states),
        )
        continuation_count = _field(
            summary,
            "phase_continuation_count",
            default=sum(
                not bool(_field(item, "phase_reset", default=False))
                and bool(_field(item, "active", default=False))
                for item in states
            ),
        )
        effective_time_us = _field(state, "command_effective_time_us", default=None)
        command_age_us = _field(state, "command_age_us", default=None)
        values = {
            "active": "active" if active else "inactive",
            "holder": _field(
                state,
                "current_holder_id",
                "qualification_holder_id",
                "holder_id",
                default=None,
            )
            or "null",
            "source_signal": _optional(_field(state, "source_signal_index", default=None)),
            "source_b": _format_b(source_b),
            "hue": _number(_field(state, "hue_degree", default=None), 3, "°"),
            "render_hue": _number(
                _field(state, "render_hue_degree", default=None),
                3,
                "°",
            ),
            "bpm": _number(_field(state, "blink_bpm", default=None), 3, " BPM"),
            "saturation": _number(
                _field(state, "saturation", default=None),
                3,
            ),
            "value": _number(
                _field(state, "current_value", "value", default=0.0),
                6,
            ),
            "phase": _number(_field(state, "phase_cycles", default=None), 6),
            "waveform": str(_field(state, "waveform", default="off")),
            "effective_time": _format_time(effective_time_us),
            "command_age": "—" if command_age_us is None else f"{command_age_us} us",
            "command_count": str(command_count),
            "segment_count": str(segment_count),
            "phase_reset_count": str(phase_reset_count),
            "phase_continuation_count": str(continuation_count),
        }
        for key, text in values.items():
            self.state_labels[key].setText(text)

    def _visible_waveform_samples(self, current_time_us: int) -> tuple[_DisplaySample, ...]:
        interval_us = int(
            _field(
                self._device_config,
                "diagnostic_sample_interval_us",
                default=20_000,
            )
        )
        window_us = int(WAVEFORM_WINDOW_SECONDS * 1_000_000)
        start_us = max(0, current_time_us - window_us)
        first_grid_us = ((start_us + interval_us - 1) // interval_us) * interval_us
        for time_us in range(first_grid_us, current_time_us + 1, interval_us):
            if time_us not in self._waveform_cache:
                state = self._device_component.state_at(time_us)
                self._waveform_cache[time_us] = _DisplaySample(
                    time_us=time_us,
                    active=bool(_field(state, "active", default=False)),
                    source_signal_index=_field(
                        state,
                        "source_signal_index",
                        default=None,
                    ),
                    holder_id=_field(
                        state,
                        "current_holder_id",
                        "qualification_holder_id",
                        "holder_id",
                        default=None,
                    ),
                    hue_degree=_field(state, "hue_degree", default=None),
                    render_hue_degree=_field(
                        state,
                        "render_hue_degree",
                        default=None,
                    ),
                    saturation=float(_field(state, "saturation", default=0.0) or 0.0),
                    blink_bpm=_field(state, "blink_bpm", default=None),
                    phase_cycles=_field(state, "phase_cycles", default=None),
                    value=float(
                        _field(state, "current_value", "value", default=0.0) or 0.0
                    ),
                )
        stale = tuple(time_us for time_us in self._waveform_cache if time_us < start_us)
        for time_us in stale:
            del self._waveform_cache[time_us]
        return tuple(self._waveform_cache[key] for key in sorted(self._waveform_cache))

    def _preview_toggled(self, checked: bool) -> None:
        if checked and not self._preview_eligible():
            self._set_preview_checked(False)
        self._paint_preview()

    def _preview_eligible(self) -> bool:
        return self._speed_mode is SpeedMode.REALTIME and self._engine_state in {
            ClockState.RUNNING,
            ClockState.PAUSED,
        }

    def _update_preview_availability(self) -> None:
        self.preview_checkbox.setEnabled(self._preview_eligible())

    def _set_preview_checked(self, checked: bool) -> None:
        blocker = QSignalBlocker(self.preview_checkbox)
        self.preview_checkbox.setChecked(checked)
        del blocker

    def _paint_preview(self) -> None:
        if self._last_state is None:
            self.color_preview.clear()
            return
        self.color_preview.set_light_state(
            self._last_state,
            live_preview_enabled=(
                self.preview_checkbox.isChecked() and self._preview_eligible()
            ),
        )

    def _set_export_enabled(
        self,
        commands: tuple[Any, ...],
        states: tuple[Any, ...],
        segments: tuple[Any, ...],
        *,
        waveform_ready: bool,
    ) -> None:
        self.export_command_button.setEnabled(bool(commands))
        self.export_state_button.setEnabled(bool(states))
        self.export_segment_button.setEnabled(bool(segments))
        self.export_waveform_button.setEnabled(bool(commands) and waveform_ready)

    def _export_commands(self) -> None:
        records = tuple(self._mapper_component.command_records())
        if records:
            self._save_records(
                "Stage 6 Light command CSVを保存",
                LIGHT_COMMAND_CSV_FILENAME,
                "export_light_commands_csv",
                records,
            )

    def _export_states(self) -> None:
        records = tuple(self._device_component.stimulus_state_records())
        if records:
            self._save_records(
                "Stage 6 stimulus state CSVを保存",
                LIGHT_STATE_CSV_FILENAME,
                "export_light_stimulus_states_csv",
                records,
            )

    def _export_segments(self) -> None:
        records = tuple(self._device_component.stimulus_segments())
        if records:
            self._save_records(
                "Stage 6 stimulus segment CSVを保存",
                LIGHT_SEGMENT_CSV_FILENAME,
                "export_light_stimulus_segments_csv",
                records,
            )

    def _export_waveform(self) -> None:
        records = tuple(self._device_component.waveform_samples())
        if records:
            self._save_records(
                "Stage 6 20ms波形CSVを保存",
                LIGHT_WAVEFORM_CSV_FILENAME,
                "export_light_waveform_samples_csv",
                records,
            )

    def _save_records(
        self,
        title: str,
        filename: str,
        exporter_name: str,
        records: tuple[Any, ...],
    ) -> None:
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            title,
            filename,
            "CSV (*.csv)",
        )
        if not destination:
            return
        from symbiotic_sim_v2.devices.virtual_light import diagnostics

        exporter = getattr(diagnostics, exporter_name)
        exporter(destination, records)


def _field(record: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default


def _optional(value: Any) -> str:
    return "—" if value is None else str(value)


def _number(value: Any, places: int, suffix: str = "") -> str:
    return "—" if value is None else f"{float(value):.{places}f}{suffix}"


def _format_b(value: Any) -> str:
    if value is None:
        return "—"
    return "[" + ", ".join(f"{float(item):.6f}" for item in value) + "]"


def _format_time(value: Any) -> str:
    return "—" if value is None else format_time_us(int(value))
