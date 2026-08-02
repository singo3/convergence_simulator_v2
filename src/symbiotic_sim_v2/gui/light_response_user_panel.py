"""Scrollable Stage 7 fixed-preference light-responsive user diagnostics."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.light_response_chart import (
    GardenEvaluationResponseChart,
    LightResponsePhysiologyChart,
    LightStimulusResponseChart,
)
from symbiotic_sim_v2.gui.light_response_table_model import (
    LightResponseReceiptTableModel,
)
from symbiotic_sim_v2.gui.responsive_heartbeat_table_model import (
    ResponsiveHeartbeatTableModel,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.engine import EngineSnapshot
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.diagnostics import (
    LIGHT_RESPONSE_SAMPLES_CSV_FILENAME,
    LIGHT_RESPONSE_SEGMENTS_CSV_FILENAME,
    LIGHT_RESPONSIVE_HEARTBEATS_CSV_FILENAME,
    LIGHT_STIMULUS_RECEIPTS_CSV_FILENAME,
    export_light_response_samples_csv,
    export_light_response_segments_csv,
    export_light_responsive_heartbeats_csv,
    export_light_stimulus_receipts_csv,
)
from symbiotic_sim_v2.virtual_user.light_response.presets import (
    light_response_config_for_preset,
    light_response_preset_names,
)

DESCRIPTION = (
    "この仮想ユーザーは、提示された光のHueと点滅BPMに対する"
    "固定された反応特性を持ちます。"
)
STATIONARY_NOTICE = "好みは1run中に変化しません。"
BOUNDARY_NOTICE = (
    "光はRMSSDやNを直接変更せず、将来の心拍間隔を生成する"
    "生理モデルへ作用します。"
)
ASSUMPTION_NOTICE = (
    "この反応モデルは実データ未校正のsimulation assumptionです。"
)

RESPONSE_TOP_SPLITTER_MIN_HEIGHT = 610
RESPONSE_DIAGNOSTICS_MIN_HEIGHT = 2_610
RESPONSE_TABLE_TABS_MIN_HEIGHT = 330
RESPONSE_DIAGNOSTIC_INITIAL_SIZES = (800, 720, 720, 350)


class LightResponseUserPanel(QWidget):
    """Read Stage 7 diagnostic records without reproducing any model formula."""

    config_applied = Signal(object)

    def __init__(
        self,
        config: LightResponseConfig,
        component: Any,
        garden_input_component: Any,
        parent: QWidget | None = None,
        *,
        preset_name: str = "aligned_green_center",
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._component = component
        self._garden_input_component = garden_input_component
        self._preset_name = preset_name
        self._engine_state = ClockState.STOPPED
        self._record_revision = (-1, -1, -1, -1, -1)
        self._build_ui()
        self.set_config(config, preset_name=preset_name)
        self.reset_views()

    @property
    def config(self) -> LightResponseConfig:
        return self._config

    @property
    def preset_name(self) -> str:
        return self._preset_name

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("lightResponseDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("lightResponseDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(4, 4, 4, 4)
        content.setSpacing(7)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.description_label = self._notice(
            DESCRIPTION, "lightResponseDescription", self.diagnostics_content
        )
        self.stationary_notice = self._notice(
            STATIONARY_NOTICE, "lightResponseStationaryNotice", self.diagnostics_content
        )
        self.boundary_notice = self._notice(
            BOUNDARY_NOTICE, "lightResponseBoundaryNotice", self.diagnostics_content
        )
        self.assumption_notice = self._notice(
            ASSUMPTION_NOTICE,
            "lightResponseAssumptionNotice",
            self.diagnostics_content,
        )
        for notice in (
            self.description_label,
            self.stationary_notice,
            self.boundary_notice,
            self.assumption_notice,
        ):
            content.addWidget(notice)
        content.addWidget(self._build_flow())

        self.top_splitter = QSplitter(
            Qt.Orientation.Horizontal, self.diagnostics_content
        )
        self.top_splitter.setObjectName("lightResponseSettingsStateSplitter")
        self.top_splitter.setMinimumHeight(RESPONSE_TOP_SPLITTER_MIN_HEIGHT)
        self.settings_frame = self._build_settings_frame()
        self.state_frame = self._build_state_frame()
        self.top_splitter.addWidget(self.settings_frame)
        self.top_splitter.addWidget(self.state_frame)
        self.top_splitter.setCollapsible(0, False)
        self.top_splitter.setCollapsible(1, False)
        self.top_splitter.setStretchFactor(0, 1)
        self.top_splitter.setStretchFactor(1, 2)
        self.top_splitter.setSizes([430, 930])
        content.addWidget(self.top_splitter)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical, self.diagnostics_content
        )
        self.chart_table_splitter.setObjectName("lightResponseChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(RESPONSE_DIAGNOSTICS_MIN_HEIGHT)
        self.light_response_chart = LightStimulusResponseChart(
            parent=self.chart_table_splitter
        )
        self.physiology_chart = LightResponsePhysiologyChart(
            parent=self.chart_table_splitter
        )
        self.garden_evaluation_chart = GardenEvaluationResponseChart(
            parent=self.chart_table_splitter
        )
        self.rmssd_n_chart = self.garden_evaluation_chart
        self.table_tabs = self._build_table_tabs()
        for widget in (
            self.light_response_chart,
            self.physiology_chart,
            self.garden_evaluation_chart,
            self.table_tabs,
        ):
            self.chart_table_splitter.addWidget(widget)
        for index in range(4):
            self.chart_table_splitter.setCollapsible(index, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 1)
        self.chart_table_splitter.setStretchFactor(2, 1)
        self.chart_table_splitter.setStretchFactor(3, 0)
        self.chart_table_splitter.setSizes(list(RESPONSE_DIAGNOSTIC_INITIAL_SIZES))
        content.addWidget(self.chart_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self._diagnostic_scroll_wheel_targets = (
            self.light_response_chart.graphics.viewport(),
            self.physiology_chart.graphics.viewport(),
            self.garden_evaluation_chart.graphics.viewport(),
        )
        for target in self._diagnostic_scroll_wheel_targets:
            target.installEventFilter(self)
        root.addWidget(self.diagnostics_scroll)

        self.setStyleSheet(
            """
                QLabel#lightResponseDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5;
                    border-radius: 6px; color: #234A75; padding: 7px 10px;
                }
                QLabel#lightResponseStationaryNotice,
                QLabel#lightResponseBoundaryNotice,
                QLabel#lightResponseAssumptionNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A;
                    border-radius: 6px; color: #6B4B16; padding: 7px 10px;
                }
                QFrame#lightResponseFlowFrame {
                    background: #ECFDF5; border: 1px solid #A7F3D0;
                    border-radius: 7px;
                }
                QLabel#lightResponseFlowNode {
                    background: white; border: 1px solid #6EE7B7;
                    border-radius: 5px; color: #065F46; font-weight: 700;
                    padding: 5px 3px;
                }
                QLabel#lightResponseFlowArrow {
                    color: #059669; font-size: 17px; font-weight: 700;
                }
                QFrame#lightResponseSettingsFrame, QFrame#lightResponseStateFrame {
                    background: #F8FAFC; border: 1px solid #CBD5E1;
                    border-radius: 8px;
                }
                QLabel#lightResponseStateCaption {
                    color: #64748B; font-size: 10px;
                }
                QLabel#lightResponseStateValue {
                    color: #172033; font-weight: 700;
                }
                QLabel#lightResponseSettingExplanation {
                    color: #6B778C; font-size: 10px;
                }
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
        frame.setObjectName("lightResponseFlowFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        nodes = (
            "LightStimulusStateEvent",
            "物理光projection",
            "Hue/BPM適合度",
            "一次遅れ反応R(t)",
            "呼吸性RRI変動幅・平均RRI",
            "HeartbeatEvent",
            "H10",
            "RRI",
            "Garden RMSSD/N",
        )
        for index, text in enumerate(nodes):
            if index:
                arrow = QLabel("→", frame)
                arrow.setObjectName("lightResponseFlowArrow")
                layout.addWidget(arrow)
            node = QLabel(text, frame)
            node.setObjectName("lightResponseFlowNode")
            node.setAlignment(Qt.AlignmentFlag.AlignCenter)
            node.setWordWrap(True)
            layout.addWidget(node, stretch=1)
        return frame

    def _build_settings_frame(self) -> QFrame:
        frame = QFrame(self.top_splitter)
        frame.setObjectName("lightResponseSettingsFrame")
        frame.setMinimumWidth(350)
        frame.setMaximumWidth(490)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(7)
        heading = QLabel("固定ユーザー特性設定", frame)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.preset_combo = QComboBox(frame)
        self.preset_combo.setObjectName("lightResponsePresetCombo")
        for name in light_response_preset_names():
            self.preset_combo.addItem(name, name)
        self._add_setting(
            form,
            "preset",
            self.preset_combo,
            "固定された反応特性の診断用プリセット",
        )
        self.preferred_hue_spin = self._spin(0.0, 360.0, 2, " °")
        self._add_setting(
            form,
            "preferred Hue",
            self.preferred_hue_spin,
            "最も反応が高くなる光の色相",
        )
        self.hue_sigma_spin = self._spin(0.01, 180.0, 2, " °")
        self._add_setting(
            form,
            "Hueの好み幅",
            self.hue_sigma_spin,
            "中心色相から離れたときに反応が下がる広さ",
        )
        self.preferred_bpm_spin = self._spin(10.0, 165.0, 2, " BPM")
        self._add_setting(
            form,
            "preferred blink BPM",
            self.preferred_bpm_spin,
            "最も反応が高くなる点滅速度",
        )
        self.bpm_sigma_spin = self._spin(0.01, 500.0, 2, " BPM")
        self._add_setting(
            form,
            "BPMの好み幅",
            self.bpm_sigma_spin,
            "中心点滅速度から離れたときに反応が下がる広さ",
        )
        self.respiratory_gain_spin = self._spin(0.0, 500.0, 2, " ms")
        self._add_setting(
            form,
            "呼吸性変動への最大作用",
            self.respiratory_gain_spin,
            "R(t)=1で加わる呼吸性RRI変動幅",
        )
        self.mean_rri_gain_spin = self._spin(0.0, 500.0, 2, " ms")
        self._add_setting(
            form,
            "平均RRIへの最大作用",
            self.mean_rri_gain_spin,
            "R(t)=1で加わる平均RRI",
        )
        self.onset_tau_spin = self._spin(0.01, 600.0, 2, " 秒")
        self._add_setting(
            form,
            "立ち上がり時間",
            self.onset_tau_spin,
            "光反応が目標へ近づく一次遅れの時定数",
        )
        self.recovery_tau_spin = self._spin(0.01, 600.0, 2, " 秒")
        self._add_setting(
            form,
            "回復時間",
            self.recovery_tau_spin,
            "光が弱まった後に反応が回復する時定数",
        )
        layout.addLayout(form)
        self.apply_settings_button = QPushButton("設定を適用", frame)
        self.apply_settings_button.setObjectName("applyLightResponseSettingsButton")
        layout.addWidget(self.apply_settings_button)
        self.settings_help_label = QLabel(
            "presetと特性は停止中またはreset後だけ変更できます。",
            frame,
        )
        self.settings_help_label.setObjectName("lightResponseSettingExplanation")
        self.settings_help_label.setWordWrap(True)
        layout.addWidget(self.settings_help_label)
        layout.addStretch(1)
        self.preset_combo.activated.connect(self._preset_activated)
        self.apply_settings_button.clicked.connect(self._apply_clicked)
        return frame

    def _build_state_frame(self) -> QFrame:
        frame = QFrame(self.top_splitter)
        frame.setObjectName("lightResponseStateFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        heading = QLabel("現在の光知覚・反応・生理状態", frame)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        fields = (
            ("light_active", "light active"),
            ("hue", "perceived Hue"),
            ("bpm", "perceived BPM"),
            ("hue_match", "Hue match"),
            ("bpm_match", "BPM match"),
            ("preference_match", "total preference match"),
            ("response_target", "response target"),
            ("response_level", "response level"),
            ("base_respiratory", "base respiratory amplitude"),
            ("effective_respiratory", "effective respiratory amplitude"),
            ("base_mean_rri", "base mean RRI"),
            ("effective_mean_rri", "effective mean RRI"),
            ("latest_rri", "latest true RRI"),
            ("latest_hr", "latest instantaneous HR"),
            ("heartbeat_count", "heartbeat count"),
        )
        self.state_labels: dict[str, QLabel] = {}
        for index, (key, caption) in enumerate(fields):
            cell = QWidget(frame)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(3, 2, 3, 2)
            cell_layout.setSpacing(1)
            caption_label = QLabel(caption, cell)
            caption_label.setObjectName("lightResponseStateCaption")
            caption_label.setWordWrap(True)
            value_label = QLabel("—", cell)
            value_label.setObjectName("lightResponseStateValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            cell_layout.addWidget(caption_label)
            cell_layout.addWidget(value_label)
            grid.addWidget(cell, index // 4, index % 4)
            self.state_labels[key] = value_label
        layout.addLayout(grid)
        layout.addStretch(1)

        self.light_active_label = self.state_labels["light_active"]
        self.preference_match_label = self.state_labels["preference_match"]
        self.response_target_label = self.state_labels["response_target"]
        self.response_level_label = self.state_labels["response_level"]
        self.effective_respiratory_amplitude_label = self.state_labels[
            "effective_respiratory"
        ]
        self.effective_mean_rri_label = self.state_labels["effective_mean_rri"]
        self.heartbeat_count_label = self.state_labels["heartbeat_count"]
        return frame

    def _build_table_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self.chart_table_splitter)
        tabs.setObjectName("lightResponseTableTabs")
        tabs.setMinimumHeight(RESPONSE_TABLE_TABS_MIN_HEIGHT)

        receipt_page = QWidget(tabs)
        receipt_layout = QVBoxLayout(receipt_page)
        receipt_layout.setContentsMargins(4, 4, 4, 4)
        self.receipt_model = LightResponseReceiptTableModel(self)
        self.receipt_table = QTableView(receipt_page)
        self.receipt_table.setObjectName("lightResponseReceiptTable")
        self._configure_table(self.receipt_table, self.receipt_model)
        receipt_layout.addWidget(self.receipt_table)
        receipt_buttons = QHBoxLayout()
        self.export_receipt_button = QPushButton("light receipt CSVを保存", receipt_page)
        self.export_receipt_button.setObjectName("exportLightResponseReceiptCsvButton")
        self.export_segment_button = QPushButton("response segment CSVを保存", receipt_page)
        self.export_segment_button.setObjectName("exportLightResponseSegmentCsvButton")
        receipt_buttons.addWidget(self.export_receipt_button)
        receipt_buttons.addWidget(self.export_segment_button)
        receipt_buttons.addStretch(1)
        receipt_layout.addLayout(receipt_buttons)
        tabs.addTab(receipt_page, "light receipt")

        heartbeat_page = QWidget(tabs)
        heartbeat_layout = QVBoxLayout(heartbeat_page)
        heartbeat_layout.setContentsMargins(4, 4, 4, 4)
        self.heartbeat_model = ResponsiveHeartbeatTableModel(self)
        self.heartbeat_table = QTableView(heartbeat_page)
        self.heartbeat_table.setObjectName("lightResponsiveHeartbeatTable")
        self._configure_table(self.heartbeat_table, self.heartbeat_model)
        heartbeat_layout.addWidget(self.heartbeat_table)
        heartbeat_buttons = QHBoxLayout()
        self.export_heartbeat_button = QPushButton(
            "responsive heartbeat CSVを保存", heartbeat_page
        )
        self.export_heartbeat_button.setObjectName(
            "exportLightResponsiveHeartbeatCsvButton"
        )
        self.export_sample_button = QPushButton("100ms response CSVを保存", heartbeat_page)
        self.export_sample_button.setObjectName("exportLightResponseSampleCsvButton")
        heartbeat_buttons.addWidget(self.export_heartbeat_button)
        heartbeat_buttons.addWidget(self.export_sample_button)
        heartbeat_buttons.addStretch(1)
        heartbeat_layout.addLayout(heartbeat_buttons)
        tabs.addTab(heartbeat_page, "responsive heartbeat")

        self.export_receipt_button.clicked.connect(self._export_receipts)
        self.export_segment_button.clicked.connect(self._export_segments)
        self.export_heartbeat_button.clicked.connect(self._export_heartbeats)
        self.export_sample_button.clicked.connect(self._export_samples)
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
        config: LightResponseConfig,
        component: Any,
        garden_input_component: Any,
        *,
        preset_name: str | None = None,
    ) -> None:
        self._component = component
        self._garden_input_component = garden_input_component
        self.set_config(config, preset_name=preset_name)

    def set_config(
        self,
        config: LightResponseConfig,
        *,
        preset_name: str | None = None,
    ) -> None:
        self._config = config
        if preset_name is not None:
            self._preset_name = preset_name
        with QSignalBlocker(self.preset_combo):
            custom_index = self.preset_combo.findData("custom")
            if self._preset_name == "custom" and custom_index < 0:
                self.preset_combo.addItem("custom (手動設定)", "custom")
            elif self._preset_name != "custom" and custom_index >= 0:
                self.preset_combo.removeItem(custom_index)
            index = self.preset_combo.findData(self._preset_name)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
        self._set_exact_spin_value(
            self.preferred_hue_spin,
            config.preferred_hue_degree,
            "preferred_hue_degree",
        )
        self._set_exact_spin_value(
            self.hue_sigma_spin,
            config.hue_sigma_degree,
            "hue_sigma_degree",
        )
        self._set_exact_spin_value(
            self.preferred_bpm_spin,
            config.preferred_blink_bpm,
            "preferred_blink_bpm",
        )
        self._set_exact_spin_value(
            self.bpm_sigma_spin,
            config.blink_sigma_bpm,
            "blink_sigma_bpm",
        )
        self._set_exact_spin_value(
            self.respiratory_gain_spin,
            config.maximum_respiratory_amplitude_gain_ms,
            "maximum_respiratory_amplitude_gain_ms",
        )
        self._set_exact_spin_value(
            self.mean_rri_gain_spin,
            config.maximum_mean_rri_increase_ms,
            "maximum_mean_rri_increase_ms",
        )
        self._set_exact_spin_value(
            self.onset_tau_spin,
            config.response_onset_time_constant_seconds,
            "response_onset_time_constant_seconds",
        )
        self._set_exact_spin_value(
            self.recovery_tau_spin,
            config.response_recovery_time_constant_seconds,
            "response_recovery_time_constant_seconds",
        )
        duration_seconds = us_to_seconds(config.simulation_end_time_us)
        self.light_response_chart.set_duration_seconds(duration_seconds)
        self.physiology_chart.set_duration_seconds(duration_seconds)
        self.garden_evaluation_chart.set_duration_seconds(duration_seconds)

    def selected_config(self) -> LightResponseConfig:
        return replace(
            self._config,
            preferred_hue_degree=self.preferred_hue_spin.value(),
            hue_sigma_degree=self.hue_sigma_spin.value(),
            preferred_blink_bpm=self.preferred_bpm_spin.value(),
            blink_sigma_bpm=self.bpm_sigma_spin.value(),
            maximum_respiratory_amplitude_gain_ms=self.respiratory_gain_spin.value(),
            maximum_mean_rri_increase_ms=self.mean_rri_gain_spin.value(),
            response_onset_time_constant_seconds=self.onset_tau_spin.value(),
            response_recovery_time_constant_seconds=self.recovery_tau_spin.value(),
        )

    def update_diagnostics(self, engine_snapshot: EngineSnapshot) -> None:
        self._engine_state = engine_snapshot.state
        component_snapshot = self._component.snapshot()
        receipts = tuple(self._component.light_receipt_records())
        segments = tuple(self._component.response_segments())
        heartbeats = tuple(self._component.responsive_heartbeat_records())
        latest_observed_time_us = max(
            component_snapshot.current_heartbeat_time_us or 0,
            receipts[-1].event_time_us if receipts else 0,
        )
        if (
            engine_snapshot.state is ClockState.STOPPED
            and engine_snapshot.current_time_us == 0
            and not receipts
            and not heartbeats
        ):
            samples = ()
        elif engine_snapshot.state is ClockState.COMPLETED:
            samples = tuple(self._component.response_samples())
        else:
            samples = tuple(
                self._component.response_samples_through(latest_observed_time_us)
            )
        evaluations = tuple(self._garden_input_component.evaluation_records())

        self._update_state_labels(component_snapshot)
        revision = (
            len(receipts),
            len(segments),
            len(heartbeats),
            len(evaluations),
            len(samples),
        )
        if revision != self._record_revision:
            previous_receipts = self.receipt_model.rowCount()
            previous_heartbeats = self.heartbeat_model.rowCount()
            self.receipt_model.set_records(receipts)
            self.heartbeat_model.set_records(heartbeats)
            self.light_response_chart.set_records(
                samples,
                receipts,
                segments,
                engine_snapshot.current_time_us,
            )
            self.physiology_chart.set_records(
                heartbeats, engine_snapshot.current_time_us
            )
            self.garden_evaluation_chart.set_records(
                evaluations, engine_snapshot.current_time_us
            )
            if self.receipt_model.rowCount() > previous_receipts:
                self.receipt_table.scrollToBottom()
            if self.heartbeat_model.rowCount() > previous_heartbeats:
                self.heartbeat_table.scrollToBottom()
            self._record_revision = revision
        else:
            self.light_response_chart.set_current_time_us(
                engine_snapshot.current_time_us
            )
            self.physiology_chart.set_current_time_us(engine_snapshot.current_time_us)
            self.garden_evaluation_chart.set_current_time_us(
                engine_snapshot.current_time_us
            )
        self.set_settings_editable(engine_snapshot.state is ClockState.STOPPED)
        self._set_export_enabled(
            receipts,
            segments,
            heartbeats,
            samples,
            completed=engine_snapshot.state is ClockState.COMPLETED,
        )

    def _update_state_labels(self, snapshot: Any) -> None:
        values = {
            "light_active": "active" if snapshot.current_light_active else "inactive",
            "hue": _number(snapshot.current_render_hue_degree, 3, "°"),
            "bpm": _number(snapshot.current_blink_bpm, 3, " BPM"),
            "hue_match": _number(snapshot.current_hue_match, 6),
            "bpm_match": _number(snapshot.current_bpm_match, 6),
            "preference_match": _number(snapshot.current_preference_match, 6),
            "response_target": _number(snapshot.current_response_target, 6),
            "response_level": _number(snapshot.current_response_level, 6),
            "base_respiratory": _number(
                snapshot.base_respiratory_amplitude_ms, 3, " ms"
            ),
            "effective_respiratory": _number(
                snapshot.effective_respiratory_amplitude_ms, 3, " ms"
            ),
            "base_mean_rri": _number(snapshot.base_mean_rri_ms, 3, " ms"),
            "effective_mean_rri": _number(
                snapshot.effective_mean_rri_ms, 3, " ms"
            ),
            "latest_rri": _number(snapshot.latest_true_rri_ms, 3, " ms"),
            "latest_hr": _number(
                snapshot.latest_instantaneous_hr_bpm, 2, " bpm"
            ),
            "heartbeat_count": f"{snapshot.heartbeat_count} 拍",
        }
        for key, text in values.items():
            self.state_labels[key].setText(text)

    def reset_views(self) -> None:
        self._engine_state = ClockState.STOPPED
        self._record_revision = (-1, -1, -1, -1, -1)
        self.receipt_model.clear()
        self.heartbeat_model.clear()
        self.light_response_chart.clear()
        self.physiology_chart.clear()
        self.garden_evaluation_chart.clear()
        for label in self.state_labels.values():
            label.setText("—")
        self.state_labels["light_active"].setText("inactive")
        self.state_labels["response_target"].setText("0.000000")
        self.state_labels["response_level"].setText("0.000000")
        self.state_labels["heartbeat_count"].setText("0 拍")
        self.set_settings_editable(True)
        self._set_export_enabled((), (), (), (), completed=False)
        self.diagnostics_scroll.verticalScrollBar().setValue(0)

    def set_settings_editable(self, editable: bool) -> None:
        self.settings_frame.setEnabled(editable)

    def _preset_activated(self, _index: int) -> None:
        if self._engine_state is not ClockState.STOPPED:
            return
        name = str(self.preset_combo.currentData())
        if name == "custom":
            return
        try:
            config = light_response_config_for_preset(name)
        except (TypeError, ValueError) as exc:
            QMessageBox.warning(self, "presetを適用できません", str(exc))
            return
        self._preset_name = name
        self.set_config(config, preset_name=name)
        self.config_applied.emit(config)

    def _apply_clicked(self) -> None:
        if self._engine_state is not ClockState.STOPPED:
            return
        try:
            config = self.selected_config()
        except (TypeError, ValueError) as exc:
            QMessageBox.warning(self, "設定を適用できません", str(exc))
            return
        self.set_config(config, preset_name="custom")
        self.config_applied.emit(config)

    def _set_export_enabled(
        self,
        receipts: tuple[Any, ...],
        segments: tuple[Any, ...],
        heartbeats: tuple[Any, ...],
        samples: tuple[Any, ...],
        *,
        completed: bool,
    ) -> None:
        self.export_receipt_button.setEnabled(bool(receipts))
        self.export_segment_button.setEnabled(completed and bool(segments))
        self.export_heartbeat_button.setEnabled(bool(heartbeats))
        self.export_sample_button.setEnabled(completed and bool(samples))

    def _export_receipts(self) -> None:
        self._export(
            "light receipt診断CSVを保存",
            LIGHT_STIMULUS_RECEIPTS_CSV_FILENAME,
            export_light_stimulus_receipts_csv,
            self._component.light_receipt_records(),
        )

    def _export_segments(self) -> None:
        self._export(
            "light response segment診断CSVを保存",
            LIGHT_RESPONSE_SEGMENTS_CSV_FILENAME,
            export_light_response_segments_csv,
            self._component.response_segments(),
        )

    def _export_heartbeats(self) -> None:
        self._export(
            "light responsive heartbeat診断CSVを保存",
            LIGHT_RESPONSIVE_HEARTBEATS_CSV_FILENAME,
            export_light_responsive_heartbeats_csv,
            self._component.responsive_heartbeat_records(),
        )

    def _export_samples(self) -> None:
        self._export(
            "100ms light response診断CSVを保存",
            LIGHT_RESPONSE_SAMPLES_CSV_FILENAME,
            export_light_response_samples_csv,
            self._component.response_samples(),
        )

    def _export(
        self,
        title: str,
        suggested_name: str,
        exporter: Any,
        records: tuple[Any, ...],
    ) -> None:
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self, title, suggested_name, "CSV (*.csv)"
        )
        if destination:
            exporter(destination, records)

    @staticmethod
    def _spin(
        minimum: float,
        maximum: float,
        decimals: int,
        suffix: str,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setSingleStep(0.1)
        return spin

    @staticmethod
    def _set_exact_spin_value(
        spin: QDoubleSpinBox,
        value: float,
        field_name: str,
    ) -> None:
        spin.setValue(value)
        if spin.value() != value:
            raise ValueError(
                f"{field_name} cannot be represented by the editable GUI; "
                "the value was not silently clipped"
            )

    @staticmethod
    def _add_setting(
        form: QFormLayout,
        label_text: str,
        control: QWidget,
        explanation: str,
    ) -> None:
        label = QLabel(label_text)
        detail = QWidget()
        layout = QVBoxLayout(detail)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(control)
        note = QLabel(explanation)
        note.setObjectName("lightResponseSettingExplanation")
        note.setWordWrap(True)
        layout.addWidget(note)
        form.addRow(label, detail)


LightResponsiveVirtualUserPanel = LightResponseUserPanel


def _number(value: float | None, decimals: int, suffix: str = "") -> str:
    return "—" if value is None else f"{value:.{decimals}f}{suffix}"
