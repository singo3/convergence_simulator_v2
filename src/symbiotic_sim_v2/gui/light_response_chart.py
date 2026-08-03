"""Record-backed Stage 7 charts; no preference or physiology is calculated here."""

from __future__ import annotations

import math
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

LIGHT_RESPONSE_CHART_MIN_HEIGHT = 780
LIGHT_RESPONSE_PLOT_MIN_HEIGHT = 180
PHYSIOLOGY_CHART_MIN_HEIGHT = 700
PHYSIOLOGY_PLOT_MIN_HEIGHT = 210
GARDEN_RESPONSE_CHART_MIN_HEIGHT = 700
GARDEN_RESPONSE_PLOT_MIN_HEIGHT = 280


def _configure_plot(plot, title: str, left: str, units: str | None = None) -> None:
    plot.setTitle(title, color="#E5E7EB", size="11pt")
    plot.setLabel("left", left, units=units)
    plot.setLabel("bottom", "仮想時間", units="秒")
    plot.showGrid(x=True, y=True, alpha=0.16)


def _fix_plot_height(plot, minimum_height: int) -> None:
    plot.setMinimumHeight(minimum_height)
    plot.setPreferredHeight(minimum_height)


def _current_line(plot) -> pg.InfiniteLine:
    line = pg.InfiniteLine(
        pos=0.0,
        angle=90,
        movable=False,
        pen=pg.mkPen("#FFFFFF", width=1),
    )
    plot.addItem(line)
    return line


