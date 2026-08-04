"""Recorded reference/effective sigma and physical candidate deltas."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import first_record_value

SIGMA_TRAJECTORY_CHART_MIN_HEIGHT = 780


class SigmaTrajectoryChart(QWidget):
    """Project core sigma diagnostics without recreating the search equation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stage8a1SigmaTrajectoryChart")
        self.setMinimumHeight(SIGMA_TRAJECTORY_CHART_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setBackground("#111827")
        self.context_plot = self.graphics.addPlot(row=0, col=0)
        self.context_plot.setTitle(
            "W anchor / common sigma multiplier", color="#E5E7EB"
        )
        self.context_plot.setLabel("bottom", "session")
        self.context_plot.setLabel("left", "W / multiplier")
        self.context_plot.setYRange(0.0, 1.6, padding=0.02)
        self.context_plot.showGrid(x=True, y=True, alpha=0.18)
        self.context_plot.addLegend(offset=(8, 8))
        self.w_anchor_item = self.context_plot.plot(
            pen=pg.mkPen("#34D399", width=2, style=Qt.PenStyle.DashLine),
            symbol="d",
            symbolSize=6,
            name="W anchor",
        )
        self.multiplier_item = self.context_plot.plot(
            pen=pg.mkPen("#FB7185", width=2, style=Qt.PenStyle.DotLine),
            symbol="+",
            symbolSize=8,
            name="sigma multiplier",
        )
        self.graphics.nextRow()
        self.sigma_plot = self.graphics.addPlot(row=1, col=0)
        self.sigma_plot.setTitle(
            "reference / effective sigma at candidate generation", color="#E5E7EB"
        )
        self.sigma_plot.setLabel("bottom", "session")
        self.sigma_plot.setLabel("left", "sigma")
        self.sigma_plot.showGrid(x=True, y=True, alpha=0.18)
        self.sigma_plot.addLegend(offset=(8, 8))
        self.reference_item = self.sigma_plot.plot(
            pen=pg.mkPen("#94A3B8", width=2),
            symbol="o",
            symbolSize=6,
            name="reference sigma",
        )
        self.effective_item = self.sigma_plot.plot(
            pen=pg.mkPen("#FBBF24", width=3),
            symbol="star",
            symbolSize=9,
            name="effective sigma",
        )
        self.graphics.nextRow()
        self.delta_plot = self.graphics.addPlot(row=2, col=0)
        self.delta_plot.setTitle("actual candidate displacement", color="#E5E7EB")
        self.delta_plot.setLabel("bottom", "session")
        self.delta_plot.setLabel("left", "Hue degree / BPM")
        self.delta_plot.showGrid(x=True, y=True, alpha=0.18)
        self.delta_plot.addLegend(offset=(8, 8))
        self.delta_hue_item = self.delta_plot.plot(
            pen=pg.mkPen("#C084FC", width=2),
            symbol="t",
            symbolSize=7,
            name="delta Hue",
        )
        self.delta_bpm_item = self.delta_plot.plot(
            pen=pg.mkPen("#38BDF8", width=2),
            symbol="s",
            symbolSize=7,
            name="delta BPM",
        )
        self.accepted_item = self.delta_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=15,
            symbolBrush="#34D399",
            name="accepted",
        )
        self.rejected_item = self.delta_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=14,
            symbolPen=pg.mkPen("#FB7185", width=3),
            name="rejected",
        )
        layout.addWidget(self.graphics)
        self.record_count = 0

    def set_records(self, records: Sequence[object]) -> None:
        selected = tuple(records)

        def series(*names: str) -> tuple[list[float], list[float]]:
            points = []
            for record in selected:
                session = first_record_value(record, ("session_index",))
                value = first_record_value(record, tuple(names))
                if (
                    isinstance(session, int)
                    and not isinstance(session, bool)
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(float(value))
                ):
                    points.append((float(session), float(value)))
            return [point[0] for point in points], [point[1] for point in points]

        self.reference_item.setData(*series("reference_sigma_at_w", "reference_sigma"))
        self.effective_item.setData(*series("effective_sigma", "sigma_effective"))
        self.w_anchor_item.setData(*series("w_anchor_session", "W_anchor_session"))
        self.multiplier_item.setData(*series("sigma_multiplier", "multiplier"))
        self.delta_hue_item.setData(*series("resulting_delta_hue", "delta_hue_degree"))
        self.delta_bpm_item.setData(*series("resulting_delta_bpm", "delta_blink_bpm"))
        accepted = []
        rejected = []
        for record in selected:
            session = first_record_value(record, ("session_index",))
            delta = first_record_value(record, ("resulting_delta_bpm", "delta_blink_bpm"))
            if not isinstance(session, int) or isinstance(session, bool):
                continue
            if not isinstance(delta, (int, float)) or isinstance(delta, bool):
                continue
            target = (
                accepted
                if bool(first_record_value(record, ("candidate_accepted", "accepted"), False))
                else rejected
            )
            target.append((float(session), float(delta)))
        self.accepted_item.setData(
            [point[0] for point in accepted],
            [point[1] for point in accepted],
        )
        self.rejected_item.setData(
            [point[0] for point in rejected],
            [point[1] for point in rejected],
        )
        self.record_count = len(selected)

    def clear(self) -> None:
        self.set_records(())


__all__ = ["SIGMA_TRAJECTORY_CHART_MIN_HEIGHT", "SigmaTrajectoryChart"]
