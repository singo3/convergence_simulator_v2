"""Scrollable Stage 8A multi-session controls and diagnostic projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.convergence_history_table_model import (
    ConvergenceHistoryTableModel,
)
from symbiotic_sim_v2.gui.multi_session_convergence_chart import (
    MultiSessionConvergenceChart,
)
from symbiotic_sim_v2.gui.session_history_table_model import (
    SessionHistoryTableModel,
    convergence_record_index,
    first_record_value,
    record_value,
    truth_value,
)
from symbiotic_sim_v2.gui.user_type_comparison_table_model import (
    UserTypeComparisonTableModel,
)

MULTI_SESSION_TABLE_MIN_HEIGHT = 300
MULTI_SESSION_TABLE_TABS_MIN_HEIGHT = 360
MULTI_SESSION_CHART_TABLE_SPLITTER_MIN_HEIGHT = 2_250
DEFAULT_USER_TYPE_ID = "green_narrow_moderate"
DEFAULT_MASTER_SEED = 20_260_802
DEFAULT_SEED_POLICY = "deterministic_per_session_physiology_seed_v0_1"
REPEAT_SEED_POLICY = "repeat_same_physiology_seed_v0_1"

EXPLANATIONS = (
    "収束とは探索停止ではなく、同じDigital Lifeと近しい点滅パターンが"
    "ローリング履歴の多数を占める状態です。",
    "1セッション中の3Bundleは同じ資格生命を共有するため、一次収束判定では"
    "完了セッションを独立単位として使います。",
    "収束後もp_explore_minとσ_minによる探索は継続します。",
    "仮想ユーザーの好みはこのrun中に変化しません。",
)


class MultiSessionConvergencePanel(QWidget):
    """Expose operations as signals and render records supplied by a runner."""

    settings_changed = Signal(object)
    next_session_requested = Signal(object)
    run_all_requested = Signal(object)
    pause_after_current_changed = Signal(bool)
    compare_all_requested = Signal(object)
    reset_requested = Signal()
    save_state_requested = Signal(object)
    load_state_requested = Signal(object)
    export_csv_requested = Signal(object)

    def __init__(
        self,
        user_types: Mapping[str, Any] | Sequence[str] | Sequence[Any],
        parent: QWidget | None = None,
        *,
        convergence_config: Any | None = None,
        selected_user_type_id: str = DEFAULT_USER_TYPE_ID,
        master_seed: int = DEFAULT_MASTER_SEED,
        seed_policy: str = DEFAULT_SEED_POLICY,
    ) -> None:
        super().__init__(parent)
        self._user_types = _user_type_mapping(user_types)
        self._run_active = False
        self._completed_session_count = 0
        self._build_ui()
        self.set_settings(
            convergence_config,
            selected_user_type_id=selected_user_type_id,
            master_seed=master_seed,
            seed_policy=seed_policy,
        )
        self.reset_views()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("multiSessionConvergenceDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("multiSessionConvergenceDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(4, 4, 4, 4)
        content.setSpacing(8)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.explanation_labels: list[QLabel] = []
        for index, text in enumerate(EXPLANATIONS):
            label = _notice(
                text,
                "multiSessionConvergenceDescription"
                if index == 0
                else "multiSessionConvergenceBoundaryNotice",
                self.diagnostics_content,
            )
            self.explanation_labels.append(label)
            content.addWidget(label)

        self.settings_frame = self._build_settings_frame()
        content.addWidget(self.settings_frame)
        self.operations_frame = self._build_operations_frame()
        content.addWidget(self.operations_frame)
        self.state_cards_frame = self._build_state_cards()
        content.addWidget(self.state_cards_frame)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("multiSessionChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(
            MULTI_SESSION_CHART_TABLE_SPLITTER_MIN_HEIGHT
        )
        self.chart = MultiSessionConvergenceChart(
            self.chart_table_splitter,
            maximum_sessions=self.maximum_sessions_spin.value(),
        )
        self.table_tabs = self._build_table_tabs()
        self.chart_table_splitter.addWidget(self.chart)
        self.chart_table_splitter.addWidget(self.table_tabs)
        self.chart_table_splitter.setCollapsible(0, False)
        self.chart_table_splitter.setCollapsible(1, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 0)
        self.chart_table_splitter.setSizes([1_850, 400])
        content.addWidget(self.chart_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self.chart.graphics.viewport().installEventFilter(self)
        root.addWidget(self.diagnostics_scroll, stretch=1)
        self._connect_ui()
        self.setStyleSheet(
            """
                QLabel#multiSessionConvergenceDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5;
                    border-radius: 6px; color: #234A75; padding: 7px 10px;
                }
                QLabel#multiSessionConvergenceBoundaryNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A;
                    border-radius: 6px; color: #6B4B16; padding: 7px 10px;
                }
                QFrame#multiSessionSettingsFrame,
                QFrame#multiSessionOperationsFrame,
                QFrame#multiSessionStateCardsFrame {
                    background: #F8FAFC; border: 1px solid #CBD5E1;
                    border-radius: 8px;
                }
                QLabel#multiSessionStateCaption { color: #64748B; font-size: 10px; }
                QLabel#multiSessionStateValue { color: #172033; font-weight: 700; }
            """
        )

    def _build_settings_frame(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("multiSessionSettingsFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        heading = QLabel("固定user type / rolling convergence設定", frame)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(5)

        self.user_type_combo = QComboBox(frame)
        self.user_type_combo.setObjectName("multiSessionUserTypeCombo")
        for user_type_id, profile in self._user_types.items():
            display = first_record_value(
                profile,
                ("display_name_ja", "display_name"),
                user_type_id,
            )
            self.user_type_combo.addItem(f"{display} ({user_type_id})", user_type_id)

        self.maximum_sessions_spin = QSpinBox(frame)
        self.maximum_sessions_spin.setObjectName("multiSessionMaximumSessionsSpin")
        self.maximum_sessions_spin.setRange(4, 1_000)
        self.maximum_sessions_spin.setValue(24)
        # QSpinBox is signed-int limited, while the deterministic seed contract
        # is the full uint32 range. A zero-decimal double spin preserves every
        # integer exactly and avoids silent clamping on state load.
        self.master_seed_spin = QDoubleSpinBox(frame)
        self.master_seed_spin.setObjectName("multiSessionMasterSeedSpin")
        self.master_seed_spin.setDecimals(0)
        self.master_seed_spin.setRange(0.0, 4_294_967_295.0)
        self.master_seed_spin.setValue(float(DEFAULT_MASTER_SEED))
        self.seed_policy_combo = QComboBox(frame)
        self.seed_policy_combo.setObjectName("multiSessionSeedPolicyCombo")
        self.seed_policy_combo.addItem("sessionごとに決定論的に変更", DEFAULT_SEED_POLICY)
        self.seed_policy_combo.addItem("全sessionで同じseed", REPEAT_SEED_POLICY)

        self.window_spin = QSpinBox(frame)
        self.window_spin.setObjectName("convergenceWindowSpin")
        self.window_spin.setRange(2, 12)
        self.window_spin.setValue(4)
        self.required_spin = QSpinBox(frame)
        self.required_spin.setObjectName("convergenceRequiredSpin")
        self.required_spin.setRange(2, 4)
        self.required_spin.setValue(3)
        self.hue_tolerance_spin = _double_spin(frame, 0.001, 180.0, 2.0, 3)
        self.hue_tolerance_spin.setObjectName("convergenceHueToleranceSpin")
        self.bpm_tolerance_spin = _double_spin(frame, 0.001, 500.0, 20.0, 3)
        self.bpm_tolerance_spin.setObjectName("convergenceBpmToleranceSpin")
        self.truth_gap_spin = _double_spin(frame, 0.0, 1.0, 0.05, 4)
        self.truth_gap_spin.setObjectName("truthResponseGapThresholdSpin")

        fields = (
            ("user type", self.user_type_combo),
            ("maximum sessions", self.maximum_sessions_spin),
            ("master seed", self.master_seed_spin),
            ("session physiology seed policy", self.seed_policy_combo),
            ("convergence window M", self.window_spin),
            ("required K", self.required_spin),
            ("Hue tolerance", self.hue_tolerance_spin),
            ("BPM tolerance", self.bpm_tolerance_spin),
            ("truth gap threshold", self.truth_gap_spin),
        )
        for index, (caption, widget) in enumerate(fields):
            column = 0 if index < 5 else 2
            row = index if index < 5 else index - 5
            form.addWidget(QLabel(caption, frame), row, column)
            form.addWidget(widget, row, column + 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        layout.addLayout(form)
        self.settings_notice = _notice(
            "設定はstopped / reset時だけ変更できます。Mは12以下に制限します。",
            "multiSessionSettingsNotice",
            frame,
        )
        layout.addWidget(self.settings_notice)
        return frame

    def _build_operations_frame(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("multiSessionOperationsFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        buttons = QHBoxLayout()
        self.next_session_button = QPushButton("次の1セッションを実行", frame)
        self.next_session_button.setObjectName("runNextSessionButton")
        self.run_all_button = QPushButton("残りを最後まで実行", frame)
        self.run_all_button.setObjectName("runAllSessionsButton")
        self.pause_after_session_button = QPushButton(
            "現在session完了後に一時停止",
            frame,
        )
        self.pause_after_session_button.setObjectName("pauseAfterCurrentSessionButton")
        self.pause_after_session_button.setCheckable(True)
        self.compare_all_button = QPushButton("全タイプ比較", frame)
        self.compare_all_button.setObjectName("compareAllUserTypesButton")
        self.reset_button = QPushButton("全reset", frame)
        self.reset_button.setObjectName("resetMultiSessionButton")
        for button in (
            self.next_session_button,
            self.run_all_button,
            self.pause_after_session_button,
            self.compare_all_button,
            self.reset_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        io_buttons = QHBoxLayout()
        self.save_state_button = QPushButton("run state JSON保存", frame)
        self.save_state_button.setObjectName("saveMultiSessionStateButton")
        self.load_state_button = QPushButton("run state JSON読込", frame)
        self.load_state_button.setObjectName("loadMultiSessionStateButton")
        self.export_csv_button = QPushButton("CSV保存", frame)
        self.export_csv_button.setObjectName("exportMultiSessionCsvButton")
        for button in (
            self.save_state_button,
            self.load_state_button,
            self.export_csv_button,
        ):
            io_buttons.addWidget(button)
        io_buttons.addStretch(1)
        layout.addLayout(io_buttons)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("session progress", frame))
        self.progress_bar = QProgressBar(frame)
        self.progress_bar.setObjectName("multiSessionProgressBar")
        self.progress_bar.setRange(0, 24)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(progress_layout)
        return frame

    def _build_state_cards(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("multiSessionStateCardsFrame")
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        fields = (
            ("completed_sessions", "completed sessions"),
            ("valid_sessions", "valid sessions"),
            ("current_session", "current session"),
            ("convergence_state", "current convergence state"),
            ("first_convergence", "first convergence session"),
            ("dominant_life", "dominant Digital Life"),
            ("support", "support K / M"),
            ("cluster_pattern", "cluster Hue / BPM"),
            ("nearest_peak", "nearest hidden peak / σ distance"),
            ("latest_outlier", "latest session outlier"),
            ("truth_classification", "truth classification"),
            ("response_gap", "response gap"),
            ("explore_count", "explore count"),
            ("accepted_count", "accepted count"),
            ("outlier_rate", "post-convergence outlier rate"),
        )
        self.state_labels: dict[str, QLabel] = {}
        for index, (key, caption) in enumerate(fields):
            column = index % 4
            row = (index // 4) * 2
            caption_label = QLabel(caption, frame)
            caption_label.setObjectName("multiSessionStateCaption")
            value_label = QLabel("—", frame)
            value_label.setObjectName("multiSessionStateValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            layout.addWidget(caption_label, row, column)
            layout.addWidget(value_label, row + 1, column)
            self.state_labels[key] = value_label
        return frame

    def _build_table_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self.chart_table_splitter)
        tabs.setObjectName("multiSessionHistoryTableTabs")
        tabs.setMinimumHeight(MULTI_SESSION_TABLE_TABS_MIN_HEIGHT)

        self.session_history_model = SessionHistoryTableModel(self)
        session_page, self.session_history_table = _table_page(
            tabs,
            self.session_history_model,
            "multiSessionSessionHistoryTable",
        )
        tabs.addTab(session_page, "session history")

        self.convergence_history_model = ConvergenceHistoryTableModel(self)
        convergence_page, self.convergence_history_table = _table_page(
            tabs,
            self.convergence_history_model,
            "multiSessionConvergenceHistoryTable",
        )
        tabs.addTab(convergence_page, "convergence history")

        self.comparison_model = UserTypeComparisonTableModel(self)
        comparison_page, self.comparison_table = _table_page(
            tabs,
            self.comparison_model,
            "multiSessionUserTypeComparisonTable",
        )
        tabs.addTab(comparison_page, "user type comparison")
        return tabs

    def _connect_ui(self) -> None:
        for widget in (
            self.user_type_combo,
            self.maximum_sessions_spin,
            self.master_seed_spin,
            self.seed_policy_combo,
            self.window_spin,
            self.required_spin,
            self.hue_tolerance_spin,
            self.bpm_tolerance_spin,
            self.truth_gap_spin,
        ):
            signal = (
                widget.currentIndexChanged
                if isinstance(widget, QComboBox)
                else widget.valueChanged
            )
            signal.connect(self._settings_widget_changed)
        self.window_spin.valueChanged.connect(self._window_changed)
        self.maximum_sessions_spin.valueChanged.connect(self._maximum_sessions_changed)
        self.next_session_button.clicked.connect(self._request_next_session)
        self.run_all_button.clicked.connect(self._request_run_all)
        self.pause_after_session_button.toggled.connect(
            self.pause_after_current_changed
        )
        self.compare_all_button.clicked.connect(self._request_comparison)
        self.reset_button.clicked.connect(self.reset_requested)
        self.save_state_button.clicked.connect(self._choose_save_state)
        self.load_state_button.clicked.connect(self._choose_load_state)
        self.export_csv_button.clicked.connect(self._choose_csv_directory)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.chart.graphics.viewport() and event.type() is QEvent.Type.Wheel:
            delta = event.pixelDelta().y() or event.angleDelta().y()
            if delta:
                bar = self.diagnostics_scroll.verticalScrollBar()
                bar.setValue(bar.value() - delta)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def settings_values(self) -> dict[str, Any]:
        return {
            "stationary_user_type": self.user_type_combo.currentData(),
            "maximum_sessions": self.maximum_sessions_spin.value(),
            "master_seed": int(self.master_seed_spin.value()),
            "session_seed_policy": self.seed_policy_combo.currentData(),
            "convergence_window": self.window_spin.value(),
            "convergence_required": self.required_spin.value(),
            "hue_tolerance_degree": self.hue_tolerance_spin.value(),
            "blink_bpm_tolerance": self.bpm_tolerance_spin.value(),
            "truth_response_gap_threshold": self.truth_gap_spin.value(),
        }

    def set_settings(
        self,
        convergence_config: Any | None,
        *,
        selected_user_type_id: str,
        master_seed: int,
        seed_policy: str,
    ) -> None:
        selected = (
            selected_user_type_id
            if selected_user_type_id in self._user_types
            else next(iter(self._user_types), None)
        )
        values = (
            (self.user_type_combo, selected),
            (
                self.maximum_sessions_spin,
                record_value(convergence_config, "maximum_sessions", 24),
            ),
            (self.master_seed_spin, master_seed),
            (self.seed_policy_combo, seed_policy),
            (
                self.window_spin,
                record_value(convergence_config, "window_sessions", 4),
            ),
            (
                self.required_spin,
                record_value(convergence_config, "required_sessions", 3),
            ),
            (
                self.hue_tolerance_spin,
                record_value(convergence_config, "hue_tolerance_degree", 2.0),
            ),
            (
                self.bpm_tolerance_spin,
                record_value(convergence_config, "blink_bpm_tolerance", 20.0),
            ),
            (
                self.truth_gap_spin,
                record_value(
                    convergence_config,
                    "truth_response_gap_threshold",
                    0.05,
                ),
            ),
        )
        for widget, value in values:
            with QSignalBlocker(widget):
                if isinstance(widget, QComboBox):
                    index = widget.findData(value)
                    if index >= 0:
                        widget.setCurrentIndex(index)
                else:
                    widget.setValue(value)
        self._window_changed(self.window_spin.value())
        self._maximum_sessions_changed(self.maximum_sessions_spin.value())

    def set_state(
        self,
        state: Any,
        *,
        summary: Any | None = None,
        convergence_config: Any | None = None,
        user_profile: Any | None = None,
        comparison_rows: Sequence[Any] = (),
        truth_alignment_records: Sequence[Any] = (),
    ) -> None:
        outcomes = tuple(record_value(state, "session_outcomes", ()) or ())
        records = tuple(record_value(state, "convergence_records", ()) or ())
        truth_records = tuple(
            truth_alignment_records
            or record_value(state, "truth_alignment_records", ())
            or ()
        )
        self.session_history_model.set_records(outcomes, records, truth_records)
        self.convergence_history_model.set_records(records, truth_records)
        self.comparison_model.set_records(comparison_rows)
        selected_config = convergence_config or record_value(
            state,
            "convergence_config",
            None,
        )
        self.chart.set_records(
            outcomes,
            records,
            truth_alignment_records=truth_records,
            convergence_config=selected_config,
            user_profile=user_profile,
        )

        latest = records[-1] if records else None
        truth_by_session = {
            index: truth
            for truth in truth_records
            if (index := convergence_record_index(truth)) is not None
        }
        latest_truth = truth_by_session.get(convergence_record_index(latest), latest)
        completed = int(
            first_record_value(
                summary,
                ("completed_sessions", "completed_session_count"),
                record_value(state, "completed_session_count", len(outcomes)),
            )
        )
        valid = int(
            first_record_value(
                summary,
                ("valid_sessions", "valid_session_count"),
                record_value(
                    state,
                    "valid_session_count",
                    sum(
                        bool(record_value(outcome, "valid_for_convergence", False))
                        for outcome in outcomes
                    ),
                ),
            )
        )
        maximum = int(
            first_record_value(
                summary,
                ("maximum_sessions",),
                record_value(
                    selected_config,
                    "maximum_sessions",
                    self.maximum_sessions_spin.value(),
                ),
            )
        )
        window = int(
            record_value(
                latest,
                "window_size",
                record_value(
                    selected_config,
                    "window_sessions",
                    self.window_spin.value(),
                ),
            )
        )
        support = int(record_value(latest, "support_count", 0))
        medoid_hue = first_record_value(latest, ("medoid_hue_degree", "medoid_hue"))
        medoid_bpm = first_record_value(latest, ("medoid_blink_bpm", "medoid_bpm"))
        outlier_indices = tuple(
            record_value(latest, "outlier_session_indices", ()) or ()
        )
        latest_session_index = (
            None if not outcomes else record_value(outcomes[-1], "session_index")
        )
        latest_outlier = record_value(
            latest,
            "latest_valid_session_is_outlier",
            None,
        )
        if latest_outlier is None:
            latest_outlier = latest_session_index in outlier_indices
        explore_count = first_record_value(
            summary,
            ("explore_count",),
            sum(
                record_value(outcome, "exploration_decision") == "explore"
                for outcome in outcomes
            ),
        )
        accepted_count = first_record_value(
            summary,
            ("accepted_count",),
            sum(bool(record_value(outcome, "candidate_accepted", False)) for outcome in outcomes),
        )
        outlier_rate = first_record_value(
            summary,
            ("post_convergence_outlier_rate",),
            record_value(latest, "post_convergence_outlier_rate", None),
        )
        if outlier_rate is None:
            total_after_convergence = int(
                (record_value(latest, "post_convergence_cluster_member_count", 0) or 0)
                + (record_value(latest, "post_convergence_outlier_count", 0) or 0)
            )
            if total_after_convergence:
                outlier_rate = float(
                    record_value(latest, "post_convergence_outlier_count", 0) or 0
                ) / float(total_after_convergence)
        card_values = {
            "completed_sessions": str(completed),
            "valid_sessions": str(valid),
            "current_session": str(
                record_value(state, "next_session_index", completed)
            ),
            "convergence_state": str(
                first_record_value(
                    state,
                    ("current_convergence_state",),
                    first_record_value(latest, ("convergence_state", "state"), "—"),
                )
            ),
            "first_convergence": _text(
                record_value(state, "first_convergence_session_index")
            ),
            "dominant_life": _text(
                first_record_value(latest, ("holder_id", "dominant_holder_id"))
            ),
            "support": f"{support} / {window}",
            "cluster_pattern": _pattern(medoid_hue, medoid_bpm),
            "latest_outlier": "yes" if latest_outlier else "no",
            "truth_classification": _text(
                truth_value(
                    latest_truth,
                    "truth_classification",
                    truth_value(latest_truth, "classification"),
                )
            ),
            "response_gap": _number(truth_value(latest_truth, "response_gap")),
            "nearest_peak": _nearest_peak(latest_truth),
            "explore_count": str(explore_count),
            "accepted_count": str(accepted_count),
            "outlier_rate": (
                "—" if outlier_rate is None else f"{100.0 * float(outlier_rate):.2f}%"
            ),
        }
        for key, text in card_values.items():
            self.state_labels[key].setText(text)
        self._completed_session_count = completed
        self.progress_bar.setRange(0, maximum)
        self.progress_bar.setValue(completed)
        self.chart.set_maximum_sessions(maximum)
        self.set_run_active(False)
        self._update_operation_state(maximum)

    def set_comparison_records(self, comparison_rows: Sequence[Any]) -> None:
        self.comparison_model.set_records(comparison_rows)

    def set_run_active(self, active: bool) -> None:
        if not isinstance(active, bool):
            raise TypeError("active must be boolean")
        self._run_active = active
        self.set_settings_editable(not active and self._completed_session_count == 0)
        self._update_operation_state(self.maximum_sessions_spin.value())

    def set_settings_editable(self, editable: bool) -> None:
        if not isinstance(editable, bool):
            raise TypeError("editable must be boolean")
        for widget in (
            self.user_type_combo,
            self.maximum_sessions_spin,
            self.master_seed_spin,
            self.seed_policy_combo,
            self.window_spin,
            self.required_spin,
            self.hue_tolerance_spin,
            self.bpm_tolerance_spin,
            self.truth_gap_spin,
        ):
            widget.setEnabled(editable)

    def reset_views(self) -> None:
        self.session_history_model.clear()
        self.convergence_history_model.clear()
        self.comparison_model.clear()
        self.chart.clear()
        defaults = {
            "completed_sessions": "0",
            "valid_sessions": "0",
            "current_session": "0",
            "convergence_state": "insufficient_valid_sessions",
            "first_convergence": "—",
            "dominant_life": "—",
            "support": f"0 / {self.window_spin.value()}",
            "cluster_pattern": "—",
            "latest_outlier": "no",
            "truth_classification": "not_converged",
            "response_gap": "—",
            "nearest_peak": "—",
            "explore_count": "0",
            "accepted_count": "0",
            "outlier_rate": "—",
        }
        for key, text in defaults.items():
            self.state_labels[key].setText(text)
        self._completed_session_count = 0
        self._run_active = False
        self.progress_bar.setRange(0, self.maximum_sessions_spin.value())
        self.progress_bar.setValue(0)
        self.pause_after_session_button.setChecked(False)
        self.set_settings_editable(True)
        self._update_operation_state(self.maximum_sessions_spin.value())
        self.diagnostics_scroll.verticalScrollBar().setValue(0)

    def _settings_widget_changed(self, *_args: Any) -> None:
        if not self._run_active and self._completed_session_count == 0:
            self.settings_changed.emit(self.settings_values())

    def _window_changed(self, window: int) -> None:
        self.required_spin.setMaximum(window)
        self.maximum_sessions_spin.setMinimum(window)
        self.state_labels.get("support", QLabel()).setText(f"0 / {window}")

    def _maximum_sessions_changed(self, maximum: int) -> None:
        self.progress_bar.setMaximum(maximum)
        self.chart.set_maximum_sessions(maximum)
        self._update_operation_state(maximum)

    def _update_operation_state(self, maximum: int) -> None:
        can_continue = not self._run_active and self._completed_session_count < maximum
        self.next_session_button.setEnabled(can_continue)
        self.run_all_button.setEnabled(can_continue)
        # This is an arm switch, not an immediate pause command. It must be
        # selectable before Run All because one 240 s virtual session executes
        # synchronously between Qt event-loop turns.
        self.pause_after_session_button.setEnabled(
            self._completed_session_count < maximum
        )
        self.compare_all_button.setEnabled(not self._run_active)
        self.reset_button.setEnabled(not self._run_active)
        self.save_state_button.setEnabled(
            not self._run_active and self._completed_session_count > 0
        )
        self.load_state_button.setEnabled(not self._run_active)
        self.export_csv_button.setEnabled(
            not self._run_active and self._completed_session_count > 0
        )

    def _request_next_session(self) -> None:
        self.set_run_active(True)
        self.next_session_requested.emit(self.settings_values())

    def _request_run_all(self) -> None:
        self.set_run_active(True)
        self.run_all_requested.emit(self.settings_values())

    def _request_comparison(self) -> None:
        self.compare_all_requested.emit(self.settings_values())

    def _choose_save_state(self) -> None:
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "multi-session run state JSONを保存",
            "stage-08a-multi-session-state.json",
            "JSON (*.json)",
        )
        if destination:
            self.save_state_requested.emit(Path(destination))

    def _choose_load_state(self) -> None:
        source, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "multi-session run state JSONを読込",
            "",
            "JSON (*.json)",
        )
        if source:
            self.load_state_requested.emit(Path(source))

    def _choose_csv_directory(self) -> None:
        destination = QFileDialog.getExistingDirectory(
            self,
            "Stage 8A CSV保存先を選択",
        )
        if destination:
            self.export_csv_requested.emit(Path(destination))


def _user_type_mapping(
    values: Mapping[str, Any] | Sequence[str] | Sequence[Any],
) -> dict[str, Any]:
    if isinstance(values, Mapping):
        selected = dict(values)
    elif isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        selected = {}
        for value in values:
            user_type_id = value if isinstance(value, str) else record_value(value, "user_type_id")
            selected[str(user_type_id)] = value
    else:
        raise TypeError("user_types must be a mapping or sequence")
    if not selected:
        raise ValueError("at least one stationary user type is required")
    if any(not isinstance(key, str) or not key for key in selected):
        raise ValueError("user type IDs must be non-empty strings")
    return selected


def _table_page(
    parent: QTabWidget,
    model: Any,
    object_name: str,
) -> tuple[QWidget, QTableView]:
    page = QWidget(parent)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(4, 4, 4, 4)
    table = QTableView(page)
    table.setObjectName(object_name)
    table.setModel(model)
    table.setMinimumHeight(MULTI_SESSION_TABLE_MIN_HEIGHT)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)
    layout.addWidget(table)
    return page, table


def _double_spin(
    parent: QWidget,
    minimum: float,
    maximum: float,
    value: float,
    decimals: int,
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox(parent)
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setValue(value)
    spin.setSingleStep(10 ** (-decimals))
    return spin


def _notice(text: str, name: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _text(value: Any) -> str:
    return "—" if value is None else str(value)


def _number(value: Any) -> str:
    return "—" if value is None else f"{float(value):.6f}"


def _nearest_peak(record: Any) -> str:
    peak_id = truth_value(record, "nearest_peak_id")
    distance = truth_value(record, "distance_to_nearest_peak_center")
    if peak_id is None or distance is None:
        return "—"
    return f"{peak_id} / {float(distance):.6f} σ"


def _pattern(hue: Any, bpm: Any) -> str:
    if hue is None or bpm is None:
        return "—"
    return f"{float(hue):.3f}° / {float(bpm):.3f} BPM"


__all__ = [
    "DEFAULT_MASTER_SEED",
    "DEFAULT_SEED_POLICY",
    "DEFAULT_USER_TYPE_ID",
    "EXPLANATIONS",
    "MULTI_SESSION_CHART_TABLE_SPLITTER_MIN_HEIGHT",
    "MULTI_SESSION_TABLE_MIN_HEIGHT",
    "MULTI_SESSION_TABLE_TABS_MIN_HEIGHT",
    "MultiSessionConvergencePanel",
    "REPEAT_SEED_POLICY",
]
