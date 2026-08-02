"""Reusable PyQtGraph plots for Stage 3 RRI comparison diagnostics."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from symbiotic_sim_v2.devices.polar_h10.diagnostics import RriMeasurementDiagnostic
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds


class PolarH10Chart(QWidget):
    """Update fixed PlotDataItems for measured/true RRI and absolute error."""

    def __init__(self, duration_seconds: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("polarH10Chart")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setBackground("#111827")
        root.addWidget(self.graphics)

        self.comparison_plot = self.graphics.addPlot(row=0, col=0)
        self.error_plot = self.graphics.addPlot(row=1, col=0)
        self._configure_plots()

        truth_pen = pg.mkPen("#FFB648", width=4, style=Qt.PenStyle.DashLine)
        self.true_rri_item = self.comparison_plot.plot(
            pen=truth_pen,
            name="仮想ユーザー内部の真のRRI（診断用）",
        )
        self.measured_rri_item = self.comparison_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush="#4DA3FF",
            name="H10測定RRI",
        )
        self.error_item = self.error_plot.plot(
            pen=pg.mkPen("#FF647C", width=2),
            symbol="o",
            symbolSize=5,
            symbolBrush="#FF647C",
            name="絶対誤差",
        )
        self.zero_error_line = pg.InfiniteLine(
            pos=0.0,
            angle=0,
            pen=pg.mkPen("#94A3B8", style=Qt.PenStyle.DashLine),
        )
        self.error_plot.addItem(self.zero_error_line)

        self._current_lines: list[pg.InfiniteLine] = []
        for plot in (self.comparison_plot, self.error_plot):
            line = pg.InfiniteLine(
                pos=0.0,
                angle=90,
                pen=pg.mkPen("#FFFFFF", width=1),
            )
            plot.addItem(line)
            self._current_lines.append(line)

        # Short aliases make widget-level inspection straightforward without exposing plots.
        self.true_item = self.true_rri_item
        self.measurement_item = self.measured_rri_item
        self.measurement_count = 0
        self.record_count = 0
        self.set_duration_seconds(duration_seconds)
        self.clear()

    def _configure_plots(self) -> None:
        self.comparison_plot.setTitle(
            "RRI比較（2系列は一致時に重なります）",
            color="#E5E7EB",
            size="11pt",
        )
        self.comparison_plot.setLabel("left", "RRI", units="ms")
        self.comparison_plot.setLabel("bottom", "仮想時間", units="秒")
        self.comparison_plot.showGrid(x=True, y=True, alpha=0.16)
        self.comparison_plot.addLegend(offset=(8, 8))

        self.error_plot.setTitle("測定絶対誤差（理想モデルは0線）", color="#E5E7EB")
        self.error_plot.setLabel("left", "絶対誤差", units="µs")
        self.error_plot.setLabel("bottom", "仮想時間", units="秒")
        self.error_plot.showGrid(x=True, y=True, alpha=0.16)
        self.error_plot.setXLink(self.comparison_plot)

    def set_duration_seconds(self, duration_seconds: int) -> None:
        """Set the shared virtual-time range without rebuilding either plot."""

        if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int):
            raise TypeError("duration_seconds must be an integer")
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        self._duration_seconds = duration_seconds
        for plot in (self.comparison_plot, self.error_plot):
            plot.setXRange(0.0, float(duration_seconds), padding=0.01)

    def set_records(
        self,
        records: tuple[RriMeasurementDiagnostic, ...],
        current_time_us: int,
    ) -> None:
        """Refresh existing data items from immutable comparison diagnostics."""

        x_values = [record.event_time_seconds for record in records]
        self.true_rri_item.setData(
            x_values,
            [record.diagnostic_true_rri_ms for record in records],
        )
        self.measured_rri_item.setData(x_values, [record.rri_ms for record in records])
        self.error_item.setData(x_values, [record.absolute_error_us for record in records])
        maximum_error = max((record.absolute_error_us for record in records), default=0)
        error_ceiling = max(1.0, maximum_error * 1.1)
        self.error_plot.setYRange(-0.05 * error_ceiling, error_ceiling, padding=0)
        self.set_current_time_us(current_time_us)
        self.measurement_count = len(records)
        self.record_count = len(records)

    def set_current_time_us(self, current_time_us: int) -> None:
        """Move both current-time lines without changing any data series."""

        seconds = us_to_seconds(current_time_us)
        for line in self._current_lines:
            line.setValue(seconds)

    def clear(self) -> None:
        """Clear every series while keeping PlotDataItems and lines alive."""

        self.true_rri_item.setData([], [])
        self.measured_rri_item.setData([], [])
        self.error_item.setData([], [])
        self.error_plot.setYRange(-0.05, 1.0, padding=0)
        self.set_current_time_us(0)
        self.measurement_count = 0
        self.record_count = 0
