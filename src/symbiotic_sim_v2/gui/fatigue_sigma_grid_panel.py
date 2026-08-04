"""Condition-grid controls, progress, heatmap, and aggregate table."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.condition_heatmap import (
    HEATMAP_METRICS,
    ConditionHeatmap,
)
from symbiotic_sim_v2.gui.condition_result_table_model import (
    ConditionResultTableModel,
)
from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import (
    first_record_value,
)
from symbiotic_sim_v2.gui.fatigue_sigma_single_run_panel import (
    DEFAULT_MASTER_SEED,
    DEFAULT_V2_USER_TYPES,
)

GRID_TABLE_MIN_HEIGHT = 300
GRID_SPLITTER_MIN_HEIGHT = 1_050
MAXIMUM_PLANNED_SESSIONS = 30_000

QUICK_FATIGUE_VALUES = "0.03,0.08,0.15"
QUICK_SIGMA_VALUES = "0.50,1.00,1.50"
STANDARD_FATIGUE_VALUES = "0.03,0.05,0.08,0.10,0.15"
STANDARD_SIGMA_VALUES = "0.50,0.75,1.00,1.25,1.50"


class FatigueSigmaGridPanel(QWidget):
    """Collect grid settings and display already aggregated condition results."""

    run_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(
        self,
        user_types: Mapping[str, object] | Sequence[str] = DEFAULT_V2_USER_TYPES,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_types = (
            dict(user_types)
            if isinstance(user_types, Mapping)
            else {str(value): object() for value in user_types}
        )
        self._run_active = False
        self._backend_available = True
        self._build_ui()
        self._connect_ui()
        self._apply_preset("standard")
        self.reset_views()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("stage8a1GridScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(5, 5, 5, 5)
        content.setSpacing(8)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.paired_notice = QLabel(
            "同じreplicate indexは条件間でpaired physiology seedを使います。"
            "condition ID/hashは乱数keyに入れません。Monte_Carlo=false。",
            self.diagnostics_content,
        )
        self.paired_notice.setObjectName("stage8a1PairedSeedNotice")
        self.paired_notice.setWordWrap(True)
        content.addWidget(self.paired_notice)
        self.settings_frame = self._build_settings()
        content.addWidget(self.settings_frame)
        self.operations_frame = self._build_operations()
        content.addWidget(self.operations_frame)

        self.reference_card = QLabel(
            "v2.0 reference coefficient arm: eta/rho reference, sigma×1.0, "
            "unselected full recoveryなし。experimental cellとは別系列です。",
            self.diagnostics_content,
        )
        self.reference_card.setObjectName("stage8a1GridReferenceCard")
        self.reference_card.setWordWrap(True)
        content.addWidget(self.reference_card)

        metric_row = QHBoxLayout()
        metric_row.addWidget(QLabel("heatmap metric", self.diagnostics_content))
        self.metric_combo = QComboBox(self.diagnostics_content)
        self.metric_combo.setObjectName("stage8a1HeatmapMetricCombo")
        for name, caption in HEATMAP_METRICS:
            self.metric_combo.addItem(caption, name)
        metric_row.addWidget(self.metric_combo)
        metric_row.addStretch(1)
        content.addLayout(metric_row)

        self.heatmap_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.heatmap_table_splitter.setObjectName("stage8a1GridHeatmapTableSplitter")
        self.heatmap_table_splitter.setMinimumHeight(GRID_SPLITTER_MIN_HEIGHT)
        self.heatmap = ConditionHeatmap(self.heatmap_table_splitter)
        self.result_model = ConditionResultTableModel(self)
        self.result_table = QTableView(self.heatmap_table_splitter)
        self.result_table.setObjectName("stage8a1ConditionResultTable")
        self.result_table.setModel(self.result_model)
        self.result_table.setMinimumHeight(GRID_TABLE_MIN_HEIGHT)
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.result_table.horizontalHeader().setStretchLastSection(True)
        self.heatmap_table_splitter.addWidget(self.heatmap)
        self.heatmap_table_splitter.addWidget(self.result_table)
        self.heatmap_table_splitter.setCollapsible(0, False)
        self.heatmap_table_splitter.setCollapsible(1, False)
        self.heatmap_table_splitter.setSizes([700, 350])
        content.addWidget(self.heatmap_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        root.addWidget(self.diagnostics_scroll)
        self.setStyleSheet(
            """
            QLabel#stage8a1PairedSeedNotice {
                background: #E8F1FF; border: 1px solid #B9D2F5;
                border-radius: 6px; color: #234A75; padding: 8px 10px;
            }
            QLabel#stage8a1GridReferenceCard {
                background: #FFF7E6; border: 1px solid #F5D28A;
                border-radius: 6px; color: #6B4B16; padding: 8px 10px;
            }
            QFrame#stage8a1GridSettings, QFrame#stage8a1GridOperations {
                background: #F8FAFC; border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
            """
        )

    def _build_settings(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("stage8a1GridSettings")
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        self.preset_combo = QComboBox(frame)
        self.preset_combo.setObjectName("stage8a1GridPresetCombo")
        self.preset_combo.addItem("quick", "quick")
        self.preset_combo.addItem("standard", "standard")
        self.preset_combo.addItem("detailed", "detailed")
        self.preset_combo.setCurrentIndex(1)
        self.user_type_combo = QComboBox(frame)
        self.user_type_combo.setObjectName("stage8a1GridUserTypeCombo")
        for user_type_id in self._user_types:
            self.user_type_combo.addItem(user_type_id, user_type_id)
        self.fatigue_values_edit = QLineEdit(STANDARD_FATIGUE_VALUES, frame)
        self.fatigue_values_edit.setObjectName("stage8a1GridFatigueValues")
        self.sigma_values_edit = QLineEdit(STANDARD_SIGMA_VALUES, frame)
        self.sigma_values_edit.setObjectName("stage8a1GridSigmaValues")
        self.maximum_sessions_spin = QSpinBox(frame)
        self.maximum_sessions_spin.setObjectName("stage8a1GridMaximumSessionsSpin")
        self.maximum_sessions_spin.setRange(4, 100)
        self.maximum_sessions_spin.setValue(24)
        self.replicates_spin = QSpinBox(frame)
        self.replicates_spin.setObjectName("stage8a1GridReplicatesSpin")
        self.replicates_spin.setRange(1, 20)
        self.replicates_spin.setValue(5)
        self.master_seed_spin = QDoubleSpinBox(frame)
        self.master_seed_spin.setObjectName("stage8a1GridMasterSeedSpin")
        self.master_seed_spin.setDecimals(0)
        self.master_seed_spin.setRange(0.0, 4_294_967_295.0)
        self.master_seed_spin.setValue(float(DEFAULT_MASTER_SEED))
        fields = (
            ("preset", self.preset_combo),
            ("user type", self.user_type_combo),
            ("fatigue target values", self.fatigue_values_edit),
            ("sigma multiplier values", self.sigma_values_edit),
            ("sessions", self.maximum_sessions_spin),
            ("replicates", self.replicates_spin),
            ("base master seed", self.master_seed_spin),
        )
        for index, (caption, widget) in enumerate(fields):
            column = 0 if index < 4 else 2
            row = index if index < 4 else index - 4
            layout.addWidget(QLabel(caption, frame), row, column)
            layout.addWidget(widget, row, column + 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        self.settings_widgets = tuple(widget for _caption, widget in fields)
        return frame

    def _build_operations(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("stage8a1GridOperations")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        row = QHBoxLayout()
        self.run_button = QPushButton("条件比較を実行", frame)
        self.run_button.setObjectName("stage8a1RunGridButton")
        self.cancel_button = QPushButton("session / condition境界でcancel", frame)
        self.cancel_button.setObjectName("stage8a1CancelGridButton")
        self.planned_label = QLabel("", frame)
        self.planned_label.setObjectName("stage8a1PlannedSessionRunsLabel")
        row.addWidget(self.run_button)
        row.addWidget(self.cancel_button)
        row.addWidget(self.planned_label)
        row.addStretch(1)
        layout.addLayout(row)
        progress_row = QHBoxLayout()
        self.progress_label = QLabel("停止", frame)
        self.progress_label.setObjectName("stage8a1GridProgressLabel")
        self.progress_bar = QProgressBar(frame)
        self.progress_bar.setObjectName("stage8a1GridProgressBar")
        progress_row.addWidget(self.progress_label)
        progress_row.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(progress_row)
        return frame

    def _connect_ui(self) -> None:
        self.preset_combo.currentIndexChanged.connect(
            lambda _index: self._apply_preset(str(self.preset_combo.currentData()))
        )
        for widget in (
            self.fatigue_values_edit,
            self.sigma_values_edit,
        ):
            widget.textChanged.connect(self._update_plan)
        for widget in (self.maximum_sessions_spin, self.replicates_spin):
            widget.valueChanged.connect(self._update_plan)
        self.run_button.clicked.connect(self._request_run)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.metric_combo.currentIndexChanged.connect(
            lambda _index: self.heatmap.set_metric(str(self.metric_combo.currentData()))
        )

    def settings_values(self) -> dict[str, object]:
        return {
            "experiment_preset": self.preset_combo.currentData(),
            "user_type_id": self.user_type_combo.currentData(),
            "fatigue_targets": _float_values(self.fatigue_values_edit.text()),
            "sigma_multipliers": _float_values(self.sigma_values_edit.text()),
            "maximum_sessions": self.maximum_sessions_spin.value(),
            "replicate_count": self.replicates_spin.value(),
            "base_master_seed": int(self.master_seed_spin.value()),
            "total_planned_session_runs": self.total_planned_session_runs,
        }

    @property
    def total_planned_session_runs(self) -> int:
        fatigue_count = len(_tokens(self.fatigue_values_edit.text()))
        sigma_count = len(_tokens(self.sigma_values_edit.text()))
        return (
            fatigue_count
            * sigma_count
            * self.maximum_sessions_spin.value()
            * self.replicates_spin.value()
        )

    def set_result(self, result: object) -> None:
        summaries = (
            first_record_value(
                result,
                ("condition_summaries", "per_condition_summaries"),
                (),
            )
            or ()
        )
        self.result_model.set_records(tuple(summaries))
        self.heatmap.set_records(tuple(summaries))
        completed = first_record_value(
            result,
            ("completed_session_runs", "total_completed_session_runs"),
            self.progress_bar.maximum(),
        )
        if isinstance(completed, int) and not isinstance(completed, bool):
            self.progress_bar.setValue(min(completed, self.progress_bar.maximum()))
        completed_conditions = first_record_value(
            result,
            ("completed_conditions",),
            len(tuple(summaries)),
        )
        failed_conditions = first_record_value(result, ("failed_conditions",), 0)
        self.progress_label.setText(
            f"completed conditions: {completed_conditions}  |  failed: {failed_conditions}"
        )

    def set_progress(self, progress: object) -> None:
        completed = first_record_value(
            progress,
            ("completed_session_runs", "completed"),
            self.progress_bar.value(),
        )
        total = first_record_value(
            progress,
            ("total_planned_session_runs", "total"),
            self.total_planned_session_runs,
        )
        if isinstance(total, int) and not isinstance(total, bool) and total > 0:
            self.progress_bar.setRange(0, total)
        if isinstance(completed, int) and not isinstance(completed, bool):
            self.progress_bar.setValue(min(max(completed, 0), self.progress_bar.maximum()))
        condition = first_record_value(progress, ("condition_id",), "")
        replicate = first_record_value(progress, ("replicate_index",), "")
        session = first_record_value(progress, ("session_index",), "")
        self.progress_label.setText(
            f"{first_record_value(progress, ('message', 'status'), '実行中')}  "
            f"condition={condition} replicate={replicate} session={session}"
        )

    def set_operation_active(self, active: bool) -> None:
        self._run_active = bool(active)
        self.progress_label.setText("実行中" if active else "停止")
        self._update_enabled_state()

    def set_backend_available(self, available: bool) -> None:
        self._backend_available = bool(available)
        self._update_enabled_state()

    def reset_views(self) -> None:
        self.result_model.set_records(())
        self.heatmap.clear()
        self.progress_bar.setRange(0, max(1, self.total_planned_session_runs))
        self.progress_bar.setValue(0)
        self.progress_label.setText("停止")
        self._update_plan()

    def _request_run(self) -> None:
        self.set_operation_active(True)
        self.run_requested.emit(self.settings_values())

    def _apply_preset(self, preset: str) -> None:
        if preset == "quick":
            self.fatigue_values_edit.setText(QUICK_FATIGUE_VALUES)
            self.sigma_values_edit.setText(QUICK_SIGMA_VALUES)
            self.maximum_sessions_spin.setValue(12)
            self.replicates_spin.setValue(3)
        elif preset == "standard":
            self.fatigue_values_edit.setText(STANDARD_FATIGUE_VALUES)
            self.sigma_values_edit.setText(STANDARD_SIGMA_VALUES)
            self.maximum_sessions_spin.setValue(24)
            self.replicates_spin.setValue(5)
        elif preset == "detailed":
            self.maximum_sessions_spin.setValue(60)
        self._update_plan()

    def _update_plan(self, *_args: object) -> None:
        planned = self.total_planned_session_runs
        if planned > MAXIMUM_PLANNED_SESSIONS:
            self.planned_label.setText(
                f"予定 {planned:,} sessions — 上限 {MAXIMUM_PLANNED_SESSIONS:,} を超えるため拒否"
            )
        else:
            self.planned_label.setText(f"予定 {planned:,} session runs")
        self.progress_bar.setRange(0, max(1, planned))
        self._update_enabled_state()

    def _update_enabled_state(self) -> None:
        for widget in self.settings_widgets:
            widget.setEnabled(not self._run_active)
        within_budget = 0 < self.total_planned_session_runs <= MAXIMUM_PLANNED_SESSIONS
        self.run_button.setEnabled(
            self._backend_available and not self._run_active and within_budget
        )
        self.cancel_button.setEnabled(self._backend_available and self._run_active)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _float_values(value: str) -> tuple[float, ...]:
    converted = []
    for item in _tokens(value):
        try:
            converted.append(float(item))
        except ValueError:
            # The core validator remains authoritative. Preserve an obviously
            # invalid sentinel so the GUI never silently drops a bad entry.
            converted.append(float("nan"))
    return tuple(converted)


__all__ = [
    "GRID_SPLITTER_MIN_HEIGHT",
    "GRID_TABLE_MIN_HEIGHT",
    "MAXIMUM_PLANNED_SESSIONS",
    "FatigueSigmaGridPanel",
]
