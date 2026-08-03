"""Offscreen acceptance tests for Stage 8A record-backed GUI panels."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QTableView

from symbiotic_sim_v2.gui.convergence_history_table_model import (
    ConvergenceHistoryTableModel,
)
from symbiotic_sim_v2.gui.multi_session_convergence_chart import (
    MULTI_SESSION_CHART_MIN_HEIGHT,
)
from symbiotic_sim_v2.gui.multi_session_convergence_panel import (
    EXPLANATIONS,
    MULTI_SESSION_TABLE_MIN_HEIGHT,
    MultiSessionConvergencePanel,
)
from symbiotic_sim_v2.gui.session_history_table_model import (
    SessionHistoryTableModel,
)
from symbiotic_sim_v2.gui.stationary_user_type_panel import (
    ROLE_HUE_BANDS,
    STATIONARY_USER_HEATMAP_MIN_HEIGHT,
    STATIONARY_USER_TABLE_MIN_HEIGHT,
    StationaryUserTypePanel,
)
from symbiotic_sim_v2.gui.user_type_comparison_table_model import (
    UserTypeComparisonTableModel,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    evaluate_stationary_preference,
    stationary_user_type_profile,
)


@pytest.fixture
def user_profiles() -> dict[str, object]:
    user_type_ids = (
        "green_narrow_moderate",
        "red_blue_dual_peak",
        "flat_control",
    )
    return {
        user_type_id: stationary_user_type_profile(user_type_id)
        for user_type_id in user_type_ids
    }


def _final_k(offset: float) -> dict[str, tuple[float, float, float, float]]:
    return {
        "life-red": (0.20 + offset, 0.5, 0.30, 0.5),
        "life-green": (0.70 + offset, 0.5, 0.74, 0.5),
        "life-blue": (0.40 + offset, 0.5, 0.60, 0.5),
    }


@pytest.fixture
def stage8a_records():
    outcomes = (
        SimpleNamespace(
            session_index=0,
            valid_for_convergence=True,
            physiology_root_seed=100,
            holder_id="life-green",
            holder_final_hue_degree=128.0,
            holder_final_blink_bpm=118.0,
            holder_initial_hue_degree=125.0,
            holder_initial_blink_bpm=87.5,
            exploration_decision="hold",
            adoption_result="hold",
            candidate_generated=False,
            candidate_accepted=False,
            holder_k_trial=None,
            bundle_presentations=(),
            holder_W_anchor_session=0.61,
            holder_W_trial_1=None,
            holder_W_trial_2=None,
            final_k_anchor_by_life=_final_k(0.00),
        ),
        SimpleNamespace(
            session_index=1,
            valid_for_convergence=True,
            physiology_root_seed=101,
            holder_id="life-green",
            holder_final_hue_degree=129.0,
            holder_final_blink_bpm=121.0,
            holder_initial_hue_degree=128.0,
            holder_initial_blink_bpm=118.0,
            exploration_decision="explore",
            adoption_result="accepted",
            candidate_generated=True,
            candidate_accepted=True,
            holder_k_trial=(0.71, 0.5, 0.75, 0.5),
            bundle_presentations=(),
            holder_W_anchor_session=0.62,
            holder_W_trial_1=0.70,
            holder_W_trial_2=0.71,
            final_k_anchor_by_life=_final_k(0.01),
        ),
        SimpleNamespace(
            session_index=2,
            valid_for_convergence=True,
            physiology_root_seed=102,
            holder_id="life-green",
            holder_final_hue_degree=128.5,
            holder_final_blink_bpm=120.0,
            holder_initial_hue_degree=129.0,
            holder_initial_blink_bpm=121.0,
            exploration_decision="explore",
            adoption_result="rejected",
            candidate_generated=True,
            candidate_accepted=False,
            holder_k_trial=(0.91, 0.5, 0.22, 0.5),
            bundle_presentations=(),
            holder_W_anchor_session=0.63,
            holder_W_trial_1=0.60,
            holder_W_trial_2=0.59,
            final_k_anchor_by_life=_final_k(0.01),
        ),
        SimpleNamespace(
            session_index=3,
            valid_for_convergence=True,
            physiology_root_seed=103,
            holder_id="life-red",
            holder_final_hue_degree=4.0,
            holder_final_blink_bpm=65.0,
            holder_initial_hue_degree=5.0,
            holder_initial_blink_bpm=70.0,
            exploration_decision="hold",
            adoption_result="hold",
            candidate_generated=False,
            candidate_accepted=False,
            holder_k_trial=None,
            bundle_presentations=(),
            holder_W_anchor_session=0.55,
            holder_W_trial_1=None,
            holder_W_trial_2=None,
            final_k_anchor_by_life=_final_k(0.01),
        ),
    )
    records = tuple(
        SimpleNamespace(
            evaluated_at_session_index=index,
            window_session_indices=tuple(range(index + 1)),
            support_count=index + 1 if index < 3 else 3,
            window_size=4,
            holder_id="life-green",
            member_session_indices=tuple(range(index + 1)) if index < 3 else (0, 1, 2),
            outlier_session_indices=() if index < 3 else (3,),
            maximum_pairwise_distance=0.2,
            mean_pairwise_distance=0.1,
            medoid_session_index=min(index, 1),
            medoid_hue_degree=129.0,
            medoid_blink_bpm=121.0,
            convergence_state=(
                "insufficient_valid_sessions"
                if index < 2
                else (
                    "converged_monitoring"
                    if index == 2
                    else "converged_monitoring_latest_outlier"
                )
            ),
            latest_valid_session_is_outlier=index == 3,
            total_sessions_after_first_convergence=2 if index == 3 else 0,
            post_convergence_outlier_count=1 if index == 3 else 0,
            reconvergence_count=0,
        )
        for index in range(4)
    )
    truth_records = tuple(
        SimpleNamespace(
            evaluated_at_session_index=index,
            truth_classification=(
                "correct_convergence" if index >= 2 else "not_converged"
            ),
            preference_match_at_medoid=0.95 if index >= 2 else None,
            global_maximum_preference_match=1.0,
            response_gap=0.05 if index >= 2 else None,
            nearest_peak_id="green" if index >= 2 else None,
        )
        for index in range(4)
    )
    state = SimpleNamespace(
        completed_session_count=4,
        valid_session_count=4,
        next_session_index=4,
        session_outcomes=outcomes,
        convergence_records=records,
        first_convergence_session_index=2,
        current_convergence_state="converged_monitoring_latest_outlier",
    )
    config = SimpleNamespace(
        maximum_sessions=24,
        window_sessions=4,
        required_sessions=3,
        hue_tolerance_degree=2.0,
        blink_bpm_tolerance=20.0,
        truth_response_gap_threshold=0.05,
    )
    comparison = (
        SimpleNamespace(
            user_type_id="green_narrow_moderate",
            first_convergence_session_index=2,
            current_convergence_state="converged_monitoring_latest_outlier",
            dominant_holder_id="life-green",
            dominant_hue_degree=129.0,
            dominant_blink_bpm=121.0,
            truth_classification="correct_convergence",
            explore_count=2,
            accepted_candidate_count=1,
            post_convergence_outlier_rate=0.5,
        ),
    )
    return outcomes, records, truth_records, state, config, comparison


def test_table_models_project_outcomes_evaluator_truth_and_comparison(
    stage8a_records,
) -> None:
    outcomes, records, truth_records, _state, _config, comparison = stage8a_records
    sessions = SessionHistoryTableModel()
    convergence = ConvergenceHistoryTableModel()
    comparisons = UserTypeComparisonTableModel()

    sessions.set_records(outcomes, records, truth_records)
    convergence.set_records(records, truth_records)
    comparisons.set_records(comparison)

    assert sessions.rowCount() == 4
    assert sessions.columnCount() == 15
    assert sessions.row_at(3)["outlier"] is True
    assert sessions.row_at(3)["cluster_member"] is False
    assert sessions.row_at(3)["truth_classification"] == "correct_convergence"
    assert convergence.rowCount() == 4
    assert convergence.row_at(3)["member_indices"] == (0, 1, 2)
    assert convergence.row_at(3)["response_gap"] == pytest.approx(0.05)
    assert comparisons.rowCount() == 1
    assert comparisons.row_at(0)["dominant_life"] == "life-green"
    assert comparisons.row_at(0)["accepted_count"] == 1


def test_multi_session_panel_has_controls_cards_six_graphs_three_tables_and_locking(
    qtbot,
    user_profiles,
    stage8a_records,
) -> None:
    outcomes, records, truth_records, state, config, comparison = stage8a_records
    panel = MultiSessionConvergencePanel(
        user_profiles,
        convergence_config=config,
    )
    qtbot.addWidget(panel)
    panel.resize(1280, 800)
    panel.show()
    qtbot.wait(30)

    assert [label.text() for label in panel.explanation_labels] == list(EXPLANATIONS)
    assert panel.settings_values() == {
        "stationary_user_type": "green_narrow_moderate",
        "maximum_sessions": 24,
        "master_seed": 20_260_802,
        "session_seed_policy": "deterministic_per_session_physiology_seed_v0_1",
        "convergence_window": 4,
        "convergence_required": 3,
        "hue_tolerance_degree": 2.0,
        "blink_bpm_tolerance": 20.0,
        "truth_response_gap_threshold": 0.05,
    }
    assert len(panel.chart.plots) == 6
    assert panel.chart.minimumHeight() >= MULTI_SESSION_CHART_MIN_HEIGHT
    assert panel.table_tabs.count() == 3
    assert all(
        panel.table_tabs.widget(index).findChild(QTableView).minimumHeight()
        >= MULTI_SESSION_TABLE_MIN_HEIGHT
        for index in range(3)
    )
    assert isinstance(panel.diagnostics_scroll, QScrollArea)
    assert panel.diagnostics_scroll.verticalScrollBar().maximum() > 0
    assert panel.diagnostics_scroll.horizontalScrollBar().maximum() == 0
    assert not panel.chart_table_splitter.isCollapsible(0)
    assert not panel.chart_table_splitter.isCollapsible(1)

    requested: list[dict[str, object]] = []
    panel.next_session_requested.connect(requested.append)
    qtbot.mouseClick(panel.next_session_button, Qt.MouseButton.LeftButton)
    assert requested and requested[0]["convergence_required"] == 3
    assert not panel.user_type_combo.isEnabled()

    panel.set_settings(
        config,
        selected_user_type_id="green_narrow_moderate",
        master_seed=2**32 - 1,
        seed_policy="deterministic_per_session_physiology_seed_v0_1",
    )
    assert panel.settings_values()["master_seed"] == 2**32 - 1

    panel.set_state(
        state,
        convergence_config=config,
        user_profile=user_profiles["green_narrow_moderate"],
        comparison_rows=comparison,
        truth_alignment_records=truth_records,
    )
    assert panel.session_history_model.rowCount() == len(outcomes)
    assert panel.convergence_history_model.rowCount() == len(records)
    assert panel.comparison_model.rowCount() == 1
    assert panel.chart.session_count == 4
    assert panel.chart.convergence_record_count == 4
    assert panel.chart.truth_record_count == 4
    assert panel.chart.cluster_member_count == 3
    assert panel.chart.outlier_count == 1
    assert panel.chart.tolerance_ellipse.isVisible()
    assert panel.state_labels["convergence_state"].text() == (
        "converged_monitoring_latest_outlier"
    )
    assert panel.state_labels["support"].text() == "3 / 4"
    assert panel.state_labels["latest_outlier"].text() == "yes"
    assert panel.state_labels["truth_classification"].text() == "correct_convergence"
    assert panel.progress_bar.value() == 4
    assert not panel.user_type_combo.isEnabled()

    panel.reset_views()
    assert panel.session_history_model.rowCount() == 0
    assert panel.progress_bar.value() == 0
    assert panel.user_type_combo.isEnabled()


def test_stationary_user_panel_is_preset_only_scrollable_and_uses_core_evaluator(
    qtbot,
    user_profiles,
) -> None:
    calls: list[tuple[str, float, float]] = []

    def evaluator(
        profile,
        *,
        active: bool,
        hue_degree: float,
        blink_bpm: float,
    ):
        calls.append((profile.user_type_id, hue_degree, blink_bpm))
        return evaluate_stationary_preference(
            profile,
            active=active,
            hue_degree=hue_degree,
            blink_bpm=blink_bpm,
        )

    panel = StationaryUserTypePanel(
        user_profiles,
        landscape_evaluator=evaluator,
    )
    qtbot.addWidget(panel)
    panel.resize(1280, 800)
    panel.show()
    qtbot.wait(30)

    assert panel.selected_user_type_id == "green_narrow_moderate"
    assert panel.peak_model.rowCount() == 1
    assert panel.peak_table.minimumHeight() >= STATIONARY_USER_TABLE_MIN_HEIGHT
    assert panel.heatmap_widget.minimumHeight() >= STATIONARY_USER_HEATMAP_MIN_HEIGHT
    assert panel.heatmap_shape == (63, 361)
    assert panel.heatmap_maximum > 0.9
    assert calls
    assert "schema_version=stationary_user_type_profile_v1" in (
        panel.profile_labels["versions"].text()
    )
    assert set(panel.role_band_items) == set(ROLE_HUE_BANDS)
    assert "隠れた正解" in panel.hidden_truth_notice.text()
    assert "探索計算には入力されません" in panel.hidden_truth_notice.text()
    assert panel.peak_table.editTriggers() == QTableView.EditTrigger.NoEditTriggers
    assert panel.diagnostics_scroll.verticalScrollBar().maximum() > 0
    assert panel.diagnostics_scroll.horizontalScrollBar().maximum() == 0
    assert not panel.chart_table_splitter.isCollapsible(0)
    assert not panel.chart_table_splitter.isCollapsible(1)

    selected: list[str] = []
    panel.user_type_selected.connect(selected.append)
    panel.set_selected_user_type("flat_control")
    assert panel.peak_model.rowCount() == 0
    assert panel.heatmap_maximum == 0.0
    assert selected[-1] == "flat_control"

    panel.set_settings_editable(False)
    assert not panel.user_type_combo.isEnabled()
