"""Stage 5B read-only Garden output-qualification diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.garden.output_layer.diagnostics import (
    QUALIFICATION_CSV_FILENAME,
    QUALIFIED_B_CSV_FILENAME,
    TOUCH_CSV_FILENAME,
    export_qualification_records_csv,
    export_qualified_b_records_csv,
    export_touch_records_csv,
)
from symbiotic_sim_v2.gui.garden_output_chart import GardenOutputChart
from symbiotic_sim_v2.gui.qualification_table_model import QualificationTableModel
from symbiotic_sim_v2.simulation.engine import EngineSnapshot
from symbiotic_sim_v2.simulation.time_utils import format_time_us

GARDEN_OUTPUT_DESCRIPTION = (
    "Garden出力資格層は実際に到着したIDとBだけを入力として、資格holderと"
    "qualified Bを管理します。"
)
GARDEN_OUTPUT_RULES = (
    "固定規則: first touch when empty / hold while S=1 / release after closing "
    "second round when S=0 / equal arrival tie-break"
)
GARDEN_OUTPUT_BOUNDARY_NOTICE = (
    "Garden formal boundary receives ID/B only。touch payloadにrole、P、V、tauは"
    "含まれず、roleはRuntime / GUI診断だけに使用します。"
)
GARDEN_OUTPUT_TIMING_NOTICE = (
    "active qualified Bはholder touchの実到着時刻に正式出力します。round finalizeは"
    "全touch確認、feedback確定、第2周同期の時刻であり、光開始時刻ではありません。"
    "round finalizeでactive Bを再出力しません。"
)
NO_LIGHT_NOTICE = (
    "Garden出力資格層はまだHue、BPM、光波形Iを生成しません。"
    "Stage 6はGardenQualifiedBEventを入力として光を生成します。"
)

GARDEN_OUTPUT_TABLE_MIN_HEIGHT = 350
GARDEN_OUTPUT_SPLITTER_MIN_HEIGHT = 1_100
GARDEN_OUTPUT_SPLITTER_INITIAL_SIZES = (720, 380)


class GardenOutputPanel(QWidget):
    """Observe Garden holder state without reproducing qualification logic."""

    def __init__(self, config: Any, component: Any | None = None, parent=None) -> None:
        super().__init__(parent)
        if hasattr(config, "snapshot"):
            selected_component = config
            selected_config = component or getattr(selected_component, "config", None)
        else:
            selected_config = config
            selected_component = component
        if selected_component is None or not hasattr(selected_component, "snapshot"):
            raise TypeError("component must provide an immutable snapshot")
        self._config = selected_config
        self._component = selected_component
        self._build_ui()
        self.reset_views()

    @property
    def config(self) -> Any:
        return self._config

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        description = QLabel(GARDEN_OUTPUT_DESCRIPTION, self)
        description.setObjectName("gardenOutputDescription")
        description.setWordWrap(True)
        root.addWidget(description)

        rules = QLabel(GARDEN_OUTPUT_RULES, self)
        rules.setObjectName("gardenOutputRulesNotice")
        rules.setWordWrap(True)
        root.addWidget(rules)

        boundary = QLabel(GARDEN_OUTPUT_BOUNDARY_NOTICE, self)
        boundary.setObjectName("gardenOutputBoundaryNotice")
        boundary.setWordWrap(True)
        root.addWidget(boundary)

        timing = QLabel(GARDEN_OUTPUT_TIMING_NOTICE, self)
        timing.setObjectName("gardenOutputTimingNotice")
        timing.setWordWrap(True)
        root.addWidget(timing)

        no_light = QLabel(NO_LIGHT_NOTICE, self)
        no_light.setObjectName("gardenOutputNoLightNotice")
        no_light.setWordWrap(True)
        root.addWidget(no_light)

        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("gardenOutputDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("gardenOutputDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content_layout = QVBoxLayout(self.diagnostics_content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(7)
        content_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        content_layout.addWidget(self._build_state_frame())

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("gardenOutputChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(GARDEN_OUTPUT_SPLITTER_MIN_HEIGHT)
        self.chart = GardenOutputChart(self.chart_table_splitter)
        self._apply_chart_config()
        self.chart_table_splitter.addWidget(self.chart)
        self._build_qualification_table()
        self.chart_table_splitter.addWidget(self.table_frame)
        self.chart_table_splitter.setCollapsible(0, False)
        self.chart_table_splitter.setCollapsible(1, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 0)
        self.chart_table_splitter.setSizes(list(GARDEN_OUTPUT_SPLITTER_INITIAL_SIZES))
        content_layout.addWidget(self.chart_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self._diagnostic_scroll_wheel_targets = (self.chart.graphics.viewport(),)
        for target in self._diagnostic_scroll_wheel_targets:
            target.installEventFilter(self)
        root.addWidget(self.diagnostics_scroll, stretch=1)

        self.setStyleSheet(
            """
                QLabel#gardenOutputDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5;
                    border-radius: 6px; color: #234A75; padding: 6px 10px;
                }
                QLabel#gardenOutputRulesNotice, QLabel#gardenOutputBoundaryNotice,
                QLabel#gardenOutputTimingNotice {
                    background: #F5F3FF; border: 1px solid #C4B5FD;
                    border-radius: 6px; color: #4C1D95; padding: 6px 10px;
                }
                QLabel#gardenOutputNoLightNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A;
                    border-radius: 6px; color: #6B4B16; padding: 6px 10px;
                }
                QFrame#gardenOutputStateFrame {
                    background: #F8FAFC; border: 1px solid #CBD5E1;
                    border-radius: 7px;
                }
                QLabel#gardenOutputStateValue {
                    color: #172033; font-weight: 700;
                }
            """
        )

    def _build_state_frame(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("gardenOutputStateFrame")
        form = QFormLayout(frame)
        form.setContentsMargins(10, 8, 10, 8)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(4)
        fields = (
            ("current_holder", "current holder"),
            ("assignment_signal", "assignment signal"),
            ("assignment_time", "assignment time"),
            ("holder_active", "holder active"),
            ("touch_current", "touch count current round"),
            ("touch_total", "total touch count"),
            ("active_outputs", "active output count"),
            ("inactive_outputs", "inactive output count"),
            ("feedback", "feedback count"),
            ("assignments", "assignment count"),
            ("releases", "release count"),
            ("latest_qualified_b", "latest qualified B"),
            ("qualified_effective_time", "latest command effective time"),
            (
                "active_qualified_effective_time",
                "latest active qualified B effective time",
            ),
            ("holder_touch_time", "latest active holder touch arrival time"),
            ("holder_touch_delay", "holder touch → qualified B delay"),
            ("emission_policy", "qualified B emission policy"),
            ("touch_schema", "touch schema version"),
            ("qualified_b_schema", "qualified B schema version"),
            ("active_emission_status", "active B emitted at holder touch"),
        )
        self.state_labels: dict[str, QLabel] = {}
        for key, caption in fields:
            value = QLabel("—", frame)
            value.setObjectName("gardenOutputStateValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            form.addRow(caption, value)
            self.state_labels[key] = value

        self.current_holder_label = self.state_labels["current_holder"]
        self.assignment_signal_label = self.state_labels["assignment_signal"]
        self.assignment_time_label = self.state_labels["assignment_time"]
        self.holder_active_label = self.state_labels["holder_active"]
        self.touch_current_label = self.state_labels["touch_current"]
        self.touch_count_current_round_label = self.touch_current_label
        self.total_touch_label = self.state_labels["touch_total"]
        self.total_touch_count_label = self.total_touch_label
        self.active_output_label = self.state_labels["active_outputs"]
        self.active_output_count_label = self.active_output_label
        self.inactive_output_label = self.state_labels["inactive_outputs"]
        self.inactive_output_count_label = self.inactive_output_label
        self.feedback_count_label = self.state_labels["feedback"]
        self.assignment_count_label = self.state_labels["assignments"]
        self.release_count_label = self.state_labels["releases"]
        self.latest_qualified_b_label = self.state_labels["latest_qualified_b"]
        self.qualified_effective_time_label = self.state_labels[
            "qualified_effective_time"
        ]
        self.effective_time_label = self.qualified_effective_time_label
        self.active_qualified_effective_time_label = self.state_labels[
            "active_qualified_effective_time"
        ]
        self.holder_touch_time_label = self.state_labels["holder_touch_time"]
        self.qualified_b_delay_label = self.state_labels["holder_touch_delay"]
        self.holder_touch_delay_label = self.qualified_b_delay_label
        self.emission_policy_label = self.state_labels["emission_policy"]
        self.touch_schema_version_label = self.state_labels["touch_schema"]
        self.qualified_b_schema_version_label = self.state_labels[
            "qualified_b_schema"
        ]
        self.active_emission_status_label = self.state_labels[
            "active_emission_status"
        ]
        return frame

    def _build_qualification_table(self) -> None:
        self.table_frame = QFrame(self.chart_table_splitter)
        self.table_frame.setObjectName("gardenQualificationTableFrame")
        self.table_frame.setMinimumHeight(GARDEN_OUTPUT_TABLE_MIN_HEIGHT)
        layout = QVBoxLayout(self.table_frame)
        layout.setContentsMargins(4, 4, 4, 4)

        self.qualification_model = QualificationTableModel(self)
        self.qualification_table = QTableView(self.table_frame)
        self.qualification_table.setObjectName("gardenQualificationTable")
        self.qualification_table.setModel(self.qualification_model)
        self.qualification_table.setAlternatingRowColors(True)
        self.qualification_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.qualification_table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )
        header = self.qualification_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        layout.addWidget(self.qualification_table)

        button_row = QHBoxLayout()
        self.export_touch_button = QPushButton("touch CSVを保存", self.table_frame)
        self.export_touches_button = self.export_touch_button
        self.export_touch_button.setObjectName("exportGardenTouchCsvButton")
        self.export_touch_button.clicked.connect(self._export_touch_clicked)
        button_row.addWidget(self.export_touch_button)
        self.export_qualification_button = QPushButton(
            "qualification CSVを保存",
            self.table_frame,
        )
        self.export_qualifications_button = self.export_qualification_button
        self.export_qualification_button.setObjectName(
            "exportGardenQualificationCsvButton"
        )
        self.export_qualification_button.clicked.connect(
            self._export_qualification_clicked
        )
        button_row.addWidget(self.export_qualification_button)
        self.export_qualified_b_button = QPushButton(
            "qualified B CSVを保存",
            self.table_frame,
        )
        self.export_qualified_outputs_button = self.export_qualified_b_button
        self.export_qualified_b_button.setObjectName("exportGardenQualifiedBCsvButton")
        self.export_qualified_b_button.clicked.connect(
            self._export_qualified_b_clicked
        )
        button_row.addWidget(self.export_qualified_b_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            watched in self._diagnostic_scroll_wheel_targets
            and event.type() is QEvent.Type.Wheel
        ):
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

    def set_component(self, component: Any) -> None:
        self._component = component

    def set_config(self, config: Any) -> None:
        self._config = config
        self._apply_chart_config()

    def set_duration_seconds(self, duration_seconds: int) -> None:
        self.chart.set_duration_seconds(duration_seconds)

    def update_diagnostics(self, engine_snapshot: EngineSnapshot) -> None:
        snapshot = self._component.snapshot()
        qualification_records = self._component.qualification_records()
        qualified_b_records = self._component.qualified_b_records()

        self._update_state(snapshot)
        previous_rows = self.qualification_model.rowCount()
        self.qualification_model.set_records(qualification_records)
        self.chart.set_records(
            qualification_records,
            qualified_b_records,
            engine_snapshot.current_time_us,
            self._component.touch_records(),
        )
        if self.qualification_model.rowCount() > previous_rows:
            self.qualification_table.scrollToBottom()
        self.export_touch_button.setEnabled(bool(self._component.touch_records()))
        self.export_qualification_button.setEnabled(bool(qualification_records))
        self.export_qualified_b_button.setEnabled(bool(qualified_b_records))

    def reset_views(self) -> None:
        self.qualification_model.clear()
        self.chart.clear()
        self._update_state(self._component.snapshot())
        self.export_touch_button.setEnabled(False)
        self.export_qualification_button.setEnabled(False)
        self.export_qualified_b_button.setEnabled(False)
        self.diagnostics_scroll.verticalScrollBar().setValue(0)

    def _update_state(self, snapshot: Any) -> None:
        labels = self.state_labels
        labels["current_holder"].setText(snapshot.qualification_holder_id or "null")
        labels["assignment_signal"].setText(
            self._optional_integer(snapshot.qualification_assigned_signal_index)
        )
        labels["assignment_time"].setText(
            "—"
            if snapshot.qualification_assignment_time_us is None
            else format_time_us(snapshot.qualification_assignment_time_us)
        )
        labels["holder_active"].setText("yes" if snapshot.holder_active else "no")
        labels["touch_current"].setText(str(snapshot.touch_count_current_round))
        labels["touch_total"].setText(str(snapshot.total_touch_count))
        labels["active_outputs"].setText(str(snapshot.active_output_count))
        labels["inactive_outputs"].setText(str(snapshot.inactive_output_count))
        labels["feedback"].setText(str(snapshot.feedback_count))
        labels["assignments"].setText(str(snapshot.assignment_count))
        labels["releases"].setText(str(snapshot.release_count))
        labels["latest_qualified_b"].setText(
            self._format_b(snapshot.latest_qualified_b)
        )
        effective_time_us = getattr(
            snapshot,
            "latest_qualified_b_effective_time_us",
            None,
        )
        active_effective_time_us = getattr(
            snapshot,
            "latest_active_qualified_b_effective_time_us",
            None,
        )
        holder_touch_time_us = getattr(
            snapshot,
            "latest_active_holder_touch_time_us",
            None,
        )
        delay_us = getattr(snapshot, "latest_active_qualified_b_delay_us", None)
        labels["qualified_effective_time"].setText(
            self._format_time(effective_time_us)
        )
        labels["active_qualified_effective_time"].setText(
            self._format_time(active_effective_time_us)
        )
        labels["holder_touch_time"].setText(
            self._format_time(holder_touch_time_us)
        )
        labels["holder_touch_delay"].setText(
            "—" if delay_us is None else f"{delay_us} us"
        )
        policy = getattr(
            snapshot,
            "qualified_b_emission_policy_version",
            getattr(self._config, "qualified_b_emission_policy_version", "—"),
        )
        labels["emission_policy"].setText(str(policy))
        labels["touch_schema"].setText(
            str(getattr(self._config, "touch_schema_version", "—"))
        )
        labels["qualified_b_schema"].setText(
            str(getattr(self._config, "qualified_b_schema_version", "—"))
        )
        if snapshot.active_output_count == 0:
            emission_status = "未発行"
        elif delay_us == 0:
            emission_status = "yes — holder touchと同じmicrosecond"
        else:
            emission_status = "no"
        labels["active_emission_status"].setText(emission_status)

    def _apply_chart_config(self) -> None:
        if not hasattr(self, "chart") or self._config is None:
            return
        self.chart.set_round_finalize_offset_us(
            self._config.round_finalize_offset_us
        )
        self.chart.set_roster(self._config.expected_digital_life_ids)

    def _export_touch_clicked(self) -> None:
        self._export_records(
            title="Stage 5B touch CSVを保存",
            filename=TOUCH_CSV_FILENAME,
            records=self._component.touch_records(),
            exporter=export_touch_records_csv,
        )

    def _export_qualification_clicked(self) -> None:
        self._export_records(
            title="Stage 5B qualification CSVを保存",
            filename=QUALIFICATION_CSV_FILENAME,
            records=self._component.qualification_records(),
            exporter=export_qualification_records_csv,
        )

    def _export_qualified_b_clicked(self) -> None:
        self._export_records(
            title="Stage 5B qualified B CSVを保存",
            filename=QUALIFIED_B_CSV_FILENAME,
            records=self._component.qualified_b_records(),
            exporter=export_qualified_b_records_csv,
        )

    def _export_records(
        self,
        *,
        title: str,
        filename: str,
        records: tuple[Any, ...],
        exporter: Callable[[str, tuple[Any, ...]], Any],
    ) -> None:
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            title,
            filename,
            "CSV (*.csv)",
        )
        if destination:
            exporter(destination, records)

    @staticmethod
    def _optional_integer(value: int | None) -> str:
        return "—" if value is None else str(value)

    @staticmethod
    def _format_b(value: tuple[float, float, float, float] | None) -> str:
        if value is None:
            return "—"
        return "[" + ", ".join(f"{item:.6f}" for item in value) + "]"

    @staticmethod
    def _format_time(value: int | None) -> str:
        return "—" if value is None else format_time_us(value)


GardenOutputQualificationPanel = GardenOutputPanel
