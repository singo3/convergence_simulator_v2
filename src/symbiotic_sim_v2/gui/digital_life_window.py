"""Stage 5A main window for one Digital Life's first round."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QLabel

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.scenario import (
    SingleDigitalLifeSimulation,
    create_single_digital_life_simulation,
)
from symbiotic_sim_v2.gui.controller import ControllerSnapshot, SimulationController
from symbiotic_sim_v2.gui.digital_life_panel import DigitalLifePanel
from symbiotic_sim_v2.gui.garden_input_window import GardenInputMainWindow
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig

WINDOW_TITLE = (
    "環境共生型デジタル生命シミュレーター v2 — 1体のデジタル生命・第1周"
)


class SingleDigitalLifeMainWindow(GardenInputMainWindow):
    """Add a Stage 5A tab while preserving every Stage 2-4 diagnostic view."""

    def __init__(
        self,
        controller: SimulationController,
        simulation: SingleDigitalLifeSimulation,
    ) -> None:
        # Do not override _apply_stage_3_copy or _apply_stage_4_copy. Both are called
        # dynamically while this super-constructor runs, before the life panel exists.
        super().__init__(controller, simulation)
        self.simulation = simulation
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1560, 980)

        self.digital_life_panel = DigitalLifePanel(
            simulation.digital_life_config,
            simulation.digital_life_component,
            self.tabs,
        )
        self.tabs.insertTab(0, self.digital_life_panel, "デジタル生命")
        self.digital_life_tab = self.digital_life_panel
        self.life_panel = self.digital_life_panel
        self._apply_stage_5a_copy()

        self.virtual_user_panel.duration_spin.setEnabled(False)
        self.virtual_user_panel.duration_spin.setToolTip(
            "Stage 5AのGarden / Digital Lifeセッションは240秒固定です。"
        )
        self.digital_life_panel.role_selected.connect(self._apply_life_role)
        self.controller.snapshot_changed.connect(self._update_life_snapshot)
        self.controller.scenario_reset.connect(self._reset_life_view)
        self._update_life_snapshot(self.controller.current_snapshot())
        self.tabs.setCurrentWidget(self.digital_life_panel)

    def _apply_stage_5a_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText("1体のデジタル生命・第1周  ·  Stage 05A")

        garden_assumption = self.garden_input_panel.findChild(
            QLabel,
            "gardenAssumptionNotice",
        )
        if garden_assumption is not None:
            garden_assumption.setText(
                "Garden入力層自身はNとSまでを生成します。NdとWは、"
                "Gardenの正式eventだけを入力とするデジタル生命tabで確認します。"
            )
        garden_flow_nodes = self.garden_input_panel.findChildren(
            QLabel,
            "gardenFlowNode",
        )
        if garden_flow_nodes:
            garden_flow_nodes[-1].setText("1体のデジタル生命")

        diagnostic_note = self.time_diagnostics_tab.findChild(QLabel, "stageDescription")
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "Stage 1のinteger-microseconds時計とdeterministic event orderingを、"
                "VirtualUser→Polar H10→Garden入力層→1体のデジタル生命の"
                "240秒scenarioで確認します。"
            )
        speed_note = self.findChild(QLabel, "speedNote")
        if speed_note is not None:
            speed_note.setText(
                "速度は実時間上の進み方だけを変え、Garden N/Sと第1周の値は"
                "変えません。"
            )

    def _apply_config(self, config: VirtualUserConfig) -> None:
        """Rebuild all four components after a stopped physiology change."""

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
        simulation = create_single_digital_life_simulation(
            virtual_user_config=selected_user_config,
            polar_h10_config=selected_h10_config,
            garden_input_config=self.simulation.garden_input_config,
            digital_life_config=self.simulation.digital_life_config,
        )
        self._install_simulation(simulation)

    def _apply_life_role(self, role: str) -> None:
        """Apply one authoritative role preset only to a stopped scenario."""

        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            return
        if role == self.simulation.digital_life_config.role:
            return
        simulation = create_single_digital_life_simulation(
            virtual_user_config=self.simulation.virtual_user_config,
            polar_h10_config=self.simulation.polar_h10_config,
            garden_input_config=self.simulation.garden_input_config,
            digital_life_config=digital_life_config_for_role(role),
        )
        self._install_simulation(simulation)

    def _install_simulation(self, simulation: SingleDigitalLifeSimulation) -> None:
        """Rebind every panel before controller reset/publish signals are emitted."""

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
        self.digital_life_panel.set_component(simulation.digital_life_component)
        self.digital_life_panel.set_config(simulation.digital_life_config)
        self.digital_life_panel.reset_views()
        self.controller.replace_engine(simulation.engine)

    def _update_life_snapshot(self, snapshot: ControllerSnapshot) -> None:
        self.digital_life_panel.update_diagnostics(snapshot.engine)

    def _reset_life_view(self, _events) -> None:
        self.digital_life_panel.reset_views()


DigitalLifeMainWindow = SingleDigitalLifeMainWindow
