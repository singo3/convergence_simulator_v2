"""Stage 2 configuration and developer-diagnostic panel."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.heartbeat_table_model import HeartbeatTableModel
from symbiotic_sim_v2.gui.virtual_user_chart import VirtualUserChart
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.engine import EngineSnapshot
from symbiotic_sim_v2.virtual_user.component import VirtualUserComponent
from symbiotic_sim_v2.virtual_user.config import MAX_ROOT_SEED, VirtualUserConfig
from symbiotic_sim_v2.virtual_user.diagnostics import (
    DIAGNOSTIC_CSV_FILENAME,
    export_heartbeat_diagnostics_csv,
    full_run_rmssd_ms,
    rolling_rmssd_ms,
)

DEVELOPER_DIAGNOSTIC_NOTICE = (
    "このRRIとRMSSDは仮想ユーザー内部の真値から計算する開発用診断です。"
    "仮想Polar H10およびGarden入力層はまだ実装されていません。"
)
STAGE_2_NOTICE = (
    "Stage 2では外部刺激なしの仮想ユーザーを検証しています。正式出力は心拍イベントです。"
    "表示しているRRI・RMSSDは開発用診断であり、H10やGardenの出力ではありません。"
)


class VirtualUserPanel(QWidget):
    """Edit pre-run assumptions and visualize immutable component diagnostics."""

    config_applied = Signal(object)

    def __init__(
        self,
        config: VirtualUserConfig,
        component: VirtualUserComponent,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._component = component
        self._build_ui()
        self.set_config(config)
        self.reset_views()

    @property
    def config(self) -> VirtualUserConfig:
        """Return the configuration represented by the current scenario."""

        return self._config

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        notice = QLabel(STAGE_2_NOTICE, self)
        notice.setObjectName("stageDescription")
        notice.setWordWrap(True)
        root.addWidget(notice)

        stimulus_notice = QLabel(
            "このStageでは光や外部刺激を入力しません。"
            "仮想ユーザー自身の内部変動だけを生成します。",
            self,
        )
        stimulus_notice.setObjectName("stimulusNotice")
        stimulus_notice.setWordWrap(True)
        root.addWidget(stimulus_notice)

        splitter = QSplitter(self)
        self.settings_scroll = QScrollArea(splitter)
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setMinimumWidth(330)
        self.settings_scroll.setMaximumWidth(430)
        self.settings_group = QWidget()
        settings_layout = QVBoxLayout(self.settings_group)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(8)

        heading = QLabel("仮想ユーザー設定", self.settings_group)
        heading.setObjectName("sectionTitle")
        settings_layout.addWidget(heading)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 3600)
        self.duration_spin.setSuffix(" 秒")
        self._add_setting(form, "シミュレーション時間", self.duration_spin, "仮想時間上の実行時間")

        self.mean_hr_spin = self._double_spin(30.0, 200.0, 1, " bpm")
        self._add_setting(
            form,
            "平均心拍数",
            self.mean_hr_spin,
            "外部刺激がないときの中心的な心拍数",
        )
        self.respiratory_rate_spin = self._double_spin(3.0, 40.0, 1, " 回/分")
        self._add_setting(
            form,
            "呼吸数",
            self.respiratory_rate_spin,
            "呼吸性変動を作る周期",
        )
        self.respiratory_amplitude_spin = self._double_spin(0.0, 200.0, 1, " ms")
        self._add_setting(
            form,
            "呼吸性変動幅",
            self.respiratory_amplitude_spin,
            "呼吸周期によってRRIが上下する幅",
        )
        self.slow_frequency_spin = self._double_spin(0.01, 0.20, 3, " Hz", 0.01)
        self._add_setting(
            form,
            "ゆっくりした変動の周波数",
            self.slow_frequency_spin,
            "低周波の周期的変動",
        )
        self.slow_amplitude_spin = self._double_spin(0.0, 100.0, 1, " ms")
        self._add_setting(
            form,
            "ゆっくりした変動幅",
            self.slow_amplitude_spin,
            "低周波成分がRRIを上下する幅",
        )
        self.correlated_sd_spin = self._double_spin(0.0, 100.0, 1, " ms")
        self._add_setting(
            form,
            "連続的な自然変動幅",
            self.correlated_sd_spin,
            "前の拍から連続する、ゆっくりした不規則変動",
        )
        self.persistence_spin = self._double_spin(0.0, 0.99, 2, "", 0.05)
        self._add_setting(
            form,
            "連続性",
            self.persistence_spin,
            "1に近いほど前の内部状態が残ります",
        )
        self.jitter_sd_spin = self._double_spin(0.0, 50.0, 1, " ms")
        self._add_setting(
            form,
            "拍ごとの微小変動幅",
            self.jitter_sd_spin,
            "各拍に独立して加わる小さな変動",
        )
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, MAX_ROOT_SEED)
        self._add_setting(
            form,
            "再現用seed",
            self.seed_spin,
            "同じ値なら同じ内部変動を再現します。"
            "外部刺激や好みの山を表す値ではありません。",
        )
        settings_layout.addLayout(form)

        detailed_group = QGroupBox("詳細設定（RRI範囲）", self.settings_group)
        detailed_form = QFormLayout(detailed_group)
        self.min_rri_spin = self._double_spin(250.0, 2999.0, 1, " ms")
        self.max_rri_spin = self._double_spin(251.0, 3000.0, 1, " ms")
        detailed_form.addRow("最小RRI", self.min_rri_spin)
        detailed_form.addRow("最大RRI", self.max_rri_spin)
        settings_layout.addWidget(detailed_group)

        buttons = QHBoxLayout()
        self.apply_settings_button = QPushButton("設定を適用")
        self.apply_settings_button.setObjectName("applySettingsButton")
        self.restore_defaults_button = QPushButton("Stage 2標準値へ戻す")
        self.restore_defaults_button.setObjectName("restoreDefaultsButton")
        buttons.addWidget(self.apply_settings_button)
        buttons.addWidget(self.restore_defaults_button)
        settings_layout.addLayout(buttons)
        self.export_csv_button = QPushButton("診断CSVを保存")
        self.export_csv_button.setObjectName("exportCsvButton")
        settings_layout.addWidget(self.export_csv_button)
        settings_layout.addStretch(1)
        self.settings_scroll.setWidget(self.settings_group)
        splitter.addWidget(self.settings_scroll)

        diagnostics = QWidget(splitter)
        diagnostics_layout = QVBoxLayout(diagnostics)
        diagnostics_layout.setContentsMargins(4, 0, 0, 0)
        diagnostics_layout.setSpacing(7)
        state_frame = QFrame(diagnostics)
        state_frame.setObjectName("statusFrame")
        state_grid = QGridLayout(state_frame)
        self.heartbeat_count_label = self._state_card(state_grid, 0, "心拍数", "0 拍")
        self.latest_rri_label = self._state_card(state_grid, 1, "最新の真のRRI", "—")
        self.latest_hr_label = self._state_card(state_grid, 2, "最新の瞬時心拍数", "—")
        self.rolling_rmssd_label = self._state_card(
            state_grid, 3, "rolling RMSSD 30秒", "—"
        )
        self.full_rmssd_label = self._state_card(state_grid, 4, "全期間RMSSD", "—")
        self.clamped_count_label = self._state_card(state_grid, 5, "clampされた拍数", "0")
        diagnostics_layout.addWidget(state_frame)

        diagnostic_notice = QLabel(DEVELOPER_DIAGNOSTIC_NOTICE, diagnostics)
        diagnostic_notice.setObjectName("diagnosticNotice")
        diagnostic_notice.setWordWrap(True)
        diagnostics_layout.addWidget(diagnostic_notice)

        chart_table_splitter = QSplitter(Qt.Orientation.Vertical, diagnostics)
        self.chart = VirtualUserChart(self._config, chart_table_splitter)
        self.chart.setMinimumHeight(350)
        chart_table_splitter.addWidget(self.chart)
        table_group = QGroupBox("最近の心拍（内部真値・診断用）", chart_table_splitter)
        table_layout = QVBoxLayout(table_group)
        self.heartbeat_model = HeartbeatTableModel(self)
        self.heartbeat_table = QTableView(table_group)
        self.heartbeat_table.setObjectName("heartbeatTable")
        self.heartbeat_table.setModel(self.heartbeat_model)
        self.heartbeat_table.setAlternatingRowColors(True)
        self.heartbeat_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.heartbeat_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self.heartbeat_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table_layout.addWidget(self.heartbeat_table)
        chart_table_splitter.addWidget(table_group)
        chart_table_splitter.setSizes([470, 210])
        diagnostics_layout.addWidget(chart_table_splitter, stretch=1)
        splitter.addWidget(diagnostics)
        splitter.setSizes([360, 900])
        root.addWidget(splitter, stretch=1)

        self.apply_settings_button.clicked.connect(self._apply_clicked)
        self.restore_defaults_button.clicked.connect(self._restore_defaults_clicked)
        self.export_csv_button.clicked.connect(self._export_csv_clicked)

    def set_component(self, component: VirtualUserComponent) -> None:
        """Switch the immutable diagnostic read source after config reconstruction."""

        self._component = component

    def set_config(self, config: VirtualUserConfig) -> None:
        """Populate controls from one validated configuration."""

        self._config = config
        self.duration_spin.setValue(config.duration_seconds)
        self.mean_hr_spin.setValue(config.mean_heart_rate_bpm)
        self.respiratory_rate_spin.setValue(config.respiratory_rate_bpm)
        self.respiratory_amplitude_spin.setValue(config.respiratory_amplitude_ms)
        self.slow_frequency_spin.setValue(config.slow_wave_frequency_hz)
        self.slow_amplitude_spin.setValue(config.slow_wave_amplitude_ms)
        self.correlated_sd_spin.setValue(config.correlated_variability_sd_ms)
        self.persistence_spin.setValue(config.correlated_variability_persistence)
        self.jitter_sd_spin.setValue(config.beat_jitter_sd_ms)
        self.seed_spin.setValue(config.root_seed)
        self.min_rri_spin.setValue(config.min_rri_ms)
        self.max_rri_spin.setValue(config.max_rri_ms)
        self.chart.set_config(config)

    def selected_config(self) -> VirtualUserConfig:
        """Build and validate a configuration from currently displayed controls."""

        return VirtualUserConfig(
            user_id=self._config.user_id,
            duration_seconds=self.duration_spin.value(),
            mean_heart_rate_bpm=self.mean_hr_spin.value(),
            respiratory_rate_bpm=self.respiratory_rate_spin.value(),
            respiratory_amplitude_ms=self.respiratory_amplitude_spin.value(),
            slow_wave_frequency_hz=self.slow_frequency_spin.value(),
            slow_wave_amplitude_ms=self.slow_amplitude_spin.value(),
            correlated_variability_sd_ms=self.correlated_sd_spin.value(),
            correlated_variability_persistence=self.persistence_spin.value(),
            beat_jitter_sd_ms=self.jitter_sd_spin.value(),
            min_rri_ms=self.min_rri_spin.value(),
            max_rri_ms=self.max_rri_spin.value(),
            root_seed=self.seed_spin.value(),
        )

    def update_diagnostics(self, engine_snapshot: EngineSnapshot) -> None:
        """Read frozen component state/records and update existing GUI items."""

        component_snapshot = self._component.snapshot()
        records = self._component.heartbeat_records()
        rolling = rolling_rmssd_ms(records, engine_snapshot.current_time_us)
        full = full_run_rmssd_ms(records)
        self.heartbeat_count_label.setText(f"{component_snapshot.heartbeat_count} 拍")
        self.latest_rri_label.setText(self._format_ms(component_snapshot.latest_true_rri_ms))
        self.latest_hr_label.setText(
            "—"
            if component_snapshot.latest_instantaneous_hr_bpm is None
            else f"{component_snapshot.latest_instantaneous_hr_bpm:.2f} bpm"
        )
        self.rolling_rmssd_label.setText(self._format_ms(rolling))
        self.full_rmssd_label.setText(self._format_ms(full))
        self.clamped_count_label.setText(str(component_snapshot.clamped_beat_count))
        previous_rows = self.heartbeat_model.rowCount()
        self.heartbeat_model.set_records(records)
        self.chart.set_records(records, engine_snapshot.current_time_us)
        if self.heartbeat_model.rowCount() > previous_rows:
            self.heartbeat_table.scrollToBottom()
        self.set_settings_editable(engine_snapshot.state is ClockState.STOPPED)
        self.export_csv_button.setEnabled(bool(records))

    def reset_views(self) -> None:
        """Clear chart/table/card state while retaining the current settings."""

        self.heartbeat_model.clear()
        self.chart.clear()
        self.heartbeat_count_label.setText("0 拍")
        self.latest_rri_label.setText("—")
        self.latest_hr_label.setText("—")
        self.rolling_rmssd_label.setText("—")
        self.full_rmssd_label.setText("—")
        self.clamped_count_label.setText("0")
        self.export_csv_button.setEnabled(False)

    def set_settings_editable(self, editable: bool) -> None:
        """Allow configuration changes only in a reset/stopped scenario."""

        self.settings_group.setEnabled(editable)

    def _apply_clicked(self) -> None:
        try:
            config = self.selected_config()
        except (TypeError, ValueError) as exc:
            QMessageBox.warning(self, "設定を適用できません", str(exc))
            return
        self.config_applied.emit(config)

    def _restore_defaults_clicked(self) -> None:
        defaults = VirtualUserConfig()
        self.set_config(defaults)
        self.config_applied.emit(defaults)

    def _export_csv_clicked(self) -> None:
        records = self._component.heartbeat_records()
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "仮想ユーザーの真値診断CSVを保存",
            DIAGNOSTIC_CSV_FILENAME,
            "CSV (*.csv)",
        )
        if destination:
            export_heartbeat_diagnostics_csv(destination, records)

    @staticmethod
    def _double_spin(
        minimum: float,
        maximum: float,
        decimals: int,
        suffix: str,
        step: float = 1.0,
    ) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(step)
        widget.setSuffix(suffix)
        return widget

    @staticmethod
    def _add_setting(
        form: QFormLayout,
        label: str,
        widget: QWidget,
        explanation: str,
    ) -> None:
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 1, 0, 4)
        layout.setSpacing(1)
        layout.addWidget(widget)
        detail = QLabel(explanation)
        detail.setObjectName("settingExplanation")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        form.addRow(label, field)

    @staticmethod
    def _state_card(layout: QGridLayout, column: int, caption: str, value: str) -> QLabel:
        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(7, 3, 7, 3)
        caption_label = QLabel(caption)
        caption_label.setObjectName("statusCaption")
        value_label = QLabel(value)
        value_label.setObjectName("statusValue")
        card_layout.addWidget(caption_label)
        card_layout.addWidget(value_label)
        layout.addWidget(card, 0, column)
        return value_label

    @staticmethod
    def _format_ms(value: float | None) -> str:
        return "—" if value is None else f"{value:.3f} ms"
