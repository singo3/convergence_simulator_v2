"""Stage 5C nine-tab confirmed relation-memory closed-loop window."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtWidgets import QLabel

from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.gui.controller import ControllerSnapshot, SimulationController
from symbiotic_sim_v2.gui.light_responsive_window import LightResponsiveMainWindow
from symbiotic_sim_v2.gui.relation_memory_panel import RelationMemoryPanel
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig

WINDOW_TITLE = (
    "環境共生型デジタル生命シミュレーター v2 — 3Bundle関係記憶探索"
)
OFF_CENTER_DIAGNOSTIC_OPTIMUM_FT = (0.9, (125.0 - 10.0) / 155.0)


def _diagnostic_optimum(preset_name: str) -> tuple[float, float] | None:
    """Expose the off-center optimum to GUI diagnostics only."""

    return (
        OFF_CENTER_DIAGNOSTIC_OPTIMUM_FT
        if preset_name == "off_center_green"
        else None
    )


class AdaptiveClosedLoopMainWindow(LightResponsiveMainWindow):
    """Add relation-memory observation while retaining all Stage 7.1 views."""

    def __init__(
        self,
        controller: SimulationController,
        simulation: AdaptiveRelationMemoryClosedLoopSimulation,
        *,
        preset_name: str = "off_center_green",
    ) -> None:
        components = adaptive_digital_life_components(simulation)
        self._initial_persistent_states_by_life_id: Mapping[
            str, RelationMemoryPersistentState
        ] = {
            life_id: component.initial_persistent_state()
            for life_id, component in components.items()
        }
        super().__init__(controller, simulation, preset_name=preset_name)
        self.setWindowTitle(WINDOW_TITLE)

        self.relation_memory_panel = RelationMemoryPanel(
            components,
            self.tabs,
            preset_name=preset_name,
            diagnostic_optimum_ft=_diagnostic_optimum(preset_name),
            garden_output_component=simulation.garden_output_component,
            garden_light_mapper_component=(
                simulation.garden_light_mapper_component
            ),
        )
        self.tabs.insertTab(0, self.relation_memory_panel, "関係記憶探索")
        self._apply_stage_5c_copy()
        self.controller.snapshot_changed.connect(self._update_stage_5c_snapshot)
        self.controller.scenario_reset.connect(self._reset_stage_5c_view)
        self._update_stage_5c_snapshot(self.controller.current_snapshot())
        self.tabs.setCurrentWidget(self.relation_memory_panel)

    def _apply_stage_5c_copy(self) -> None:
        page_title = self.findChild(QLabel, "pageTitle")
        if page_title is not None:
            page_title.setText("3Bundle関係記憶探索  ·  Stage 05C")
        diagnostic_note = self.time_diagnostics_tab.findChild(
            QLabel,
            "stageDescription",
        )
        if diagnostic_note is not None:
            diagnostic_note.setText(
                "integer-microseconds時計上でBundle 0 anchor評価、"
                "Bundle 1 trial、Bundle 2確認とnext-signal反映を監査します。"
            )

    def _create_simulation(
        self,
        *,
        virtual_user_config: VirtualUserConfig,
        polar_h10_config,
        light_response_config: LightResponseConfig,
    ) -> AdaptiveRelationMemoryClosedLoopSimulation:
        return create_adaptive_relation_memory_closed_loop_simulation(
            virtual_user_config=virtual_user_config,
            polar_h10_config=polar_h10_config,
            garden_input_config=self.simulation.garden_input_config,
            digital_life_configs=self.simulation.digital_life_configs,
            runtime_config=self.simulation.runtime_config,
            garden_output_config=self.simulation.garden_output_config,
            garden_light_mapper_config=self.simulation.garden_light_mapper_config,
            virtual_light_device_config=self.simulation.virtual_light_device_config,
            light_response_config=light_response_config,
            initial_persistent_states_by_life_id=(
                self._initial_persistent_states_by_life_id
            ),
        )

    def _install_simulation(
        self,
        simulation: AdaptiveRelationMemoryClosedLoopSimulation,
        preset_name: str,
    ) -> None:
        super()._install_simulation(simulation, preset_name)
        self.relation_memory_panel.set_components(
            adaptive_digital_life_components(simulation)
        )
        self.relation_memory_panel.set_formal_output_components(
            simulation.garden_output_component,
            simulation.garden_light_mapper_component,
        )
        self.relation_memory_panel.set_diagnostic_optimum(
            preset_name,
            _diagnostic_optimum(preset_name),
        )

    def _update_stage_5c_snapshot(self, snapshot: ControllerSnapshot) -> None:
        self.relation_memory_panel.update_diagnostics(snapshot.engine)

    def _reset_stage_5c_view(self, _events) -> None:
        self.relation_memory_panel.reset_views()


RelationMemoryMainWindow = AdaptiveClosedLoopMainWindow

__all__ = [
    "AdaptiveClosedLoopMainWindow",
    "OFF_CENTER_DIAGNOSTIC_OPTIMUM_FT",
    "RelationMemoryMainWindow",
    "WINDOW_TITLE",
]
