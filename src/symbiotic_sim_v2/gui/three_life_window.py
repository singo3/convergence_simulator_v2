"""Stage 5B main window for three independent Digital Lives and Garden output."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QLabel

from symbiotic_sim_v2.gui.controller import ControllerSnapshot, SimulationController
from symbiotic_sim_v2.gui.garden_input_window import GardenInputMainWindow
from symbiotic_sim_v2.gui.garden_output_panel import GardenOutputPanel
from symbiotic_sim_v2.gui.multi_life_panel import MultiLifePanel
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    ThreeDigitalLifeCompetitionSimulation,
    create_three_digital_life_competition_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig

WINDOW_TITLE = (
    "環境共生型デジタル生命シミュレーター v2 — 3生命・資格競争・第2周 "
    "— Stage 5B.1 出力境界補正"
)


class ThreeDigitalLifeMainWindow(GardenInputMainWindow):
    """Add Stage 5B views while preserving the complete Stage 2-4 diagnostics."""

    def __init__(
        self,
        controller: SimulationController,
        simulation: ThreeDigitalLifeCompetitionSimulation,
    ) -> None:
        # GardenInputMainWindow calls Stage 3/4 copy helpers dynamically during its
        # construction.  Those methods are intentionally not overridden here.
        super().__init__(controller, simulation)
        self.simulation = simulation
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1560, 980)

        self.multi_life_panel = MultiLifePanel(
            simulation.digital_life_components,
            simulation.garden_output_component,
            self.tabs,
        )
        self.three_life_panel = self.multi_life_panel
        self.three_digital_life_panel = self.multi_life_panel
        self.tabs.insertTab(0, self.multi_life_panel, "3生命・資格競争")

        self.garden_output_panel = GardenOutputPanel(
            simulation.garden_output_config,
            simulation.garden_output_component,
            self.tabs,
        )
        self.garden_output_qualification_panel = self.garden_output_panel
        self.tabs.insertTab(1, self.garden_output_panel, "Garden出力資格層")
        self._apply_stage_5b_copy()

        self.virtual_user_panel.duration_spin.setEnabled(False)
        self.virtual_user_panel.duration_spin.setToolTip(
            "Stage 5BのGarden / 3生命セッションは240秒固定です。"
        )
        duration_seconds = simulation.garden_input_config.total_duration_seconds
        self.multi_life_panel.chart.set_duration_seconds(duration_seconds)
        self.garden_output_panel.set_duration_seconds(duration_seconds)

        self.controller.snapshot_changed.connect(self._update_stage_5b_snapshot)
        self.controller.scenario_reset.connect(self._reset_stage_5b_views)
        self._update_stage_5b_snapshot(self.controller.current_snapshot())
        self.tabs.setCurrentWidget(self.multi_life_panel)

    def _apply_stage_5b_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText(
                "3生命・資格競争・第2周・出力境界補正  ·  Stage 05B.1"
            )

        garden_assumption = self.garden_input_panel.findChild(
            QLabel,
            "gardenAssumptionNotice",
        )
        if garden_assumption is not None:
            garden_assumption.setText(
                "Garden入力層自身はNとSまでを生成します。NdとWは、Gardenの"
                "正式eventだけを入力とする3体のデジタル生命で独立に計算します。"
            )
        garden_flow_nodes = self.garden_input_panel.findChildren(
            QLabel,
            "gardenFlowNode",
        )
        if garden_flow_nodes:
            garden_flow_nodes[-1].setText("3体のデジタル生命")

        diagnostic_note = self.time_diagnostics_tab.findChild(
            QLabel,
            "stageDescription",
        )
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "Stage 1のinteger-microseconds時計とdeterministic event orderingを、"
                "VirtualUser→Polar H10→Garden入力層→3生命→Garden出力資格層の"
                "240秒scenarioで確認します。"
            )
        speed_note = self.findChild(QLabel, "speedNote")
        if speed_note is not None:
            speed_note.setText(
                "速度は実時間上の進み方だけを変え、3生命の独立演算、touch到着、"
                "資格holder、第2周の結果は変えません。"
            )

    def _apply_config(self, config: VirtualUserConfig) -> None:
        """Rebuild the complete Stage 5B scenario after a stopped setting change."""

        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            return
        selected_user_config = replace(
            config,
            duration_seconds=self.simulation.garden_input_config.total_duration_seconds,
        )
        selected_h10_config = replace(
            self.simulation.polar_h10_config,
            expected_user_id=selected_user_config.user_id,
        )
        simulation = create_three_digital_life_competition_simulation(
            virtual_user_config=selected_user_config,
            polar_h10_config=selected_h10_config,
            garden_input_config=self.simulation.garden_input_config,
            digital_life_configs=self.simulation.digital_life_configs,
            runtime_config=self.simulation.runtime_config,
            garden_output_config=self.simulation.garden_output_config,
        )
        self._install_simulation(simulation)

    def _install_simulation(
        self,
        simulation: ThreeDigitalLifeCompetitionSimulation,
    ) -> None:
        """Rebind all six-tab views before controller reset signals are emitted."""

        self.simulation = simulation
        self.virtual_user_panel.set_component(simulation.virtual_user_component)
        self.virtual_user_panel.set_config(simulation.virtual_user_config)
        self.virtual_user_panel.duration_spin.setEnabled(False)
        self.virtual_user_panel.reset_views()
        self.polar_h10_panel.set_components(
            simulation.polar_h10_component,
            simulation.virtual_user_component,
        )
        self.polar_h10_panel.set_duration_seconds(
            simulation.virtual_user_config.duration_seconds
        )
        self.garden_input_panel.set_component(simulation.garden_input_component)
        self.garden_input_panel.set_config(simulation.garden_input_config)
        self.garden_input_panel.reset_views()
        self.multi_life_panel.set_components(
            simulation.digital_life_components,
            simulation.garden_output_component,
        )
        self.multi_life_panel.chart.set_duration_seconds(
            simulation.garden_input_config.total_duration_seconds
        )
        self.multi_life_panel.reset_views()
        self.garden_output_panel.set_component(simulation.garden_output_component)
        self.garden_output_panel.set_config(simulation.garden_output_config)
        self.garden_output_panel.set_duration_seconds(
            simulation.garden_input_config.total_duration_seconds
        )
        self.garden_output_panel.reset_views()
        self.controller.replace_engine(simulation.engine)

    def _update_stage_5b_snapshot(self, snapshot: ControllerSnapshot) -> None:
        self.multi_life_panel.update_diagnostics(snapshot.engine)
        self.garden_output_panel.update_diagnostics(snapshot.engine)

    def _reset_stage_5b_views(self, _events) -> None:
        self.multi_life_panel.reset_views()
        self.garden_output_panel.reset_views()


ThreeLifeMainWindow = ThreeDigitalLifeMainWindow
ThreeDigitalLifeCompetitionMainWindow = ThreeDigitalLifeMainWindow
