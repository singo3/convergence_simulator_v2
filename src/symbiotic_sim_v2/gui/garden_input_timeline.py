"""Read-only 240-second phase and S timeline for the Garden input layer."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.records import GardenInputSignalRecord
from symbiotic_sim_v2.garden.input_layer.timing import phase_at, phase_change_times_us
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

PHASE_COLORS = (
    "#334155",
    "#1E40AF",
    "#475569",
    "#047857",
    "#475569",
    "#0F766E",
    "#475569",
    "#0E7490",
)


class GardenInputTimeline(pg.PlotWidget):
    """Render formal phase boundaries and immutable one-second S records."""

    def __init__(self, config: GardenInputConfig, parent=None) -> None:
        axis = pg.AxisItem(orientation="left")
        axis.setTicks([[(0.13, "S=0"), (0.36, "S=1"), (0.78, "phase")]])
        super().__init__(parent=parent, axisItems={"left": axis})
        self.setObjectName("gardenSessionTimeline")
        self.setBackground(QColor("#111827"))
        self.setLabel("bottom", "仮想時間", units="秒")
        self.setLabel("left", "Garden session")
        self.showGrid(x=True, y=False, alpha=0.18)
        self.setYRange(-0.02, 1.02, padding=0)
        self.getPlotItem().setMouseEnabled(x=True, y=False)

        self._phase_regions: list[pg.LinearRegionItem] = []
        self._phase_labels: list[pg.TextItem] = []
        self.s_item = self.plot(
            pen=pg.mkPen("#FBBF24", width=3),
            symbol="o",
            symbolSize=3,
            symbolBrush="#FBBF24",
            name="S",
        )
        self.current_time_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen("#FFFFFF", width=2),
            label="現在",
            labelOpts={"color": "#FFFFFF", "position": 0.96},
        )
        self.addItem(self.current_time_line)
        self.outside_marker = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen("#FB7185", width=2, style=Qt.PenStyle.DashLine),
            label="outside",
            labelOpts={"color": "#FB7185", "position": 0.82},
        )
        self.addItem(self.outside_marker)
        self.signal_count = 0
        self.current_time_us = 0
        self.set_config(config)
        self.clear_records()

    def set_config(self, config: GardenInputConfig) -> None:
        """Rebuild only the static bands when a whole scenario is replaced."""

        self._config = config
        for item in (*self._phase_regions, *self._phase_labels):
            self.removeItem(item)
        self._phase_regions.clear()
        self._phase_labels.clear()

        boundaries = phase_change_times_us(config)
        for index, (start_us, end_us) in enumerate(
            zip(boundaries[:-1], boundaries[1:], strict=True)
        ):
            start_seconds = us_to_seconds(start_us)
            end_seconds = us_to_seconds(end_us)
            descriptor = phase_at(start_us, config)
            color = PHASE_COLORS[index % len(PHASE_COLORS)]
            region = pg.LinearRegionItem(
                values=(start_seconds, end_seconds),
                orientation="vertical",
                movable=False,
                brush=pg.mkBrush(color + "66"),
                pen=pg.mkPen(color),
            )
            region.setZValue(-20)
            self.addItem(region)
            self._phase_regions.append(region)

            label = pg.TextItem(
                text=descriptor.phase.value.replace("_", "\n"),
                color="#E5E7EB",
                anchor=(0.5, 0.5),
            )
            label.setPos((start_seconds + end_seconds) / 2.0, 0.78)
            label.setZValue(-5)
            self.addItem(label)
            self._phase_labels.append(label)

        duration = float(config.total_duration_seconds)
        self.outside_marker.setValue(duration)
        self.setXRange(0.0, duration, padding=0.01)
        self.phase_region_count = len(self._phase_regions)

    def set_signal_records(
        self,
        records: tuple[GardenInputSignalRecord, ...],
        current_time_us: int,
    ) -> None:
        """Refresh the existing S series directly from formal signal records."""

        self.s_item.setData(
            [us_to_seconds(record.signal_time_us) for record in records],
            [0.13 + 0.23 * record.s for record in records],
            stepMode="left",
        )
        self.set_current_time_us(current_time_us)
        self.signal_count = len(records)

    def set_records(
        self,
        records: tuple[GardenInputSignalRecord, ...],
        current_time_us: int,
    ) -> None:
        """Compatibility alias for other diagnostic widgets."""

        self.set_signal_records(records, current_time_us)

    def set_current_time_us(self, current_time_us: int) -> None:
        self.current_time_us = current_time_us
        self.current_time_line.setValue(us_to_seconds(current_time_us))

    def clear_records(self) -> None:
        self.s_item.setData([], [])
        self.set_current_time_us(0)
        self.signal_count = 0

    def clear(self) -> None:
        """Clear dynamic data while retaining the formal phase background."""

        self.clear_records()
