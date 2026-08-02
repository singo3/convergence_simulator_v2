"""Stage 5A read-only first-round diagnostics for one Digital Life."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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

from symbiotic_sim_v2.digital_life.component import SingleDigitalLifeComponent
from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.digital_life.diagnostics import (
    EVALUATION_UPDATE_CSV_FILENAME,
    FIRST_ROUND_CSV_FILENAME,
    export_evaluation_updates_csv,
    export_first_round_diagnostics_csv,
)
from symbiotic_sim_v2.gui.digital_life_chart import DigitalLifeChart
from symbiotic_sim_v2.gui.digital_life_evaluation_table_model import (
    DigitalLifeEvaluationTableModel,
)
from symbiotic_sim_v2.gui.digital_life_signal_table_model import (
    DigitalLifeSignalTableModel,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.engine import EngineSnapshot

DIGITAL_LIFE_STAGE_DESCRIPTION = (
    "Stage 5Aでは、1体のデジタル生命がGarden入力層のNとSを知覚し、"
    "第1周としてNd、W、P、V、B、tauを計算します。"
)
DIGITAL_LIFE_BOUNDARY_NOTICE = (
    "Garden出力層とGはまだ未接続です。このStageではタッチ配送、第2周、"
    "E・q・k更新、関係記憶探索を行いません。"
)
TAU_NOTICE = (
    "tauは計算済みですが、Stage 5AではGardenへのタッチをまだ配送しません。"
)
HOLDING_NOTICE = "Stage 5AではG未接続のためEとqを更新しません。"
ANCHOR_NOTICE = "W_anchor_session: 未実装 / Bundle適応はStage 5C"

DIGITAL_LIFE_TABLE_TABS_MIN_HEIGHT = 330
DIGITAL_LIFE_CHART_TABLE_SPLITTER_MIN_HEIGHT = 1_280
DIGITAL_LIFE_CHART_TABLE_INITIAL_SIZES = (940, 340)


class DigitalLifePanel(QWidget):
    """Observe immutable Stage 5A state/records and select one role preset."""

    role_selected = Signal(str)

    def __init__(
        self,
        config: DigitalLifeConfig,
        component: SingleDigitalLifeComponent,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._component = component
        self._build_ui()
        self.set_config(config)
        self.reset_views()

    @property
    def config(self) -> DigitalLifeConfig:
        return self._config

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)

        description = QLabel(DIGITAL_LIFE_STAGE_DESCRIPTION, self)
        description.setObjectName("digitalLifeDescription")
        description.setWordWrap(True)
        root.addWidget(description)
        boundary = QLabel(DIGITAL_LIFE_BOUNDARY_NOTICE, self)
        boundary.setObjectName("digitalLifeBoundaryNotice")
        boundary.setWordWrap(True)
        root.addWidget(boundary)
        root.addWidget(self._build_flow())

        self.body_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.body_splitter.setObjectName("digitalLifeBodySplitter")
        self._build_fixed_column()
        self._build_diagnostics_column()
        self.body_splitter.setSizes([465, 1040])
        root.addWidget(self.body_splitter, stretch=1)

        self.role_combo.currentIndexChanged.connect(self._role_changed)
        self.export_first_round_button.clicked.connect(self._export_first_round_clicked)
        self.export_evaluation_button.clicked.connect(self._export_evaluation_clicked)
        self.setStyleSheet(
            """
                QLabel#digitalLifeDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5; border-radius: 6px;
                    color: #234A75; padding: 6px 10px;
                }
                QLabel#digitalLifeBoundaryNotice, QLabel#digitalLifeHoldingNotice,
                QLabel#digitalLifeTauNotice, QLabel#digitalLifeAnchorNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A; border-radius: 6px;
                    color: #6B4B16; padding: 6px 10px;
                }
                QFrame#digitalLifeSignalFlowFrame {
                    background: #F5F3FF; border: 1px solid #C4B5FD; border-radius: 7px;
                }
                QLabel#digitalLifeFlowNode {
                    background: white; border: 1px solid #A78BFA; border-radius: 5px;
                    color: #4C1D95; font-weight: 700; padding: 5px 6px;
                }
                QLabel#digitalLifeFlowArrow {
                    color: #7C3AED; font-size: 18px; font-weight: 700;
                }
                QLabel#digitalLifeFixedValue { color: #1E3A5F; font-weight: 600; }
            """
        )

    def _build_flow(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("digitalLifeSignalFlowFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(9, 5, 9, 5)
        layout.setSpacing(2)
        rows = (
            (
                "Garden入力層",
                "N, S",
                "外受容系",
                "状態系: Nd, P, E",
                "情動系: W",
            ),
            (
                "関係記憶: k",
                "修飾系: q, V",
                "制御系: B",
                "遠心系: tau",
                "将来のGarden出力層",
            ),
        )
        for row_index, nodes in enumerate(rows):
            row_widget = QWidget(frame)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            for index, text in enumerate(nodes):
                if index:
                    arrow = QLabel("→", row_widget)
                    arrow.setObjectName("digitalLifeFlowArrow")
                    row_layout.addWidget(arrow)
                node = QLabel(text, row_widget)
                node.setObjectName("digitalLifeFlowNode")
                node.setAlignment(Qt.AlignmentFlag.AlignCenter)
                node.setWordWrap(True)
                row_layout.addWidget(node, stretch=1)
            layout.addWidget(row_widget)
            if row_index == 0:
                continuation = QLabel("↓", frame)
                continuation.setObjectName("digitalLifeFlowArrow")
                continuation.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(continuation)
        return frame

    def _build_fixed_column(self) -> None:
        self.fixed_scroll = QScrollArea(self.body_splitter)
        self.fixed_scroll.setObjectName("digitalLifeFixedScroll")
        self.fixed_scroll.setWidgetResizable(True)
        self.fixed_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.fixed_scroll.setMinimumWidth(365)
        self.fixed_scroll.setMaximumWidth(485)
        container = QWidget(self.fixed_scroll)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(7)

        preset_group = QGroupBox("life preset", container)
        preset_layout = QFormLayout(preset_group)
        self.role_combo = QComboBox(preset_group)
        self.role_combo.setObjectName("digitalLifeRoleCombo")
        for role in ("red", "green", "blue"):
            self.role_combo.addItem(role, role)
        preset_layout.addRow("role", self.role_combo)
        layout.addWidget(preset_group)

        intrinsic_group = QGroupBox("生得要素（読み取り専用）", container)
        intrinsic_form = QFormLayout(intrinsic_group)
        intrinsic_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.life_id_label = self._fixed_value(intrinsic_form, "digital life ID")
        self.role_label = self._fixed_value(intrinsic_form, "role")
        self.p_intrinsic_label = self._fixed_value(intrinsic_form, "p_intrinsic")
        self.birth_phase_label = self._fixed_value(intrinsic_form, "birth phase")
        self.f_range_label = self._fixed_value(intrinsic_form, "F range")
        self.a_fixed_label = self._fixed_value(intrinsic_form, "A fixed")
        self.t_range_label = self._fixed_value(intrinsic_form, "T range")
        self.d_fixed_label = self._fixed_value(intrinsic_form, "D fixed")
        self.phi_b_label = self._fixed_value(intrinsic_form, "Phi_B")
        self.phi_p_label = self._fixed_value(intrinsic_form, "Phi_P")
        self.model_version_label = self._fixed_value(intrinsic_form, "model version")
        self.profile_version_label = self._fixed_value(intrinsic_form, "profile version")
        self.algorithm_version_label = self._fixed_value(
            intrinsic_form,
            "algorithm version",
        )
        self.state_schema_version_label = self._fixed_value(
            intrinsic_form,
            "state schema version",
        )
        layout.addWidget(intrinsic_group)

        conditions_group = QGroupBox("Stage 5A固定条件", container)
        conditions_form = QFormLayout(conditions_group)
        conditions_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.delta_n_label = self._fixed_value(conditions_form, "delta N")
        self.w_mapping_label = self._fixed_value(conditions_form, "W")
        self.initial_e_label = self._fixed_value(conditions_form, "E initial")
        self.initial_q_label = self._fixed_value(conditions_form, "q initial")
        self.initial_k_label = self._fixed_value(conditions_form, "k initial")
        self.epsilon_tau_label = self._fixed_value(conditions_form, "epsilon tau")
        self.b_mapping_label = self._fixed_value(conditions_form, "B")
        self.s_zero_label = self._fixed_value(conditions_form, "S=0")
        self.s_one_label = self._fixed_value(conditions_form, "S=1")
        layout.addWidget(conditions_group)

        anchor_notice = QLabel(ANCHOR_NOTICE, container)
        anchor_notice.setObjectName("digitalLifeAnchorNotice")
        anchor_notice.setWordWrap(True)
        layout.addWidget(anchor_notice)

        export_group = QGroupBox("診断CSV export", container)
        export_layout = QVBoxLayout(export_group)
        self.export_first_round_button = QPushButton("第1周signal CSVを保存", export_group)
        self.export_first_round_button.setObjectName("exportDigitalLifeFirstRoundCsvButton")
        self.export_evaluation_button = QPushButton("評価更新CSVを保存", export_group)
        self.export_evaluation_button.setObjectName("exportDigitalLifeEvaluationCsvButton")
        export_layout.addWidget(self.export_first_round_button)
        export_layout.addWidget(self.export_evaluation_button)
        layout.addWidget(export_group)
        layout.addStretch(1)
        self.fixed_scroll.setWidget(container)
        self.body_splitter.addWidget(self.fixed_scroll)

    def _build_diagnostics_column(self) -> None:
        self.diagnostics_scroll = QScrollArea(self.body_splitter)
        self.diagnostics_scroll.setObjectName("digitalLifeDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("digitalLifeDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        layout = QVBoxLayout(self.diagnostics_content)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(6)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        state_frame = QFrame(self.diagnostics_content)
        state_frame.setObjectName("statusFrame")
        state_grid = QGridLayout(state_frame)
        state_grid.setContentsMargins(7, 4, 7, 4)
        self.n_label = self._state_card(state_grid, 0, 0, "N", "—")
        self.baseline_n_label = self._state_card(state_grid, 0, 1, "baseline N", "—")
        self.nd_label = self._state_card(state_grid, 0, 2, "Nd", "0.500000")
        self.w_label = self._state_card(state_grid, 0, 3, "W", "0.500000")
        self.p_label = self._state_card(state_grid, 1, 0, "P", "1.000000")
        self.e_label = self._state_card(state_grid, 1, 1, "E", "0.000000")
        self.q_label = self._state_card(state_grid, 1, 2, "q", "0.500000")
        self.v_label = self._state_card(state_grid, 1, 3, "V", "—")
        self.k_anchor_label = self._state_card(state_grid, 2, 0, "k_anchor", "—")
        self.k_current_label = self._state_card(state_grid, 2, 1, "k_current", "—")
        self.b_label = self._state_card(state_grid, 2, 2, "B=[F,A,T,D]", "—")
        self.tau_label = self._state_card(state_grid, 2, 3, "tau", "—")
        self.s_label = self._state_card(state_grid, 3, 0, "S", "—")
        self.revision_label = self._state_card(state_grid, 3, 1, "evaluation revision", "0")
        self.latest_evaluation_label = self._state_card(
            state_grid,
            3,
            2,
            "latest evaluation",
            "—",
        )
        self.g_label = self._state_card(state_grid, 3, 3, "G", "未接続")
        self.second_round_label = self._state_card(
            state_grid,
            4,
            0,
            "second round",
            "未実装",
        )
        self.touch_dispatch_label = self._state_card(
            state_grid,
            4,
            1,
            "touch dispatch",
            "未実行",
        )
        layout.addWidget(state_frame)

        holding_notice = QLabel(HOLDING_NOTICE, self.diagnostics_content)
        holding_notice.setObjectName("digitalLifeHoldingNotice")
        holding_notice.setWordWrap(True)
        layout.addWidget(holding_notice)
        tau_notice = QLabel(TAU_NOTICE, self.diagnostics_content)
        tau_notice.setObjectName("digitalLifeTauNotice")
        tau_notice.setWordWrap(True)
        layout.addWidget(tau_notice)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("digitalLifeChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(
            DIGITAL_LIFE_CHART_TABLE_SPLITTER_MIN_HEIGHT
        )
        self.chart = DigitalLifeChart(self._config, self.chart_table_splitter)
        self.chart_table_splitter.addWidget(self.chart)

        self.table_tabs = QTabWidget(self.chart_table_splitter)
        self.table_tabs.setObjectName("digitalLifeTableTabs")
        self.table_tabs.setMinimumHeight(DIGITAL_LIFE_TABLE_TABS_MIN_HEIGHT)
        signal_page = QWidget(self.table_tabs)
        signal_layout = QVBoxLayout(signal_page)
        signal_layout.setContentsMargins(4, 4, 4, 4)
        self.signal_model = DigitalLifeSignalTableModel(self)
        self.signal_table = QTableView(signal_page)
        self.signal_table.setObjectName("digitalLifeSignalTable")
        self._configure_table(self.signal_table, self.signal_model)
        signal_layout.addWidget(self.signal_table)
        self.table_tabs.addTab(signal_page, "1秒signal")

        evaluation_page = QWidget(self.table_tabs)
        evaluation_layout = QVBoxLayout(evaluation_page)
        evaluation_layout.setContentsMargins(4, 4, 4, 4)
        self.evaluation_model = DigitalLifeEvaluationTableModel(self)
        self.evaluation_table = QTableView(evaluation_page)
        self.evaluation_table.setObjectName("digitalLifeEvaluationTable")
        self._configure_table(self.evaluation_table, self.evaluation_model)
        evaluation_layout.addWidget(self.evaluation_table)
        self.table_tabs.addTab(evaluation_page, "評価更新")

        self.chart_table_splitter.addWidget(self.table_tabs)
        self.chart_table_splitter.setCollapsible(0, False)
        self.chart_table_splitter.setCollapsible(1, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 0)
        self.chart_table_splitter.setSizes(
            list(DIGITAL_LIFE_CHART_TABLE_INITIAL_SIZES)
        )
        layout.addWidget(self.chart_table_splitter)
        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self._diagnostic_scroll_wheel_targets = (self.chart.graphics.viewport(),)
        for target in self._diagnostic_scroll_wheel_targets:
            target.installEventFilter(self)
        self.body_splitter.addWidget(self.diagnostics_scroll)

        self.current_n_label = self.n_label
        self.current_nd_label = self.nd_label
        self.current_w_label = self.w_label
        self.current_s_label = self.s_label
        self.valid_evaluation_revision_label = self.revision_label
        self.first_round_model = self.signal_model
        self.first_round_table = self.signal_table
        self.evaluation_table_model = self.evaluation_model
        self.export_first_round_csv_button = self.export_first_round_button
        self.export_evaluation_csv_button = self.export_evaluation_button

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        """Give ordinary plot-wheel gestures to the page's vertical scroll."""

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

    def set_component(self, component: SingleDigitalLifeComponent) -> None:
        self._component = component

    def set_config(self, config: DigitalLifeConfig) -> None:
        """Synchronize the authoritative role preset and read-only values."""

        self._config = config
        with QSignalBlocker(self.role_combo):
            index = self.role_combo.findData(config.role)
            if index >= 0:
                self.role_combo.setCurrentIndex(index)
        self.life_id_label.setText(config.digital_life_id)
        self.role_label.setText(config.role)
        self.f_range_label.setText(f"{config.f_min:.6f} 〜 {config.f_max:.6f}")
        self.a_fixed_label.setText(f"{config.a_fixed:.6f}")
        self.t_range_label.setText(f"{config.t_min:.6f} 〜 {config.t_max:.6f}")
        self.d_fixed_label.setText(f"{config.d_fixed:.6f}")
        self.phi_b_label.setText("B = Phi_B(k_current)")
        self.phi_p_label.setText("P = 1 - S × (1 - p_intrinsic)")
        self.model_version_label.setText(config.model_version)
        self.profile_version_label.setText(config.profile_version)
        self.algorithm_version_label.setText(config.algorithm_version)
        self.state_schema_version_label.setText(config.state_schema_version)
        self.delta_n_label.setText(f"{config.delta_n:.2f}")
        self.w_mapping_label.setText("W = Nd（別field）")
        self.initial_e_label.setText(f"{config.initial_e:.1f}")
        self.initial_q_label.setText(f"{config.initial_q:.1f}")
        self.initial_k_label.setText(self._format_vector(config.initial_k_anchor))
        self.epsilon_tau_label.setText(f"{config.epsilon_tau:.6f}")
        self.b_mapping_label.setText("Phi_B(k_current)")
        self.s_zero_label.setText("P=1、tauなし")
        self.s_one_label.setText("P=p_i")
        self.chart.set_config(config)

    def update_diagnostics(self, engine_snapshot: EngineSnapshot) -> None:
        """Read only immutable Digital Life state and records."""

        snapshot = self._component.snapshot()
        first_round_records = self._component.first_round_records()
        evaluation_records = self._component.evaluation_update_records()
        self._update_cards(snapshot)

        previous_signal_rows = self.signal_model.rowCount()
        previous_evaluation_rows = self.evaluation_model.rowCount()
        self.signal_model.set_records(first_round_records)
        self.evaluation_model.set_records(evaluation_records)
        self.chart.set_records(first_round_records, engine_snapshot.current_time_us)
        if self.signal_model.rowCount() > previous_signal_rows:
            self.signal_table.scrollToBottom()
        if self.evaluation_model.rowCount() > previous_evaluation_rows:
            self.evaluation_table.scrollToBottom()
        self.export_first_round_button.setEnabled(bool(first_round_records))
        self.export_evaluation_button.setEnabled(bool(evaluation_records))
        self.set_role_editable(engine_snapshot.state is ClockState.STOPPED)

    def reset_views(self) -> None:
        self.signal_model.clear()
        self.evaluation_model.clear()
        self.chart.clear()
        self._update_cards(self._component.snapshot())
        self.export_first_round_button.setEnabled(False)
        self.export_evaluation_button.setEnabled(False)

    def set_role_editable(self, editable: bool) -> None:
        self.role_combo.setEnabled(editable)

    def _update_cards(self, snapshot) -> None:
        self.life_id_label.setText(snapshot.digital_life_id)
        self.role_label.setText(snapshot.role)
        self.p_intrinsic_label.setText(self._format_number(snapshot.p_intrinsic))
        self.birth_phase_label.setText(self._format_number(snapshot.birth_phase))
        self.n_label.setText(self._format_number(snapshot.n_current))
        self.baseline_n_label.setText(
            self._format_number(snapshot.n_baseline_session)
        )
        self.nd_label.setText(self._format_number(snapshot.nd))
        self.w_label.setText(self._format_number(snapshot.w))
        self.p_label.setText(self._format_number(snapshot.p))
        self.e_label.setText(self._format_number(snapshot.e))
        self.q_label.setText(self._format_number(snapshot.q))
        self.v_label.setText(self._format_number(snapshot.v))
        self.k_anchor_label.setText(self._format_vector(snapshot.k_anchor))
        self.k_current_label.setText(self._format_vector(snapshot.k_current))
        self.b_label.setText(self._format_vector(snapshot.b))
        self.tau_label.setText(self._format_number(snapshot.tau))
        self.s_label.setText("—" if snapshot.latest_s is None else str(snapshot.latest_s))
        self.revision_label.setText(str(snapshot.last_revision))
        self.latest_evaluation_label.setText(
            snapshot.latest_evaluation_id or "—"
        )
        self.g_label.setText(
            "未接続" if snapshot.g_status == "not_connected" else snapshot.g_status
        )
        self.second_round_label.setText(
            "接続済み" if snapshot.second_round_connected else "未実装"
        )
        self.touch_dispatch_label.setText(
            "未実行"
            if snapshot.touch_dispatched_count == 0
            else f"{snapshot.touch_dispatched_count} 件"
        )

    def _role_changed(self, _index: int) -> None:
        role = self.role_combo.currentData()
        if role is not None:
            self.role_selected.emit(str(role))

    def _export_first_round_clicked(self) -> None:
        records = self._component.first_round_records()
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "デジタル生命・第1周signal CSVを保存",
            FIRST_ROUND_CSV_FILENAME,
            "CSV (*.csv)",
        )
        if destination:
            export_first_round_diagnostics_csv(destination, records)

    def _export_evaluation_clicked(self) -> None:
        records = self._component.evaluation_update_records()
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "デジタル生命・評価更新CSVを保存",
            EVALUATION_UPDATE_CSV_FILENAME,
            "CSV (*.csv)",
        )
        if destination:
            export_evaluation_updates_csv(destination, records)

    @staticmethod
    def _configure_table(table: QTableView, model) -> None:
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

    @staticmethod
    def _fixed_value(form: QFormLayout, caption: str) -> QLabel:
        value = QLabel("—")
        value.setObjectName("digitalLifeFixedValue")
        value.setMinimumWidth(0)
        value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
        value_label.setWordWrap(True)
        card_layout.addWidget(caption_label)
        card_layout.addWidget(value_label)
        layout.addWidget(card, row, column)
        return value_label

    @staticmethod
    def _format_number(value: float | None) -> str:
        if value is None:
            return "—"
        if value != 0.0 and abs(value) < 0.000001:
            return f"{value:.6e}"
        return f"{value:.6f}"

    @classmethod
    def _format_vector(cls, values) -> str:
        return "[" + ", ".join(cls._format_number(value) for value in values) + "]"
