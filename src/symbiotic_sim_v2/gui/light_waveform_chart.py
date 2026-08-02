"""Stage 6 light waveform and full-session parameter charts."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

WAVEFORM_WINDOW_SECONDS = 15.0
LIGHT_WAVEFORM_CHART_MIN_HEIGHT = 520
LIGHT_WAVEFORM_GRAPHICS_MIN_HEIGHT = 500
LIGHT_WAVEFORM_PLOT_MIN_HEIGHT = 145
LIGHT_PARAMETER_CHART_MIN_HEIGHT = 540
LIGHT_PARAMETER_GRAPHICS_MIN_HEIGHT = 520
LIGHT_PARAMETER_PLOT_MIN_HEIGHT = 120


class LightWaveformChart(QWidget):
    """Display state_at-derived Value, phase and BPM on a recent virtual window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lightWaveformChart")
        self.setMinimumHeight(LIGHT_WAVEFORM_CHART_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("lightWaveformGraphics")
        self.graphics.setBackground("#111827")
        self.graphics.setMinimumHeight(LIGHT_WAVEFORM_GRAPHICS_MIN_HEIGHT)
        layout.addWidget(self.graphics)

        self._build_value_plot()
        self._build_phase_plot()
        self._build_bpm_plot()
        self.clear()

    def _build_value_plot(self) -> None:
        self.value_plot = self.graphics.addPlot(row=0, col=0)
        self._configure_plot(
            self.value_plot,
            "直近15仮想秒のHSV Value（device state_at）",
            "HSV Value",
        )
        self.value_plot.setYRange(-0.02, 0.54, padding=0)
        self.value_plot.addLegend(offset=(8, 8))
        self.value_item = self.value_plot.plot(
            pen=pg.mkPen("#FDE047", width=2),
            name="Value",
        )
        self.command_boundary_item = self.value_plot.plot(
            pen=pg.mkPen("#F8FAFC", width=1, style=Qt.PenStyle.DotLine),
            name="command boundary",
        )
        self.value_reference_lines = tuple(
            pg.InfiniteLine(
                pos=value,
                angle=0,
                movable=False,
                pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine),
                label=f"{value:.3f}",
                labelOpts={"color": color},
            )
            for value, color in (
                (0.35, "#60A5FA"),
                (0.425, "#A78BFA"),
                (0.50, "#34D399"),
            )
        )
        for line in self.value_reference_lines:
            self.value_plot.addItem(line)
        self.value_current_line = _current_line(self.value_plot)

    def _build_phase_plot(self) -> None:
        self.phase_plot = self.graphics.addPlot(row=1, col=0)
        self._configure_plot(self.phase_plot, "連続位相（cycle）/ active", "phase")
        self.phase_plot.setXLink(self.value_plot)
        self.phase_plot.setYRange(-0.05, 1.05, padding=0)
        self.phase_plot.addLegend(offset=(8, 8))
        self.phase_item = self.phase_plot.plot(
            pen=pg.mkPen("#22D3EE", width=2),
            name="phase cycles",
        )
        self.active_item = self.phase_plot.plot(
            pen=pg.mkPen("#F8FAFC", width=1, style=Qt.PenStyle.DotLine),
            name="active",
        )
        self.phase_current_line = _current_line(self.phase_plot)

    def _build_bpm_plot(self) -> None:
        self.bpm_plot = self.graphics.addPlot(row=2, col=0)
        self._configure_plot(self.bpm_plot, "点滅BPM / active", "BPM")
        self.bpm_plot.setXLink(self.value_plot)
        self.bpm_plot.setYRange(0.0, 175.0, padding=0)
        self.bpm_plot.addLegend(offset=(8, 8))
        self.bpm_item = self.bpm_plot.plot(
            pen=pg.mkPen("#FB7185", width=2),
            name="blink BPM",
        )
        self.bpm_current_line = _current_line(self.bpm_plot)

    @staticmethod
    def _configure_plot(plot: pg.PlotItem, title: str, left: str) -> None:
        plot.setTitle(title, color="#E5E7EB", size="11pt")
        plot.setLabel("left", left)
        plot.setLabel("bottom", "仮想時間", units="秒")
        plot.getAxis("left").enableAutoSIPrefix(False)
        plot.showGrid(x=True, y=True, alpha=0.16)
        plot.setMinimumHeight(LIGHT_WAVEFORM_PLOT_MIN_HEIGHT)
        plot.setPreferredHeight(LIGHT_WAVEFORM_PLOT_MIN_HEIGHT)

    def set_records(
        self,
        samples: Sequence[Any],
        commands: Sequence[Any],
        current_time_us: int,
    ) -> None:
        selected = tuple(samples)
        times = [
            us_to_seconds(
                _field(sample, "time_us", "current_time_us", default=0)
            )
            for sample in selected
        ]
        self.value_item.setData(
            times,
            [float(_field(sample, "value", "current_value", default=0.0)) for sample in selected],
        )
        self.phase_item.setData(
            times,
            [
                math.nan
                if _field(sample, "phase_cycles", default=None) is None
                else float(_field(sample, "phase_cycles"))
                for sample in selected
            ],
        )
        self.active_item.setData(
            times,
            [1.0 if _field(sample, "active", default=False) else 0.0 for sample in selected],
            stepMode="left",
        )
        self.bpm_item.setData(
            times,
            [
                math.nan
                if _field(sample, "blink_bpm", default=None) is None
                else float(_field(sample, "blink_bpm"))
                for sample in selected
            ],
        )

        window_end = us_to_seconds(current_time_us)
        window_start = max(0.0, window_end - WAVEFORM_WINDOW_SECONDS)
        boundary_times = tuple(
            us_to_seconds(
                _field(command, "effective_time_us", "command_effective_time_us", default=0)
            )
            for command in commands
            if window_start
            <= us_to_seconds(
                _field(command, "effective_time_us", "command_effective_time_us", default=0)
            )
            <= window_end
        )
        boundary_x: list[float] = []
        boundary_y: list[float] = []
        for boundary in boundary_times:
            boundary_x.extend((boundary, boundary, math.nan))
            boundary_y.extend((0.0, 0.52, math.nan))
        self.command_boundary_item.setData(boundary_x, boundary_y)

        visible_end = max(WAVEFORM_WINDOW_SECONDS, window_end)
        visible_start = max(0.0, visible_end - WAVEFORM_WINDOW_SECONDS)
        for plot in (self.value_plot, self.phase_plot, self.bpm_plot):
            plot.setXRange(visible_start, visible_end, padding=0)
        self.set_current_time_us(current_time_us)
        self.sample_count = len(selected)
        self.command_boundary_count = len(boundary_times)

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        for line in (
            self.value_current_line,
            self.phase_current_line,
            self.bpm_current_line,
        ):
            line.setValue(seconds)

    def clear(self) -> None:
        self.value_item.setData([], [])
        self.phase_item.setData([], [])
        self.active_item.setData([], [])
        self.bpm_item.setData([], [])
        self.command_boundary_item.setData([], [])
        self.set_current_time_us(0)
        for plot in (self.value_plot, self.phase_plot, self.bpm_plot):
            plot.setXRange(0.0, WAVEFORM_WINDOW_SECONDS, padding=0)
        self.sample_count = 0
        self.command_boundary_count = 0


