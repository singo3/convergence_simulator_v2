"""Stage 6 seven-tab main window for logical virtual-light feedback."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QLabel

from symbiotic_sim_v2.gui.controller import ControllerSnapshot, SimulationController
from symbiotic_sim_v2.gui.light_output_panel import LightOutputPanel
from symbiotic_sim_v2.gui.three_life_window import ThreeDigitalLifeMainWindow
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    LightFeedbackSimulation,
    create_light_feedback_simulation,
)
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig

WINDOW_TITLE = (
    "環境共生型デジタル生命シミュレーター v2 — 光点滅シミュレーター"
)


class LightSimulationMainWindow(ThreeDigitalLifeMainWindow):
    """Add Stage 6 light diagnostics while retaining all six upstream tabs."""

    def __init__(
        self,
        controller: SimulationController,
        simulation: LightFeedbackSimulation,
    ) -> None:
        upstream = simulation.upstream_simulation
        super().__init__(controller, upstream)
        self.simulation = simulation
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1560, 980)

        self.light_output_panel = LightOutputPanel(
            simulation.garden_light_mapper_config,
            simulation.garden_light_mapper_component,
            simulation.virtual_light_device_config,
            simulation.virtual_light_device_component,
            self.tabs,
        )
        self.light_panel = self.light_output_panel
        self.virtual_light_panel = self.light_output_panel
        self.tabs.insertTab(0, self.light_output_panel, "光点滅シミュレーター")
        self._apply_stage_6_copy()

        self.controller.snapshot_changed.connect(self._update_stage_6_snapshot)
        self.controller.scenario_reset.connect(self._reset_stage_6_view)
        self.controller.speed_changed.connect(self.light_output_panel.set_speed_mode)
        self._update_stage_6_snapshot(self.controller.current_snapshot())
        self.tabs.setCurrentWidget(self.light_output_panel)

    def _apply_stage_6_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText("光点滅シミュレーター  ·  Stage 06")

        output_timing = self.garden_output_panel.findChild(
            QLabel,
            "gardenOutputTimingNotice",
        )
        if output_timing is not None:
            output_timing.setText(
                "active qualified Bはholder touchの実到着時刻に正式出力し、"
                "Stage 6では同じeffective timeのLightCommandへ変換します。"
                "round finalizeは引き続きfeedback・第2周同期の境界です。"
            )
        no_light = self.garden_output_panel.findChild(
            QLabel,
            "gardenOutputNoLightNotice",
        )
        if no_light is not None:
            no_light.setText(
                "Garden出力資格層自身はHue、BPM、光波形Iを生成しません。"
                "GardenQualifiedBEvent v2だけをStage 6 Mapperへ渡します。"
            )

        diagnostic_note = self.time_diagnostics_tab.findChild(
            QLabel,
            "stageDescription",
        )
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "integer-microseconds時計とdeterministic event orderingを、"
                "VirtualUser→H10→Garden→3生命→qualified B→LightCommand→"
                "LightStimulusStateEventの240秒scenarioで確認します。"
            )
        speed_note = self.findChild(QLabel, "speedNote")
        if speed_note is not None:
            speed_note.setText(
                "速度は論理光の結果を変えません。10倍・100倍・最速では"
                "安全のため実光previewだけを自動OFFにします。"
            )

    def _apply_config(self, config: VirtualUserConfig) -> None:
        """Rebuild Stage 6, never fall back to the Stage 5B.1 factory."""

        if self.controller.current_snapshot().engine.state is not ClockState.STOPPED:
            return
        previous = self.simulation
        upstream = previous.upstream_simulation
        selected_user_config = replace(
            config,
            duration_seconds=upstream.garden_input_config.total_duration_seconds,
        )
        selected_h10_config = replace(
            upstream.polar_h10_config,
            expected_user_id=selected_user_config.user_id,
        )
        simulation = create_light_feedback_simulation(
            virtual_user_config=selected_user_config,
            polar_h10_config=selected_h10_config,
            garden_input_config=upstream.garden_input_config,
            digital_life_configs=upstream.digital_life_configs,
            runtime_config=upstream.runtime_config,
            garden_output_config=upstream.garden_output_config,
            garden_light_mapper_config=previous.garden_light_mapper_config,
            virtual_light_device_config=previous.virtual_light_device_config,
        )
        self._install_light_simulation(simulation)

    def _install_light_simulation(
        self,
        simulation: LightFeedbackSimulation,
    ) -> None:
        """Rebind all seven views before controller reset signals are emitted."""

        upstream = simulation.upstream_simulation
        self.simulation = simulation
        self.virtual_user_panel.set_component(upstream.virtual_user_component)
        self.virtual_user_panel.set_config(upstream.virtual_user_config)
        self.virtual_user_panel.duration_spin.setEnabled(False)
        self.virtual_user_panel.reset_views()
        self.polar_h10_panel.set_components(
            upstream.polar_h10_component,
            upstream.virtual_user_component,
        )
        self.polar_h10_panel.set_duration_seconds(
            upstream.virtual_user_config.duration_seconds
        )
        self.garden_input_panel.set_component(upstream.garden_input_component)
        self.garden_input_panel.set_config(upstream.garden_input_config)
        self.garden_input_panel.reset_views()
        self.multi_life_panel.set_components(
            upstream.digital_life_components,
            upstream.garden_output_component,
        )
        self.multi_life_panel.chart.set_duration_seconds(
            upstream.garden_input_config.total_duration_seconds
        )
        self.multi_life_panel.reset_views()
        self.garden_output_panel.set_component(upstream.garden_output_component)
        self.garden_output_panel.set_config(upstream.garden_output_config)
        self.garden_output_panel.set_duration_seconds(
            upstream.garden_input_config.total_duration_seconds
        )
        self.garden_output_panel.reset_views()
        self.light_output_panel.set_components(
            simulation.garden_light_mapper_config,
            simulation.garden_light_mapper_component,
            simulation.virtual_light_device_config,
            simulation.virtual_light_device_component,
        )
        self.light_output_panel.reset_views()
        self.controller.replace_engine(simulation.engine)

    def _update_stage_6_snapshot(self, snapshot: ControllerSnapshot) -> None:
        self.light_output_panel.update_diagnostics(snapshot.engine, snapshot.speed_mode)

    def _reset_stage_6_view(self, _events) -> None:
        self.light_output_panel.reset_views()


LightFeedbackMainWindow = LightSimulationMainWindow
VirtualLightMainWindow = LightSimulationMainWindow
