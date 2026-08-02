"""Stage 5B Garden holder and qualified-B timelines."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

GARDEN_OUTPUT_CHART_MIN_HEIGHT = 720
GARDEN_OUTPUT_GRAPHICS_MIN_HEIGHT = 700
GARDEN_OUTPUT_PLOT_MIN_HEIGHT = 300

HOLDER_LEVELS = {
    None: 0.0,
    "life-blue": 1.0,
    "life-green": 2.0,
    "life-red": 3.0,
}


class GardenOutputChart(QWidget):
    """Render only holder and qualified-output records produced by the Garden."""

    def __init__(self, parent=None, *, duration_seconds: int = 240) -> None:
        super().__init__(parent)
        self._duration_seconds = duration_seconds
        self.setObjectName("gardenOutputChart")
        self.setMinimumHeight(GARDEN_OUTPUT_CHART_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("gardenOutputGraphics")
        self.graphics.setBackground("#111827")
        self.graphics.setMinimumHeight(GARDEN_OUTPUT_GRAPHICS_MIN_HEIGHT)
        layout.addWidget(self.graphics)
        self._build_holder_plot()
        self._build_qualified_b_plot()
        self.set_duration_seconds(duration_seconds)
        self.clear()

    def _build_holder_plot(self) -> None:
        axis = pg.AxisItem(orientation="left")
        axis.setTicks(
            [[(0.0, "null"), (1.0, "blue"), (2.0, "green"), (3.0, "red")]]
        )
        self.holder_plot = self.graphics.addPlot(row=0, col=0, axisItems={"left": axis})
        self.holder_timeline_plot = self.holder_plot
        self._configure_plot(self.holder_plot, "資格holder timeline", "holder")
        self.holder_plot.setYRange(-0.2, 3.2, padding=0)
        self.holder_plot.addLegend(offset=(8, 8))
        self.holder_item = self.holder_plot.plot(
            pen=pg.mkPen("#FBBF24", width=3),
            symbol="s",
            symbolSize=5,
            name="holder",
        )
        self.assignment_item = self.holder_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=14,
            symbolBrush="#38D996",
            name="assignment",
        )
        self.release_item = self.holder_plot.plot(
            pen=None,
            symbol="t",
            symbolSize=14,
            symbolBrush="#FFFFFF",
            name="release",
        )
        self.holder_current_line = self._current_line(self.holder_plot)

    def _build_qualified_b_plot(self) -> None:
        self.qualified_b_plot = self.graphics.addPlot(row=1, col=0)
        self.qualified_b_step_plot = self.qualified_b_plot
        self._configure_plot(
            self.qualified_b_plot,
            "GardenQualifiedBEvent: active / holder ID / B_F / B_T",
            "active / holder / B",
        )
        self.qualified_b_plot.setXLink(self.holder_plot)
        self.qualified_b_plot.setYRange(-0.05, 1.05, padding=0)
        self.qualified_b_plot.addLegend(offset=(8, 8))
        self.active_item = self.qualified_b_plot.plot(
            pen=pg.mkPen("#FFFFFF", width=1, style=Qt.PenStyle.DotLine),
            name="active",
        )
        self.qualified_holder_item = self.qualified_b_plot.plot(
            pen=pg.mkPen("#FBBF24", width=2, style=Qt.PenStyle.DotLine),
            name="holder ID lane",
        )
        self.holder_output_item = self.qualified_holder_item
        self.b_f_item = self.qualified_b_plot.plot(
            pen=pg.mkPen("#38D996", width=2),
            name="qualified B_F",
        )
        self.b_t_item = self.qualified_b_plot.plot(
            pen=pg.mkPen("#60A5FA", width=2, style=Qt.PenStyle.DashLine),
            name="qualified B_T",
        )
        self.qualified_b_current_line = self._current_line(self.qualified_b_plot)

    @staticmethod
    def _configure_plot(plot: pg.PlotItem, title: str, left: str) -> None:
        plot.setTitle(title, color="#E5E7EB", size="11pt")
        plot.setLabel("left", left)
        plot.setLabel("bottom", "signal time", units="秒")
        plot.showGrid(x=True, y=True, alpha=0.16)
        plot.setMinimumHeight(GARDEN_OUTPUT_PLOT_MIN_HEIGHT)
        plot.setPreferredHeight(GARDEN_OUTPUT_PLOT_MIN_HEIGHT)

    @staticmethod
    def _current_line(plot: pg.PlotItem) -> pg.InfiniteLine:
        line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen("#FFFFFF", width=1),
        )
        plot.addItem(line)
        return line

    def set_duration_seconds(self, duration_seconds: int) -> None:
        self._duration_seconds = duration_seconds
        self.holder_plot.setXRange(0.0, float(duration_seconds), padding=0.01)
        self.qualified_b_plot.setXRange(0.0, float(duration_seconds), padding=0.01)

    def set_records(
        self,
        qualification_records: Sequence[Any],
        qualified_b_records: Sequence[Any],
        current_time_us: int,
    ) -> None:
        qualifications = tuple(qualification_records)
        times = [us_to_seconds(record.signal_time_us) for record in qualifications]
        self.holder_item.setData(
            times,
            [HOLDER_LEVELS.get(record.holder_after, math.nan) for record in qualifications],
            stepMode="left",
        )
        assignments = tuple(record for record in qualifications if record.assigned_this_signal)
        self.assignment_item.setData(
            [us_to_seconds(record.assignment_touch_time_us) for record in assignments],
            [HOLDER_LEVELS.get(record.holder_after, math.nan) for record in assignments],
        )
        releases = tuple(
            record for record in qualifications if record.released_after_second_round
        )
        self.release_item.setData(
            [us_to_seconds(record.signal_time_us) for record in releases],
            [0.0] * len(releases),
        )

        outputs = tuple(qualified_b_records)
        output_times = [us_to_seconds(record.signal_time_us) for record in outputs]
        self.active_item.setData(
            output_times,
            [1 if record.active else 0 for record in outputs],
            stepMode="left",
        )
        self.qualified_holder_item.setData(
            output_times,
            [
                HOLDER_LEVELS.get(record.qualification_holder_id, math.nan) / 3.0
                for record in outputs
            ],
            stepMode="left",
        )
        self.b_f_item.setData(
            output_times,
            [math.nan if record.b is None else record.b[0] for record in outputs],
            stepMode="left",
        )
        self.b_t_item.setData(
            output_times,
            [math.nan if record.b is None else record.b[2] for record in outputs],
            stepMode="left",
        )
        self.set_current_time_us(current_time_us)
        self.qualification_count = len(qualifications)
        self.qualified_b_count = len(outputs)
        self.assignment_count = len(assignments)
        self.release_count = len(releases)

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        self.holder_current_line.setValue(seconds)
        self.qualified_b_current_line.setValue(seconds)

    def clear(self) -> None:
        for item in (
            self.holder_item,
            self.assignment_item,
            self.release_item,
            self.active_item,
            self.qualified_holder_item,
            self.b_f_item,
            self.b_t_item,
        ):
            item.setData([], [])
        self.set_current_time_us(0)
        self.qualification_count = 0
        self.qualified_b_count = 0
        self.assignment_count = 0
        self.release_count = 0
