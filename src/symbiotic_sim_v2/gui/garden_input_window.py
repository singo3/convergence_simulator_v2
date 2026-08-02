"""Stage 4 main window composing Garden, user, H10, and time views."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QLabel

from symbiotic_sim_v2.garden.input_layer.scenario import (
    GardenInputSimulation,
    create_garden_input_simulation,
)
from symbiotic_sim_v2.gui.controller import ControllerSnapshot, SimulationController
from symbiotic_sim_v2.gui.garden_input_panel import GardenInputPanel
from symbiotic_sim_v2.gui.polar_h10_window import PolarH10MainWindow
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig

WINDOW_TITLE = "環境共生型デジタル生命シミュレーター v2 — Garden入力層"

STAGE_4_VIRTUAL_USER_NOTICE = (
    "Stage 4でも仮想ユーザーの正式出力はHeartbeatEventだけです。"
    "このtabのRRI・RMSSDは仮想ユーザー内部の開発用診断です。"
)
STAGE_4_TRUE_VALUE_NOTICE = (
    "Garden入力層が受け取るのは仮想ユーザー内部真値ではなく、"
    "Polar H10の正式なRriMeasurementEventだけです。"
)


class GardenInputMainWindow(PolarH10MainWindow):
    """Add the Stage 4 Garden tab while retaining all Stage 2/3 views."""

    def __init__(
        self,
        controller: SimulationController,
        simulation: GardenInputSimulation,
    ) -> None:
        # GardenInputSimulation deliberately preserves the Stage 2 aliases and all
        # Stage 3 fields.  Do not override _apply_stage_3_copy: its construction-time
        # dynamic dispatch must remain the Stage 3 implementation.
        super().__init__(controller, simulation)
        self.simulation = simulation
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1560, 980)

        self.garden_input_panel = GardenInputPanel(
            simulation.garden_input_config,
            simulation.garden_input_component,
            self.tabs,
        )
        self.tabs.insertTab(0, self.garden_input_panel, "Garden入力層")
        self.garden_input_tab = self.garden_input_panel
        self.garden_panel = self.garden_input_panel
        self._apply_stage_4_copy()

        # The fixed Garden session is 240 seconds; Stage 4 keeps the retained Stage 2
        # setting visible but read-only so applying unrelated physiology settings cannot
        # create an invalid cross-component duration.
        self.virtual_user_panel.duration_spin.setEnabled(False)
        self.virtual_user_panel.duration_spin.setToolTip(
            "Stage 4 Gardenセッションは240秒固定です。"
        )

        self.controller.snapshot_changed.connect(self._update_garden_snapshot)
        self.controller.scenario_reset.connect(self._reset_garden_view)
        self._update_garden_snapshot(self.controller.current_snapshot())
        self.tabs.setCurrentWidget(self.garden_input_panel)

    def _apply_stage_4_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText("Garden入力層  ·  Stage 04")

        virtual_user_notice = self.virtual_user_panel.findChild(QLabel, "stageDescription")
        if virtual_user_notice is not None:
            virtual_user_notice.setText(STAGE_4_VIRTUAL_USER_NOTICE)
        true_value_notice = self.virtual_user_panel.findChild(QLabel, "diagnosticNotice")
        if true_value_notice is not None:
            true_value_notice.setText(STAGE_4_TRUE_VALUE_NOTICE)

        h10_flow_nodes = self.polar_h10_panel.findChildren(QLabel, "flowNode")
        if h10_flow_nodes:
            h10_flow_nodes[-1].setText("Garden入力層")
        h10_boundary = self.polar_h10_panel.findChild(QLabel, "h10BoundaryNotice")
        if h10_boundary is not None:
            h10_boundary.setText(
                "RRIのartifact判定、評価窓RMSSD、N、SはGarden入力層tabで"
                "確認します。H10自身はこれらを計算しません。"
            )

        diagnostic_note = self.time_diagnostics_tab.findChild(QLabel, "stageDescription")
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "Stage 1のinteger-microseconds時計とdeterministic event orderingを、"
                "VirtualUser→Polar H10→Garden入力層の240秒scenarioで確認します。"
            )
        speed_note = self.findChild(QLabel, "speedNote")
        if speed_note is not None:
            speed_note.setText(
                "速度は実時間上の進み方だけを変え、RRI判定・評価・N/Sは変えません。"
            )

    def _apply_config(self, config: VirtualUserConfig) -> None:
        """Rebuild and rebind all three Stage 4 components as one scenario."""

        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            return
        garden_config = self.simulation.garden_input_config
        selected_user_config = replace(
            config,
            duration_seconds=garden_config.total_duration_seconds,
        )
        selected_h10_config = replace(
            self.simulation.polar_h10_config,
            expected_user_id=selected_user_config.user_id,
        )
        simulation = create_garden_input_simulation(
            selected_user_config,
            selected_h10_config,
            garden_config,
        )
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
        self.controller.replace_engine(simulation.engine)

    def _update_garden_snapshot(self, snapshot: ControllerSnapshot) -> None:
        """Forward one immutable engine snapshot to the Garden observation panel."""

        self.garden_input_panel.update_diagnostics(snapshot.engine)

    def _reset_garden_view(self, _events) -> None:
        self.garden_input_panel.reset_views()
