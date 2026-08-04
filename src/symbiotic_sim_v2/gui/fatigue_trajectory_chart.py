"""Record-backed fatigue phase trajectories for Stage 8A.1."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import first_record_value

FATIGUE_TRAJECTORY_CHART_MIN_HEIGHT = 480
LIFE_COLORS = {
    "life-red": "#FB7185",
    "life-green": "#34D399",
    "life-blue": "#60A5FA",
}
PHASE_FIELDS = (
    ("e_at_session_start", "start", -0.36, "o"),
    ("e_after_baseline", "after baseline", -0.18, "t"),
    ("e_after_active", "after active", 0.0, "s"),
    ("e_before_session_end_policy", "before end policy", 0.18, "d"),
    ("e_after_session_end_policy", "after end policy", 0.36, "star"),
)


class FatigueTrajectoryChart(QWidget):
    """Display recorded E phases; no fatigue equation is evaluated here."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stage8a1FatigueTrajectoryChart")
        self.setMinimumHeight(FATIGUE_TRAJECTORY_CHART_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.PlotWidget(self)
        self.graphics.setBackground("#111827")
        self.plot = self.graphics.getPlotItem()
        self.plot.setTitle("life-specific E trajectory and session-end recovery", color="#E5E7EB")
        self.plot.setLabel("bottom", "session / recorded phase")
        self.plot.setLabel("left", "E")
        self.plot.setYRange(-0.01, 0.22, padding=0.02)
        self.plot.showGrid(x=True, y=True, alpha=0.18)
        self.plot.addLegend(offset=(8, 8), colCount=3)
        self.phase_items: dict[tuple[str, str], pg.PlotDataItem] = {}
        for life_id, color in LIFE_COLORS.items():
            for field, caption, _offset, symbol in PHASE_FIELDS:
                self.phase_items[(life_id, field)] = self.plot.plot(
                    pen=None,
                    symbol=symbol,
                    symbolSize=7 if field != "e_after_session_end_policy" else 10,
                    symbolBrush=color,
                    symbolPen=pg.mkPen(color),
                    name=f"{life_id.removeprefix('life-')} {caption}"
                    if field
                    in {
                        "e_after_active",
                        "e_after_session_end_policy",
                    }
                    else None,
                )
        self.full_recovery_item = self.plot.plot(
            pen=None,
            symbol="x",
            symbolSize=16,
            symbolPen=pg.mkPen("#FFFFFF", width=3),
            name="unselected full recovery",
        )
        self.target_line = pg.InfiniteLine(
            pos=0.05,
            angle=0,
            pen=pg.mkPen("#FBBF24", width=2, style=Qt.PenStyle.DashLine),
            label="selected fatigue target",
            labelOpts={"color": "#FBBF24"},
        )
        self.plot.addItem(self.target_line)
        layout.addWidget(self.graphics)
        self.record_count = 0
        self.full_recovery_count = 0
        self.display_y_max = 0.22

    def set_records(
        self,
        records: Sequence[object],
        *,
        selected_fatigue_target: float = 0.05,
    ) -> None:
        selected = tuple(records)
        for life_id in LIFE_COLORS:
            life_records = tuple(
                record
                for record in selected
                if first_record_value(record, ("digital_life_id", "life_id")) == life_id
            )
            for field, _caption, offset, _symbol in PHASE_FIELDS:
                points = []
                for record in life_records:
                    session = first_record_value(record, ("session_index",))
                    value = first_record_value(
                        record,
                        (field, field.replace("e_", "E_", 1)),
                    )
                    if (
                        isinstance(session, int)
                        and not isinstance(session, bool)
                        and isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(float(value))
                    ):
                        points.append((float(session) + offset, float(value)))
                self.phase_items[(life_id, field)].setData(
                    [point[0] for point in points],
                    [point[1] for point in points],
                )
        recoveries = []
        for record in selected:
            if not bool(first_record_value(record, ("full_recovery_applied",), False)):
                continue
            session = first_record_value(record, ("session_index",))
            if isinstance(session, int) and not isinstance(session, bool):
                recoveries.append((float(session) + 0.36, 0.0))
        self.full_recovery_item.setData(
            [point[0] for point in recoveries],
            [point[1] for point in recoveries],
        )
        self.target_line.setValue(float(selected_fatigue_target))
        finite_e_values = tuple(
            float(value)
            for record in selected
            for field, _caption, _offset, _symbol in PHASE_FIELDS
            for value in (first_record_value(record, (field,)),)
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
        highest = max((float(selected_fatigue_target), *finite_e_values), default=0.05)
        self.display_y_max = max(0.22, min(1.02, highest * 1.08 + 0.01))
        self.plot.setYRange(-0.01, self.display_y_max, padding=0.02)
        self.record_count = len(selected)
        self.full_recovery_count = len(recoveries)

    def clear(self) -> None:
        self.set_records(())


__all__ = [
    "FATIGUE_TRAJECTORY_CHART_MIN_HEIGHT",
    "FatigueTrajectoryChart",
    "PHASE_FIELDS",
]
