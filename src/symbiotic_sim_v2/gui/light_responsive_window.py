"""Stage 7 eight-tab fixed-preference light-responsive closed-loop window."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QLabel

from symbiotic_sim_v2.gui.controller import ControllerSnapshot, SimulationController
from symbiotic_sim_v2.gui.light_response_user_panel import LightResponseUserPanel
from symbiotic_sim_v2.gui.light_simulation_window import LightSimulationMainWindow
from symbiotic_sim_v2.runtime.closed_loop.light_responsive_scenario import (
    LightResponsiveClosedLoopSimulation,
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig

WINDOW_TITLE = (
    "環境共生型デジタル生命シミュレーター v2 — 光応答仮想ユーザー閉ループ"
)


class LightResponsiveMainWindow(LightSimulationMainWindow):
    """Add Stage 7 response diagnostics while retaining every Stage 2–6 tab."""

    def __init__(
        self,
        controller: SimulationController,
        simulation: LightResponsiveClosedLoopSimulation,
        *,
        preset_name: str = "aligned_green_center",
    ) -> None:
        super().__init__(controller, simulation.upstream_simulation)
        self.simulation = simulation
        self._light_response_preset_name = preset_name
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1560, 980)

        responsive_user = simulation.light_responsive_virtual_user_component
        self.virtual_user_panel.set_component(responsive_user)
        self.virtual_user_panel.set_config(simulation.virtual_user_config)
        self.virtual_user_panel.duration_spin.setEnabled(False)
        self.virtual_user_panel.reset_views()
        self.polar_h10_panel.set_components(
            simulation.polar_h10_component,
            responsive_user,
        )

        self.light_response_user_panel = LightResponseUserPanel(
            simulation.light_response_config,
            responsive_user,
            simulation.garden_input_component,
            self.tabs,
            preset_name=preset_name,
        )
        self.light_responsive_user_panel = self.light_response_user_panel
        self.response_panel = self.light_response_user_panel
        self.tabs.insertTab(
            0,
            self.light_response_user_panel,
            "光応答仮想ユーザー",
        )
        self.tabs.setTabText(5, "仮想ユーザー心拍")
        self._apply_stage_7_copy()

        self.light_response_user_panel.config_applied.connect(
            self._apply_light_response_config
        )
        self.controller.snapshot_changed.connect(self._update_stage_7_snapshot)
        self.controller.scenario_reset.connect(self._reset_stage_7_view)
        self._update_stage_7_snapshot(self.controller.current_snapshot())
        self.tabs.setCurrentWidget(self.light_response_user_panel)

    def _apply_stage_7_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText("光応答仮想ユーザー閉ループ  ·  Stage 07")

        self.light_output_panel.no_response_notice.setText(
            "Stage 7ではLightStimulusStateEventだけを光応答仮想"
            "ユーザーの正式光入力とします。"
        )
        flow_nodes = self.light_output_panel.findChildren(QLabel, "lightFlowNode")
        if flow_nodes:
            flow_nodes[-1].setText("光応答仮想ユーザー")

        virtual_user_notice = self.virtual_user_panel.findChild(
            QLabel, "stageDescription"
        )
        if virtual_user_notice is not None:
            virtual_user_notice.setText(
                "Stage 7の光応答仮想ユーザーも、正式出力は"
                "HeartbeatEventだけです。このtabは心拍内部真値の"
                "開発用診断を表示します。"
            )
        stimulus_notice = self.virtual_user_panel.findChild(QLabel, "stimulusNotice")
        if stimulus_notice is not None:
            stimulus_notice.setText(
                "光への固定反応特性とR(t)は、光応答仮想ユーザーtabで"
                "確認します。このtabは生成された心拍の診断表示です。"
            )

        diagnostic_note = self.time_diagnostics_tab.findChild(
            QLabel, "stageDescription"
        )
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "integer-microseconds時計とdeterministic event orderingを、"
                "LightStimulusStateEvent→固定好み→R(t)→HeartbeatEvent→"
                "H10→Garden→3生命→光の240秒閉ループで確認します。"
            )
        speed_note = self.findChild(QLabel, "speedNote")
        if speed_note is not None:
            speed_note.setText(
                "速度は閉ループの結果を変えません。10倍・100倍・最速では"
                "安全のため実光previewだけを自動OFFにします。"
            )

    def _apply_config(self, config: VirtualUserConfig) -> None:
        """Rebuild Stage 7 after a stopped base-physiology settings change."""

        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            return
        selected = replace(
            config,
            duration_seconds=self.simulation.garden_input_config.total_duration_seconds,
        )
        selected_h10 = replace(
            self.simulation.polar_h10_config,
            expected_user_id=selected.user_id,
        )
        rebuilt = self._create_simulation(
            virtual_user_config=selected,
            polar_h10_config=selected_h10,
            light_response_config=self.simulation.light_response_config,
        )
        self._install_simulation(rebuilt, self._light_response_preset_name)

    def _apply_light_response_config(self, config: LightResponseConfig) -> None:
        """Rebuild the whole loop when a stopped fixed characteristic is applied."""

        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            return
        preset_name = self.light_response_user_panel.preset_name
        rebuilt = self._create_simulation(
            virtual_user_config=self.simulation.virtual_user_config,
            polar_h10_config=self.simulation.polar_h10_config,
            light_response_config=config,
        )
        self._install_simulation(rebuilt, preset_name)

    def _create_simulation(
        self,
        *,
        virtual_user_config: VirtualUserConfig,
        polar_h10_config,
        light_response_config: LightResponseConfig,
    ) -> LightResponsiveClosedLoopSimulation:
        return create_light_responsive_closed_loop_simulation(
            virtual_user_config=virtual_user_config,
            polar_h10_config=polar_h10_config,
            garden_input_config=self.simulation.garden_input_config,
            digital_life_configs=self.simulation.digital_life_configs,
            runtime_config=self.simulation.runtime_config,
            garden_output_config=self.simulation.garden_output_config,
            garden_light_mapper_config=self.simulation.garden_light_mapper_config,
            virtual_light_device_config=self.simulation.virtual_light_device_config,
            light_response_config=light_response_config,
        )

    def _install_simulation(
        self,
        simulation: LightResponsiveClosedLoopSimulation,
        preset_name: str,
    ) -> None:
        """Rebind all eight views before controller reset signals are emitted."""

        responsive_user = simulation.light_responsive_virtual_user_component
        upstream = simulation.upstream_simulation.upstream_simulation
        self.simulation = simulation
        self._light_response_preset_name = preset_name

        self.virtual_user_panel.set_component(responsive_user)
        self.virtual_user_panel.set_config(simulation.virtual_user_config)
        self.virtual_user_panel.duration_spin.setEnabled(False)
        self.virtual_user_panel.reset_views()
        self.polar_h10_panel.set_components(
            simulation.polar_h10_component,
            responsive_user,
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
        self.light_output_panel.set_components(
            simulation.garden_light_mapper_config,
            simulation.garden_light_mapper_component,
            simulation.virtual_light_device_config,
            simulation.virtual_light_device_component,
        )
        self.light_output_panel.reset_views()
        self.light_response_user_panel.set_components(
            simulation.light_response_config,
            responsive_user,
            simulation.garden_input_component,
            preset_name=preset_name,
        )
        self.light_response_user_panel.reset_views()
        if upstream.virtual_user_component is not responsive_user:
            raise RuntimeError("Stage 7 GUI is not bound to the responsive heartbeat source")
        self.controller.replace_engine(simulation.engine)

    def _update_stage_7_snapshot(self, snapshot: ControllerSnapshot) -> None:
        self.light_response_user_panel.update_diagnostics(snapshot.engine)

    def _reset_stage_7_view(self, _events) -> None:
        self.light_response_user_panel.reset_views()


LightResponsiveVirtualUserMainWindow = LightResponsiveMainWindow
LightResponsiveClosedLoopMainWindow = LightResponsiveMainWindow