class LightParameterChart(QWidget):
    """Display full-session command-held active, Hue, BPM and holder steps."""

    def __init__(self, parent: QWidget | None = None, *, duration_seconds: int = 240) -> None:
        super().__init__(parent)
        self._duration_seconds = duration_seconds
        self.setObjectName("lightParameterChart")
        self.setMinimumHeight(LIGHT_PARAMETER_CHART_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("lightParameterGraphics")
        self.graphics.setBackground("#111827")
        self.graphics.setMinimumHeight(LIGHT_PARAMETER_GRAPHICS_MIN_HEIGHT)
        layout.addWidget(self.graphics)

        self.active_plot = self._plot(0, "active / command effective time", "active")
        self.hue_plot = self._plot(1, "formal Hue = 360F", "degree")
        self.bpm_plot = self._plot(2, "blink BPM = 10 + 155T", "BPM")
        self.holder_axis = pg.AxisItem(orientation="left")
        self.holder_plot = self.graphics.addPlot(
            row=3,
            col=0,
            axisItems={"left": self.holder_axis},
        )
        self._configure_plot(self.holder_plot, "source holder", "holder")
        self.holder_plot.setXLink(self.active_plot)

        self.active_item = self.active_plot.plot(
            pen=pg.mkPen("#F8FAFC", width=2),
            name="active",
        )
        self.command_item = self.active_plot.plot(
            pen=None,
            symbol="o",
            symbolSize=5,
            symbolBrush="#2DD4BF",
            name="command effective",
        )
        self.hue_item = self.hue_plot.plot(
            pen=pg.mkPen("#A78BFA", width=2),
            name="Hue",
        )
        self.bpm_item = self.bpm_plot.plot(
            pen=pg.mkPen("#FB7185", width=2),
            name="BPM",
        )
        self.holder_item = self.holder_plot.plot(
            pen=pg.mkPen("#FBBF24", width=2),
            symbol="s",
            symbolSize=4,
            name="holder",
        )
        self._current_lines = tuple(
            _current_line(plot)
            for plot in (self.active_plot, self.hue_plot, self.bpm_plot, self.holder_plot)
        )
        self.set_duration_seconds(duration_seconds)
        self.clear()

    def _plot(self, row: int, title: str, left: str) -> pg.PlotItem:
        plot = self.graphics.addPlot(row=row, col=0)
        self._configure_plot(plot, title, left)
        if row:
            plot.setXLink(self.active_plot)
        return plot

    @staticmethod
    def _configure_plot(plot: pg.PlotItem, title: str, left: str) -> None:
        plot.setTitle(title, color="#E5E7EB", size="11pt")
        plot.setLabel("left", left)
        plot.setLabel("bottom", "command effective time", units="秒")
        plot.getAxis("left").enableAutoSIPrefix(False)
        plot.showGrid(x=True, y=True, alpha=0.16)
        plot.setMinimumHeight(LIGHT_PARAMETER_PLOT_MIN_HEIGHT)
        plot.setPreferredHeight(LIGHT_PARAMETER_PLOT_MIN_HEIGHT)

    def set_duration_seconds(self, duration_seconds: int) -> None:
        self._duration_seconds = duration_seconds
        for plot in (self.active_plot, self.hue_plot, self.bpm_plot, self.holder_plot):
            plot.setXRange(0.0, float(duration_seconds), padding=0.01)

    def set_records(self, commands: Sequence[Any], current_time_us: int) -> None:
        records = tuple(commands)
        times = [
            us_to_seconds(
                _field(record, "effective_time_us", "command_effective_time_us", default=0)
            )
            for record in records
        ]
        active = [1.0 if _field(record, "active", default=False) else 0.0 for record in records]
        self.active_item.setData(times, active, stepMode="left")
        self.command_item.setData(times, active)
        self.hue_item.setData(
            times,
            [
                math.nan
                if _field(record, "hue_degree", default=None) is None
                else float(_field(record, "hue_degree"))
                for record in records
            ],
            stepMode="left",
        )
        self.bpm_item.setData(
            times,
            [
                math.nan
                if _field(record, "blink_bpm", default=None) is None
                else float(_field(record, "blink_bpm"))
                for record in records
            ],
            stepMode="left",
        )

        roster = tuple(
            sorted(
                {
                    str(holder)
                    for record in records
                    if (
                        holder := _field(
                            record,
                            "qualification_holder_id",
                            "holder_id",
                            default=None,
                        )
                    )
                    is not None
                }
            )
        )
        holder_levels = {None: 0.0}
        holder_levels.update({holder: float(index) for index, holder in enumerate(roster, 1)})
        self.holder_axis.setTicks(
            [[(0.0, "null"), *((holder_levels[item], item) for item in roster)]]
        )
        self.holder_plot.setYRange(-0.2, max(holder_levels.values(), default=0.0) + 0.2)
        self.holder_item.setData(
            times,
            [
                holder_levels.get(
                    _field(
                        record,
                        "qualification_holder_id",
                        "holder_id",
                        default=None,
                    ),
                    math.nan,
                )
                for record in records
            ],
            stepMode="left",
        )
        self.active_plot.setYRange(-0.1, 1.1, padding=0)
        self.hue_plot.setYRange(-5.0, 365.0, padding=0)
        self.bpm_plot.setYRange(0.0, 175.0, padding=0)
        self.set_current_time_us(current_time_us)
        self.command_count = len(records)

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        for line in self._current_lines:
            line.setValue(seconds)

    def clear(self) -> None:
        for item in (
            self.active_item,
            self.command_item,
            self.hue_item,
            self.bpm_item,
            self.holder_item,
        ):
            item.setData([], [])
        self.set_current_time_us(0)
        self.command_count = 0


def _current_line(plot: pg.PlotItem) -> pg.InfiniteLine:
    line = pg.InfiniteLine(
        pos=0.0,
        angle=90,
        movable=False,
        pen=pg.mkPen("#FFFFFF", width=1),
    )
    plot.addItem(line)
    return line


def _field(record: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default
