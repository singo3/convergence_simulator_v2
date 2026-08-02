"""Fixed-item Stage 5A plots for one Digital Life's first round."""

from __future__ import annotations

import math

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.digital_life.records import DigitalLifeFirstRoundRecord
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

DIGITAL_LIFE_CHART_MIN_HEIGHT = 930
DIGITAL_LIFE_GRAPHICS_MIN_HEIGHT = 910
DIGITAL_LIFE_PLOT_MIN_HEIGHT = 210
STAGE_5A_DURATION_SECONDS = 240


class DigitalLifeChart(QWidget):
    """Render immutable first-round records through persistent PlotDataItems."""

    def __init__(self, config: DigitalLifeConfig, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("digitalLifeChart")
        self.setMinimumHeight(DIGITAL_LIFE_CHART_MIN_HEIGHT)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("digitalLifeGraphics")
        self.graphics.setBackground("#111827")
        self.graphics.setMinimumHeight(DIGITAL_LIFE_GRAPHICS_MIN_HEIGHT)
        root.addWidget(self.graphics)

        self._build_state_plot()
        self._build_activity_plot()
        self._build_holding_plot()
        self._build_relation_plot()
        self.set_config(config)
        self.clear()

    def _build_state_plot(self) -> None:
        self.state_plot = self.graphics.addPlot(row=0, col=0)
        self._configure_plot(
            self.state_plot,
            "N / baseline / Nd / W",
            "state",
        )
        self.state_plot.addLegend(offset=(8, 8))
        self.n_item = self.state_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=2),
            name="N_current",
        )
        self.baseline_n_item = self.state_plot.plot(
            pen=pg.mkPen("#FBBF24", width=2),
            name="N_baseline_session",
        )
        self.nd_item = self.state_plot.plot(
            pen=pg.mkPen("#38D996", width=2),
            name="Nd",
        )
        self.w_item = self.state_plot.plot(
            pen=pg.mkPen("#C78BFA", width=2, style=Qt.PenStyle.DotLine),
            name="W",
        )
        self.evaluation_item = self.state_plot.plot(
            pen=None,
            symbol="star",
            symbolSize=12,
            symbolBrush="#FB7185",
            name="evaluation確定点",
        )
        self.state_current_line = self._current_line(self.state_plot)

    def _build_activity_plot(self) -> None:
        self.activity_plot = self.graphics.addPlot(row=1, col=0)
        self._configure_plot(self.activity_plot, "P / V / tau", "activity")
        self.activity_plot.setXLink(self.state_plot)
        self.activity_plot.addLegend(offset=(8, 8))
        self.p_item = self.activity_plot.plot(
            pen=pg.mkPen("#FBBF24", width=2),
            name="P",
        )
        self.v_item = self.activity_plot.plot(
            pen=pg.mkPen("#4DA3FF", width=2),
            name="V",
        )
        self.tau_item = self.activity_plot.plot(
            pen=pg.mkPen("#FB7185", width=2),
            name="tau",
        )
        self.s_item = self.activity_plot.plot(
            pen=pg.mkPen("#FFFFFF", width=1),
            name="S",
        )
        self.activity_current_line = self._current_line(self.activity_plot)

    def _build_holding_plot(self) -> None:
        self.holding_plot = self.graphics.addPlot(row=2, col=0)
        self._configure_plot(self.holding_plot, "E / q（Stage 5Aは保持値）", "holding")
        self.holding_plot.setXLink(self.state_plot)
        self.holding_plot.addLegend(offset=(8, 8))
        self.e_item = self.holding_plot.plot(
            pen=pg.mkPen("#FB7185", width=2),
            name="E",
        )
        self.q_item = self.holding_plot.plot(
            pen=pg.mkPen("#C78BFA", width=2),
            name="q",
        )
        self.holding_current_line = self._current_line(self.holding_plot)

    def _build_relation_plot(self) -> None:
        self.relation_plot = self.graphics.addPlot(row=3, col=0)
        self._configure_plot(self.relation_plot, "B / k / role F range", "normalized value")
        self.relation_plot.setXLink(self.state_plot)
        self.relation_plot.addLegend(offset=(8, 8))
        self.k_f_item = self.relation_plot.plot(
            pen=pg.mkPen("#22D3EE", width=2),
            name="k F",
        )
        self.k_t_item = self.relation_plot.plot(
            pen=pg.mkPen("#60A5FA", width=2, style=Qt.PenStyle.DashLine),
            name="k T",
        )
        self.b_f_item = self.relation_plot.plot(
            pen=pg.mkPen("#38D996", width=2),
            name="B F",
        )
        self.b_t_item = self.relation_plot.plot(
            pen=pg.mkPen("#FBBF24", width=2, style=Qt.PenStyle.DotLine),
            name="B T",
        )
        self.b_a_item = self.relation_plot.plot(
            pen=pg.mkPen("#C78BFA", width=1, style=Qt.PenStyle.DashDotLine),
            name="B A（固定）",
        )
        self.b_d_item = self.relation_plot.plot(
            pen=pg.mkPen("#FB7185", width=1, style=Qt.PenStyle.DashLine),
            name="B D（固定）",
        )
        self.f_range_region = pg.LinearRegionItem(
            values=(0.0, 1.0),
            orientation="horizontal",
            movable=False,
            brush=pg.mkBrush("#34D39933"),
            pen=pg.mkPen("#34D399"),
        )
        self.f_range_region.setZValue(-20)
        self.relation_plot.addItem(self.f_range_region)
        self.relation_current_line = self._current_line(self.relation_plot)

    @staticmethod
    def _configure_plot(plot, title: str, left: str) -> None:
        plot.setTitle(title, color="#E5E7EB", size="11pt")
        plot.setLabel("left", left)
        plot.setLabel("bottom", "仮想時間", units="秒")
        plot.setYRange(-0.05, 1.05, padding=0)
        plot.showGrid(x=True, y=True, alpha=0.16)
        plot.setMinimumHeight(DIGITAL_LIFE_PLOT_MIN_HEIGHT)
        plot.setPreferredHeight(DIGITAL_LIFE_PLOT_MIN_HEIGHT)

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

    def set_config(self, config: DigitalLifeConfig) -> None:
        """Update only static role/config decoration after scenario replacement."""

        self._config = config
        self.f_range_region.setRegion((config.f_min, config.f_max))
        for plot in (
            self.state_plot,
            self.activity_plot,
            self.holding_plot,
            self.relation_plot,
        ):
            plot.setXRange(0.0, float(STAGE_5A_DURATION_SECONDS), padding=0.01)

    def set_records(
        self,
        records: tuple[DigitalLifeFirstRoundRecord, ...],
        current_time_us: int,
    ) -> None:
        """Copy immutable record values into existing plot items."""

        times = [us_to_seconds(record.signal_time_us) for record in records]
        self.n_item.setData(times, [self._optional(record.n_current) for record in records])
        self.baseline_n_item.setData(
            times,
            [self._optional(record.n_baseline_session) for record in records],
        )
        self.nd_item.setData(times, [record.nd for record in records])
        self.w_item.setData(times, [record.w for record in records])
        evaluations = tuple(record for record in records if record.is_new_valid_evaluation)
        self.evaluation_item.setData(
            [us_to_seconds(record.signal_time_us) for record in evaluations],
            [self._optional(record.n_current) for record in evaluations],
        )

        self.p_item.setData(times, [record.p for record in records])
        self.v_item.setData(times, [self._optional(record.v) for record in records])
        self.tau_item.setData(times, [self._optional(record.tau) for record in records])
        self.s_item.setData(times, [record.s for record in records], stepMode="left")

        self.e_item.setData(times, [record.e for record in records])
        self.q_item.setData(times, [record.q for record in records])
        self.k_f_item.setData(times, [record.k_current[0] for record in records])
        self.k_t_item.setData(times, [record.k_current[2] for record in records])
        self.b_f_item.setData(times, [record.b_f for record in records])
        self.b_t_item.setData(times, [record.b_t for record in records])
        self.b_a_item.setData(times, [record.b_a for record in records])
        self.b_d_item.setData(times, [record.b_d for record in records])
        self.set_current_time_us(current_time_us)
        self.record_count = len(records)
        self.signal_count = len(records)
        self.evaluation_point_count = len(evaluations)

    def set_current_time_us(self, current_time_us: int) -> None:
        seconds = us_to_seconds(current_time_us)
        for line in (
            self.state_current_line,
            self.activity_current_line,
            self.holding_current_line,
            self.relation_current_line,
        ):
            line.setValue(seconds)

    def clear(self) -> None:
        """Clear dynamic data without replacing PlotDataItems."""

        for item in (
            self.n_item,
            self.baseline_n_item,
            self.nd_item,
            self.w_item,
            self.evaluation_item,
            self.p_item,
            self.v_item,
            self.tau_item,
            self.s_item,
            self.e_item,
            self.q_item,
            self.k_f_item,
            self.k_t_item,
            self.b_f_item,
            self.b_t_item,
            self.b_a_item,
            self.b_d_item,
        ):
            item.setData([], [])
        self.set_current_time_us(0)
        self.record_count = 0
        self.signal_count = 0
        self.evaluation_point_count = 0

    @staticmethod
    def _optional(value: float | None) -> float:
        return math.nan if value is None else value
