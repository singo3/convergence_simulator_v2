"""Scrollable single-condition surface for the Stage 8A.1 lab."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import (
    first_record_value,
    record_value,
)
from symbiotic_sim_v2.gui.fatigue_trajectory_chart import FatigueTrajectoryChart
from symbiotic_sim_v2.gui.session_bpm_hue_chart import SessionBpmHueChart
from symbiotic_sim_v2.gui.sigma_trajectory_chart import SigmaTrajectoryChart

DEFAULT_V2_USER_TYPES = (
    "green_hue_dominant_broad_bpm",
    "bpm_common_100_hue_neutral",
    "three_life_bpm_equal",
    "three_life_bpm_green_dominant",
    "green_single_peak_narrow",
    "flat_control",
)
DEFAULT_V2_USER_TYPE = DEFAULT_V2_USER_TYPES[0]
DEFAULT_MASTER_SEED = 20_260_802
SINGLE_CHART_SPLITTER_MIN_HEIGHT = 1_420


class FatigueSigmaSingleRunPanel(QWidget):
    """Emit immutable settings and display core-supplied Stage 8A.1 records."""

    run_next_requested = Signal(object)
    run_all_requested = Signal(object)
    pause_after_session_changed = Signal(bool)
    cancel_requested = Signal()
    reset_requested = Signal()
    reference_compare_requested = Signal(object)
    save_state_requested = Signal(object)
    load_state_requested = Signal(object)
    export_csv_requested = Signal(object)
    settings_changed = Signal(object)

    def __init__(
        self,
        user_types: Mapping[str, object] | Sequence[str] = DEFAULT_V2_USER_TYPES,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_types = _user_type_mapping(user_types)
        self._run_active = False
        self._completed_sessions = 0
        self._backend_available = True
        self._build_ui()
        self._connect_ui()
        self.reset_views()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("stage8a1SingleConditionScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("stage8a1SingleConditionContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(5, 5, 5, 5)
        content.setSpacing(8)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.boundary_notice = _notice(
            "Stage 8A.1 experimental arm: formal_spec_adoption=false。"
            "非選出全回復とsigma倍率は実験policyで、v2.0 reference armと分離します。",
            "stage8a1BoundaryNotice",
            self.diagnostics_content,
        )
        content.addWidget(self.boundary_notice)
        self.settings_frame = self._build_settings()
        content.addWidget(self.settings_frame)
        self.profile_frame = self._build_profile_summary()
        content.addWidget(self.profile_frame)
        self.operations_frame = self._build_operations()
        content.addWidget(self.operations_frame)
        self.cards_frame = self._build_cards()
        content.addWidget(self.cards_frame)

        self.chart_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_splitter.setObjectName("stage8a1SingleChartSplitter")
        self.chart_splitter.setMinimumHeight(SINGLE_CHART_SPLITTER_MIN_HEIGHT)
        self.session_chart = SessionBpmHueChart(self.chart_splitter)
        self.trajectory_splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.chart_splitter,
        )
        self.trajectory_splitter.setObjectName("stage8a1FatigueSigmaTrajectorySplitter")
        self.fatigue_chart = FatigueTrajectoryChart(self.trajectory_splitter)
        self.sigma_chart = SigmaTrajectoryChart(self.trajectory_splitter)
        self.trajectory_splitter.addWidget(self.fatigue_chart)
        self.trajectory_splitter.addWidget(self.sigma_chart)
        self.trajectory_splitter.setCollapsible(0, False)
        self.trajectory_splitter.setCollapsible(1, False)
        self.trajectory_splitter.setSizes([750, 750])
        self.chart_splitter.addWidget(self.session_chart)
        self.chart_splitter.addWidget(self.trajectory_splitter)
        self.chart_splitter.setCollapsible(0, False)
        self.chart_splitter.setCollapsible(1, False)
        self.chart_splitter.setSizes([680, 700])
        content.addWidget(self.chart_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        root.addWidget(self.diagnostics_scroll)
        self.setStyleSheet(
            """
            QLabel#stage8a1BoundaryNotice {
                background: #FFF7E6; border: 1px solid #F5D28A;
                border-radius: 6px; color: #6B4B16; padding: 8px 10px;
            }
            QFrame#stage8a1SingleSettings,
            QFrame#stage8a1SingleOperations,
            QFrame#stage8a1SingleCards,
            QFrame#stage8a1ProfileSummary {
                background: #F8FAFC; border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
            QLabel#stage8a1CardCaption { color: #64748B; font-size: 10px; }
            QLabel#stage8a1CardValue { color: #172033; font-weight: 700; }
            """
        )

    def _build_settings(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("stage8a1SingleSettings")
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        self.user_type_combo = QComboBox(frame)
        self.user_type_combo.setObjectName("stage8a1UserTypeCombo")
        for user_type_id, profile in self._user_types.items():
            display = first_record_value(
                profile,
                ("display_name_ja", "display_name"),
                user_type_id,
            )
            self.user_type_combo.addItem(f"{display} ({user_type_id})", user_type_id)
        self.fatigue_target_spin = _double_spin(frame, 0.0, 0.20, 0.05, 3, 0.01)
        self.fatigue_target_spin.setObjectName("stage8a1FatigueTargetSpin")
        self.sigma_multiplier_spin = _double_spin(frame, 0.25, 1.50, 1.0, 2, 0.05)
        self.sigma_multiplier_spin.setObjectName("stage8a1SigmaMultiplierSpin")
        self.session_preset_combo = QComboBox(frame)
        self.session_preset_combo.setObjectName("stage8a1SessionPresetCombo")
        for label, value in (
            ("12 sessions — 短期傾向", 12),
            ("24 sessions — 標準", 24),
            ("60 sessions — 長期", 60),
            ("custom", None),
        ):
            self.session_preset_combo.addItem(label, value)
        self.session_preset_combo.setCurrentIndex(1)
        self.maximum_sessions_spin = QSpinBox(frame)
        self.maximum_sessions_spin.setObjectName("stage8a1MaximumSessionsSpin")
        self.maximum_sessions_spin.setRange(4, 100)
        self.maximum_sessions_spin.setValue(24)
        self.master_seed_spin = QDoubleSpinBox(frame)
        self.master_seed_spin.setObjectName("stage8a1MasterSeedSpin")
        self.master_seed_spin.setDecimals(0)
        self.master_seed_spin.setRange(0.0, 4_294_967_295.0)
        self.master_seed_spin.setValue(float(DEFAULT_MASTER_SEED))
        self.compare_reference_checkbox = QCheckBox("reference arm比較", frame)
        self.compare_reference_checkbox.setObjectName("stage8a1CompareReferenceCheck")

        fields = (
            ("固定仮想ユーザータイプ", self.user_type_combo),
            ("選出時1セッション疲労蓄積率", self.fatigue_target_spin),
            ("探索幅倍率", self.sigma_multiplier_spin),
            ("セッションpreset", self.session_preset_combo),
            ("セッション数", self.maximum_sessions_spin),
            ("master seed", self.master_seed_spin),
            ("比較", self.compare_reference_checkbox),
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

    def _build_profile_summary(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("stage8a1ProfileSummary")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        self.profile_summary_label = QLabel("", frame)
        self.profile_summary_label.setObjectName("stage8a1ProfileSummaryLabel")
        self.profile_summary_label.setWordWrap(True)
        self.hidden_truth_notice = QLabel(
            "この地図はシミュレーターだけが知る固定された隠れた反応傾向で、"
            "Digital Life、Runtime、Gardenの探索計算には入力されません。",
            frame,
        )
        self.hidden_truth_notice.setObjectName("stage8a1HiddenTruthNotice")
        self.hidden_truth_notice.setWordWrap(True)
        layout.addWidget(self.profile_summary_label)
        layout.addWidget(self.hidden_truth_notice)
        self._refresh_profile_summary()
        return frame

    def _build_operations(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("stage8a1SingleOperations")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        row = QHBoxLayout()
        self.next_button = QPushButton("次の1session", frame)
        self.next_button.setObjectName("stage8a1NextSessionButton")
        self.run_all_button = QPushButton("最後まで実行", frame)
        self.run_all_button.setObjectName("stage8a1RunAllButton")
        self.pause_button = QPushButton("session完了後pause", frame)
        self.pause_button.setObjectName("stage8a1PauseAfterSessionButton")
        self.pause_button.setCheckable(True)
        self.cancel_button = QPushButton("安全境界でcancel", frame)
        self.cancel_button.setObjectName("stage8a1SingleCancelButton")
        self.reset_button = QPushButton("reset", frame)
        self.reset_button.setObjectName("stage8a1ResetButton")
        self.reference_button = QPushButton("reference比較", frame)
        self.reference_button.setObjectName("stage8a1ReferenceCompareButton")
        for button in (
            self.next_button,
            self.run_all_button,
            self.pause_button,
            self.cancel_button,
            self.reset_button,
            self.reference_button,
        ):
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        io_row = QHBoxLayout()
        self.save_state_button = QPushButton("state JSON保存", frame)
        self.save_state_button.setObjectName("stage8a1SaveStateButton")
        self.load_state_button = QPushButton("state JSON読込", frame)
        self.load_state_button.setObjectName("stage8a1LoadStateButton")
        self.export_csv_button = QPushButton("CSV保存", frame)
        self.export_csv_button.setObjectName("stage8a1ExportCsvButton")
        for button in (self.save_state_button, self.load_state_button, self.export_csv_button):
            io_row.addWidget(button)
        io_row.addStretch(1)
        layout.addLayout(io_row)
        progress_row = QHBoxLayout()
        self.progress_label = QLabel("停止", frame)
        self.progress_label.setObjectName("stage8a1SingleProgressLabel")
        self.progress_bar = QProgressBar(frame)
        self.progress_bar.setObjectName("stage8a1SingleProgressBar")
        self.progress_bar.setRange(0, 24)
        progress_row.addWidget(self.progress_label)
        progress_row.addWidget(self.progress_bar, stretch=1)
        layout.addLayout(progress_row)
        return frame

    def _build_cards(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("stage8a1SingleCards")
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 9, 10, 9)
        fields = (
            ("sessions_completed", "sessions completed"),
            ("holder", "latest / dominant life"),
            ("summary", "observed structure"),
            ("truth", "truth alignment"),
            ("early", "早期の単一生命・近接パターン兆候"),
            ("mechanical", "mechanical rotation"),
            ("w_ceiling", "W ceiling"),
            ("reference", "reference arm"),
            ("digests", "trajectory / convergence digests"),
        )
        self.card_labels: dict[str, QLabel] = {}
        for index, (key, caption) in enumerate(fields):
            column = index % 3
            row = (index // 3) * 2
            caption_label = QLabel(caption, frame)
            caption_label.setObjectName("stage8a1CardCaption")
            value_label = QLabel("—", frame)
            value_label.setObjectName("stage8a1CardValue")
            value_label.setWordWrap(True)
            layout.addWidget(caption_label, row, column)
            layout.addWidget(value_label, row + 1, column)
            self.card_labels[key] = value_label
        return frame

    def _connect_ui(self) -> None:
        for widget in self.settings_widgets:
            signal = (
                widget.currentIndexChanged
                if isinstance(widget, QComboBox)
                else (widget.toggled if isinstance(widget, QCheckBox) else widget.valueChanged)
            )
            signal.connect(self._settings_changed)
        self.user_type_combo.currentIndexChanged.connect(self._refresh_profile_summary)
        self.session_preset_combo.currentIndexChanged.connect(self._session_preset_changed)
        self.maximum_sessions_spin.valueChanged.connect(self._session_count_changed)
        self.next_button.clicked.connect(self._request_next)
        self.run_all_button.clicked.connect(self._request_all)
        self.pause_button.toggled.connect(self.pause_after_session_changed)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.reset_button.clicked.connect(self.reset_requested)
        self.reference_button.clicked.connect(self._request_reference)
        self.save_state_button.clicked.connect(self._choose_save_state)
        self.load_state_button.clicked.connect(self._choose_load_state)
        self.export_csv_button.clicked.connect(self._choose_csv_root)

    def settings_values(self) -> dict[str, object]:
        return {
            "user_type_id": self.user_type_combo.currentData(),
            "selected_session_fatigue_target": self.fatigue_target_spin.value(),
            "unselected_session_end_recovery_fraction": 1.0,
            "sigma_multiplier": self.sigma_multiplier_spin.value(),
            "maximum_sessions": self.maximum_sessions_spin.value(),
            "master_seed": int(self.master_seed_spin.value()),
            "compare_reference_arm": self.compare_reference_checkbox.isChecked(),
        }

    def set_result(self, result: object) -> None:
        pattern_records = (
            first_record_value(
                result,
                ("session_pattern_trajectory", "session_pattern_records", "session_outcomes"),
                (),
            )
            or ()
        )
        fatigue_records = (
            first_record_value(
                result,
                ("fatigue_trajectory", "fatigue_trajectory_records"),
                (),
            )
            or ()
        )
        sigma_records = (
            first_record_value(
                result,
                ("sigma_trajectory", "sigma_trajectory_records"),
                (),
            )
            or ()
        )
        completed = int(
            first_record_value(
                result,
                ("sessions_completed", "completed_session_count"),
                len(tuple(pattern_records)),
            )
            or 0
        )
        self._completed_sessions = completed
        self.session_chart.set_maximum_sessions(self.maximum_sessions_spin.value())
        self.session_chart.set_records(tuple(pattern_records))
        self.fatigue_chart.set_records(
            tuple(fatigue_records),
            selected_fatigue_target=self.fatigue_target_spin.value(),
        )
        self.sigma_chart.set_records(tuple(sigma_records))
        self.progress_bar.setRange(0, self.maximum_sessions_spin.value())
        self.progress_bar.setValue(min(completed, self.maximum_sessions_spin.value()))
        structured = first_record_value(
            result,
            ("structured_convergence", "latest_structured_convergence"),
            result,
        )
        truth = first_record_value(result, ("truth_alignment", "latest_truth_alignment"), result)
        mechanical = first_record_value(
            result,
            ("mechanical_rotation_diagnostics",),
            result,
        )
        w_ceiling = first_record_value(result, ("w_ceiling_diagnostics",), result)
        self.card_labels["sessions_completed"].setText(str(completed))
        self.card_labels["holder"].setText(
            str(first_record_value(structured, ("dominant_life_id", "holder_id"), "—"))
        )
        self.card_labels["summary"].setText(
            str(
                first_record_value(
                    structured, ("summary_classification", "observed_structure"), "—"
                )
            )
        )
        self.card_labels["truth"].setText(
            str(first_record_value(truth, ("truth_classification", "classification"), "—"))
        )
        self.card_labels["early"].setText(
            _yes_no(first_record_value(structured, ("early_single_life_pattern_signal",), None))
        )
        self.card_labels["mechanical"].setText(
            str(first_record_value(mechanical, ("classification", "warning"), "—"))
        )
        self.card_labels["w_ceiling"].setText(
            str(first_record_value(w_ceiling, ("classification",), "—"))
        )
        reference = first_record_value(result, ("reference_arm_metadata", "reference_arm"), None)
        reference_enabled = first_record_value(reference, ("enabled",), False)
        reference_result = first_record_value(result, ("reference_arm_result",), None)
        if reference_enabled is True and reference_result is not None:
            reference_history = tuple(
                first_record_value(
                    reference_result,
                    ("structured_convergence_history",),
                    (),
                )
                or ()
            )
            reference_latest = reference_history[-1] if reference_history else None
            reference_truth_history = tuple(
                first_record_value(reference_result, ("truth_alignment_history",), ())
                or ()
            )
            reference_truth = (
                reference_truth_history[-1] if reference_truth_history else None
            )
            reference_w = first_record_value(
                reference_result,
                ("w_ceiling_diagnostics",),
                {},
            )
            self.card_labels["reference"].setText(
                "paired complete | observed="
                f"{first_record_value(reference_latest, ('summary_classification',), '—')} | "
                "truth="
                f"{first_record_value(reference_truth, ('truth_classification',), '—')} | "
                "W="
                f"{first_record_value(reference_w, ('classification',), '—')} | "
                "digest="
                f"{str(first_record_value(reference_result, ('digest',), '—'))[:12]}"
            )
        else:
            self.card_labels["reference"].setText(
                "available / not run" if reference is not None else "not available"
            )
        digests = []
        for name in (
            "fatigue_trajectory_digest",
            "sigma_trajectory_digest",
            "structured_convergence_digest",
        ):
            value = record_value(result, name)
            if value is not None:
                digests.append(f"{name.removesuffix('_digest')}: {str(value)[:12]}")
        self.card_labels["digests"].setText(" / ".join(digests) or "—")
        self._update_enabled_state()

    def apply_loaded_result_settings(self, result: object) -> None:
        """Synchronize widgets to an authoritative state JSON before locking."""

        condition = first_record_value(result, ("condition",), None)
        if condition is None:
            raise ValueError("loaded Stage 8A.1 result has no condition")
        user_type_id = first_record_value(condition, ("user_type_id",))
        user_index = self.user_type_combo.findData(user_type_id)
        if user_index < 0:
            raise ValueError("loaded Stage 8A.1 state has an unknown user type")
        fatigue_target = first_record_value(
            condition,
            ("selected_session_fatigue_target",),
        )
        sigma_multiplier = first_record_value(condition, ("sigma_multiplier",))
        maximum_sessions = first_record_value(condition, ("maximum_sessions",))
        master_seed = first_record_value(condition, ("master_seed",))
        reference = first_record_value(result, ("reference_arm_metadata",), {})
        reference_enabled = first_record_value(reference, ("enabled",), False)
        blockers = tuple(QSignalBlocker(widget) for widget in self.settings_widgets)
        try:
            self.user_type_combo.setCurrentIndex(user_index)
            self.fatigue_target_spin.setValue(float(fatigue_target))
            self.sigma_multiplier_spin.setValue(float(sigma_multiplier))
            self.maximum_sessions_spin.setValue(int(maximum_sessions))
            self.master_seed_spin.setValue(int(master_seed))
            self.compare_reference_checkbox.setChecked(reference_enabled is True)
        finally:
            del blockers
        self._session_count_changed(self.maximum_sessions_spin.value())
        self._refresh_profile_summary()

    def set_progress(self, progress: object) -> None:
        completed = first_record_value(
            progress,
            ("completed_session_runs", "completed_sessions", "completed"),
            self.progress_bar.value(),
        )
        total = first_record_value(
            progress,
            ("total_planned_session_runs", "total_sessions", "total"),
            self.progress_bar.maximum(),
        )
        if isinstance(total, int) and not isinstance(total, bool) and total > 0:
            self.progress_bar.setRange(0, total)
        if isinstance(completed, int) and not isinstance(completed, bool):
            self.progress_bar.setValue(max(0, min(completed, self.progress_bar.maximum())))
        self.progress_label.setText(
            str(first_record_value(progress, ("message", "status"), "実行中"))
        )

    def set_operation_active(self, active: bool) -> None:
        self._run_active = bool(active)
        self.progress_label.setText("実行中" if active else "停止")
        self._update_enabled_state()

    def set_backend_available(self, available: bool) -> None:
        self._backend_available = bool(available)
        self._update_enabled_state()

    def reset_views(self) -> None:
        self._completed_sessions = 0
        self.session_chart.clear()
        self.fatigue_chart.clear()
        self.sigma_chart.clear()
        self.progress_bar.setRange(0, self.maximum_sessions_spin.value())
        self.progress_bar.setValue(0)
        self.progress_label.setText("停止")
        for label in self.card_labels.values():
            label.setText("—")
        self.card_labels["sessions_completed"].setText("0")
        self._update_enabled_state()

    def _settings_changed(self, *_args: object) -> None:
        if not self._run_active and self._completed_sessions == 0:
            self.settings_changed.emit(self.settings_values())

    def _session_preset_changed(self, _index: int) -> None:
        value = self.session_preset_combo.currentData()
        if isinstance(value, int):
            with QSignalBlocker(self.maximum_sessions_spin):
                self.maximum_sessions_spin.setValue(value)
            self.session_chart.set_maximum_sessions(value)
            self.progress_bar.setRange(0, value)

    def _session_count_changed(self, value: int) -> None:
        preset_index = self.session_preset_combo.findData(value)
        if preset_index < 0:
            preset_index = self.session_preset_combo.findData(None)
        with QSignalBlocker(self.session_preset_combo):
            self.session_preset_combo.setCurrentIndex(preset_index)
        self.session_chart.set_maximum_sessions(value)
        if self._completed_sessions == 0:
            self.progress_bar.setRange(0, value)

    def _refresh_profile_summary(self, *_args: object) -> None:
        profile = self._user_types.get(self.user_type_combo.currentData())
        user_type_id = self.user_type_combo.currentData()
        expected = first_record_value(profile, ("expected_structure",), "diagnostic assumption")
        peaks = tuple(first_record_value(profile, ("peaks",), ()) or ())
        self.profile_summary_label.setText(
            f"user type: {user_type_id}  |  expected structure: {expected}  |  "
            f"peak count: {len(peaks)}  |  stationary_preference=true / moving_preference=false"
        )

    def _request_next(self) -> None:
        self._lock_for_request()
        self.run_next_requested.emit(self.settings_values())

    def _request_all(self) -> None:
        self._lock_for_request()
        self.run_all_requested.emit(self.settings_values())

    def _request_reference(self) -> None:
        self._lock_for_request()
        self.reference_compare_requested.emit(self.settings_values())

    def _lock_for_request(self) -> None:
        self._run_active = True
        self._update_enabled_state()

    def _update_enabled_state(self) -> None:
        editable = not self._run_active and self._completed_sessions == 0
        for widget in self.settings_widgets:
            widget.setEnabled(editable)
        can_run = self._backend_available and not self._run_active
        maximum = self.maximum_sessions_spin.value()
        self.next_button.setEnabled(can_run and self._completed_sessions < maximum)
        self.run_all_button.setEnabled(can_run and self._completed_sessions < maximum)
        self.reference_button.setEnabled(can_run)
        self.pause_button.setEnabled(
            self._backend_available and (self._run_active or self._completed_sessions < maximum)
        )
        self.cancel_button.setEnabled(self._backend_available and self._run_active)
        self.reset_button.setEnabled(self._backend_available and not self._run_active)
        self.save_state_button.setEnabled(
            self._backend_available and not self._run_active and self._completed_sessions > 0
        )
        self.load_state_button.setEnabled(self._backend_available and not self._run_active)
        self.export_csv_button.setEnabled(
            self._backend_available and not self._run_active and self._completed_sessions > 0
        )

    def _choose_save_state(self) -> None:
        destination, _filter = QFileDialog.getSaveFileName(
            self,
            "Stage 8A.1 experiment state JSONを保存",
            "stage-08a1-experiment-state.json",
            "JSON (*.json)",
        )
        if destination:
            self.save_state_requested.emit(Path(destination))

    def _choose_load_state(self) -> None:
        source, _filter = QFileDialog.getOpenFileName(
            self,
            "Stage 8A.1 experiment state JSONを読込",
            "",
            "JSON (*.json)",
        )
        if source:
            self.load_state_requested.emit(Path(source))

    def _choose_csv_root(self) -> None:
        destination = QFileDialog.getExistingDirectory(self, "Stage 8A.1 CSV保存先")
        if destination:
            self.export_csv_requested.emit(Path(destination))


def _user_type_mapping(
    values: Mapping[str, object] | Sequence[str],
) -> dict[str, object]:
    if isinstance(values, Mapping):
        return dict(values)
    return {str(value): {"user_type_id": str(value)} for value in values}


def _double_spin(
    parent: QWidget,
    minimum: float,
    maximum: float,
    value: float,
    decimals: int,
    step: float,
) -> QDoubleSpinBox:
    spin = QDoubleSpinBox(parent)
    spin.setDecimals(decimals)
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setValue(value)
    return spin


def _notice(text: str, name: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _yes_no(value: object) -> str:
    if value is None:
        return "—"
    return "yes" if bool(value) else "no"


__all__ = [
    "DEFAULT_MASTER_SEED",
    "DEFAULT_V2_USER_TYPE",
    "DEFAULT_V2_USER_TYPES",
    "FatigueSigmaSingleRunPanel",
    "SINGLE_CHART_SPLITTER_MIN_HEIGHT",
]