class LightStimulusResponseChart(QWidget):
    """Show physical light, stored preference results, and stored R(t) samples."""

    def __init__(self, duration_seconds: float = 240.0, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("lightStimulusResponseChart")
        self.setMinimumHeight(LIGHT_RESPONSE_CHART_MIN_HEIGHT)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.boundary_summary_label = QLabel(self)
        self.boundary_summary_label.setObjectName("lightResponseBoundarySummary")
        self.boundary_summary_label.setTextFormat(Qt.TextFormat.RichText)
        self.boundary_summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.boundary_summary_label.setStyleSheet(
            "QLabel#lightResponseBoundarySummary {"
            "background: #111827; color: #E5E7EB; padding: 4px 8px;"
            "border-bottom: 1px solid #334155; }"
        )
        root.addWidget(self.boundary_summary_label)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("lightStimulusResponseGraphics")
        self.graphics.setBackground("#111827")
        root.addWidget(self.graphics)

        self.active_plot = self.graphics.addPlot(row=0, col=0)
        self.physical_plot = self.graphics.addPlot(row=1, col=0)
        self.preference_plot = self.graphics.addPlot(row=2, col=0)
        self.response_plot = self.graphics.addPlot(row=3, col=0)
        for plot in self.plots:
            _fix_plot_height(plot, LIGHT_RESPONSE_PLOT_MIN_HEIGHT)
        _configure_plot(self.active_plot, "light active", "active")
        _configure_plot(self.physical_plot, "知覚した物理光 Hue / blink BPM", "degree / BPM")
        _configure_plot(
            self.preference_plot,
            "Hue/BPM適合度・total preference match",
            "match",
        )
        _configure_plot(
            self.response_plot,
            "response target / 一次遅れ response level R(t)",
            "response",
        )
        self.active_plot.setYRange(-0.05, 1.05, padding=0)
        self.preference_plot.setYRange(-0.05, 1.05, padding=0)
        self.response_plot.setYRange(-0.05, 1.05, padding=0)
        for plot in (self.active_plot, self.physical_plot, self.preference_plot):
            plot.setXLink(self.response_plot)

        self.physical_plot.addLegend(offset=(8, 8))
        self.preference_plot.addLegend(offset=(8, 8))
        self.response_plot.addLegend(offset=(8, 8))
        self.active_item = self.active_plot.plot(
            pen=pg.mkPen("#FBBF24", width=2),
            name="light active",
        )
        self.hue_item = self.physical_plot.plot(
            pen=pg.mkPen("#38D996", width=2),
            symbol="o",
            symbolSize=4,
            name="Hue",
        )
        self.bpm_item = self.physical_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=2),
            symbol="o",
            symbolSize=4,
            name="BPM",
        )
        self.hue_match_item = self.preference_plot.plot(
            pen=pg.mkPen("#38D996", width=1), name="Hue match"
        )
        self.bpm_match_item = self.preference_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=1), name="BPM match"
        )
        self.preference_item = self.preference_plot.plot(
            pen=pg.mkPen("#C78BFA", width=3), name="total preference match"
        )
        self.target_item = self.response_plot.plot(
            pen=pg.mkPen("#FBBF24", width=2, style=Qt.PenStyle.DashLine),
            name="response target",
        )
        self.response_item = self.response_plot.plot(
            pen=pg.mkPen("#FF647C", width=3), name="response level"
        )
        self._current_lines = tuple(_current_line(plot) for plot in self.plots)
        self._first_active_lines: list[pg.InfiniteLine] = []
        self._audit_segment_lines: list[pg.InfiniteLine] = []
        self._response_epoch_lines: list[pg.InfiniteLine] = []
        self._segment_lines = self._audit_segment_lines
        self.sample_count = 0
        self.receipt_count = 0
        self.audit_segment_boundary_count = 0
        self.response_epoch_boundary_count = 0
        self.segment_boundary_count = 0
        self.set_duration_seconds(duration_seconds)
        self.clear()

    @property
    def plots(self) -> tuple[Any, ...]:
        return (
            self.active_plot,
            self.physical_plot,
            self.preference_plot,
            self.response_plot,
        )

    def set_duration_seconds(self, duration_seconds: float) -> None:
        for plot in self.plots:
            plot.setXRange(0.0, float(duration_seconds), padding=0.01)

    def set_records(
        self,
        samples: tuple[Any, ...],
        receipts: tuple[Any, ...],
        audit_segments: tuple[Any, ...],
        response_epochs: tuple[Any, ...],
        current_time_us: int,
    ) -> None:
        sample_x = [us_to_seconds(record.time_us) for record in samples]
        self.active_item.setData(
            sample_x,
            [1.0 if record.light_active else 0.0 for record in samples],
            stepMode="left",
        )
        _set_optional_series(
            self.hue_item,
            sample_x,
            [record.render_hue_degree for record in samples],
        )
        _set_optional_series(
            self.bpm_item,
            sample_x,
            [record.blink_bpm for record in samples],
        )
        self.preference_item.setData(
            sample_x,
            [record.preference_match for record in samples],
        )
        self.target_item.setData(
            sample_x,
            [record.response_target for record in samples],
            stepMode="left",
        )
        self.response_item.setData(
            sample_x,
            [record.response_level for record in samples],
        )

        receipt_x = [us_to_seconds(record.event_time_us) for record in receipts]
        _set_optional_series(
            self.hue_match_item,
            receipt_x,
            [record.hue_match for record in receipts],
        )
        _set_optional_series(
            self.bpm_match_item,
            receipt_x,
            [record.bpm_match for record in receipts],
        )
        self._replace_markers(receipts, audit_segments, response_epochs)
        self.set_current_time_us(current_time_us)
        self.sample_count = len(samples)
        self.receipt_count = len(receipts)
        self.segment_boundary_count = self.audit_segment_boundary_count
        self._update_boundary_summary()

    def _replace_markers(
        self,
        receipts: tuple[Any, ...],
        audit_segments: tuple[Any, ...],
        response_epochs: tuple[Any, ...],
    ) -> None:
        for line in self._first_active_lines:
            self.active_plot.removeItem(line)
        for line in self._audit_segment_lines:
            self.physical_plot.removeItem(line)
        for line in self._response_epoch_lines:
            self.response_plot.removeItem(line)
        self._first_active_lines.clear()
        self._audit_segment_lines.clear()
        self._response_epoch_lines.clear()

        first_active = next((record for record in receipts if record.active), None)
        if first_active is not None:
            line = pg.InfiniteLine(
                pos=us_to_seconds(first_active.event_time_us),
                angle=90,
                movable=False,
                pen=pg.mkPen("#38D996", width=2, style=Qt.PenStyle.DashLine),
                label="first active",
                labelOpts={"color": "#38D996"},
            )
            self.active_plot.addItem(line)
            self._first_active_lines.append(line)

        audit_boundary_times_us = {
            segment.start_time_us for segment in audit_segments
        }
        audit_boundary_times_us.update(
            receipt.event_time_us
            for receipt in receipts
            if (
                getattr(receipt, "physical_parameters_changed", False)
                or getattr(receipt, "target_changed", False)
            )
            and getattr(receipt, "audit_segment_index", None) is not None
        )
        response_epoch_times_us = {
            epoch.start_time_us for epoch in response_epochs
        }
        response_epoch_times_us.update(
            receipt.event_time_us
            for receipt in receipts
            if getattr(receipt, "target_changed", False)
            and getattr(receipt, "response_dynamics_epoch_index", None) is not None
        )

        for boundary_time_us in sorted(audit_boundary_times_us):
            line = pg.InfiniteLine(
                pos=us_to_seconds(boundary_time_us),
                angle=90,
                movable=False,
                pen=pg.mkPen("#F59E0B", width=2, style=Qt.PenStyle.DotLine),
            )
            line.setToolTip("physical audit segment start")
            self.physical_plot.addItem(line)
            self._audit_segment_lines.append(line)

        for boundary_time_us in sorted(response_epoch_times_us):
            line = pg.InfiniteLine(
                pos=us_to_seconds(boundary_time_us),
                angle=90,
                movable=False,
                pen=pg.mkPen("#C084FC", width=2, style=Qt.PenStyle.DashLine),
            )
            line.setToolTip("response dynamics epoch start")
            self.response_plot.addItem(line)
            self._response_epoch_lines.append(line)
        self.audit_segment_boundary_count = len(audit_boundary_times_us)
        self.response_epoch_boundary_count = len(response_epoch_times_us)

    def _update_boundary_summary(self) -> None:
        self.boundary_summary_label.setText(
            '<span style="color:#F59E0B">● physical audit segment: '
            f"{self.audit_segment_boundary_count}</span>"
            "&nbsp;&nbsp;&nbsp;"
            '<span style="color:#C084FC">● response dynamics epoch: '
            f"{self.response_epoch_boundary_count}</span>"
        )
        self.boundary_summary_label.setToolTip(
            "orange dotted: physical parameter audit boundary; "
            "purple dashed: response target/dynamics boundary"
        )

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        for line in self._current_lines:
            line.setValue(seconds)

    def clear(self) -> None:
        for item in (
            self.active_item,
            self.hue_item,
            self.bpm_item,
            self.hue_match_item,
            self.bpm_match_item,
            self.preference_item,
            self.target_item,
            self.response_item,
        ):
            item.setData([], [])
        self._replace_markers((), (), ())
        self.set_current_time_us(0)
        self.sample_count = 0
        self.receipt_count = 0
        self.audit_segment_boundary_count = 0
        self.response_epoch_boundary_count = 0
        self.segment_boundary_count = 0
        self._update_boundary_summary()


