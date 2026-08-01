"""PyQtGraph diagnostic timeline with incremental execution updates."""

from __future__ import annotations

from collections import defaultdict

import pyqtgraph as pg
from PySide6.QtGui import QColor

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

EVENT_STYLES: dict[str, tuple[int, str, str, str]] = {
    "heartbeat": (0, "o", "#FF647C", "heartbeat"),
    "clock_tick": (1, "o", "#4DA3FF", "clock_tick"),
    "demo_marker": (2, "t", "#38D996", "demo_marker"),
    "demo_same_time_a": (3, "s", "#FFB648", "same_time_a"),
    "demo_same_time_b": (4, "d", "#C78BFA", "same_time_b"),
    "simulation_complete": (5, "star", "#FF647C", "simulation_complete"),
}


class TimelineWidget(pg.PlotWidget):
    """Plot planned event lanes and move one current-time line per refresh."""

    def __init__(self, parent=None) -> None:
        axis = pg.AxisItem(orientation="left")
        ticks = [
            (lane, label)
            for _event, (lane, _symbol, _color, label) in EVENT_STYLES.items()
        ]
        axis.setTicks([ticks])
        super().__init__(parent=parent, axisItems={"left": axis})
        self.setObjectName("timelineWidget")
        self.setBackground(QColor("#111827"))
        self.showGrid(x=True, y=True, alpha=0.18)
        self.setLabel("bottom", "仮想時間", units="秒")
        self.setLabel("left", "event type")
        self.setYRange(-0.65, 5.65, padding=0)
        self.getPlotItem().setMouseEnabled(x=True, y=False)

        self._current_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen("#FFFFFF", width=2),
            label="現在",
            labelOpts={"color": "#FFFFFF", "position": 0.94},
        )
        self.addItem(self._current_line)
        self._planned_items: list[pg.ScatterPlotItem] = []
        self._executed_item = pg.ScatterPlotItem(
            symbol="o",
            size=15,
            brush=pg.mkBrush(0, 0, 0, 0),
            pen=pg.mkPen("#FFFFFF", width=2),
        )
        self.addItem(self._executed_item)
        self._executed_x: list[float] = []
        self._executed_y: list[int] = []
        self.current_time_us = 0

    def set_scenario_events(self, events: tuple[SimulationEvent, ...]) -> None:
        """Set static planned markers once when a scenario is loaded or reset."""

        for item in self._planned_items:
            self.removeItem(item)
        self._planned_items.clear()

        grouped: dict[str, list[SimulationEvent]] = defaultdict(list)
        for event in events:
            grouped[event.event_type].append(event)
        for event_type, typed_events in grouped.items():
            lane, symbol, color, _label = EVENT_STYLES.get(
                event_type,
                (5, "x", "#D1D5DB", event_type),
            )
            item = pg.ScatterPlotItem(
                x=[us_to_seconds(event.scheduled_time_us) for event in typed_events],
                y=[lane] * len(typed_events),
                symbol=symbol,
                size=10 if event_type == "clock_tick" else 13,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color),
                name=event_type,
            )
            self.addItem(item)
            self._planned_items.append(item)
        end_seconds = max(
            (us_to_seconds(event.scheduled_time_us) for event in events),
            default=20.0,
        )
        self.setXRange(0.0, max(1.0, end_seconds), padding=0.025)
        self.reset_execution()

    def set_current_time_us(self, current_time_us: int) -> None:
        """Move only the current-time line; planned points are left untouched."""

        self.current_time_us = current_time_us
        self._current_line.setValue(us_to_seconds(current_time_us))

    def mark_executed(self, events: tuple[SimulationEvent, ...]) -> None:
        """Append executed-point outlines without regenerating planned plots."""

        for event in events:
            lane = EVENT_STYLES.get(event.event_type, (5, "x", "#D1D5DB", ""))[0]
            self._executed_x.append(us_to_seconds(event.scheduled_time_us))
            self._executed_y.append(lane)
        self._executed_item.setData(x=self._executed_x, y=self._executed_y)

    def reset_execution(self) -> None:
        """Clear incremental execution outlines and return the line to zero."""

        self._executed_x.clear()
        self._executed_y.clear()
        self._executed_item.setData(x=[], y=[])
        self.set_current_time_us(0)
