"""Readable Stage 5B charts built only from immutable diagnostic records."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

MULTI_LIFE_CHART_MIN_HEIGHT = 1_140
MULTI_LIFE_GRAPHICS_MIN_HEIGHT = 1_120
MULTI_LIFE_PLOT_MIN_HEIGHT = 210

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
HOLDER_LEVELS = {
    None: 0.0,
    "life-blue": 0.25,
    "life-green": 0.55,
    "life-red": 0.85,
}


class MultiLifeChart(QWidget):
    """Show five linked graph groups without calculating simulation decisions."""

    def __init__(self, parent=None, *, duration_seconds: int = 240) -> None:
        super().__init__(parent)
        self._duration_seconds = duration_seconds
        self.setObjectName("multiLifeChart")
        self.setMinimumHeight(MULTI_LIFE_CHART_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("multiLifeGraphics")
        self.graphics.setBackground("#111827")
        self.graphics.setMinimumHeight(MULTI_LIFE_GRAPHICS_MIN_HEIGHT)
        layout.addWidget(self.graphics)

        self._build_tau_touch_plot()
        self._build_g_holder_plot()
        self._build_e_q_plot()
        self._build_p_v_plot()
        self._build_b_plot()
        self.set_duration_seconds(duration_seconds)
        self.clear()

    def _build_tau_touch_plot(self) -> None:
        self.tau_touch_plot = self.graphics.addPlot(row=0, col=0)
        self._configure_plot(
            self.tau_touch_plot,
            "tau / 実タッチ到着offset（別概念）",
            "normalized / seconds",
        )
        self.tau_touch_plot.addLegend(offset=(8, 8), colCount=3)
        self.tau_items: dict[str, pg.PlotDataItem] = {}
        self.touch_offset_items: dict[str, pg.PlotDataItem] = {}
        for life_id in LIFE_COLORS:
            role = LIFE_ROLES[life_id]
            color = LIFE_COLORS[life_id]
            self.tau_items[life_id] = self.tau_touch_plot.plot(
                pen=pg.mkPen(color, width=2),
                name=f"{role} tau",
            )
            self.touch_offset_items[life_id] = self.tau_touch_plot.plot(
                pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DotLine),
                symbol="o",
                symbolSize=4,
                symbolBrush=color,
                name=f"{role} touch offset",
            )
        self.assignment_item = self.tau_touch_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=13,
            symbolBrush="#FBBF24",
            name="holder assignment",
        )
        self.exact_tie_item = self.tau_touch_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=11,
            symbolPen=pg.mkPen("#FFFFFF", width=2),
            name="exact tie",
        )
        self.tau_touch_current_line = self._current_line(self.tau_touch_plot)

    def _build_g_holder_plot(self) -> None:
        self.g_holder_plot = self.graphics.addPlot(row=1, col=0)
        self._configure_plot(self.g_holder_plot, "G / holder / 240秒release", "G / holder lane")
        self.g_holder_plot.setXLink(self.tau_touch_plot)
        self.g_holder_plot.addLegend(offset=(8, 8), colCount=3)
        self.g_items: dict[str, pg.PlotDataItem] = {}
        for life_id in LIFE_COLORS:
            role = LIFE_ROLES[life_id]
            self.g_items[life_id] = self.g_holder_plot.plot(
                pen=pg.mkPen(LIFE_COLORS[life_id], width=2),
                name=f"{role} G",
            )
        self.holder_item = self.g_holder_plot.plot(
            pen=pg.mkPen("#FBBF24", width=3, style=Qt.PenStyle.DashLine),
            symbol="s",
            symbolSize=4,
            name="holder ID lane",
        )
        self.release_item = self.g_holder_plot.plot(
            pen=None,
            symbol="t",
            symbolSize=14,
            symbolBrush="#FFFFFF",
            name="holder release",
        )
        self.g_holder_current_line = self._current_line(self.g_holder_plot)

    def _build_e_q_plot(self) -> None:
        self.e_q_plot = self.graphics.addPlot(row=2, col=0)
        self._configure_plot(self.e_q_plot, "生命別 E / q（第2周後の保持値）", "E / q")
        self.e_q_plot.setXLink(self.tau_touch_plot)
        self.e_q_plot.addLegend(offset=(8, 8), colCount=3)
        self.e_items: dict[str, pg.PlotDataItem] = {}
        self.q_items: dict[str, pg.PlotDataItem] = {}
        for life_id in LIFE_COLORS:
            role = LIFE_ROLES[life_id]
            color = LIFE_COLORS[life_id]
            self.e_items[life_id] = self.e_q_plot.plot(
                pen=pg.mkPen(color, width=2),
                name=f"{role} E",
            )
            self.q_items[life_id] = self.e_q_plot.plot(
                pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine),
                name=f"{role} q",
            )
        self.e_q_current_line = self._current_line(self.e_q_plot)

    def _build_p_v_plot(self) -> None:
        self.p_v_plot = self.graphics.addPlot(row=3, col=0)
        self._configure_plot(self.p_v_plot, "生命別 P / V（第1周）", "P / V")
        self.p_v_plot.setXLink(self.tau_touch_plot)
        self.p_v_plot.addLegend(offset=(8, 8), colCount=3)
        self.p_items: dict[str, pg.PlotDataItem] = {}
        self.v_items: dict[str, pg.PlotDataItem] = {}
        for life_id in LIFE_COLORS:
            role = LIFE_ROLES[life_id]
            color = LIFE_COLORS[life_id]
            self.p_items[life_id] = self.p_v_plot.plot(
                pen=pg.mkPen(color, width=2),
                name=f"{role} P",
            )
            self.v_items[life_id] = self.p_v_plot.plot(
                pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine),
                name=f"{role} V",
            )
        self.p_v_current_line = self._current_line(self.p_v_plot)

    def _build_b_plot(self) -> None:
        self.b_plot = self.graphics.addPlot(row=4, col=0)
        self._configure_plot(self.b_plot, "生命別 B_F / B_T（Stage 5Bでkは固定）", "B")
        self.b_plot.setXLink(self.tau_touch_plot)
        self.b_plot.addLegend(offset=(8, 8), colCount=3)
        self.b_f_items: dict[str, pg.PlotDataItem] = {}
        self.b_t_items: dict[str, pg.PlotDataItem] = {}
        for life_id in LIFE_COLORS:
            role = LIFE_ROLES[life_id]
            color = LIFE_COLORS[life_id]
            self.b_f_items[life_id] = self.b_plot.plot(
                pen=pg.mkPen(color, width=2),
                name=f"{role} B_F",
            )
            self.b_t_items[life_id] = self.b_plot.plot(
                pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine),
                name=f"{role} B_T",
            )
        self.b_current_line = self._current_line(self.b_plot)

    @staticmethod
    def _configure_plot(plot: pg.PlotItem, title: str, left: str) -> None:
        plot.setTitle(title, color="#E5E7EB", size="11pt")
        plot.setLabel("left", left)
        plot.setLabel("bottom", "signal time", units="秒")
        plot.setYRange(-0.05, 1.05, padding=0)
        plot.showGrid(x=True, y=True, alpha=0.16)
        plot.setMinimumHeight(MULTI_LIFE_PLOT_MIN_HEIGHT)
        plot.setPreferredHeight(MULTI_LIFE_PLOT_MIN_HEIGHT)

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
        for plot in self._plots():
            plot.setXRange(0.0, float(duration_seconds), padding=0.01)

    def set_records(
        self,
        first_round_by_id: Mapping[str, Sequence[Any]],
        second_round_by_id: Mapping[str, Sequence[Any]],
        touch_records: Sequence[Any],
        qualification_records: Sequence[Any],
        current_time_us: int,
    ) -> None:
        """Copy record values to plot items; never infer holder or life state."""

        for life_id in LIFE_COLORS:
            first_records = tuple(first_round_by_id.get(life_id, ()))
            first_times = [us_to_seconds(record.signal_time_us) for record in first_records]
            self.tau_items[life_id].setData(
                first_times,
                [self._optional(record.tau) for record in first_records],
            )
            self.p_items[life_id].setData(first_times, [record.p for record in first_records])
            self.v_items[life_id].setData(
                first_times,
                [self._optional(record.v) for record in first_records],
            )
            self.b_f_items[life_id].setData(
                first_times,
                [record.b_f for record in first_records],
            )
            self.b_t_items[life_id].setData(
                first_times,
                [record.b_t for record in first_records],
            )

            life_touches = tuple(
                record for record in touch_records if record.digital_life_id == life_id
            )
            self.touch_offset_items[life_id].setData(
                [us_to_seconds(record.signal_time_us) for record in life_touches],
                [
                    us_to_seconds(record.arrival_time_us - record.signal_time_us)
                    for record in life_touches
                ],
            )

            second_records = tuple(second_round_by_id.get(life_id, ()))
            second_times = [us_to_seconds(record.signal_time_us) for record in second_records]
            self.g_items[life_id].setData(second_times, [record.g for record in second_records])
            self.e_items[life_id].setData(
                second_times,
                [record.e_after for record in second_records],
            )
            self.q_items[life_id].setData(
                second_times,
                [record.q_after for record in second_records],
            )

        qualifications = tuple(qualification_records)
        qualification_times = [
            us_to_seconds(record.signal_time_us) for record in qualifications
        ]
        self.holder_item.setData(
            qualification_times,
            [HOLDER_LEVELS.get(record.holder_after, math.nan) for record in qualifications],
            stepMode="left",
        )
        assignments = tuple(record for record in qualifications if record.assigned_this_signal)
        self.assignment_item.setData(
            [us_to_seconds(record.signal_time_us) for record in assignments],
            [
                us_to_seconds(record.assignment_touch_time_us - record.signal_time_us)
                for record in assignments
            ],
        )
        ties = tuple(record for record in touch_records if record.exact_time_tie)
        self.exact_tie_item.setData(
            [us_to_seconds(record.signal_time_us) for record in ties],
            [us_to_seconds(record.arrival_time_us - record.signal_time_us) for record in ties],
        )
        releases = tuple(
            record for record in qualifications if record.released_after_second_round
        )
        self.release_item.setData(
            [us_to_seconds(record.signal_time_us) for record in releases],
            [0.0] * len(releases),
        )
        self.set_current_time_us(current_time_us)
        self.first_round_count = sum(len(records) for records in first_round_by_id.values())
        self.second_round_count = sum(len(records) for records in second_round_by_id.values())
        self.touch_count = len(touch_records)
        self.qualification_count = len(qualification_records)

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        for line in (
            self.tau_touch_current_line,
            self.g_holder_current_line,
            self.e_q_current_line,
            self.p_v_current_line,
            self.b_current_line,
        ):
            line.setValue(seconds)

    def clear(self) -> None:
        for items in (
            self.tau_items,
            self.touch_offset_items,
            self.g_items,
            self.e_items,
            self.q_items,
            self.p_items,
            self.v_items,
            self.b_f_items,
            self.b_t_items,
        ):
            for item in items.values():
                item.setData([], [])
        for item in (
            self.assignment_item,
            self.exact_tie_item,
            self.holder_item,
            self.release_item,
        ):
            item.setData([], [])
        self.set_current_time_us(0)
        self.first_round_count = 0
        self.second_round_count = 0
        self.touch_count = 0
        self.qualification_count = 0

    def _plots(self) -> tuple[pg.PlotItem, ...]:
        return (
            self.tau_touch_plot,
            self.g_holder_plot,
            self.e_q_plot,
            self.p_v_plot,
            self.b_plot,
        )

    @staticmethod
    def _optional(value: float | None) -> float:
        return math.nan if value is None else value