class LightResponsePhysiologyChart(QWidget):
    """Plot only physiology values stored on responsive heartbeat records."""

    def __init__(self, duration_seconds: float = 240.0, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("lightResponsePhysiologyChart")
        self.setMinimumHeight(PHYSIOLOGY_CHART_MIN_HEIGHT)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("lightResponsePhysiologyGraphics")
        self.graphics.setBackground("#111827")
        root.addWidget(self.graphics)

        self.amplitude_plot = self.graphics.addPlot(row=0, col=0)
        self.rri_plot = self.graphics.addPlot(row=1, col=0)
        self.hr_plot = self.graphics.addPlot(row=2, col=0)
        for plot in self.plots:
            _fix_plot_height(plot, PHYSIOLOGY_PLOT_MIN_HEIGHT)
        _configure_plot(
            self.amplitude_plot,
            "base / effective respiratory amplitude",
            "amplitude",
            "ms",
        )
        _configure_plot(
            self.rri_plot,
            "base / effective mean RRI・true RRI",
            "RRI",
            "ms",
        )
        _configure_plot(self.hr_plot, "instantaneous HR", "HR", "bpm")
        self.amplitude_plot.setXLink(self.rri_plot)
        self.hr_plot.setXLink(self.rri_plot)
        self.amplitude_plot.addLegend(offset=(8, 8))
        self.rri_plot.addLegend(offset=(8, 8))
        self.base_amplitude_item = self.amplitude_plot.plot(
            pen=pg.mkPen("#94A3B8", width=2), name="base respiratory amplitude"
        )
        self.effective_amplitude_item = self.amplitude_plot.plot(
            pen=pg.mkPen("#38D996", width=3), name="effective respiratory amplitude"
        )
        self.base_mean_item = self.rri_plot.plot(
            pen=pg.mkPen("#94A3B8", width=2), name="base mean RRI"
        )
        self.effective_mean_item = self.rri_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=3), name="effective mean RRI"
        )
        self.true_rri_item = self.rri_plot.plot(
            pen=pg.mkPen("#FF647C", width=1),
            symbol="o",
            symbolSize=3,
            name="true RRI",
        )
        self.hr_item = self.hr_plot.plot(pen=pg.mkPen("#C78BFA", width=2))
        self._current_lines = tuple(_current_line(plot) for plot in self.plots)
        self.record_count = 0
        self.set_duration_seconds(duration_seconds)
        self.clear()

    @property
    def plots(self) -> tuple[Any, ...]:
        return (self.amplitude_plot, self.rri_plot, self.hr_plot)

    def set_duration_seconds(self, duration_seconds: float) -> None:
        for plot in self.plots:
            plot.setXRange(0.0, float(duration_seconds), padding=0.01)

    def set_records(self, records: tuple[Any, ...], current_time_us: int) -> None:
        usable = tuple(record for record in records if record.true_rri_ms is not None)
        x = [us_to_seconds(record.heartbeat_time_us) for record in usable]
        self.base_amplitude_item.setData(
            x, [record.base_respiratory_amplitude_ms for record in usable]
        )
        self.effective_amplitude_item.setData(
            x, [record.effective_respiratory_amplitude_ms for record in usable]
        )
        self.base_mean_item.setData(x, [record.base_mean_rri_ms for record in usable])
        self.effective_mean_item.setData(
            x, [record.effective_mean_rri_ms for record in usable]
        )
        self.true_rri_item.setData(x, [record.true_rri_ms for record in usable])
        self.hr_item.setData(x, [record.instantaneous_hr_bpm for record in usable])
        self.set_current_time_us(current_time_us)
        self.record_count = len(records)

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        for line in self._current_lines:
            line.setValue(seconds)

    def clear(self) -> None:
        for item in (
            self.base_amplitude_item,
            self.effective_amplitude_item,
            self.base_mean_item,
            self.effective_mean_item,
            self.true_rri_item,
            self.hr_item,
        ):
            item.setData([], [])
        self.set_current_time_us(0)
        self.record_count = 0


