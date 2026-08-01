"""Incrementally updated PyQtGraph views for Stage 2 developer diagnostics."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.diagnostics import (
    HeartbeatRecord,
    rolling_rmssd_series,
)


class VirtualUserChart(QWidget):
    """Reuse PlotDataItems while displaying heartbeats, RRI, HR, RMSSD, and components."""

    def __init__(self, config: VirtualUserConfig, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("virtualUserChart")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs)

        self._overview_graphics = pg.GraphicsLayoutWidget(self)
        self._overview_graphics.setBackground("#111827")
        self.heartbeat_plot = self._overview_graphics.addPlot(row=0, col=0)
        self.rri_plot = self._overview_graphics.addPlot(row=1, col=0)
        self.hr_plot = self._overview_graphics.addPlot(row=2, col=0)
        self.tabs.addTab(self._overview_graphics, "心拍・RRI・瞬時心拍数")

        self._details_graphics = pg.GraphicsLayoutWidget(self)
        self._details_graphics.setBackground("#111827")
        self.rmssd_plot = self._details_graphics.addPlot(row=0, col=0)
        self.components_plot = self._details_graphics.addPlot(row=1, col=0)
        self.final_rri_plot = self._details_graphics.addPlot(row=2, col=0)
        self.tabs.addTab(self._details_graphics, "rolling RMSSD・内部成分")

        self._configure_plots()
        self.heartbeat_item = self.heartbeat_plot.plot(
            pen=None,
            symbol="o",
            symbolSize=6,
            symbolBrush="#FF647C",
        )
        self.rri_item = self.rri_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=2),
            symbol="o",
            symbolSize=4,
            symbolBrush="#4DA3FF",
        )
        self.hr_item = self.hr_plot.plot(pen=pg.mkPen("#38D996", width=2))
        self.rmssd_item = self.rmssd_plot.plot(
            pen=pg.mkPen("#C78BFA", width=2),
            symbol="o",
            symbolSize=4,
        )
        self.respiratory_item = self.components_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=2), name="呼吸性"
        )
        self.slow_wave_item = self.components_plot.plot(
            pen=pg.mkPen("#38D996", width=2), name="低周波"
        )
        self.correlated_item = self.components_plot.plot(
            pen=pg.mkPen("#FFB648", width=2), name="連続変動"
        )
        self.jitter_item = self.components_plot.plot(
            pen=pg.mkPen("#C78BFA", width=1), name="微小変動"
        )
        self.final_rri_item = self.final_rri_plot.plot(
            pen=pg.mkPen("#FF647C", width=2),
            name="合成後RRI",
        )

        self._current_lines: list[pg.InfiniteLine] = []
        for plot in (
            self.heartbeat_plot,
            self.rri_plot,
            self.hr_plot,
            self.rmssd_plot,
            self.components_plot,
            self.final_rri_plot,
        ):
            line = pg.InfiniteLine(pos=0.0, angle=90, pen=pg.mkPen("#FFFFFF", width=1))
            plot.addItem(line)
            self._current_lines.append(line)

        reference_pen = pg.mkPen("#64748B", style=Qt.PenStyle.DashLine)
        self._min_rri_line = pg.InfiniteLine(angle=0, pen=reference_pen)
        self._max_rri_line = pg.InfiniteLine(angle=0, pen=reference_pen)
        self.rri_plot.addItem(self._min_rri_line)
        self.rri_plot.addItem(self._max_rri_line)
        self.record_count = 0
        self.set_config(config)
        self.clear()

    def _configure_plots(self) -> None:
        plots = (
            (self.heartbeat_plot, "心拍イベント", "beat index"),
            (self.rri_plot, "真のRRI（診断用）", "ms"),
            (self.hr_plot, "瞬時心拍数（診断用）", "bpm"),
            (self.rmssd_plot, "rolling RMSSD 30秒（診断用）", "ms"),
            (self.components_plot, "内部変動成分", "ms"),
            (self.final_rri_plot, "合成後のRRI", "ms"),
        )
        for plot, title, units in plots:
            plot.setTitle(title, color="#E5E7EB", size="10pt")
            plot.setLabel("left", units)
            plot.setLabel("bottom", "仮想時間", units="秒")
            plot.showGrid(x=True, y=True, alpha=0.16)
        self.heartbeat_plot.setXLink(self.rri_plot)
        self.hr_plot.setXLink(self.rri_plot)
        self.rmssd_plot.setXLink(self.components_plot)
        self.final_rri_plot.setXLink(self.components_plot)
        self.components_plot.addLegend(offset=(8, 8))

    def set_config(self, config: VirtualUserConfig) -> None:
        """Update duration and RRI reference lines without rebuilding plots."""

        self._config = config
        self._min_rri_line.setValue(config.min_rri_ms)
        self._max_rri_line.setValue(config.max_rri_ms)
        for plot in (
            self.heartbeat_plot,
            self.rri_plot,
            self.hr_plot,
            self.rmssd_plot,
            self.components_plot,
            self.final_rri_plot,
        ):
            plot.setXRange(0.0, float(config.duration_seconds), padding=0.01)

    def set_records(
        self,
        records: tuple[HeartbeatRecord, ...],
        current_time_us: int,
    ) -> None:
        """Update existing data items from immutable component records."""

        heartbeat_x = [record.heartbeat_time_us / 1_000_000 for record in records]
        heartbeat_y = [record.beat_index for record in records]
        interval_records = tuple(record for record in records if record.true_rri_ms is not None)
        interval_x = [record.heartbeat_time_us / 1_000_000 for record in interval_records]

        self.heartbeat_item.setData(heartbeat_x, heartbeat_y)
        self.rri_item.setData(interval_x, [record.true_rri_ms for record in interval_records])
        self.hr_item.setData(
            interval_x,
            [record.instantaneous_hr_bpm for record in interval_records],
        )

        rolling_values = rolling_rmssd_series(records)
        rolling_points = [
            (record.heartbeat_time_us / 1_000_000, value)
            for record, value in zip(records, rolling_values, strict=True)
            if value is not None
        ]
        self.rmssd_item.setData(
            [point[0] for point in rolling_points],
            [point[1] for point in rolling_points],
        )
        self.respiratory_item.setData(
            interval_x,
            [record.respiratory_component_ms for record in interval_records],
        )
        self.slow_wave_item.setData(
            interval_x,
            [record.slow_wave_component_ms for record in interval_records],
        )
        self.correlated_item.setData(
            interval_x,
            [record.correlated_component_ms for record in interval_records],
        )
        self.jitter_item.setData(
            interval_x,
            [record.beat_jitter_component_ms for record in interval_records],
        )
        self.final_rri_item.setData(
            interval_x,
            [record.final_rri_ms for record in interval_records],
        )
        self.set_current_time_us(current_time_us)
        self.record_count = len(records)

    def set_current_time_us(self, current_time_us: int) -> None:
        """Move each current-time line without altering series data."""

        seconds = current_time_us / 1_000_000
        for line in self._current_lines:
            line.setValue(seconds)

    def clear(self) -> None:
        """Clear all series while keeping PlotDataItems and reference lines alive."""

        for item in (
            self.heartbeat_item,
            self.rri_item,
            self.hr_item,
            self.rmssd_item,
            self.respiratory_item,
            self.slow_wave_item,
            self.correlated_item,
            self.jitter_item,
            self.final_rri_item,
        ):
            item.setData([], [])
        self.set_current_time_us(0)
        self.record_count = 0
