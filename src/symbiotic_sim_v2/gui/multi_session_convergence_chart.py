"""Stage 8A charts backed only by immutable outcomes and diagnostic records."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QGraphicsEllipseItem, QVBoxLayout, QWidget

from symbiotic_sim_v2.gui.session_history_table_model import (
    convergence_record_index,
    first_record_value,
    record_value,
    truth_value,
)

MULTI_SESSION_CHART_MIN_HEIGHT = 1_800
MULTI_SESSION_PLOT_MIN_HEIGHT = 280

LIFE_COLORS = {
    "life-red": "#FB7185",
    "life-green": "#34D399",
    "life-blue": "#60A5FA",
}
LIFE_ROLES = {
    "life-red": "red",
    "life-green": "green",
    "life-blue": "blue",
}
HOLDER_LANES = {
    "life-red": 2.0,
    "life-green": 1.0,
    "life-blue": 0.0,
}
ACTION_LANES = {
    "hold": 0.0,
    "explore": 1.0,
    "accepted": 2.0,
    "rejected": 3.0,
    "unconfirmed": 4.0,
    "invalid": 5.0,
}


class MultiSessionConvergenceChart(QWidget):
    """Render six Stage 8A views without calculating a convergence decision."""

    def __init__(self, parent=None, *, maximum_sessions: int = 24) -> None:
        super().__init__(parent)
        self.setObjectName("multiSessionConvergenceChart")
        self.setMinimumHeight(MULTI_SESSION_CHART_MIN_HEIGHT)
        self._maximum_sessions = maximum_sessions
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("multiSessionConvergenceGraphics")
        self.graphics.setBackground("#111827")
        root.addWidget(self.graphics)

        self._build_holder_plot()
        self._build_pattern_plot()
        self._build_k_plot()
        self._build_support_plot()
        self._build_action_plot()
        self._build_truth_plot()
        self.set_maximum_sessions(maximum_sessions)
        self.clear()

    @property
    def plots(self) -> tuple[pg.PlotItem, ...]:
        return (
            self.holder_plot,
            self.pattern_plot,
            self.k_plot,
            self.support_plot,
            self.action_plot,
            self.truth_plot,
        )

    def _build_holder_plot(self) -> None:
        self.holder_plot = self.graphics.addPlot(row=0, col=0)
        _configure_plot(
            self.holder_plot,
            "session holder timeline — cluster / outlier / invalid",
            "holder",
            "session",
        )
        self.holder_plot.setYRange(-0.7, 2.7, padding=0)
        self.holder_plot.getAxis("left").setTicks(
            [[(0.0, "blue"), (1.0, "green"), (2.0, "red")]]
        )
        self.holder_plot.addLegend(offset=(8, 8), colCount=4)
        self.holder_items = {
            life_id: self.holder_plot.plot(
                pen=None,
                symbol="o",
                symbolSize=9,
                symbolBrush=color,
                name=f"{LIFE_ROLES[life_id]} holder",
            )
            for life_id, color in LIFE_COLORS.items()
        }
        self.cluster_member_item = self.holder_plot.plot(
            pen=None,
            symbol="o",
            symbolSize=15,
            symbolBrush=None,
            symbolPen=pg.mkPen("#FBBF24", width=3),
            name="dominant cluster member",
        )
        self.outlier_item = self.holder_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=15,
            symbolPen=pg.mkPen("#FFFFFF", width=3),
            name="rolling outlier",
        )
        self.invalid_item = self.holder_plot.plot(
            pen=None,
            symbol="t",
            symbolSize=13,
            symbolBrush="#9CA3AF",
            name="invalid",
        )
        bundle_symbols = {0: "t1", 1: "s", 2: "t"}
        bundle_colors = {0: "#FDE68A", 1: "#C4B5FD", 2: "#67E8F9"}
        self.bundle_timeline_items = {
            bundle: self.holder_plot.plot(
                pen=None,
                symbol=bundle_symbols[bundle],
                symbolSize=7,
                symbolBrush=bundle_colors[bundle],
                symbolPen=pg.mkPen(bundle_colors[bundle], width=1),
                name=f"Bundle {bundle} physical segment",
            )
            for bundle in range(3)
        }

    def _build_pattern_plot(self) -> None:
        self.pattern_plot = self.graphics.addPlot(row=1, col=0)
        _configure_plot(
            self.pattern_plot,
            "final committed Hue / BPM trajectory — hidden peaks are diagnostic only",
            "blink BPM",
            "Hue",
        )
        self.pattern_plot.setXRange(0.0, 360.0, padding=0.01)
        self.pattern_plot.setYRange(10.0, 165.0, padding=0.02)
        self.pattern_plot.addLegend(offset=(8, 8), colCount=4)
        self.pattern_items = {
            life_id: self.pattern_plot.plot(
                pen=pg.mkPen(color, width=2),
                symbol="o",
                symbolSize=7,
                symbolBrush=color,
                name=f"{LIFE_ROLES[life_id]} final pattern",
            )
            for life_id, color in LIFE_COLORS.items()
        }
        self.pattern_cluster_item = self.pattern_plot.plot(
            pen=None,
            symbol="o",
            symbolSize=15,
            symbolBrush=None,
            symbolPen=pg.mkPen("#FBBF24", width=3),
            name="cluster member",
        )
        bundle_symbols = {0: "t1", 1: "s", 2: "t"}
        bundle_colors = {0: "#FDE68A", 1: "#C4B5FD", 2: "#67E8F9"}
        self.bundle_presentation_items = {
            bundle: self.pattern_plot.plot(
                pen=None,
                symbol=bundle_symbols[bundle],
                symbolSize=8,
                symbolBrush=bundle_colors[bundle],
                symbolPen=pg.mkPen("#E5E7EB", width=1),
                name=f"Bundle {bundle} actual presentation",
            )
            for bundle in range(3)
        }
        self.medoid_item = self.pattern_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=19,
            symbolBrush="#FBBF24",
            symbolPen=pg.mkPen("#FFFFFF", width=1),
            name="cluster medoid",
        )
        self.preference_peak_item = self.pattern_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=18,
            symbolPen=pg.mkPen("#C084FC", width=3),
            name="hidden preference peak (diagnostic)",
        )
        self.tolerance_ellipse = QGraphicsEllipseItem()
        self.tolerance_ellipse.setPen(
            pg.mkPen("#FBBF24", width=2, style=Qt.PenStyle.DashLine)
        )
        self.pattern_plot.addItem(self.tolerance_ellipse)

    def _build_k_plot(self) -> None:
        self.k_plot = self.graphics.addPlot(row=2, col=0)
        _configure_plot(
            self.k_plot,
            "persistent k_F / k_T trajectory — final anchors",
            "k",
            "session",
        )
        self.k_plot.setYRange(-0.05, 1.05, padding=0)
        self.k_plot.addLegend(offset=(8, 8), colCount=3)
        self.k_f_items: dict[str, pg.PlotDataItem] = {}
        self.k_t_items: dict[str, pg.PlotDataItem] = {}
        for life_id, color in LIFE_COLORS.items():
            role = LIFE_ROLES[life_id]
            self.k_f_items[life_id] = self.k_plot.plot(
                pen=pg.mkPen(color, width=2),
                symbol="o",
                symbolSize=5,
                name=f"{role} k_F",
            )
            self.k_t_items[life_id] = self.k_plot.plot(
                pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine),
                symbol="t",
                symbolSize=5,
                name=f"{role} k_T",
            )
        self.accepted_k_item = self.k_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=15,
            symbolBrush="#FBBF24",
            name="accepted candidate",
        )
        self.rejected_k_item = self.k_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=13,
            symbolPen=pg.mkPen("#FFFFFF", width=2),
            name="rejected trial audit",
        )

    def _build_support_plot(self) -> None:
        self.support_plot = self.graphics.addPlot(row=3, col=0)
        _configure_plot(
            self.support_plot,
            "rolling convergence support — convergence does not stop exploration",
            "support",
            "evaluated session",
        )
        self.support_plot.addLegend(offset=(8, 8))
        self.support_item = self.support_plot.plot(
            pen=pg.mkPen("#38BDF8", width=3),
            symbol="o",
            symbolSize=7,
            symbolBrush="#38BDF8",
            name="support count",
        )
        self.required_line = pg.InfiniteLine(
            pos=3.0,
            angle=0,
            movable=False,
            pen=pg.mkPen("#FBBF24", width=2, style=Qt.PenStyle.DashLine),
            label="required K",
            labelOpts={"color": "#FBBF24"},
        )
        self.support_plot.addItem(self.required_line)
        self.window_line = pg.InfiniteLine(
            pos=4.0,
            angle=0,
            movable=False,
            pen=pg.mkPen("#C084FC", width=2, style=Qt.PenStyle.DotLine),
            label="window M",
            labelOpts={"color": "#C084FC"},
        )
        self.support_plot.addItem(self.window_line)
        self.loss_item = self.support_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=14,
            symbolPen=pg.mkPen("#FB7185", width=3),
            name="convergence lost",
        )
        self.reconvergence_item = self.support_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=15,
            symbolBrush="#34D399",
            name="reconvergence",
        )

    def _build_action_plot(self) -> None:
        self.action_plot = self.graphics.addPlot(row=4, col=0)
        _configure_plot(
            self.action_plot,
            "adaptation actions — hold / explore / accepted / rejected",
            "action",
            "session",
        )
        self.action_plot.setYRange(-0.6, 5.6, padding=0)
        self.action_plot.getAxis("left").setTicks(
            [[(lane, name) for name, lane in ACTION_LANES.items()]]
        )
        action_colors = {
            "hold": "#94A3B8",
            "explore": "#38BDF8",
            "accepted": "#34D399",
            "rejected": "#FB7185",
            "unconfirmed": "#C084FC",
            "invalid": "#6B7280",
        }
        self.action_items = {
            action: self.action_plot.plot(
                pen=None,
                symbol="o" if action not in {"rejected", "invalid"} else "x",
                symbolSize=10,
                symbolBrush=color,
                symbolPen=pg.mkPen(color, width=2),
                name=action,
            )
            for action, color in action_colors.items()
        }

    def _build_truth_plot(self) -> None:
        self.truth_plot = self.graphics.addPlot(row=5, col=0)
        _configure_plot(
            self.truth_plot,
            "simulation-only truth alignment — never fed to Digital Life",
            "match / gap",
            "evaluated session",
        )
        self.truth_plot.setYRange(-0.05, 1.05, padding=0)
        self.truth_plot.addLegend(offset=(8, 8), colCount=3)
        self.preference_match_item = self.truth_plot.plot(
            pen=pg.mkPen("#C084FC", width=3),
            symbol="o",
            symbolSize=6,
            name="preference match at medoid",
        )
        self.global_maximum_item = self.truth_plot.plot(
            pen=pg.mkPen("#34D399", width=2, style=Qt.PenStyle.DashLine),
            name="global maximum match",
        )
        self.response_gap_item = self.truth_plot.plot(
            pen=pg.mkPen("#FBBF24", width=2),
            symbol="t",
            symbolSize=6,
            name="response gap",
        )
        self.nearest_peak_text = pg.TextItem(
            "",
            color="#E9D5FF",
            anchor=(1.0, 0.0),
        )
        self.nearest_peak_text.setZValue(20)
        self.truth_plot.addItem(self.nearest_peak_text)
        self.nearest_peak_text.setVisible(False)

    def set_maximum_sessions(self, maximum_sessions: int) -> None:
        if isinstance(maximum_sessions, bool) or not isinstance(maximum_sessions, int):
            raise TypeError("maximum_sessions must be an integer")
        if maximum_sessions < 1:
            raise ValueError("maximum_sessions must be positive")
        self._maximum_sessions = maximum_sessions
        for plot in (
            self.holder_plot,
            self.k_plot,
            self.support_plot,
            self.action_plot,
            self.truth_plot,
        ):
            plot.setXRange(-0.5, maximum_sessions - 0.5, padding=0.01)

    def set_records(
        self,
        session_outcomes: Sequence[Any],
        convergence_records: Sequence[Any],
        *,
        truth_alignment_records: Sequence[Any] = (),
        convergence_config: Any | None = None,
        user_profile: Any | None = None,
    ) -> None:
        """Copy diagnostic values to plots; clustering and truth stay in the core."""

        outcomes = tuple(session_outcomes)
        convergence = tuple(convergence_records)
        truth_records = tuple(truth_alignment_records)
        latest = convergence[-1] if convergence else None
        members = set(record_value(latest, "member_session_indices", ()) or ())
        outliers = set(record_value(latest, "outlier_session_indices", ()) or ())
        by_index = {
            int(record_value(outcome, "session_index", 0)): outcome for outcome in outcomes
        }

        for life_id, item in self.holder_items.items():
            selected = tuple(
                outcome
                for outcome in outcomes
                if record_value(outcome, "holder_id") == life_id
                and record_value(outcome, "valid_for_convergence", False)
            )
            item.setData(
                [record_value(outcome, "session_index") for outcome in selected],
                [HOLDER_LANES[life_id]] * len(selected),
            )
        self.cluster_member_item.setData(
            [index for index in sorted(members) if index in by_index],
            [
                HOLDER_LANES.get(record_value(by_index[index], "holder_id"), math.nan)
                for index in sorted(members)
                if index in by_index
            ],
        )
        self.outlier_item.setData(
            [index for index in sorted(outliers) if index in by_index],
            [
                HOLDER_LANES.get(record_value(by_index[index], "holder_id"), math.nan)
                for index in sorted(outliers)
                if index in by_index
            ],
        )
        invalid = tuple(
            outcome
            for outcome in outcomes
            if not record_value(outcome, "valid_for_convergence", False)
        )
        self.invalid_item.setData(
            [record_value(outcome, "session_index") for outcome in invalid],
            [-0.5] * len(invalid),
        )
        presentation_pairs = tuple(
            (outcome, presentation)
            for outcome in outcomes
            for presentation in (
                record_value(outcome, "bundle_presentations", ()) or ()
            )
        )
        for bundle, item in self.bundle_timeline_items.items():
            selected = tuple(
                (outcome, presentation)
                for outcome, presentation in presentation_pairs
                if record_value(presentation, "bundle_index") == bundle
            )
            x_values = []
            y_values = []
            for outcome, presentation in selected:
                session_index = float(record_value(outcome, "session_index", 0))
                first_signal = float(
                    record_value(presentation, "first_signal_index", 60)
                )
                last_signal = float(
                    record_value(presentation, "last_signal_index", first_signal)
                )
                midpoint = (first_signal + last_signal) / 2.0
                # Place the full 60..239 timeline inside the session's x lane.
                x_values.append(session_index - 0.4 + 0.8 * (midpoint - 60.0) / 179.0)
                y_values.append(
                    HOLDER_LANES.get(
                        record_value(outcome, "holder_id"),
                        math.nan,
                    )
                )
            item.setData(x_values, y_values)

        for life_id, item in self.pattern_items.items():
            selected = tuple(
                outcome
                for outcome in outcomes
                if record_value(outcome, "holder_id") == life_id
                and record_value(outcome, "valid_for_convergence", False)
            )
            item.setData(
                [record_value(outcome, "holder_final_hue_degree") for outcome in selected],
                [record_value(outcome, "holder_final_blink_bpm") for outcome in selected],
            )
        member_outcomes = tuple(by_index[index] for index in sorted(members) if index in by_index)
        self.pattern_cluster_item.setData(
            [record_value(outcome, "holder_final_hue_degree") for outcome in member_outcomes],
            [record_value(outcome, "holder_final_blink_bpm") for outcome in member_outcomes],
        )
        presentations = tuple(record for _outcome, record in presentation_pairs)
        for bundle, item in self.bundle_presentation_items.items():
            selected = tuple(
                record
                for record in presentations
                if record_value(record, "bundle_index") == bundle
            )
            item.setData(
                [record_value(record, "hue_degree") for record in selected],
                [record_value(record, "blink_bpm") for record in selected],
            )
        medoid_hue = first_record_value(latest, ("medoid_hue_degree", "medoid_hue"))
        medoid_bpm = first_record_value(latest, ("medoid_blink_bpm", "medoid_bpm"))
        self.medoid_item.setData(
            [] if medoid_hue is None else [medoid_hue],
            [] if medoid_bpm is None else [medoid_bpm],
        )
        peaks = tuple(record_value(user_profile, "peaks", ()) or ())
        self.preference_peak_item.setData(
            [record_value(peak, "preferred_hue_degree") for peak in peaks],
            [record_value(peak, "preferred_blink_bpm") for peak in peaks],
        )
        hue_tolerance = record_value(convergence_config, "hue_tolerance_degree", None)
        bpm_tolerance = record_value(convergence_config, "blink_bpm_tolerance", None)
        if (
            medoid_hue is None
            or medoid_bpm is None
            or hue_tolerance is None
            or bpm_tolerance is None
        ):
            self.tolerance_ellipse.setVisible(False)
        else:
            self.tolerance_ellipse.setRect(
                QRectF(
                    float(medoid_hue) - float(hue_tolerance),
                    float(medoid_bpm) - float(bpm_tolerance),
                    2.0 * float(hue_tolerance),
                    2.0 * float(bpm_tolerance),
                )
            )
            self.tolerance_ellipse.setVisible(True)

        accepted_x: list[int] = []
        accepted_y: list[float] = []
        rejected_x: list[int] = []
        rejected_y: list[float] = []
        for life_id in LIFE_COLORS:
            x_values: list[int] = []
            f_values: list[float] = []
            t_values: list[float] = []
            for outcome in outcomes:
                states = record_value(outcome, "final_k_anchor_by_life", {}) or {}
                k = record_value(states, life_id, None)
                if k is None:
                    continue
                session_index = int(record_value(outcome, "session_index", 0))
                x_values.append(session_index)
                f_values.append(float(k[0]))
                t_values.append(float(k[2]))
                if record_value(outcome, "holder_id") != life_id:
                    continue
                if record_value(outcome, "candidate_accepted", False):
                    accepted_x.append(session_index)
                    accepted_y.append(float(k[0]))
                elif record_value(outcome, "candidate_generated", False):
                    trial = first_record_value(
                        outcome,
                        ("holder_k_trial", "holder_trial_k"),
                        None,
                    )
                    if trial is not None:
                        rejected_x.append(session_index)
                        rejected_y.append(float(trial[0]))
            self.k_f_items[life_id].setData(x_values, f_values)
            self.k_t_items[life_id].setData(x_values, t_values)
        self.accepted_k_item.setData(accepted_x, accepted_y)
        self.rejected_k_item.setData(rejected_x, rejected_y)

        indexed_convergence = tuple(
            (index, record)
            for record in convergence
            if (index := convergence_record_index(record)) is not None
        )
        convergence_x = [index for index, _record in indexed_convergence]
        support_y = [
            record_value(record, "support_count", 0)
            for _index, record in indexed_convergence
        ]
        self.support_item.setData(convergence_x, support_y)
        required = record_value(convergence_config, "required_sessions", 3)
        self.required_line.setValue(float(required))
        window_sessions = record_value(convergence_config, "window_sessions", 4)
        self.window_line.setValue(float(window_sessions))
        lost = tuple(
            (index, support)
            for (index, record), support in zip(
                indexed_convergence,
                support_y,
                strict=True,
            )
            if first_record_value(record, ("convergence_state", "state"))
            == "convergence_lost"
        )
        reconverged: list[tuple[int, Any]] = []
        previous_reconvergence_count = 0
        for (index, record), support in zip(
            indexed_convergence,
            support_y,
            strict=True,
        ):
            reconvergence_count = int(
                record_value(record, "reconvergence_count", 0) or 0
            )
            if (
                bool(record_value(record, "reconverged", False))
                or reconvergence_count > previous_reconvergence_count
            ):
                reconverged.append((index, support))
            previous_reconvergence_count = reconvergence_count
        self.loss_item.setData([value[0] for value in lost], [value[1] for value in lost])
        self.reconvergence_item.setData(
            [value[0] for value in reconverged],
            [value[1] for value in reconverged],
        )

        action_points: dict[str, list[int]] = {name: [] for name in ACTION_LANES}
        for outcome in outcomes:
            action = _action_for(outcome)
            action_points[action].append(int(record_value(outcome, "session_index", 0)))
        for action, item in self.action_items.items():
            item.setData(
                action_points[action],
                [ACTION_LANES[action]] * len(action_points[action]),
            )

        indexed_truth = tuple(
            (index, record)
            for record in truth_records
            if (index := convergence_record_index(record)) is not None
        )
        if not indexed_truth:
            indexed_truth = indexed_convergence
        def finite_truth_series(field: str) -> tuple[list[int], list[float]]:
            points = tuple(
                (index, float(value))
                for index, record in indexed_truth
                if (
                    (value := truth_value(record, field, None)) is not None
                    and not isinstance(value, bool)
                    and isinstance(value, (int, float))
                    and math.isfinite(float(value))
                )
            )
            return (
                [index for index, _value in points],
                [value for _index, value in points],
            )

        self.preference_match_item.setData(
            *finite_truth_series("preference_match_at_medoid")
        )
        self.global_maximum_item.setData(
            *finite_truth_series("global_maximum_preference_match")
        )
        self.response_gap_item.setData(*finite_truth_series("response_gap"))
        latest_truth = None if not indexed_truth else indexed_truth[-1]
        if latest_truth is None:
            self.nearest_peak_text.setVisible(False)
        else:
            truth_index, truth_record = latest_truth
            nearest_peak = truth_value(truth_record, "nearest_peak_id")
            nearest_distance = truth_value(
                truth_record,
                "distance_to_nearest_peak_center",
            )
            if nearest_peak is None or nearest_distance is None:
                self.nearest_peak_text.setVisible(False)
            else:
                self.nearest_peak_text.setText(
                    f"nearest peak: {nearest_peak}  ·  "
                    f"σ-distance: {float(nearest_distance):.4f}"
                )
                self.nearest_peak_text.setPos(float(truth_index), 0.98)
                self.nearest_peak_text.setVisible(True)

        self.session_count = len(outcomes)
        self.convergence_record_count = len(convergence)
        self.truth_record_count = len(truth_records)
        self.cluster_member_count = len(member_outcomes)
        self.outlier_count = len(outliers)
        self.bundle_presentation_count = len(presentations)

    def clear(self) -> None:
        for item in (
            *self.holder_items.values(),
            self.cluster_member_item,
            self.outlier_item,
            self.invalid_item,
            *self.bundle_timeline_items.values(),
            *self.pattern_items.values(),
            self.pattern_cluster_item,
            *self.bundle_presentation_items.values(),
            self.medoid_item,
            self.preference_peak_item,
            *self.k_f_items.values(),
            *self.k_t_items.values(),
            self.accepted_k_item,
            self.rejected_k_item,
            self.support_item,
            self.loss_item,
            self.reconvergence_item,
            *self.action_items.values(),
            self.preference_match_item,
            self.global_maximum_item,
            self.response_gap_item,
        ):
            item.setData([], [])
        self.tolerance_ellipse.setVisible(False)
        self.nearest_peak_text.setVisible(False)
        self.required_line.setValue(3.0)
        self.window_line.setValue(4.0)
        self.session_count = 0
        self.convergence_record_count = 0
        self.truth_record_count = 0
        self.cluster_member_count = 0
        self.outlier_count = 0
        self.bundle_presentation_count = 0


def _action_for(outcome: Any) -> str:
    if not record_value(outcome, "valid_for_convergence", False):
        return "invalid"
    if record_value(outcome, "candidate_accepted", False):
        return "accepted"
    if record_value(outcome, "candidate_generated", False):
        adoption = str(record_value(outcome, "adoption_result", ""))
        return "unconfirmed" if "unconfirmed" in adoption else "rejected"
    if record_value(outcome, "exploration_decision") == "explore":
        return "explore"
    return "hold"


def _configure_plot(
    plot: pg.PlotItem,
    title: str,
    left: str,
    bottom: str,
) -> None:
    plot.setTitle(title, color="#E5E7EB", size="11pt")
    plot.setLabel("left", left)
    plot.setLabel("bottom", bottom)
    plot.showGrid(x=True, y=True, alpha=0.16)
    plot.setMinimumHeight(MULTI_SESSION_PLOT_MIN_HEIGHT)
    plot.setPreferredHeight(MULTI_SESSION_PLOT_MIN_HEIGHT)


__all__ = [
    "ACTION_LANES",
    "HOLDER_LANES",
    "LIFE_COLORS",
    "MULTI_SESSION_CHART_MIN_HEIGHT",
    "MULTI_SESSION_PLOT_MIN_HEIGHT",
    "MultiSessionConvergenceChart",
]