class GardenEvaluationResponseChart(QWidget):
    """Adapt authoritative Garden evaluation records; never recalculate RMSSD or N."""

    def __init__(self, duration_seconds: float = 240.0, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("gardenEvaluationResponseChart")
        self.setMinimumHeight(GARDEN_RESPONSE_CHART_MIN_HEIGHT)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("gardenEvaluationResponseGraphics")
        self.graphics.setBackground("#111827")
        root.addWidget(self.graphics)

        self.rmssd_plot = self.graphics.addPlot(row=0, col=0)
        self.n_plot = self.graphics.addPlot(row=1, col=0)
        for plot in self.plots:
            _fix_plot_height(plot, GARDEN_RESPONSE_PLOT_MIN_HEIGHT)
        _configure_plot(
            self.rmssd_plot,
            "Garden正式評価: baseline / Bundle 0 / Bundle 1 / Bundle 2 RMSSD",
            "RMSSD",
            "ms",
        )
        _configure_plot(self.n_plot, "Garden正式評価: N", "N")
        self.n_plot.setYRange(-0.05, 1.05, padding=0)
        self.n_plot.setXLink(self.rmssd_plot)
        self.rmssd_plot.addLegend(offset=(8, 8))
        self.baseline_item = self.rmssd_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=14,
            symbolBrush="#FBBF24",
            name="baseline RMSSD",
        )
        colors = ("#38D996", "#4DA3FF", "#C78BFA")
        self.bundle_items = tuple(
            self.rmssd_plot.plot(
                pen=None,
                symbol="o",
                symbolSize=10,
                symbolBrush=color,
                name=f"Bundle {index} RMSSD",
            )
            for index, color in enumerate(colors)
        )
        self.n_item = self.n_plot.plot(
            pen=pg.mkPen("#FF647C", width=2),
            symbol="o",
            symbolSize=8,
            symbolBrush="#FF647C",
        )
        self._current_lines = tuple(_current_line(plot) for plot in self.plots)
        self.evaluation_count = 0
        self.source_is_garden_evaluation_records = True
        self.set_duration_seconds(duration_seconds)
        self.clear()

    @property
    def plots(self) -> tuple[Any, ...]:
        return (self.rmssd_plot, self.n_plot)

    def set_duration_seconds(self, duration_seconds: float) -> None:
        for plot in self.plots:
            plot.setXRange(0.0, float(duration_seconds), padding=0.01)

    def set_records(self, records: tuple[Any, ...], current_time_us: int) -> None:
        accepted = tuple(record for record in records if record.is_valid)
        baseline = tuple(
            record for record in accepted if record.evaluation_kind == "baseline"
        )
        self._set_points(self.baseline_item, baseline, "rmssd_ms")
        for index, item in enumerate(self.bundle_items):
            selected = tuple(
                record
                for record in accepted
                if record.evaluation_kind == "bundle" and record.bundle_index == index
            )
            self._set_points(item, selected, "rmssd_ms")
        self._set_points(self.n_item, accepted, "n")
        self.set_current_time_us(current_time_us)
        self.evaluation_count = len(records)

    @staticmethod
    def _set_points(item: Any, records: tuple[Any, ...], field: str) -> None:
        usable = tuple(record for record in records if getattr(record, field) is not None)
        item.setData(
            [us_to_seconds(record.window_end_us) for record in usable],
            [getattr(record, field) for record in usable],
        )

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        for line in self._current_lines:
            line.setValue(seconds)

    def clear(self) -> None:
        self.baseline_item.setData([], [])
        for item in self.bundle_items:
            item.setData([], [])
        self.n_item.setData([], [])
        self.set_current_time_us(0)
        self.evaluation_count = 0


LightResponseChart = LightStimulusResponseChart
LightResponseGardenChart = GardenEvaluationResponseChart


def _finite_or_nan(value: float | None) -> float:
    return math.nan if value is None else value


def _set_optional_series(
    item: Any,
    x_values: list[float],
    y_values: list[float | None],
) -> None:
    """Keep inactive gaps when finite points exist and avoid all-NaN scatter warnings."""

    if any(value is not None for value in y_values):
        item.setData(x_values, [_finite_or_nan(value) for value in y_values])
    else:
        item.setData([], [])
