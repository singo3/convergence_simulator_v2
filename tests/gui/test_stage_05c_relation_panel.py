"""Offscreen contract tests for the read-only Stage 5C relation panel."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QScrollArea

from symbiotic_sim_v2.digital_life.relation_memory.intrinsic import (
    derive_relation_memory_intrinsic_profile,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.session_state import (
    RelationMemorySessionState,
)
from symbiotic_sim_v2.gui.relation_memory_chart import (
    RELATION_MEMORY_CHART_MIN_HEIGHT,
    RELATION_MEMORY_PLOT_MIN_HEIGHT,
)
from symbiotic_sim_v2.gui.relation_memory_panel import RelationMemoryPanel


class FakeAdaptiveComponent:
    def __init__(self, life_id: str, role: str) -> None:
        self.life_id = life_id
        self.role = role
        self.initial = RelationMemoryPersistentState.fresh(life_id)
        self.final = None
        self.session = RelationMemorySessionState.fresh(self.initial)
        self.transitions: tuple[object, ...] = ()
        self.signals: tuple[object, ...] = ()
        self.g = 0

    def relation_memory_intrinsic_profile(self):
        return derive_relation_memory_intrinsic_profile(self.life_id)

    def relation_memory_session_state(self):
        return self.session

    def relation_memory_transition_records(self):
        return self.transitions

    def adaptive_signal_records(self):
        return self.signals

    def initial_persistent_state(self):
        return self.initial

    def final_persistent_state(self):
        return self.final

    def snapshot(self):
        return SimpleNamespace(
            digital_life_id=self.life_id,
            role=self.role,
            current_g=self.g,
            holder_matches=bool(self.g),
        )

    def populate_explore(self) -> None:
        profile = self.relation_memory_intrinsic_profile()
        trial = (0.72, 0.5, 0.61, 0.5)
        self.g = 1
        self.session = replace(
            self.session,
            w_anchor_session=0.48,
            anchor_evaluated=True,
            k_trial=trial,
            w_trial_1=0.61,
            w_trial_2=0.63,
            adaptation_phase="accepted",
            exploration_decision="explore",
            u_explore=0.2,
            p_explore=1.0,
            sigma=0.3,
            direction_xi=(0.8, 0.0, 0.6, 0.0),
            candidate_generated=True,
            candidate_generation_trial_index=0,
            candidate_effective_signal_index=62,
            adoption_result="accepted",
            valid_trial_evaluation_count=2,
            session_finalized=True,
        )
        self.transitions = (
            SimpleNamespace(
                transition_index=0,
                signal_index=61,
                signal_time_us=61_000_000,
                digital_life_id=self.life_id,
                g=1,
                bundle_index=0,
                evaluation_id="bundle-0",
                evaluation_quality="valid",
                evaluation_is_valid=True,
                w=0.48,
                phase_before="anchor_evaluation",
                phase_after="trial",
                exploration_decision="explore",
                curiosity=profile.curiosity,
                sigma_min=profile.sigma_min,
                sigma_max=profile.sigma_max,
                sigma=0.3,
                epsilon_accept=profile.epsilon_accept,
                p_explore_min=profile.p_explore_min,
                p_explore=1.0,
                u_explore=0.2,
                direction_trial_index=0,
                direction_u_f=0.8,
                direction_u_t=0.6,
                direction_norm=1.0,
                direction_xi=(0.8, 0.0, 0.6, 0.0),
                k_anchor_before=self.initial.k_anchor,
                k_current_before=self.initial.k_anchor,
                k_trial=trial,
                k_current_after=trial,
                k_anchor_after=self.initial.k_anchor,
                w_anchor_session_before=None,
                w_anchor_session_after=0.48,
                w_trial_1_before=None,
                w_trial_1_after=None,
                w_trial_2_before=None,
                w_trial_2_after=None,
                provisional_condition=None,
                confirmation_condition_1=None,
                confirmation_condition_2=None,
                candidate_mean_w=None,
                trial_count_before=0,
                trial_count_after=1,
                session_count_used=0,
                session_count_after=0,
                adoption_result="pending",
                rollback_reason=None,
                candidate_effective_signal_index=62,
                relation_update_effective_policy_version="next-signal",
                algorithm_version=self.initial.algorithm_version,
                state_schema_version=self.initial.state_schema_version,
                schema_version="transition-v1",
            ),
            SimpleNamespace(
                transition_index=1,
                signal_index=181,
                signal_time_us=181_000_000,
                digital_life_id=self.life_id,
                g=1,
                bundle_index=2,
                evaluation_id="bundle-2",
                evaluation_quality="valid",
                evaluation_is_valid=True,
                w=0.63,
                phase_before="confirmation",
                phase_after="accepted",
                exploration_decision="explore",
                curiosity=profile.curiosity,
                sigma_min=profile.sigma_min,
                sigma_max=profile.sigma_max,
                sigma=0.3,
                epsilon_accept=profile.epsilon_accept,
                p_explore_min=profile.p_explore_min,
                p_explore=1.0,
                u_explore=0.2,
                direction_trial_index=0,
                direction_u_f=0.8,
                direction_u_t=0.6,
                direction_norm=1.0,
                direction_xi=(0.8, 0.0, 0.6, 0.0),
                k_anchor_before=self.initial.k_anchor,
                k_current_before=trial,
                k_trial=trial,
                k_current_after=trial,
                k_anchor_after=trial,
                w_anchor_session_before=0.48,
                w_anchor_session_after=0.48,
                w_trial_1_before=0.61,
                w_trial_1_after=0.61,
                w_trial_2_before=None,
                w_trial_2_after=0.63,
                provisional_condition=None,
                confirmation_condition_1=True,
                confirmation_condition_2=True,
                candidate_mean_w=0.62,
                trial_count_before=1,
                trial_count_after=1,
                session_count_used=0,
                session_count_after=1,
                adoption_result="accepted",
                rollback_reason=None,
                candidate_effective_signal_index=62,
                relation_update_effective_policy_version="next-signal",
                algorithm_version=self.initial.algorithm_version,
                state_schema_version=self.initial.state_schema_version,
                schema_version="transition-v1",
            ),
        )
        self.signals = (
            _signal(self.life_id, self.role, 61, 61_000_000, 0, self.initial.k_anchor),
            _signal(self.life_id, self.role, 62, 62_000_000, 1, trial),
            _signal(self.life_id, self.role, 181, 181_000_000, 2, trial),
        )
        self.final = replace(
            self.initial,
            k_anchor=trial,
            trial_count=1,
            session_count=1,
        )


def _signal(life_id, role, index, time_us, bundle, k):
    return SimpleNamespace(
        signal_index=index,
        signal_time_us=time_us,
        digital_life_id=life_id,
        role=role,
        s=1,
        bundle_index=bundle,
        phase=f"bundle_{bundle}",
        evaluation_id=f"bundle-{bundle}",
        evaluation_quality="valid",
        is_new_valid_evaluation=True,
        g=1,
        w=0.5,
        k_anchor_before=(0.5, 0.5, 0.5, 0.5),
        k_current_before=k,
        k_presented=k,
        b_presented=k,
        relation_phase_before="trial",
        relation_phase_after="trial",
        k_current_after=k,
        k_anchor_after=k if bundle == 2 else (0.5, 0.5, 0.5, 0.5),
        candidate_effective_next_signal=bundle == 0,
        q_before=0.5,
        q_after=0.5,
        e_before=0.0,
        e_after=0.0,
        schema_version="signal-v1",
    )


@pytest.fixture
def relation_panel(qtbot):
    components = {
        f"life-{role}": FakeAdaptiveComponent(f"life-{role}", role)
        for role in ("red", "green", "blue")
    }
    panel = RelationMemoryPanel(
        components,
        preset_name="off_center_green",
        diagnostic_optimum_ft=(0.9, (125.0 - 10.0) / 155.0),
    )
    qtbot.addWidget(panel)
    panel.resize(1280, 800)
    panel.show()
    qtbot.wait(20)
    yield panel, components
    panel.close()


def _snapshot(time_us: int):
    return SimpleNamespace(current_time_us=time_us)


def _point_count(item) -> int:
    return 0 if item.xData is None else len(item.xData)


def test_panel_copy_cards_parameters_charts_tables_and_non_input_notice(
    relation_panel,
) -> None:
    panel, _components = relation_panel
    assert "Bundle 0" in panel.description_label.text()
    assert "Bundle 1" in panel.description_label.text()
    assert "Bundle 2" in panel.description_label.text()
    assert "W=0.5" in panel.baseline_notice.text()
    assert "RuntimeやGardenは候補を選びません" in panel.ownership_notice.text()
    assert "探索計算には" in panel.optimum_notice.text()
    assert set(panel.life_cards) == {"life-red", "life-green", "life-blue"}
    assert all(len(labels) == 19 for labels in panel.life_value_labels.values())
    assert all(len(labels) == 9 for labels in panel.parameter_value_labels.values())
    assert panel.transition_model.columnCount() == 52
    assert panel.signal_model.columnCount() == 26
    assert panel.persistent_model.columnCount() == 10
    assert [panel.table_tabs.tabText(index) for index in range(3)] == [
        "relation transition",
        "adaptive signal",
        "persistent before / after",
    ]
    assert panel.chart.optimum_visible
    assert _point_count(panel.chart.optimum_item) == 1
    assert panel.chart.minimumHeight() >= RELATION_MEMORY_CHART_MIN_HEIGHT
    assert all(
        plot.minimumHeight() >= RELATION_MEMORY_PLOT_MIN_HEIGHT
        for plot in panel.chart.plots
    )


@pytest.mark.parametrize(("width", "height"), ((1280, 800), (1560, 980)))
def test_panel_is_vertically_scrollable_with_splitter_and_readable_regions(
    relation_panel,
    qtbot,
    width: int,
    height: int,
) -> None:
    panel, _components = relation_panel
    panel.resize(width, height)
    qtbot.wait(20)
    scroll = panel.diagnostics_scroll
    assert isinstance(scroll, QScrollArea)
    assert scroll.widget() is panel.diagnostics_content
    assert scroll.widgetResizable()
    assert scroll.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.verticalScrollBar().maximum() > 0
    assert scroll.horizontalScrollBar().maximum() == 0
    assert panel.table_tabs.minimumHeight() >= 300
    assert not panel.chart_table_splitter.isCollapsible(0)
    assert not panel.chart_table_splitter.isCollapsible(1)

    scroll.verticalScrollBar().setValue(300)
    target = panel.chart.graphics.viewport()
    center = target.rect().center()
    wheel_event = QWheelEvent(
        QPointF(center),
        QPointF(target.mapToGlobal(center)),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    before = scroll.verticalScrollBar().value()
    QApplication.sendEvent(target, wheel_event)
    assert wheel_event.isAccepted()
    assert scroll.verticalScrollBar().value() > before


def test_component_records_populate_cards_spatial_w_timeline_and_tables(
    relation_panel,
) -> None:
    panel, components = relation_panel
    components["life-green"].populate_explore()
    panel.update_diagnostics(_snapshot(181_000_000))

    assert panel.transition_model.rowCount() == 2
    assert panel.signal_model.rowCount() == 3
    assert panel.persistent_model.rowCount() == 4
    labels = panel.life_value_labels["life-green"]
    assert labels["g"].text() == "1"
    assert labels["holder"].text() == "self"
    assert labels["adaptation_phase"].text() == "accepted"
    assert labels["exploration_decision"].text() == "explore"
    assert labels["w_anchor_session"].text() == "0.480000"
    assert labels["w_trial_1"].text() == "0.610000"
    assert labels["w_trial_2"].text() == "0.630000"
    assert labels["adoption_result"].text() == "accepted"
    parameters = panel.parameter_value_labels["life-green"]
    assert parameters["sigma"].text() == "0.300000"
    assert parameters["direction_u_f"].text() == "0.800000"
    assert parameters["direction_xi"].text() == (
        "[0.800000, 0.000000, 0.600000, 0.000000]"
    )
    assert _point_count(panel.chart.trial_items["life-green"]) == 1
    assert _point_count(panel.chart.current_items["life-green"]) == 2
    assert _point_count(panel.chart.w_anchor_items["life-green"]) == 1
    assert _point_count(panel.chart.w_trial_1_items["life-green"]) == 1
    assert _point_count(panel.chart.w_trial_2_items["life-green"]) == 1
    assert _point_count(panel.chart.w_mean_items["life-green"]) == 1
    assert _point_count(panel.chart.effective_items["life-green"]) == 1
    assert _point_count(panel.chart.adoption_items["life-green"]) == 1
    assert panel.chart.timeline_current_line.value() == 181.0


def test_non_off_center_preset_hides_optimum_and_reset_keeps_before_only(
    relation_panel,
) -> None:
    panel, components = relation_panel
    panel.set_diagnostic_optimum("aligned_green_center", (0.5, 0.5))
    panel.update_diagnostics(_snapshot(0))
    assert not panel.optimum_notice.isVisible()
    assert not panel.chart.optimum_visible

    components["life-green"].populate_explore()
    panel.update_diagnostics(_snapshot(240_000_000))
    assert panel.persistent_model.rowCount() == 4
    components["life-green"].transitions = ()
    components["life-green"].signals = ()
    components["life-green"].final = None
    components["life-green"].session = RelationMemorySessionState.fresh(
        components["life-green"].initial
    )
    panel.reset_views()
    assert panel.transition_model.rowCount() == 0
    assert panel.signal_model.rowCount() == 0
    assert panel.persistent_model.rowCount() == 3
    assert panel.chart.transition_count == 0


def test_panel_rejects_missing_component_api() -> None:
    with pytest.raises(TypeError, match="missing relation-memory GUI API"):
        RelationMemoryPanel({"a": object(), "b": object(), "c": object()})
