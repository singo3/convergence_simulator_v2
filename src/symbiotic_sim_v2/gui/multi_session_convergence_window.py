"""Stage 8A eleven-tab fixed-preference multi-session laboratory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from symbiotic_sim_v2.convergence import RollingConvergenceConfig
from symbiotic_sim_v2.gui.adaptive_closed_loop_window import (
    AdaptiveClosedLoopMainWindow,
)
from symbiotic_sim_v2.gui.controller import SimulationController
from symbiotic_sim_v2.gui.multi_session_convergence_panel import (
    MultiSessionConvergencePanel,
)
from symbiotic_sim_v2.gui.stationary_user_type_panel import (
    StationaryUserTypePanel,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.multi_session import (
    MultiSessionRelationMemoryRunner,
    MultiSessionRunnerConfig,
    StationaryUserTypeComparison,
    compare_stationary_user_types,
    export_multi_session_diagnostics,
    export_multi_session_state_file,
    load_multi_session_state_file,
    physiology_root_seed_for_session,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    evaluate_stationary_preference,
    stationary_light_response_config,
    stationary_user_type_ids,
    stationary_user_type_profile,
)

WINDOW_TITLE = (
    "環境共生型デジタル生命シミュレーター v2 — "
    "固定好み・複数セッション収束ラボ"
)
TAB_TITLES = (
    "複数セッション収束",
    "固定仮想ユーザータイプ",
    "関係記憶探索",
    "光応答仮想ユーザー",
    "光点滅シミュレーター",
    "3生命・資格競争",
    "Garden出力資格層",
    "Garden入力層",
    "仮想ユーザー心拍",
    "Polar H10",
    "時間・イベント診断",
)


def runner_config_from_gui_values(values: dict[str, Any]) -> MultiSessionRunnerConfig:
    """Build the immutable diagnostic config without touching Stage 5C policy."""

    convergence = RollingConvergenceConfig(
        window_sessions=values["convergence_window"],
        required_sessions=values["convergence_required"],
        hue_tolerance_degree=values["hue_tolerance_degree"],
        blink_bpm_tolerance=values["blink_bpm_tolerance"],
        truth_response_gap_threshold=values["truth_response_gap_threshold"],
        maximum_sessions=values["maximum_sessions"],
    )
    return MultiSessionRunnerConfig(
        user_type_id=values["stationary_user_type"],
        master_seed=int(values["master_seed"]),
        session_seed_policy=values["session_seed_policy"],
        convergence_config=convergence,
    )


def create_stage8a_preview_simulation(
    runner: MultiSessionRelationMemoryRunner,
) -> AdaptiveRelationMemoryClosedLoopSimulation:
    """Create an unexecuted next-session preview for the retained nine tabs."""

    state = runner.state()
    seed = physiology_root_seed_for_session(
        master_seed=runner.config.master_seed,
        stationary_user_type_id=runner.config.user_type_id,
        session_index=state.next_session_index,
        policy=runner.config.session_seed_policy,
    )
    return create_adaptive_relation_memory_closed_loop_simulation(
        virtual_user_config=VirtualUserConfig(
            duration_seconds=240,
            root_seed=seed,
        ),
        light_response_config=stationary_light_response_config(
            runner.user_type_profile
        ),
        initial_persistent_states_by_life_id=(
            runner.current_persistent_state_by_life()
        ),
    )


class MultiSessionConvergenceMainWindow(AdaptiveClosedLoopMainWindow):
    """Orchestrate independent Stage 5C sessions and show aggregate diagnostics."""

    def __init__(
        self,
        controller: SimulationController,
        preview_simulation: AdaptiveRelationMemoryClosedLoopSimulation,
        runner: MultiSessionRelationMemoryRunner,
    ) -> None:
        self._runner = runner
        self._comparison: StationaryUserTypeComparison | None = None
        self._run_all_pending = False
        self._pause_after_current = False
        super().__init__(controller, preview_simulation, preset_name="custom")
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1560, 980)

        profiles = {
            user_type_id: stationary_user_type_profile(user_type_id)
            for user_type_id in stationary_user_type_ids()
        }
        self.multi_session_panel = MultiSessionConvergencePanel(
            profiles,
            self.tabs,
            convergence_config=runner.config.convergence_config,
            selected_user_type_id=runner.config.user_type_id,
            master_seed=runner.config.master_seed,
            seed_policy=runner.config.session_seed_policy,
        )
        self.stationary_user_type_panel = StationaryUserTypePanel(
            profiles,
            self.tabs,
            selected_user_type_id=runner.config.user_type_id,
            landscape_evaluator=self._landscape_match,
        )
        self.tabs.insertTab(0, self.multi_session_panel, TAB_TITLES[0])
        self.tabs.insertTab(1, self.stationary_user_type_panel, TAB_TITLES[1])
        self.tabs.setCurrentWidget(self.multi_session_panel)
        self._connect_stage8a_controls()
        self._lock_retained_session_controls()
        self._apply_stage8a_copy()
        self._refresh_aggregate_views()

    @property
    def runner(self) -> MultiSessionRelationMemoryRunner:
        return self._runner

    @property
    def comparison(self) -> StationaryUserTypeComparison | None:
        return self._comparison

    @staticmethod
    def _landscape_match(
        profile: Any,
        hue: float | None = None,
        bpm: float | None = None,
        *,
        active: bool = True,
        hue_degree: float | None = None,
        blink_bpm: float | None = None,
    ) -> float:
        selected_hue = hue_degree if hue_degree is not None else hue
        selected_bpm = blink_bpm if blink_bpm is not None else bpm
        if selected_hue is None or selected_bpm is None:
            raise ValueError("landscape diagnostic requires Hue and BPM")
        return evaluate_stationary_preference(
            profile,
            active=active,
            hue_degree=selected_hue,
            blink_bpm=selected_bpm,
        ).preference_match

    def _connect_stage8a_controls(self) -> None:
        panel = self.multi_session_panel
        panel.settings_changed.connect(self._apply_runner_settings)
        panel.next_session_requested.connect(self._request_next_session)
        panel.run_all_requested.connect(self._request_run_all)
        panel.pause_after_current_changed.connect(self._set_pause_after_current)
        panel.compare_all_requested.connect(self._compare_all_user_types)
        panel.reset_requested.connect(self._reset_multi_session_run)
        panel.save_state_requested.connect(self._save_run_state)
        panel.load_state_requested.connect(self._load_run_state)
        panel.export_csv_requested.connect(self._export_csv)
        self.stationary_user_type_panel.user_type_selected.connect(
            self._select_user_type_from_profile_panel
        )

    def _lock_retained_session_controls(self) -> None:
        # Stage 8A owns execution. The retained controls would otherwise run the
        # preview/current engine outside the multi-session commit boundary.
        for widget in (
            self.start_button,
            self.pause_button,
            self.resume_button,
            self.reset_button,
            self.step_second_button,
            self.step_event_button,
            self.run_to_end_button,
            self.speed_combo,
        ):
            widget.setEnabled(False)
            widget.setToolTip(
                "Stage 8Aでは複数セッション収束tabから独立セッションを実行します。"
            )
        self.light_response_user_panel.settings_frame.setEnabled(False)
        self.virtual_user_panel.settings_group.setEnabled(False)

    def _apply_stage8a_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText("固定好み・複数セッション収束ラボ  ·  Stage 08A")
        diagnostic_note = self.time_diagnostics_tab.findChild(
            QLabel,
            "stageDescription",
        )
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "各セッションは0〜240,000,000 µsの独立engineです。"
                "このtabは現在または直近セッションのevent orderingを監査します。"
            )

    def _apply_runner_settings(self, values: dict[str, Any]) -> None:
        if self._runner.state().next_session_index != 0:
            return
        config = runner_config_from_gui_values(values)
        self._runner = MultiSessionRelationMemoryRunner(config)
        self._comparison = None
        self.stationary_user_type_panel.set_selected_user_type(config.user_type_id)
        self._install_session_simulation(create_stage8a_preview_simulation(self._runner))
        self._refresh_aggregate_views()

    def _select_user_type_from_profile_panel(self, user_type_id: str) -> None:
        if self._runner.state().next_session_index != 0:
            return
        combo = self.multi_session_panel.user_type_combo
        index = combo.findData(user_type_id)
        if index >= 0 and index != combo.currentIndex():
            combo.setCurrentIndex(index)

    def _request_next_session(self, _values: dict[str, Any]) -> None:
        self._run_all_pending = False
        QTimer.singleShot(0, self._run_one_session)

    def _request_run_all(self, _values: dict[str, Any]) -> None:
        self._run_all_pending = True
        QTimer.singleShot(0, self._run_all_step)

    def _set_pause_after_current(self, selected: bool) -> None:
        self._pause_after_current = selected

    def _run_one_session(self) -> None:
        try:
            outcome = self._runner.run_next_session()
            simulation = self._runner.current_simulation
            if simulation is not None:
                self._install_session_simulation(simulation)
            self._refresh_aggregate_views()
            if not outcome.engine_completed:
                self._show_error(
                    "セッション未完了",
                    outcome.invalid_reason or "不明な実行エラー",
                )
        except Exception as exc:  # pragma: no cover - defensive GUI boundary
            self._run_all_pending = False
            self.multi_session_panel.set_run_active(False)
            self._show_error("Stage 8A実行エラー", str(exc))

    def _run_all_step(self) -> None:
        if not self._run_all_pending:
            self.multi_session_panel.set_run_active(False)
            return
        if not self._runner.can_run_next_session:
            self._run_all_pending = False
            self.multi_session_panel.set_run_active(False)
            return
        self._run_one_session()
        if (
            self._pause_after_current
            or not self._runner.can_run_next_session
            or self._runner.stopped_on_error
        ):
            self._run_all_pending = False
            self._pause_after_current = False
            self.multi_session_panel.pause_after_session_button.setChecked(False)
            self.multi_session_panel.set_run_active(False)
            return
        self.multi_session_panel.set_run_active(True)
        QTimer.singleShot(0, self._run_all_step)

    def _reset_multi_session_run(self) -> None:
        self._run_all_pending = False
        self._pause_after_current = False
        self._comparison = None
        self._runner.reset()
        self._install_session_simulation(create_stage8a_preview_simulation(self._runner))
        self.multi_session_panel.reset_views()
        self._refresh_aggregate_views()

    def _compare_all_user_types(self, _values: dict[str, Any]) -> None:
        self.multi_session_panel.set_run_active(True)
        QApplication.setOverrideCursor(self.cursor().shape())
        try:
            self._comparison = compare_stationary_user_types(self._runner.config)
            self.multi_session_panel.set_comparison_records(self._comparison.rows)
        except Exception as exc:  # pragma: no cover - defensive GUI boundary
            self._show_error("全タイプ比較エラー", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
            self.multi_session_panel.set_run_active(False)

    def _save_run_state(self, path: Path) -> None:
        try:
            export_multi_session_state_file(path, self._runner.state())
        except Exception as exc:  # pragma: no cover - file-dialog boundary
            self._show_error("run state保存エラー", str(exc))

    def _load_run_state(self, path: Path) -> None:
        try:
            state = load_multi_session_state_file(
                path,
                expected_digital_life_ids=self._runner.digital_life_ids,
            )
            self._runner = MultiSessionRelationMemoryRunner(resume_state=state)
            self._comparison = None
            self.multi_session_panel.set_settings(
                self._runner.config.convergence_config,
                selected_user_type_id=self._runner.config.user_type_id,
                master_seed=self._runner.config.master_seed,
                seed_policy=self._runner.config.session_seed_policy,
            )
            self.stationary_user_type_panel.set_selected_user_type(
                self._runner.config.user_type_id
            )
            self._install_session_simulation(
                create_stage8a_preview_simulation(self._runner)
            )
            self._refresh_aggregate_views()
        except Exception as exc:  # pragma: no cover - file-dialog boundary
            self._show_error("run state読込エラー", str(exc))

    def _export_csv(self, destination: Path) -> None:
        try:
            export_multi_session_diagnostics(
                destination,
                self._runner.state(),
                self._runner.truth_alignment_records(),
                comparison=self._comparison,
            )
        except Exception as exc:  # pragma: no cover - file-dialog boundary
            self._show_error("CSV保存エラー", str(exc))

    def _install_session_simulation(
        self,
        simulation: AdaptiveRelationMemoryClosedLoopSimulation,
    ) -> None:
        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            self.controller.reset()
        self._install_simulation(simulation, "custom")
        self._update_stage_5c_snapshot(self.controller.current_snapshot())
        self._lock_retained_session_controls()

    def _refresh_aggregate_views(self) -> None:
        state = self._runner.state()
        truth_records = self._runner.truth_alignment_records()
        latest = state.convergence_records[-1] if state.convergence_records else None
        total_after = (
            0
            if latest is None
            else latest.post_convergence_cluster_member_count
            + latest.post_convergence_outlier_count
        )
        outliers = 0 if latest is None else latest.post_convergence_outlier_count
        summary = {
            "maximum_sessions": self._runner.config.maximum_sessions,
            "completed_sessions": state.completed_session_count,
            "valid_sessions": state.valid_session_count,
            "explore_count": sum(
                outcome.exploration_decision == "explore"
                for outcome in state.session_outcomes
            ),
            "accepted_count": sum(
                outcome.candidate_accepted for outcome in state.session_outcomes
            ),
            "post_convergence_outlier_rate": (
                None if total_after == 0 else outliers / total_after
            ),
        }
        self.multi_session_panel.set_state(
            state,
            summary=summary,
            convergence_config=self._runner.config.convergence_config,
            user_profile=self._runner.user_type_profile,
            comparison_rows=() if self._comparison is None else self._comparison.rows,
            truth_alignment_records=truth_records,
        )
        self.stationary_user_type_panel.set_selected_user_type(
            self._runner.config.user_type_id
        )
        self.stationary_user_type_panel.set_settings_editable(
            state.next_session_index == 0
        )

    def _apply_config(self, _config: VirtualUserConfig) -> None:
        """Prevent retained Stage 2 controls from bypassing Stage 8A boundaries."""

    def _apply_light_response_config(self, _config) -> None:
        """Prevent retained Stage 7 controls from replacing the fixed landscape."""

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)


Stage8AMainWindow = MultiSessionConvergenceMainWindow

__all__ = [
    "MultiSessionConvergenceMainWindow",
    "Stage8AMainWindow",
    "TAB_TITLES",
    "WINDOW_TITLE",
    "create_stage8a_preview_simulation",
    "runner_config_from_gui_values",
]
