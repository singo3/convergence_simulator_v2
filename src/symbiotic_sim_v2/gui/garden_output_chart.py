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

DEFAULT_ROSTER = ("life-blue", "life-green", "life-red")


class GardenOutputChart(QWidget):
    """Render only holder and qualified-output records produced by the Garden."""

    def __init__(self, parent=None, *, duration_seconds: int = 240) -> None:
        super().__init__(parent)
        self._duration_seconds = duration_seconds
        self._round_finalize_offset_us = 999_999
        self._holder_levels: dict[str | None, float] = {None: 0.0}
        self._roster: tuple[str, ...] = ()
        self.set_roster(DEFAULT_ROSTER)
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
        self.holder_axis = axis
        self.holder_plot = self.graphics.addPlot(row=0, col=0, axisItems={"left": axis})
        self.holder_timeline_plot = self.holder_plot
        self._configure_plot(self.holder_plot, "資格holder timeline", "holder")
        self._update_holder_axis()
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
            "GardenQualifiedBEvent v2: effective / holder touch / finalize / B",
            "active / holder / B",
        )
        self.qualified_b_plot.setLabel(
            "bottom",
            "effective / finalize time",
            units="秒",
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
        self.holder_touch_item = self.qualified_b_plot.plot(
            pen=None,
            symbol="o",
            symbolSize=9,
            symbolPen=pg.mkPen("#FFFFFF", width=2),
            symbolBrush=pg.mkBrush(0, 0, 0, 0),
            name="holder touch arrival",
        )
        self.active_effective_item = self.qualified_b_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=13,
            symbolBrush="#2DD4BF",
            name="active qualified B effective",
        )
        self.round_finalize_item = self.qualified_b_plot.plot(
            pen=None,
            symbol="t",
            symbolSize=12,
            symbolBrush="#F97316",
            name="round finalize (feedback sync)",
        )
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

    def set_round_finalize_offset_us(self, offset_us: int) -> None:
        self._round_finalize_offset_us = offset_us

    def set_roster(self, digital_life_ids: Sequence[str]) -> None:
        self._roster = tuple(sorted(digital_life_ids))
        self._holder_levels = {None: 0.0}
        self._holder_levels.update(
            {life_id: float(index) for index, life_id in enumerate(self._roster, 1)}
        )
        if hasattr(self, "holder_plot"):
            self._update_holder_axis()

    def _update_holder_axis(self) -> None:
        ticks = [(0.0, "null")]
        ticks.extend(
            (self._holder_levels[life_id], life_id) for life_id in self._roster
        )
        self.holder_axis.setTicks([ticks])
        self.holder_plot.setYRange(
            -0.2,
            max(self._holder_levels.values(), default=0.0) + 0.2,
            padding=0,
        )

    def set_records(
        self,
        qualification_records: Sequence[Any],
        qualified_b_records: Sequence[Any],
        current_time_us: int,
        touch_records: Sequence[Any] = (),
    ) -> None:
        qualifications = tuple(qualification_records)
        times = [us_to_seconds(record.signal_time_us) for record in qualifications]
        self.holder_item.setData(
            times,
            [
                self._holder_levels.get(record.holder_after, math.nan)
                for record in qualifications
            ],
            stepMode="left",
        )
        assignments = tuple(record for record in qualifications if record.assigned_this_signal)
        self.assignment_item.setData(
            [us_to_seconds(record.assignment_touch_time_us) for record in assignments],
            [
                self._holder_levels.get(record.holder_after, math.nan)
                for record in assignments
            ],
        )
        releases = tuple(
            record for record in qualifications if record.released_after_second_round
        )
        self.release_item.setData(
            [us_to_seconds(record.signal_time_us) for record in releases],
            [0.0] * len(releases),
        )

        outputs = tuple(qualified_b_records)
        output_times = [us_to_seconds(record.effective_time_us) for record in outputs]
        self.active_item.setData(
            output_times,
            [1 if record.active else 0 for record in outputs],
            stepMode="left",
        )
        self.qualified_holder_item.setData(
            output_times,
            [
                self._holder_levels.get(record.qualification_holder_id, math.nan)
                / max(1, len(self._roster))
                for record in outputs
            ],
            stepMode="left",
        )
        active_outputs = tuple(record for record in outputs if record.active)
        self.active_effective_item.setData(
            [us_to_seconds(record.effective_time_us) for record in active_outputs],
            [1.0] * len(active_outputs),
        )
        touch_by_signal_and_id = {
            (record.signal_index, record.digital_life_id): record
            for record in touch_records
        }
        holder_touches = tuple(
            touch_by_signal_and_id.get(
                (record.signal_index, record.qualification_holder_id)
            )
            for record in active_outputs
        )
        holder_touches = tuple(record for record in holder_touches if record is not None)
        self.holder_touch_item.setData(
            [us_to_seconds(record.arrival_time_us) for record in holder_touches],
            [0.9] * len(holder_touches),
        )
        active_qualifications = tuple(record for record in qualifications if record.s == 1)
        self.round_finalize_item.setData(
            [
                us_to_seconds(record.signal_time_us + self._round_finalize_offset_us)
                for record in active_qualifications
            ],
            [0.8] * len(active_qualifications),
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
        self.active_effective_count = len(active_outputs)
        self.holder_touch_count = len(holder_touches)
        self.round_finalize_count = len(active_qualifications)

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
            self.holder_touch_item,
            self.active_effective_item,
            self.round_finalize_item,
            self.b_f_item,
            self.b_t_item,
        ):
            item.setData([], [])
        self.set_current_time_us(0)
        self.qualification_count = 0
        self.qualified_b_count = 0
        self.assignment_count = 0
        self.release_count = 0
        self.active_effective_count = 0
        self.holder_touch_count = 0
        self.round_finalize_count = 0
