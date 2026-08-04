"""Stage 8A.1 tab-first window while retaining the direct Stage 8A contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QThread, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

from symbiotic_sim_v2.gui.controller import SimulationController
from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import FatigueSigmaLabBackend
from symbiotic_sim_v2.gui.fatigue_sigma_lab_panel import FatigueSigmaLabPanel
from symbiotic_sim_v2.gui.fatigue_sigma_worker import (
    FatigueSigmaExecutionControl,
    FatigueSigmaOperationWorker,
)
from symbiotic_sim_v2.gui.multi_session_convergence_window import (
    TAB_TITLES as STAGE8A_TAB_TITLES,
)
from symbiotic_sim_v2.gui.multi_session_convergence_window import (
    MultiSessionConvergenceMainWindow,
)
from symbiotic_sim_v2.gui.stationary_user_type_v2_panel import (
    StationaryUserTypeV2Panel,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
)
from symbiotic_sim_v2.runtime.multi_session import MultiSessionRelationMemoryRunner

WINDOW_TITLE = "環境共生型デジタル生命シミュレーター v2 — 疲労・探索幅・収束条件ラボ"
TAB_TITLES = (
    "疲労・探索幅ラボ",
    STAGE8A_TAB_TITLES[1],
    STAGE8A_TAB_TITLES[0],
    *STAGE8A_TAB_TITLES[2:],
)

SCREENSHOT_TARGETS = (
    "stage-08a1-fatigue-sigma-lab-overview",
    "stage-08a1-session-bpm-hue-trajectory",
    "stage-08a1-structured-convergence-types",
    "stage-08a1-fatigue-and-sigma-trajectories",
    "stage-08a1-condition-grid-heatmap",
)


class FatigueSigmaLabMainWindow(MultiSessionConvergenceMainWindow):
    """Add one experimental tab without changing the direct Stage 8A window."""

    def __init__(
        self,
        controller: SimulationController,
        preview_simulation: AdaptiveRelationMemoryClosedLoopSimulation,
        runner: MultiSessionRelationMemoryRunner,
        *,
        lab_backend: FatigueSigmaLabBackend | None = None,
        user_types_v2: Mapping[str, object] | Sequence[str] | None = None,
        user_type_heatmaps_v2: Mapping[str, object] | None = None,
    ) -> None:
        self._lab_backend = lab_backend
        self._lab_thread: QThread | None = None
        self._lab_worker: FatigueSigmaOperationWorker | None = None
        self._lab_control: FatigueSigmaExecutionControl | None = None
        self._lab_operation_kind: str | None = None
        self._last_lab_result: object | None = None
        self._pause_prearmed = False
        self._close_pending = False
        super().__init__(controller, preview_simulation, runner)
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1560, 980)
        profiles = user_types_v2 if user_types_v2 is not None else ()
        self.fatigue_sigma_lab_panel = (
            FatigueSigmaLabPanel(parent=self.tabs)
            if not profiles
            else FatigueSigmaLabPanel(profiles, self.tabs)
        )
        self.stationary_user_type_v2_panel: StationaryUserTypeV2Panel | None = None
        if profiles and user_type_heatmaps_v2 is not None:
            self.stationary_user_type_v2_panel = StationaryUserTypeV2Panel(
                profiles,
                user_type_heatmaps_v2,
                self.stationary_user_type_panel,
                selected_user_type_id=str(
                    self.fatigue_sigma_lab_panel.single_panel.user_type_combo.currentData()
                ),
            )
            self.stationary_user_type_panel.install_stage8a1_profile_panel(
                self.stationary_user_type_v2_panel
            )
        self.tabs.insertTab(0, self.fatigue_sigma_lab_panel, TAB_TITLES[0])
        # In this subclass only, put the retained fixed-user explanation before
        # the retained Stage 8A convergence tab. Both original widgets and their
        # public object references remain intact.
        self.tabs.tabBar().moveTab(
            self.tabs.indexOf(self.stationary_user_type_panel),
            1,
        )
        self.tabs.tabBar().moveTab(self.tabs.indexOf(self.multi_session_panel), 2)
        self.tabs.setCurrentWidget(self.fatigue_sigma_lab_panel)
        self._connect_lab_controls()
        self._connect_user_type_v2_controls()
        self.fatigue_sigma_lab_panel.set_backend_available(lab_backend is not None)
        self._apply_stage8a1_copy()

    @property
    def lab_backend(self) -> FatigueSigmaLabBackend | None:
        return self._lab_backend

    @property
    def lab_operation_active(self) -> bool:
        return self._lab_thread is not None and self._lab_thread.isRunning()

    @property
    def last_lab_result(self) -> object | None:
        """Return the most recent worker/reset result without recomputing it."""

        return self._last_lab_result

    def set_lab_backend(self, backend: FatigueSigmaLabBackend | None) -> None:
        if self.lab_operation_active:
            raise RuntimeError("cannot replace the lab backend while an operation is active")
        self._lab_backend = backend
        self.fatigue_sigma_lab_panel.set_backend_available(backend is not None)

    def _connect_lab_controls(self) -> None:
        panel = self.fatigue_sigma_lab_panel
        panel.single_next_requested.connect(
            lambda settings: self._start_single_operation("next_session", settings)
        )
        panel.single_run_all_requested.connect(
            lambda settings: self._start_single_operation("run_all", settings)
        )
        panel.reference_compare_requested.connect(
            lambda settings: self._start_single_operation("compare_reference", settings)
        )
        panel.single_pause_changed.connect(self._set_lab_pause)
        panel.single_cancel_requested.connect(self._request_lab_cancel)
        panel.single_reset_requested.connect(self._reset_lab_single)
        panel.save_state_requested.connect(self._save_lab_state)
        panel.load_state_requested.connect(self._load_lab_state)
        panel.export_csv_requested.connect(self._export_lab_csv)
        panel.grid_run_requested.connect(self._start_grid_operation)
        panel.grid_cancel_requested.connect(self._request_lab_cancel)

    def _connect_user_type_v2_controls(self) -> None:
        panel = self.stationary_user_type_v2_panel
        if panel is None:
            return
        single = self.fatigue_sigma_lab_panel.single_panel
        single.user_type_combo.currentIndexChanged.connect(
            self._select_v2_profile_from_single_condition
        )
        panel.user_type_selected.connect(self._select_single_condition_from_v2_profile)
        self._sync_v2_profile_editability()

    def _select_v2_profile_from_single_condition(self, _index: int) -> None:
        panel = self.stationary_user_type_v2_panel
        if panel is None:
            return
        selected = self.fatigue_sigma_lab_panel.single_panel.user_type_combo.currentData()
        if isinstance(selected, str) and selected != panel.selected_user_type_id:
            panel.set_selected_user_type(selected)

    def _select_single_condition_from_v2_profile(self, user_type_id: str) -> None:
        single = self.fatigue_sigma_lab_panel.single_panel
        if not single.user_type_combo.isEnabled():
            return
        index = single.user_type_combo.findData(user_type_id)
        if index >= 0 and index != single.user_type_combo.currentIndex():
            single.user_type_combo.setCurrentIndex(index)

    def _sync_v2_profile_editability(self) -> None:
        panel = self.stationary_user_type_v2_panel
        if panel is not None:
            panel.set_settings_editable(
                self.fatigue_sigma_lab_panel.single_panel.user_type_combo.isEnabled()
            )

    def _apply_stage8a1_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText("疲労・探索幅・収束条件ラボ  ·  Stage 08A.1")
        diagnostic_note = self.time_diagnostics_tab.findChild(QLabel, "stageDescription")
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "Stage 8A.1も各sessionは独立したinteger-microseconds engineです。"
                "実験係数はDigital Life内の注入policyで使い、収束評価は観測だけを行います。"
            )

    def _start_single_operation(
        self,
        action: str,
        settings: Mapping[str, object],
    ) -> None:
        backend = self._require_backend()
        if backend is None:
            self.fatigue_sigma_lab_panel.single_panel.set_operation_active(False)
            return
        try:
            operation = backend.create_single_operation(action, dict(settings))
            self._start_operation("single", operation)
        except Exception as exc:
            self.fatigue_sigma_lab_panel.single_panel.set_operation_active(False)
            self._show_lab_error("Stage 8A.1単一条件開始エラー", exc)

    def _start_grid_operation(self, settings: Mapping[str, object]) -> None:
        backend = self._require_backend()
        if backend is None:
            self.fatigue_sigma_lab_panel.grid_panel.set_operation_active(False)
            return
        try:
            operation = backend.create_grid_operation(dict(settings))
            self._start_operation("grid", operation)
        except Exception as exc:
            self.fatigue_sigma_lab_panel.grid_panel.set_operation_active(False)
            self._show_lab_error("Stage 8A.1条件比較開始エラー", exc)

    def _start_operation(self, kind: str, operation) -> None:
        if self.lab_operation_active or self._lab_thread is not None:
            raise RuntimeError("a Stage 8A.1 operation is already active")
        control = FatigueSigmaExecutionControl()
        control.request_pause(self._pause_prearmed)
        thread = QThread(self)
        worker = FatigueSigmaOperationWorker(operation, control)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._lab_progress)
        worker.succeeded.connect(self._lab_succeeded)
        worker.cancelled.connect(self._lab_cancelled)
        worker.failed.connect(self._lab_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._lab_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._lab_operation_kind = kind
        self._lab_control = control
        self._lab_thread = thread
        self._lab_worker = worker
        self._last_lab_result = None
        if kind == "single":
            self.fatigue_sigma_lab_panel.single_panel.set_operation_active(True)
            self._sync_v2_profile_editability()
        else:
            self.fatigue_sigma_lab_panel.grid_panel.set_operation_active(True)
        thread.start()

    def _lab_progress(self, progress: object) -> None:
        if self._lab_operation_kind == "grid":
            self.fatigue_sigma_lab_panel.grid_panel.set_progress(progress)
        else:
            self.fatigue_sigma_lab_panel.single_panel.set_progress(progress)

    def _lab_succeeded(self, result: object) -> None:
        self._last_lab_result = result
        if self._lab_operation_kind == "grid":
            self.fatigue_sigma_lab_panel.set_grid_result(result)
            self.fatigue_sigma_lab_panel.grid_panel.set_operation_active(False)
        else:
            self.fatigue_sigma_lab_panel.set_single_result(result)
            self.fatigue_sigma_lab_panel.single_panel.set_operation_active(False)
            self._sync_v2_profile_editability()
            self._install_backend_simulation()
        self._clear_pause_button()

    def _lab_cancelled(self, partial_result: object) -> None:
        self._last_lab_result = partial_result
        if partial_result is not None:
            if self._lab_operation_kind == "grid":
                self.fatigue_sigma_lab_panel.set_grid_result(partial_result)
            else:
                self.fatigue_sigma_lab_panel.set_single_result(partial_result)
                self._install_backend_simulation()
        if self._lab_operation_kind == "grid":
            panel = self.fatigue_sigma_lab_panel.grid_panel
            panel.set_operation_active(False)
            self._sync_v2_profile_editability()
            panel.progress_label.setText("cancelled at safe boundary")
        else:
            panel = self.fatigue_sigma_lab_panel.single_panel
            panel.set_operation_active(False)
            self._sync_v2_profile_editability()
            panel.progress_label.setText("cancelled at safe boundary")
        self._clear_pause_button()

    def _lab_failed(self, message: str) -> None:
        self.fatigue_sigma_lab_panel.single_panel.set_operation_active(False)
        self._sync_v2_profile_editability()
        self.fatigue_sigma_lab_panel.grid_panel.set_operation_active(False)
        self._clear_pause_button()
        self._show_lab_error("Stage 8A.1実行エラー", message)

    def _lab_thread_finished(self) -> None:
        self._lab_thread = None
        self._lab_worker = None
        self._lab_control = None
        self._lab_operation_kind = None
        if self._close_pending:
            self._close_pending = False
            QTimer.singleShot(0, self.close)

    def _set_lab_pause(self, selected: bool) -> None:
        self._pause_prearmed = bool(selected)
        if self._lab_control is not None:
            self._lab_control.request_pause(selected)

    def _clear_pause_button(self) -> None:
        self._pause_prearmed = False
        button = self.fatigue_sigma_lab_panel.single_panel.pause_button
        with QSignalBlocker(button):
            button.setChecked(False)

    def _request_lab_cancel(self) -> None:
        # This direct Event mutation is intentionally not a queued worker slot;
        # the worker event loop is blocked while the core operation is running.
        if self._lab_control is not None:
            self._lab_control.request_cancel()

    def _reset_lab_single(self) -> None:
        backend = self._require_backend()
        if backend is None:
            return
        try:
            result = backend.reset_single(
                self.fatigue_sigma_lab_panel.single_panel.settings_values()
            )
            self._last_lab_result = result
            self.fatigue_sigma_lab_panel.single_panel.reset_views()
            self.fatigue_sigma_lab_panel.structured_panel.reset_views()
            if result is not None:
                self.fatigue_sigma_lab_panel.set_single_result(result)
            self._sync_v2_profile_editability()
            self._install_backend_simulation()
        except Exception as exc:
            self._show_lab_error("Stage 8A.1 resetエラー", exc)

    def _save_lab_state(self, path: Path) -> None:
        backend = self._require_backend()
        if backend is None:
            return
        try:
            backend.save_single_state(path)
        except Exception as exc:
            self._show_lab_error("Stage 8A.1 state保存エラー", exc)

    def _load_lab_state(self, path: Path) -> None:
        backend = self._require_backend()
        if backend is None:
            return
        try:
            result = backend.load_single_state(path)
            self.fatigue_sigma_lab_panel.single_panel.apply_loaded_result_settings(
                result
            )
            self.fatigue_sigma_lab_panel.set_single_result(result)
            self._select_v2_profile_from_single_condition(0)
            self._sync_v2_profile_editability()
            self._install_backend_simulation()
        except Exception as exc:
            self._show_lab_error("Stage 8A.1 state読込エラー", exc)

    def _export_lab_csv(self, path: Path) -> None:
        backend = self._require_backend()
        if backend is None:
            return
        try:
            backend.export_csv(path)
        except Exception as exc:
            self._show_lab_error("Stage 8A.1 CSV保存エラー", exc)

    def _install_backend_simulation(self) -> None:
        backend = self._lab_backend
        if backend is None:
            return
        simulation = backend.current_simulation()
        if simulation is not None:
            self._install_session_simulation(simulation)  # type: ignore[arg-type]

    def _require_backend(self) -> FatigueSigmaLabBackend | None:
        return self._lab_backend

    def _show_lab_error(self, title: str, error: object) -> None:
        QMessageBox.critical(self, title, str(error))

    def prepare_screenshot_target(self, target: str) -> None:
        if target not in SCREENSHOT_TARGETS:
            raise ValueError(f"unknown Stage 8A.1 screenshot target: {target}")
        panel = self.fatigue_sigma_lab_panel
        self.tabs.setCurrentWidget(panel)
        if target == "stage-08a1-condition-grid-heatmap":
            panel.subtabs.setCurrentWidget(panel.grid_panel)
            panel.grid_panel.diagnostics_scroll.ensureWidgetVisible(
                panel.grid_panel.heatmap_table_splitter
            )
        elif target == "stage-08a1-structured-convergence-types":
            panel.subtabs.setCurrentWidget(panel.structured_panel)
            panel.structured_panel.diagnostics_scroll.verticalScrollBar().setValue(0)
        else:
            panel.subtabs.setCurrentWidget(panel.single_panel)
            if target == "stage-08a1-fatigue-sigma-lab-overview":
                panel.single_panel.diagnostics_scroll.verticalScrollBar().setValue(0)
            elif target == "stage-08a1-session-bpm-hue-trajectory":
                panel.single_panel.diagnostics_scroll.ensureWidgetVisible(
                    panel.single_panel.session_chart
                )
            elif target == "stage-08a1-fatigue-and-sigma-trajectories":
                panel.single_panel.diagnostics_scroll.ensureWidgetVisible(
                    panel.single_panel.trajectory_splitter
                )

    def screenshot_widget(self, target: str) -> QWidget:
        panel = self.fatigue_sigma_lab_panel
        targets: dict[str, QWidget] = {
            "stage-08a1-fatigue-sigma-lab-overview": self,
            "stage-08a1-session-bpm-hue-trajectory": panel.single_panel.session_chart,
            "stage-08a1-structured-convergence-types": (panel.structured_panel.diagnostics_content),
            "stage-08a1-fatigue-and-sigma-trajectories": (panel.single_panel.trajectory_splitter),
            "stage-08a1-condition-grid-heatmap": panel.grid_panel.heatmap_table_splitter,
        }
        try:
            return targets[target]
        except KeyError as exc:
            raise ValueError(f"unknown Stage 8A.1 screenshot target: {target}") from exc

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.lab_operation_active:
            self._close_pending = True
            self._request_lab_cancel()
            event.ignore()
            return
        super().closeEvent(event)


Stage8A1MainWindow = FatigueSigmaLabMainWindow

__all__ = [
    "SCREENSHOT_TARGETS",
    "TAB_TITLES",
    "WINDOW_TITLE",
    "FatigueSigmaLabMainWindow",
    "Stage8A1MainWindow",
]
