"""Fixed-item plots for immutable Stage 4 Garden diagnostics."""

from __future__ import annotations

import math

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.records import (
    GardenEvaluationRecord,
    GardenInputSignalRecord,
    GardenRriRecord,
)
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds


class GardenInputChart(QWidget):
    """Update pre-created plot items without reproducing Garden calculations."""

    def __init__(self, config: GardenInputConfig, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gardenInputChart")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("gardenChartTabs")
        root.addWidget(self.tabs)

        self._build_rri_tab()
        self._build_evaluation_tab()
        self._build_signal_tab()
        self.set_config(config)
        self.clear()

    def _graphics(self) -> pg.GraphicsLayoutWidget:
        graphics = pg.GraphicsLayoutWidget()
        graphics.setBackground("#111827")
        return graphics

    @staticmethod
    def _configure_plot(plot, title: str, left: str, units: str | None = None) -> None:
        plot.setTitle(title, color="#E5E7EB", size="11pt")
        plot.setLabel("left", left, units=units)
        plot.setLabel("bottom", "仮想時間", units="秒")
        plot.showGrid(x=True, y=True, alpha=0.16)

    def _build_rri_tab(self) -> None:
        self.rri_graphics = self._graphics()
        self.rri_plot = self.rri_graphics.addPlot(row=0, col=0)
        self._configure_plot(self.rri_plot, "raw RRI・artifact", "RRI", "ms")
        self.rri_plot.addLegend(offset=(8, 8))
        self.valid_rri_item = self.rri_plot.plot(
            pen=pg.mkPen("#38D996", width=1),
            symbol="o",
            symbolSize=5,
            symbolBrush="#38D996",
            name="valid RRI",
        )
        self.artifact_rri_item = self.rri_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=10,
            symbolPen=pg.mkPen("#FB7185", width=2),
            name="artifact RRI",
        )
        self.rri_min_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen("#FBBF24", style=Qt.PenStyle.DashLine),
            label="300 ms",
            labelOpts={"color": "#FBBF24"},
        )
        self.rri_max_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen("#FBBF24", style=Qt.PenStyle.DashLine),
            label="2000 ms",
            labelOpts={"color": "#FBBF24"},
        )
        self.rri_current_line = self._current_line(self.rri_plot)
        self.rri_plot.addItem(self.rri_min_line)
        self.rri_plot.addItem(self.rri_max_line)
        self.tabs.addTab(self.rri_graphics, "raw RRI / artifact")

    def _build_evaluation_tab(self) -> None:
        self.evaluation_graphics = self._graphics()
        self.rmssd_plot = self.evaluation_graphics.addPlot(row=0, col=0)
        self.n_evaluation_plot = self.evaluation_graphics.addPlot(row=1, col=0)
        self._configure_plot(self.rmssd_plot, "評価窓RMSSD", "RMSSD", "ms")
        self._configure_plot(self.n_evaluation_plot, "評価確定点のN", "N")
        self.n_evaluation_plot.setXLink(self.rmssd_plot)
        self.n_evaluation_plot.setYRange(-0.05, 1.05, padding=0)
        self.rmssd_plot.addLegend(offset=(8, 8))
        self.baseline_rmssd_item = self.rmssd_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=13,
            symbolBrush="#FBBF24",
            name="baseline RMSSD",
        )
        self.bundle_rmssd_item = self.rmssd_plot.plot(
            pen=pg.mkPen("#38D996", width=2),
            symbol="o",
            symbolSize=8,
            symbolBrush="#38D996",
            name="Bundle RMSSD",
        )
        self.rejected_rmssd_item = self.rmssd_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=13,
            symbolPen=pg.mkPen("#FB7185", width=2),
            name="rejected評価",
        )
        self.n_evaluation_item = self.n_evaluation_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=2),
            symbol="o",
            symbolSize=7,
            symbolBrush="#4DA3FF",
            name="N",
        )
        self.rejected_n_item = self.n_evaluation_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=13,
            symbolPen=pg.mkPen("#FB7185", width=2),
        )
        self.evaluation_current_lines = (
            self._current_line(self.rmssd_plot),
            self._current_line(self.n_evaluation_plot),
        )
        self.tabs.addTab(self.evaluation_graphics, "評価窓RMSSD / N")

    def _build_signal_tab(self) -> None:
        self.signal_graphics = self._graphics()
        self.n_signal_plot = self.signal_graphics.addPlot(row=0, col=0)
        self.s_signal_plot = self.signal_graphics.addPlot(row=1, col=0)
        self.revision_plot = self.signal_graphics.addPlot(row=2, col=0)
        self._configure_plot(self.n_signal_plot, "GardenInputSignalEvent: N_current", "N")
        self._configure_plot(self.s_signal_plot, "GardenInputSignalEvent: S", "S")
        self._configure_plot(
            self.revision_plot,
            "valid evaluation revision",
            "revision",
        )
        self.n_signal_plot.setYRange(-0.05, 1.05, padding=0)
        self.s_signal_plot.setYRange(-0.1, 1.1, padding=0)
        self.n_signal_item = self.n_signal_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=2),
            name="N_current",
        )
        self.s_signal_item = self.s_signal_plot.plot(
            pen=pg.mkPen("#FBBF24", width=3),
            name="S",
        )
        self.revision_item = self.revision_plot.plot(
            pen=pg.mkPen("#C78BFA", width=2),
            name="valid evaluation revision",
        )
        self.signal_current_lines = tuple(
            self._current_line(plot)
            for plot in (self.n_signal_plot, self.s_signal_plot, self.revision_plot)
        )
        self.s_signal_plot.setXLink(self.n_signal_plot)
        self.revision_plot.setXLink(self.n_signal_plot)
        self.tabs.addTab(self.signal_graphics, "N / S step")

        # Names used in the Stage 4 specification and widget-level smoke checks.
        self.n_item = self.n_signal_item
        self.s_item = self.s_signal_item
        self.valid_evaluation_revision_item = self.revision_item
        self.rejected_evaluation_item = self.rejected_rmssd_item

    @staticmethod
    def _current_line(plot) -> pg.InfiniteLine:
        line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen("#FFFFFF", width=1),
        )
        plot.addItem(line)
        return line

    def set_config(self, config: GardenInputConfig) -> None:
        self._config = config
        duration = float(config.total_duration_seconds)
        self.rri_min_line.setValue(config.rri_min_us / 1_000.0)
        self.rri_max_line.setValue(config.rri_max_us / 1_000.0)
        for plot in (
            self.rri_plot,
            self.rmssd_plot,
            self.n_evaluation_plot,
            self.n_signal_plot,
            self.s_signal_plot,
            self.revision_plot,
        ):
            plot.setXRange(0.0, duration, padding=0.01)

    def set_records(
        self,
        rri_records: tuple[GardenRriRecord, ...],
        evaluation_records: tuple[GardenEvaluationRecord, ...],
        signal_records: tuple[GardenInputSignalRecord, ...],
        current_time_us: int,
    ) -> None:
        """Refresh plots using only decisions and values stored by the component."""

        valid = tuple(record for record in rri_records if not record.artifact)
        artifacts = tuple(record for record in rri_records if record.artifact)
        self.valid_rri_item.setData(
            [us_to_seconds(record.event_time_us) for record in valid],
            [record.raw_rri_ms for record in valid],
        )
        self.artifact_rri_item.setData(
            [us_to_seconds(record.event_time_us) for record in artifacts],
            [record.raw_rri_ms for record in artifacts],
        )

        accepted = tuple(record for record in evaluation_records if record.is_valid)
        baseline = tuple(record for record in accepted if record.evaluation_kind == "baseline")
        bundles = tuple(record for record in accepted if record.evaluation_kind == "bundle")
        rejected = tuple(record for record in evaluation_records if not record.is_valid)
        self._set_evaluation_item(self.baseline_rmssd_item, baseline, "rmssd_ms")
        self._set_evaluation_item(self.bundle_rmssd_item, bundles, "rmssd_ms")
        self._set_evaluation_item(self.rejected_rmssd_item, rejected, "rmssd_ms")
        self._set_evaluation_item(self.n_evaluation_item, accepted, "n")
        self._set_evaluation_item(self.rejected_n_item, rejected, "n")

        signal_times = [us_to_seconds(record.signal_time_us) for record in signal_records]
        self.n_signal_item.setData(
            signal_times,
            [record.n_current if record.n_available else math.nan for record in signal_records],
            stepMode="left",
        )
        self.s_signal_item.setData(
            signal_times,
            [record.s for record in signal_records],
            stepMode="left",
        )
        self.revision_item.setData(
            signal_times,
            [record.valid_evaluation_revision for record in signal_records],
            stepMode="left",
        )
        self.set_current_time_us(current_time_us)
        self.rri_count = len(rri_records)
        self.record_count = len(rri_records)
        self.valid_rri_count = len(valid)
        self.artifact_count = len(artifacts)
        self.evaluation_count = len(evaluation_records)
        self.signal_count = len(signal_records)

    @staticmethod
    def _set_evaluation_item(item, records, field: str) -> None:
        filtered = tuple(record for record in records if getattr(record, field) is not None)
        item.setData(
            [us_to_seconds(record.window_end_us) for record in filtered],
            [getattr(record, field) for record in filtered],
        )

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        self.rri_current_line.setValue(seconds)
        for line in (*self.evaluation_current_lines, *self.signal_current_lines):
            line.setValue(seconds)

    def clear(self) -> None:
        """Clear every dynamic series while preserving all PlotDataItems."""

        for item in (
            self.valid_rri_item,
            self.artifact_rri_item,
            self.baseline_rmssd_item,
            self.bundle_rmssd_item,
            self.rejected_rmssd_item,
            self.n_evaluation_item,
            self.rejected_n_item,
            self.n_signal_item,
            self.s_signal_item,
            self.revision_item,
        ):
            item.setData([], [])
        self.set_current_time_us(0)
        self.rri_count = 0
        self.record_count = 0
        self.valid_rri_count = 0
        self.artifact_count = 0
        self.evaluation_count = 0
        self.signal_count = 0
