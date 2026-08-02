"""Stage 4 Garden input-layer observation panel."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
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

from symbiotic_sim_v2.garden.input_layer.component import GardenInputComponent
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.diagnostics import (
    GARDEN_EVALUATION_CSV_FILENAME,
    GARDEN_RRI_CSV_FILENAME,
    GARDEN_SIGNAL_CSV_FILENAME,
    export_garden_evaluations_csv,
    export_garden_rri_csv,
    export_garden_signals_csv,
)
from symbiotic_sim_v2.garden.input_layer.records import GardenInputSnapshot
from symbiotic_sim_v2.gui.garden_evaluation_table_model import (
    GardenEvaluationTableModel,
)
from symbiotic_sim_v2.gui.garden_input_chart import GardenInputChart
from symbiotic_sim_v2.gui.garden_input_timeline import GardenInputTimeline
from symbiotic_sim_v2.gui.garden_rri_table_model import GardenRriTableModel
from symbiotic_sim_v2.simulation.engine import EngineSnapshot
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

GARDEN_STAGE_DESCRIPTION = (
    "Garden入力層は、仮想Polar H10のRriMeasurementEventだけを受け取り、"
    "artifact判定、評価窓、RMSSD、N、Sを生成します。"
)
GARDEN_RESPONSIBILITY_NOTICE = (
    "Garden入力層はNd、W、デジタル生命、光を計算しません。"
)
GARDEN_ASSUMPTION_NOTICE = (
    "NはRMSSDだけから固定式で計算し、baselineはNの式に入りません。"
    "NdとWはまだ未実装です。"
)
GARDEN_POLICY_NOTICE = (
    "RRI window membershipはmeasurement end timeを使うStage 4仮定です。"
    "baseline reject後の方針はStage 4実装上の最小安全方針です。"
)
GARDEN_TIMELINE_MIN_HEIGHT = 200
GARDEN_TABLE_TABS_MIN_HEIGHT = 300
GARDEN_CHART_TABLE_SPLITTER_MIN_HEIGHT = 1_075
GARDEN_CHART_TABLE_INITIAL_SIZES = (740, 330)


class GardenInputPanel(QWidget):
    """Read immutable Garden snapshots and records into diagnostic widgets."""

    def __init__(
        self,
        config: GardenInputConfig,
        component: GardenInputComponent,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._component = component
        self._build_ui()
        self.set_config(config)
        self.reset_views()

    @property
    def config(self) -> GardenInputConfig:
        return self._config

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)

        description = QLabel(GARDEN_STAGE_DESCRIPTION, self)
        description.setObjectName("gardenDescription")
        description.setWordWrap(True)
        root.addWidget(description)
        responsibility = QLabel(GARDEN_RESPONSIBILITY_NOTICE, self)
        responsibility.setObjectName("gardenResponsibilityNotice")
        responsibility.setWordWrap(True)
        root.addWidget(responsibility)

        flow_frame = QFrame(self)
        flow_frame.setObjectName("gardenSignalFlowFrame")
        flow_layout = QHBoxLayout(flow_frame)
        flow_layout.setContentsMargins(9, 5, 9, 5)
        flow_layout.setSpacing(6)
        for index, node_text in enumerate(
            (
                "仮想ユーザー",
                "HeartbeatEvent",
                "Polar H10",
                "RriMeasurementEvent",
                "Garden入力層",
                "N, S",
                "将来のデジタル生命",
            )
        ):
            if index:
                arrow = QLabel("→", flow_frame)
                arrow.setObjectName("gardenFlowArrow")
                flow_layout.addWidget(arrow)
            node = QLabel(node_text, flow_frame)
            node.setObjectName("gardenFlowNode")
            node.setAlignment(Qt.AlignmentFlag.AlignCenter)
            flow_layout.addWidget(node, stretch=1)
        root.addWidget(flow_frame)

        self.body_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.body_splitter.setObjectName("gardenBodySplitter")
        self.fixed_scroll = QScrollArea(self.body_splitter)
        self.fixed_scroll.setWidgetResizable(True)
        self.fixed_scroll.setMinimumWidth(365)
        self.fixed_scroll.setMaximumWidth(485)
        fixed_container = QWidget(self.fixed_scroll)
        fixed_layout = QVBoxLayout(fixed_container)
        fixed_layout.setContentsMargins(6, 6, 6, 6)
        fixed_layout.setSpacing(7)

        fixed_group = QGroupBox("v2.0参照値（読み取り専用）", fixed_container)
        fixed_form = QFormLayout(fixed_group)
        fixed_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.model_version_label = self._fixed_value(fixed_form, "model version")
        self.manifest_version_label = self._fixed_value(fixed_form, "manifest version")
        self.rri_range_label = self._fixed_value(fixed_form, "RRI範囲")
        self.median_history_start_label = self._fixed_value(fixed_form, "中央値履歴開始")
        self.median_history_max_label = self._fixed_value(fixed_form, "中央値履歴最大")
        self.median_deviation_label = self._fixed_value(fixed_form, "中央値偏差")
        self.low_confidence_label = self._fixed_value(fixed_form, "low confidence")
        self.reject_label = self._fixed_value(fixed_form, "reject")
        self.minimum_valid_label = self._fixed_value(fixed_form, "最小有効RRI数")
        self.rmssd_mapping_label = self._fixed_value(fixed_form, "RMSSD→N")
        self.baseline_timing_label = self._fixed_value(fixed_form, "baseline")
        self.bundle_timing_label = self._fixed_value(fixed_form, "bundle")
        self.bundle_count_label = self._fixed_value(fixed_form, "bundle数")
        self.signal_interval_label = self._fixed_value(fixed_form, "session signal")
        fixed_layout.addWidget(fixed_group)

        assumption = QLabel(GARDEN_ASSUMPTION_NOTICE, fixed_container)
        assumption.setObjectName("gardenAssumptionNotice")
        assumption.setWordWrap(True)
        fixed_layout.addWidget(assumption)
        policy = QLabel(GARDEN_POLICY_NOTICE, fixed_container)
        policy.setObjectName("gardenPolicyNotice")
        policy.setWordWrap(True)
        fixed_layout.addWidget(policy)

        export_group = QGroupBox("診断CSV export", fixed_container)
        export_layout = QVBoxLayout(export_group)
        self.export_rri_button = QPushButton("RRI分類CSVを保存", export_group)
        self.export_rri_button.setObjectName("exportGardenRriCsvButton")
        self.export_evaluation_button = QPushButton("評価結果CSVを保存", export_group)
        self.export_evaluation_button.setObjectName("exportGardenEvaluationCsvButton")
        self.export_signal_button = QPushButton("N/S信号CSVを保存", export_group)
        self.export_signal_button.setObjectName("exportGardenSignalCsvButton")
        export_layout.addWidget(self.export_rri_button)
        export_layout.addWidget(self.export_evaluation_button)
        export_layout.addWidget(self.export_signal_button)
        fixed_layout.addWidget(export_group)
        fixed_layout.addStretch(1)
        self.fixed_scroll.setWidget(fixed_container)
        self.body_splitter.addWidget(self.fixed_scroll)

        self.diagnostics_scroll = QScrollArea(self.body_splitter)
        self.diagnostics_scroll.setObjectName("gardenDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("gardenDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        diagnostics_layout = QVBoxLayout(self.diagnostics_content)
        diagnostics_layout.setContentsMargins(4, 0, 0, 0)
        diagnostics_layout.setSpacing(6)
        diagnostics_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        state_frame = QFrame(self.diagnostics_content)
        state_frame.setObjectName("statusFrame")
        state_grid = QGridLayout(state_frame)
        state_grid.setContentsMargins(7, 4, 7, 4)
        self.phase_label = self._state_card(state_grid, 0, 0, "現在phase", "baseline_discard")
        self.s_label = self._state_card(state_grid, 0, 1, "S", "0")
        self.bundle_label = self._state_card(state_grid, 0, 2, "bundle", "—")
        self.window_role_label = self._state_card(state_grid, 0, 3, "window role", "discard")
        self.received_rri_label = self._state_card(state_grid, 1, 0, "受信RRI数", "0 件")
        self.valid_rri_label = self._state_card(state_grid, 1, 1, "有効RRI数", "0 件")
        self.artifact_label = self._state_card(state_grid, 1, 2, "artifact数", "0 件")
        self.baseline_n_label = self._state_card(state_grid, 1, 3, "baseline N", "—")
        self.current_n_label = self._state_card(state_grid, 2, 0, "current N", "—")
        self.latest_rmssd_label = self._state_card(state_grid, 2, 1, "最新RMSSD", "—")
        self.evaluation_quality_label = self._state_card(state_grid, 2, 2, "最新評価品質", "—")
        self.revision_label = self._state_card(
            state_grid,
            2,
            3,
            "valid evaluation revision",
            "0",
        )
        diagnostics_layout.addWidget(state_frame)

        timeline_group = QGroupBox(
            "240秒 phase / S タイムライン",
            self.diagnostics_content,
        )
        timeline_layout = QVBoxLayout(timeline_group)
        self.timeline = GardenInputTimeline(self._config, timeline_group)
        self.timeline.setMinimumHeight(GARDEN_TIMELINE_MIN_HEIGHT)
        timeline_layout.addWidget(self.timeline)
        diagnostics_layout.addWidget(timeline_group)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("gardenChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(
            GARDEN_CHART_TABLE_SPLITTER_MIN_HEIGHT
        )
        self.chart = GardenInputChart(self._config, self.chart_table_splitter)
        self.chart_table_splitter.addWidget(self.chart)

        self.table_tabs = QTabWidget(self.chart_table_splitter)
        self.table_tabs.setObjectName("gardenTableTabs")
        self.table_tabs.setMinimumHeight(GARDEN_TABLE_TABS_MIN_HEIGHT)
        rri_table_page = QWidget(self.table_tabs)
        rri_table_layout = QVBoxLayout(rri_table_page)
        rri_table_layout.setContentsMargins(4, 4, 4, 4)
        self.rri_model = GardenRriTableModel(self)
        self.rri_table = QTableView(rri_table_page)
        self.rri_table.setObjectName("gardenRriTable")
        self._configure_table(self.rri_table, self.rri_model)
        rri_table_layout.addWidget(self.rri_table)
        self.table_tabs.addTab(rri_table_page, "RRI判定")

        evaluation_page = QWidget(self.table_tabs)
        evaluation_layout = QVBoxLayout(evaluation_page)
        evaluation_layout.setContentsMargins(4, 4, 4, 4)
        self.evaluation_model = GardenEvaluationTableModel(self)
        self.evaluation_table = QTableView(evaluation_page)
        self.evaluation_table.setObjectName("gardenEvaluationTable")
        self._configure_table(self.evaluation_table, self.evaluation_model)
        evaluation_layout.addWidget(self.evaluation_table)
        self.table_tabs.addTab(evaluation_page, "評価結果")
        self.chart_table_splitter.addWidget(self.table_tabs)
        self.chart_table_splitter.setCollapsible(0, False)
        self.chart_table_splitter.setCollapsible(1, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 0)
        self.chart_table_splitter.setSizes(list(GARDEN_CHART_TABLE_INITIAL_SIZES))
        diagnostics_layout.addWidget(self.chart_table_splitter)
        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self._diagnostic_scroll_wheel_targets = (
            self.timeline.viewport(),
            self.chart.rri_graphics.viewport(),
            self.chart.evaluation_graphics.viewport(),
            self.chart.signal_graphics.viewport(),
        )
        for target in self._diagnostic_scroll_wheel_targets:
            target.installEventFilter(self)
        self.body_splitter.addWidget(self.diagnostics_scroll)
        self.body_splitter.setSizes([480, 1025])
        root.addWidget(self.body_splitter, stretch=1)

        # Concise aliases support terminology used by the specification and smoke tests.
        self.current_phase_label = self.phase_label
        self.current_s_label = self.s_label
        self.received_rri_count_label = self.received_rri_label
        self.valid_rri_count_label = self.valid_rri_label
        self.artifact_count_label = self.artifact_label
        self.artifact_rri_count_label = self.artifact_label
        self.latest_evaluation_quality_label = self.evaluation_quality_label
        self.valid_evaluation_revision_label = self.revision_label
        self.rri_table_model = self.rri_model
        self.evaluation_table_model = self.evaluation_model
        self.session_timeline = self.timeline
        self.export_rri_csv_button = self.export_rri_button
        self.export_evaluation_csv_button = self.export_evaluation_button
        self.export_signal_csv_button = self.export_signal_button

        self.export_rri_button.clicked.connect(self._export_rri_clicked)
        self.export_evaluation_button.clicked.connect(self._export_evaluation_clicked)
        self.export_signal_button.clicked.connect(self._export_signal_clicked)
        self.setStyleSheet(
            """
                QLabel#gardenDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5; border-radius: 6px;
                    color: #234A75; padding: 6px 10px;
                }
                QLabel#gardenResponsibilityNotice, QLabel#gardenAssumptionNotice,
                QLabel#gardenPolicyNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A; border-radius: 6px;
                    color: #6B4B16; padding: 6px 10px;
                }
                QFrame#gardenSignalFlowFrame {
                    background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 7px;
                }
                QLabel#gardenFlowNode {
                    background: white; border: 1px solid #6EE7B7; border-radius: 5px;
                    color: #065F46; font-weight: 700; padding: 5px 6px;
                }
                QLabel#gardenFlowArrow { color: #059669; font-size: 18px; font-weight: 700; }
                QLabel#fixedConditionValue { color: #1E3A5F; font-weight: 600; }
            """
        )

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        """Route vertical plot-wheel gestures to the diagnostics scroll area."""

        if (
            watched in self._diagnostic_scroll_wheel_targets
            and event.type() is QEvent.Type.Wheel
        ):
            pixel_delta = event.pixelDelta().y()
            angle_delta = event.angleDelta().y()
            scroll_delta = pixel_delta
            if scroll_delta == 0 and angle_delta:
                steps = angle_delta / 120.0
                scroll_delta = round(
                    steps
                    * 3
                    * self.diagnostics_scroll.verticalScrollBar().singleStep()
                )
            if scroll_delta:
                scroll_bar = self.diagnostics_scroll.verticalScrollBar()
                scroll_bar.setValue(scroll_bar.value() - scroll_delta)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _configure_table(table: QTableView, model) -> None:
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

    def set_component(self, component: GardenInputComponent) -> None:
        """Switch the immutable read source after factory reconstruction."""

        self._component = component

    def set_config(self, config: GardenInputConfig) -> None:
        """Populate all read-only reference values from the validated config."""

        self._config = config
        self.model_version_label.setText(config.model_version)
        self.model_version_label.setToolTip(config.model_version)
        self.manifest_version_label.setText(config.garden_manifest_version)
        self.manifest_version_label.setToolTip(config.garden_manifest_version)
        self.rri_range_label.setText(
            f"{config.rri_min_us / 1_000:.0f}〜{config.rri_max_us / 1_000:.0f} ms"
        )
        self.median_history_start_label.setText(
            f"{config.median_history_min_valid_count} 件"
        )
        self.median_history_max_label.setText(
            f"{config.median_history_max_valid_count} 件"
        )
        self.median_deviation_label.setText(
            f"{config.median_relative_deviation_limit * 100:.0f}% 超"
        )
        self.low_confidence_label.setText(
            f"artifact率 {config.low_confidence_artifact_rate * 100:.0f}% 超"
        )
        self.reject_label.setText(f"artifact率 {config.reject_artifact_rate * 100:.0f}% 超")
        self.minimum_valid_label.setText(f"{config.minimum_valid_rri_count} 件")
        self.rmssd_mapping_label.setText(
            f"{config.rmssd_min_ms:.0f}〜{config.rmssd_max_ms:.0f} ms を N 0〜1 へ写像"
        )
        self.baseline_timing_label.setText(
            f"{config.baseline_discard_seconds}秒 discard＋"
            f"{config.baseline_evaluation_seconds}秒 evaluation"
        )
        self.bundle_timing_label.setText(
            f"{config.bundle_discard_seconds}秒 discard＋"
            f"{config.bundle_evaluation_seconds}秒 evaluation"
        )
        self.bundle_count_label.setText(f"{config.bundle_count} bundle")
        self.signal_interval_label.setText(
            f"{us_to_seconds(config.signal_interval_us):g} 秒"
        )
        self.timeline.set_config(config)
        self.chart.set_config(config)

    def update_diagnostics(self, engine_snapshot: EngineSnapshot) -> None:
        """Update every view from immutable component snapshots and record tuples."""

        snapshot = self._component.snapshot()
        rri_records = self._component.rri_records()
        evaluations = self._component.evaluation_records()
        signals = self._component.signal_records()
        self._update_cards(snapshot)

        previous_rri_rows = self.rri_model.rowCount()
        previous_evaluation_rows = self.evaluation_model.rowCount()
        self.rri_model.set_records(rri_records)
        self.evaluation_model.set_records(evaluations)
        self.timeline.set_signal_records(signals, engine_snapshot.current_time_us)
        self.chart.set_records(
            rri_records,
            evaluations,
            signals,
            engine_snapshot.current_time_us,
        )
        if self.rri_model.rowCount() > previous_rri_rows:
            self.rri_table.scrollToBottom()
        if self.evaluation_model.rowCount() > previous_evaluation_rows:
            self.evaluation_table.scrollToBottom()
        self.export_rri_button.setEnabled(bool(rri_records))
        self.export_evaluation_button.setEnabled(bool(evaluations))
        self.export_signal_button.setEnabled(bool(signals))

    def reset_views(self) -> None:
        """Clear dynamic plots/tables and restore cards from reset component state."""

        self.rri_model.clear()
        self.evaluation_model.clear()
        self.timeline.clear_records()
        self.chart.clear()
        self._update_cards(self._component.snapshot())
        self.export_rri_button.setEnabled(False)
        self.export_evaluation_button.setEnabled(False)
        self.export_signal_button.setEnabled(False)

    def _update_cards(self, snapshot: GardenInputSnapshot) -> None:
        self.phase_label.setText(snapshot.current_phase)
        self.s_label.setText(str(snapshot.current_s))
        self.bundle_label.setText(
            "—"
            if snapshot.current_bundle_index is None
            else f"Bundle {snapshot.current_bundle_index}"
        )
        self.window_role_label.setText(snapshot.current_window_role)
        self.received_rri_label.setText(f"{snapshot.received_rri_count} 件")
        self.valid_rri_label.setText(f"{snapshot.valid_rri_count} 件")
        self.artifact_label.setText(f"{snapshot.artifact_rri_count} 件")
        self.baseline_n_label.setText(self._format_n(snapshot.n_baseline_session))
        self.current_n_label.setText(self._format_n(snapshot.n_current))
        self.latest_rmssd_label.setText(
            "—" if snapshot.latest_rmssd_ms is None else f"{snapshot.latest_rmssd_ms:.3f} ms"
        )
        self.evaluation_quality_label.setText(snapshot.latest_evaluation_quality or "—")
        self.revision_label.setText(str(snapshot.valid_evaluation_revision))

    def _export_rri_clicked(self) -> None:
        records = self._component.rri_records()
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Garden RRI分類CSVを保存",
            GARDEN_RRI_CSV_FILENAME,
            "CSV (*.csv)",
        )
        if destination:
            export_garden_rri_csv(destination, records)

    def _export_evaluation_clicked(self) -> None:
        records = self._component.evaluation_records()
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Garden評価結果CSVを保存",
            GARDEN_EVALUATION_CSV_FILENAME,
            "CSV (*.csv)",
        )
        if destination:
            export_garden_evaluations_csv(destination, records)

    def _export_signal_clicked(self) -> None:
        records = self._component.signal_records()
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Garden N/S信号CSVを保存",
            GARDEN_SIGNAL_CSV_FILENAME,
            "CSV (*.csv)",
        )
        if destination:
            export_garden_signals_csv(destination, records)

    @staticmethod
    def _fixed_value(form: QFormLayout, caption: str) -> QLabel:
        value = QLabel("—")
        value.setObjectName("fixedConditionValue")
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(caption, value)
        return value

    @staticmethod
    def _state_card(
        layout: QGridLayout,
        row: int,
        column: int,
        caption: str,
        value: str,
    ) -> QLabel:
        card = QWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(6, 2, 6, 2)
        caption_label = QLabel(caption)
        caption_label.setObjectName("statusCaption")
        value_label = QLabel(value)
        value_label.setObjectName("statusValue")
        card_layout.addWidget(caption_label)
        card_layout.addWidget(value_label)
        layout.addWidget(card, row, column)
        return value_label

    @staticmethod
    def _format_n(value: float | None) -> str:
        return "—" if value is None else f"{value:.6f}"
