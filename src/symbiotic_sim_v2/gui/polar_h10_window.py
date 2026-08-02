"""Stage 3 main window reusing Stage 2 user and Stage 1 diagnostic views."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QLabel

from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.polar_h10.scenario import (
    PolarH10Simulation,
    create_polar_h10_simulation,
)
from symbiotic_sim_v2.gui.controller import ControllerSnapshot, SimulationController
from symbiotic_sim_v2.gui.polar_h10_panel import PolarH10Panel
from symbiotic_sim_v2.gui.virtual_user_window import VirtualUserMainWindow
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig

WINDOW_TITLE = "環境共生型デジタル生命シミュレーター v2 — 仮想Polar H10"

STAGE_3_VIRTUAL_USER_NOTICE = (
    "Stage 3でも仮想ユーザーの正式出力はHeartbeatEventだけです。"
    "表示しているRRI・RMSSDは仮想ユーザー内部の開発用診断であり、"
    "Polar H10の正式出力ではありません。"
)
STAGE_3_TRUE_VALUE_NOTICE = (
    "このRRIとRMSSDは仮想ユーザー内部の真値から計算する開発用診断です。"
    "H10測定値との比較はPolar H10 tabに分離しています。Garden入力層は未実装です。"
)


class PolarH10MainWindow(VirtualUserMainWindow):
    """Compose a third H10 tab without expanding the shared Stage 2 window logic."""

    def __init__(
        self,
        controller: SimulationController,
        simulation: PolarH10Simulation,
    ) -> None:
        # PolarH10Simulation intentionally exposes Stage 2-compatible component/config
        # aliases, so the existing virtual-user tab can be reused without a second view.
        super().__init__(controller, simulation)
        self.simulation = simulation
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1440, 920)

        self.polar_h10_panel = PolarH10Panel(
            simulation.polar_h10_config,
            simulation.polar_h10_component,
            simulation.virtual_user_component,
            self.tabs,
            duration_seconds=simulation.virtual_user_config.duration_seconds,
        )
        self.tabs.insertTab(1, self.polar_h10_panel, "Polar H10")
        self.polar_h10_tab = self.polar_h10_panel
        self.h10_panel = self.polar_h10_panel
        self._apply_stage_3_copy()

        self.controller.snapshot_changed.connect(self._update_h10_snapshot)
        self.controller.scenario_reset.connect(self._reset_h10_view)
        self._update_h10_snapshot(self.controller.current_snapshot())
        self.tabs.setCurrentWidget(self.polar_h10_panel)

    def _apply_stage_3_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText("仮想Polar H10  ·  Stage 03")

        virtual_user_notice = self.virtual_user_panel.findChild(QLabel, "stageDescription")
        if virtual_user_notice is not None:
            virtual_user_notice.setText(STAGE_3_VIRTUAL_USER_NOTICE)
        true_value_notice = self.virtual_user_panel.findChild(QLabel, "diagnosticNotice")
        if true_value_notice is not None:
            true_value_notice.setText(STAGE_3_TRUE_VALUE_NOTICE)

        diagnostic_note = self.time_diagnostics_tab.findChild(QLabel, "stageDescription")
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "Stage 1のinteger-microseconds時計とdeterministic event orderingを、"
                "VirtualUser→Polar H10統合scenarioの実行済みevent logで確認します。"
            )
        speed_note = self.findChild(QLabel, "speedNote")
        if speed_note is not None:
            speed_note.setText(
                "速度は実時間上の進み方だけを変え、心拍・H10測定RRI系列は変えません。"
            )

    def _apply_config(self, config: VirtualUserConfig) -> None:
        """Rebuild both Stage 2 producer and Stage 3 device from stopped settings."""

        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            return
        previous_h10_config = self.simulation.polar_h10_config
        selected_h10_config: PolarH10Config = replace(
            previous_h10_config,
            expected_user_id=config.user_id,
        )
        simulation = create_polar_h10_simulation(config, selected_h10_config)
        self.simulation = simulation
        self.virtual_user_panel.set_component(simulation.virtual_user_component)
        self.virtual_user_panel.set_config(simulation.virtual_user_config)
        self.virtual_user_panel.reset_views()
        self.polar_h10_panel.set_components(
            simulation.polar_h10_component,
            simulation.virtual_user_component,
        )
        self.polar_h10_panel.set_duration_seconds(
            simulation.virtual_user_config.duration_seconds
        )
        self.controller.replace_engine(simulation.engine)

    def _update_h10_snapshot(self, snapshot: ControllerSnapshot) -> None:
        """Forward one immutable engine snapshot to the H10 panel."""

        self.polar_h10_panel.update_diagnostics(snapshot.engine)

    def _reset_h10_view(self, _events) -> None:
        """Clear H10 plots/table whenever the integrated scenario is reset."""

        self.polar_h10_panel.reset_views()
