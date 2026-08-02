"""Stage 3 read-only Polar H10 device and comparison diagnostics panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.devices.polar_h10.component import (
    PolarH10Component,
    PolarH10State,
)
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.polar_h10.diagnostics import (
    H10_DIAGNOSTIC_CSV_FILENAME,
    H10_DIAGNOSTIC_NOTICE,
    compare_rri_measurements,
    export_rri_measurement_diagnostics_csv,
)
from symbiotic_sim_v2.gui.polar_h10_chart import PolarH10Chart
from symbiotic_sim_v2.gui.rri_measurement_table_model import (
    RriMeasurementTableModel,
)
from symbiotic_sim_v2.simulation.engine import EngineSnapshot
from symbiotic_sim_v2.simulation.time_utils import format_time_us
from symbiotic_sim_v2.virtual_user.component import VirtualUserComponent

H10_STAGE_DESCRIPTION = (
    "このStageの仮想Polar H10は、HeartbeatEventの時刻差からraw RRIを測定する"
    "理想的な入力デバイスモデルです。BLE packet、測定誤差、欠損、通信遅延は"
    "まだ再現していません。"
)
H10_RESPONSIBILITY_NOTICE = "H10はRMSSD、N、Nd、W、artifact判定を行いません。"
GARDEN_BOUNDARY_NOTICE = (
    "RRIの300〜2000ms判定、中央値判定、RMSSD、Nは次StageのGarden入力層で実装します。"
)

STATE_LABELS = {
    PolarH10State.READY: "ready（理想接続・待機）",
    PolarH10State.MEASURING: "measuring（測定中）",
    PolarH10State.COMPLETED: "completed（完了）",
}


class PolarH10Panel(QWidget):
    """Read immutable component records and render Stage 3 diagnostics only."""

    def __init__(
        self,
        config: PolarH10Config,
        polar_h10_component: PolarH10Component,
        virtual_user_component: VirtualUserComponent,
        parent=None,
        *,
        duration_seconds: int = 180,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._polar_h10_component = polar_h10_component
        self._virtual_user_component = virtual_user_component
        self._build_ui(duration_seconds)
        self.set_config(config)
        self.reset_views()

    @property
    def config(self) -> PolarH10Config:
        """Return the fixed device configuration currently displayed."""

        return self._config

    def _build_ui(self, duration_seconds: int) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)

        description = QLabel(H10_STAGE_DESCRIPTION, self)
        description.setObjectName("h10Description")
        description.setWordWrap(True)
        root.addWidget(description)

        responsibility = QLabel(H10_RESPONSIBILITY_NOTICE, self)
        responsibility.setObjectName("h10ResponsibilityNotice")
        responsibility.setWordWrap(True)
        root.addWidget(responsibility)

        flow_frame = QFrame(self)
        flow_frame.setObjectName("signalFlowFrame")
        flow_layout = QHBoxLayout(flow_frame)
        flow_layout.setContentsMargins(10, 6, 10, 6)
        flow_layout.setSpacing(8)
        for index, node_text in enumerate(
            (
                "仮想ユーザー",
                "HeartbeatEvent",
                "仮想Polar H10",
                "RriMeasurementEvent",
                "将来のGarden入力層",
            )
        ):
            if index:
                arrow = QLabel("→", flow_frame)
                arrow.setObjectName("flowArrow")
                flow_layout.addWidget(arrow)
            node = QLabel(node_text, flow_frame)
            node.setObjectName("flowNode")
            node.setAlignment(Qt.AlignmentFlag.AlignCenter)
            flow_layout.addWidget(node, stretch=1)
        root.addWidget(flow_frame)

        body = QSplitter(Qt.Orientation.Horizontal, self)
        fixed_group = QGroupBox("理想H10の固定条件（読み取り専用）", body)
        fixed_group.setMinimumWidth(440)
        fixed_group.setMaximumWidth(520)
        fixed_layout = QVBoxLayout(fixed_group)
        fixed_form = QFormLayout()
        fixed_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.model_version_label = self._fixed_value(fixed_form, "model version")
        self.event_schema_version_label = self._fixed_value(
            fixed_form,
            "event schema version",
        )
        self.device_id_label = self._fixed_value(fixed_form, "device ID")
        self.expected_user_id_label = self._fixed_value(fixed_form, "expected user ID")
        self.measurement_mode_label = self._fixed_value(fixed_form, "measurement mode")
        self.measurement_noise_label = self._fixed_value(fixed_form, "measurement noise")
        self.packet_loss_label = self._fixed_value(fixed_form, "packet loss")
        self.latency_label = self._fixed_value(fixed_form, "latency")
        self.artifact_filtering_label = self._fixed_value(fixed_form, "artifact filtering")
        fixed_layout.addLayout(fixed_form)
        fixed_layout.addStretch(1)

        self.export_csv_button = QPushButton("H10診断CSVを保存", fixed_group)
        self.export_csv_button.setObjectName("exportH10CsvButton")
        fixed_layout.addWidget(self.export_csv_button)
        boundary_notice = QLabel(GARDEN_BOUNDARY_NOTICE, fixed_group)
        boundary_notice.setObjectName("h10BoundaryNotice")
        boundary_notice.setWordWrap(True)
        fixed_layout.addWidget(boundary_notice)
        body.addWidget(fixed_group)

        diagnostics = QWidget(body)
        diagnostics_layout = QVBoxLayout(diagnostics)
        diagnostics_layout.setContentsMargins(4, 0, 0, 0)
        diagnostics_layout.setSpacing(7)

        state_frame = QFrame(diagnostics)
        state_frame.setObjectName("statusFrame")
        state_grid = QGridLayout(state_frame)
        state_grid.setContentsMargins(8, 5, 8, 5)
        self.connection_state_label = self._state_card(
            state_grid,
            0,
            0,
            "仮想接続状態",
            STATE_LABELS[PolarH10State.READY],
        )
        self.observed_heartbeat_count_label = self._state_card(
            state_grid,
            0,
            1,
            "観測heartbeat数",
            "0 拍",
        )
        self.rri_measurement_count_label = self._state_card(
            state_grid,
            0,
            2,
            "出力RRI数",
            "0 件",
        )
        self.latest_rri_label = self._state_card(state_grid, 0, 3, "最新RRI", "—")
        self.latest_measurement_time_label = self._state_card(
            state_grid,
            1,
            0,
            "最新RRI出力時刻",
            "—",
        )
        self.latest_absolute_error_label = self._state_card(
            state_grid,
            1,
            1,
            "仮想ユーザー真値との差",
            "—",
        )
        self.maximum_absolute_error_label = self._state_card(
            state_grid,
            1,
            2,
            "最大絶対誤差",
            "—",
        )
        state_grid.setColumnStretch(3, 1)
        diagnostics_layout.addWidget(state_frame)

        diagnostic_notice = QLabel(H10_DIAGNOSTIC_NOTICE, diagnostics)
        diagnostic_notice.setObjectName("diagnosticNotice")
        diagnostic_notice.setWordWrap(True)
        diagnostics_layout.addWidget(diagnostic_notice)

        chart_table_splitter = QSplitter(Qt.Orientation.Vertical, diagnostics)
        self.chart = PolarH10Chart(duration_seconds, chart_table_splitter)
        self.chart.setMinimumHeight(250)
        chart_table_splitter.addWidget(self.chart)

        table_group = QGroupBox("最近のRRI測定（raw出力＋開発用比較）", chart_table_splitter)
        table_layout = QVBoxLayout(table_group)
        self.measurement_model = RriMeasurementTableModel(self)
        self.measurement_table = QTableView(table_group)
        self.measurement_table.setObjectName("rriMeasurementTable")
        self.measurement_table.setModel(self.measurement_model)
        self.measurement_table.setAlternatingRowColors(True)
        self.measurement_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.measurement_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self.measurement_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table_layout.addWidget(self.measurement_table)
        chart_table_splitter.addWidget(table_group)
        chart_table_splitter.setSizes([330, 240])
        diagnostics_layout.addWidget(chart_table_splitter, stretch=1)
        body.addWidget(diagnostics)
        body.setSizes([480, 900])
        root.addWidget(body, stretch=1)

        # Concise aliases preserve the terminology used in the Stage 3 acceptance tests.
        self.heartbeat_count_label = self.observed_heartbeat_count_label
        self.rri_count_label = self.rri_measurement_count_label
        self.latest_error_label = self.latest_absolute_error_label
        self.max_error_label = self.maximum_absolute_error_label
        self.table_model = self.measurement_model
        self.rri_table = self.measurement_table

        self.export_csv_button.clicked.connect(self._export_csv_clicked)
        self.setStyleSheet(
            """
                QLabel#h10Description {
                    background: #E8F1FF; border: 1px solid #B9D2F5; border-radius: 6px;
                    color: #234A75; padding: 6px 10px;
                }
                QLabel#h10ResponsibilityNotice, QLabel#h10BoundaryNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A; border-radius: 6px;
                    color: #6B4B16; padding: 6px 10px;
                }
                QFrame#signalFlowFrame {
                    background: #EEF2FF; border: 1px solid #C7D2FE; border-radius: 7px;
                }
                QLabel#flowNode {
                    background: white; border: 1px solid #A5B4FC; border-radius: 5px;
                    color: #263C78; font-weight: 700; padding: 5px 7px;
                }
                QLabel#flowArrow { color: #4F46E5; font-size: 18px; font-weight: 700; }
                QLabel#fixedConditionValue { color: #1E3A5F; font-weight: 600; }
            """
        )

    def set_components(
        self,
        polar_h10_component: PolarH10Component,
        virtual_user_component: VirtualUserComponent,
    ) -> None:
        """Switch both immutable read sources after scenario reconstruction."""

        self._polar_h10_component = polar_h10_component
        self._virtual_user_component = virtual_user_component
        self.set_config(polar_h10_component.config)
        self.reset_views()

    def set_config(self, config: PolarH10Config) -> None:
        """Populate every fixed-condition label from one validated config."""

        self._config = config
        self.model_version_label.setText(config.model_version)
        self.event_schema_version_label.setText(config.event_schema_version)
        self.device_id_label.setText(config.device_id)
        self.expected_user_id_label.setText(config.expected_user_id)
        self.measurement_mode_label.setText("ideal heartbeat interval")
        self.measurement_noise_label.setText("none")
        self.packet_loss_label.setText("none")
        self.latency_label.setText("none")
        self.artifact_filtering_label.setText("none")

    def set_duration_seconds(self, duration_seconds: int) -> None:
        """Update the chart range after a virtual-user config change."""

        self.chart.set_duration_seconds(duration_seconds)

    def update_diagnostics(self, engine_snapshot: EngineSnapshot) -> None:
        """Refresh cards, plots, and rows from immutable component state."""

        device_snapshot = self._polar_h10_component.snapshot()
        measurements = self._polar_h10_component.measurement_records()
        heartbeat_records = self._virtual_user_component.heartbeat_records()
        diagnostics = compare_rri_measurements(measurements, heartbeat_records)

        self.connection_state_label.setText(STATE_LABELS[device_snapshot.state])
        self.observed_heartbeat_count_label.setText(
            f"{device_snapshot.observed_heartbeat_count} 拍"
        )
        self.rri_measurement_count_label.setText(
            f"{device_snapshot.rri_measurement_count} 件"
        )
        self.latest_rri_label.setText(
            "—"
            if device_snapshot.latest_rri_ms is None
            else f"{device_snapshot.latest_rri_ms:.3f} ms"
        )
        self.latest_measurement_time_label.setText(
            "—"
            if device_snapshot.latest_measurement_time_us is None
            else format_time_us(device_snapshot.latest_measurement_time_us)
        )
        self.latest_absolute_error_label.setText(
            "—" if not diagnostics else f"{diagnostics[-1].absolute_error_us} µs"
        )
        self.maximum_absolute_error_label.setText(
            "—"
            if not diagnostics
            else f"{max(record.absolute_error_us for record in diagnostics)} µs"
        )

        previous_rows = self.measurement_model.rowCount()
        self.measurement_model.set_records(diagnostics)
        self.chart.set_records(diagnostics, engine_snapshot.current_time_us)
        if self.measurement_model.rowCount() > previous_rows:
            self.measurement_table.scrollToBottom()
        self.export_csv_button.setEnabled(bool(measurements))

    def reset_views(self) -> None:
        """Clear cards, chart, and table while retaining fixed device identity."""

        self.measurement_model.clear()
        self.chart.clear()
        self.connection_state_label.setText(STATE_LABELS[PolarH10State.READY])
        self.observed_heartbeat_count_label.setText("0 拍")
        self.rri_measurement_count_label.setText("0 件")
        self.latest_rri_label.setText("—")
        self.latest_measurement_time_label.setText("—")
        self.latest_absolute_error_label.setText("—")
        self.maximum_absolute_error_label.setText("—")
        self.export_csv_button.setEnabled(False)

    def _export_csv_clicked(self) -> None:
        measurements = self._polar_h10_component.measurement_records()
        if not measurements:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Polar H10 RRI測定の開発用診断CSVを保存",
            H10_DIAGNOSTIC_CSV_FILENAME,
            "CSV (*.csv)",
        )
        if destination:
            export_rri_measurement_diagnostics_csv(
                destination,
                measurements,
                self._virtual_user_component.heartbeat_records(),
            )

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
        card_layout.setContentsMargins(7, 2, 7, 2)
        caption_label = QLabel(caption)
        caption_label.setObjectName("statusCaption")
        value_label = QLabel(value)
        value_label.setObjectName("statusValue")
        card_layout.addWidget(caption_label)
        card_layout.addWidget(value_label)
        layout.addWidget(card, row, column)
        return value_label
