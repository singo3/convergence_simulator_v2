"""Record-backed session/BPM chart for the Stage 8A.1 laboratory."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QToolTip, QVBoxLayout, QWidget

from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import (
    first_record_value,
    record_value,
)

SESSION_BPM_HUE_CHART_MIN_HEIGHT = 620
LIFE_SYMBOLS = {
    "life-red": "o",
    "life-green": "t",
    "life-blue": "s",
}


def actual_hue_color(hue_degree: object, *, alpha: int = 255) -> QColor:
    """Convert formal Hue to a GUI color without changing the formal value."""

    if isinstance(hue_degree, bool) or not isinstance(hue_degree, (int, float)):
        return QColor(148, 163, 184, alpha)
    hue = float(hue_degree)
    if not math.isfinite(hue):
        return QColor(148, 163, 184, alpha)
    color = QColor.fromHsvF((hue % 360.0) / 360.0, 0.78, 0.96, alpha / 255.0)
    return color


class SessionBpmHueChart(QWidget):
    """Render actual presented Hue while using life ID only for marker shape."""

    def __init__(self, parent: QWidget | None = None, *, maximum_sessions: int = 24) -> None:
        super().__init__(parent)
        self.setObjectName("stage8a1SessionBpmHueChart")
        self.setMinimumHeight(SESSION_BPM_HUE_CHART_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.PlotWidget(self)
        self.graphics.setBackground("#111827")
        self.plot = self.graphics.getPlotItem()
        self.plot.setTitle(
            "session × final committed BPM × actual Hue",
            color="#E5E7EB",
            size="12pt",
        )
        self.plot.setLabel("bottom", "session")
        self.plot.setLabel("left", "blink BPM")
        self.plot.showGrid(x=True, y=True, alpha=0.18)
        self.plot.setYRange(10.0, 165.0, padding=0.02)
        self.final_item = pg.ScatterPlotItem(name="final committed pattern")
        self.trial_item = pg.ScatterPlotItem(name="trial presentation")
        self.plot.addItem(self.final_item)
        self.plot.addItem(self.trial_item)
        self.final_item.sigHovered.connect(self._hovered)
        self.trial_item.sigHovered.connect(self._hovered)
        self.last_hover_text = ""
        self._final_spots: tuple[dict[str, Any], ...] = ()
        self._trial_spots: tuple[dict[str, Any], ...] = ()
        layout.addWidget(self.graphics)
        self.set_maximum_sessions(maximum_sessions)

    def set_maximum_sessions(self, maximum_sessions: int) -> None:
        if isinstance(maximum_sessions, bool) or not isinstance(maximum_sessions, int):
            raise TypeError("maximum_sessions must be an integer")
        if maximum_sessions < 1:
            raise ValueError("maximum_sessions must be positive")
        self._maximum_sessions = maximum_sessions
        self.plot.setXRange(-0.6, maximum_sessions - 0.4, padding=0.01)

    def set_records(self, pattern_records: Sequence[object]) -> None:
        finals: list[dict[str, Any]] = []
        trials: list[dict[str, Any]] = []
        for record in tuple(pattern_records):
            session_index = first_record_value(
                record,
                ("session_index", "evaluated_at_session_index"),
            )
            bpm = first_record_value(
                record,
                ("blink_bpm", "bpm", "holder_final_blink_bpm"),
            )
            hue = first_record_value(
                record,
                ("hue_degree", "hue", "holder_final_hue_degree"),
            )
            if (
                isinstance(session_index, bool)
                or not isinstance(session_index, int)
                or isinstance(bpm, bool)
                or not isinstance(bpm, (int, float))
                or isinstance(hue, bool)
                or not isinstance(hue, (int, float))
                or not math.isfinite(float(bpm))
                or not math.isfinite(float(hue))
            ):
                continue
            kind = str(first_record_value(record, ("point_kind", "pattern_kind"), "final"))
            is_trial = kind in {"trial", "bundle_trial", "candidate"}
            local_time_us = first_record_value(
                record,
                ("local_time_us", "presentation_time_us"),
            )
            x = float(session_index)
            if is_trial and isinstance(local_time_us, int) and not isinstance(local_time_us, bool):
                x += -0.4 + 0.8 * max(0, min(local_time_us, 240_000_000)) / 240_000_000
            life_id = str(first_record_value(record, ("digital_life_id", "holder_id"), "unknown"))
            outlier = bool(record_value(record, "outlier", False))
            member = bool(
                first_record_value(
                    record,
                    ("cluster_member", "structured_cluster_member"),
                    False,
                )
            )
            valid = bool(first_record_value(record, ("valid", "valid_for_convergence"), True))
            if not valid:
                pen = pg.mkPen("#94A3B8", width=2)
            elif outlier:
                pen = pg.mkPen("#F8FAFC", width=3)
            elif member:
                pen = pg.mkPen("#FBBF24", width=3)
            else:
                pen = pg.mkPen("#334155", width=1)
            payload = {
                "session_index": session_index,
                "digital_life_id": life_id,
                "hue_degree": float(hue),
                "blink_bpm": float(bpm),
                "e": first_record_value(record, ("e", "selected_e", "holder_e")),
                "exploration_decision": record_value(record, "exploration_decision"),
                "adoption_result": record_value(record, "adoption_result"),
                "point_kind": "trial" if is_trial else "final",
                "cluster_member": member,
                "outlier": outlier,
            }
            spot = {
                "pos": (x, float(bpm)),
                "symbol": LIFE_SYMBOLS.get(life_id, "d"),
                "size": 8 if is_trial else 17,
                "brush": pg.mkBrush(actual_hue_color(hue, alpha=105 if is_trial else 255)),
                "pen": pen,
                "data": payload,
            }
            (trials if is_trial else finals).append(spot)
        self._final_spots = tuple(finals)
        self._trial_spots = tuple(trials)
        self.final_item.setData(spots=finals)
        self.trial_item.setData(spots=trials)

    @property
    def final_point_count(self) -> int:
        return len(self._final_spots)

    @property
    def trial_point_count(self) -> int:
        return len(self._trial_spots)

    @property
    def final_symbols(self) -> tuple[str, ...]:
        return tuple(str(spot["symbol"]) for spot in self._final_spots)

    @property
    def final_hues(self) -> tuple[float, ...]:
        return tuple(float(spot["data"]["hue_degree"]) for spot in self._final_spots)

    @property
    def hover_payloads(self) -> tuple[dict[str, Any], ...]:
        return tuple(spot["data"] for spot in (*self._final_spots, *self._trial_spots))

    def clear(self) -> None:
        self.set_records(())
        self.last_hover_text = ""

    def _hovered(self, _item: object, points: object, event: object) -> None:
        selected = tuple(points) if points is not None else ()
        if not selected:
            return
        payload = selected[0].data()
        if not isinstance(payload, dict):
            return
        self.last_hover_text = (
            f"session {payload['session_index']}  |  {payload['digital_life_id']}  |  "
            f"Hue {payload['hue_degree']:.3f}°  |  BPM {payload['blink_bpm']:.3f}  |  "
            f"E {payload['e']}  |  explore {payload['exploration_decision']}  |  "
            f"adoption {payload['adoption_result']}"
        )
        screen_pos = getattr(event, "screenPos", lambda: None)()
        if screen_pos is not None:
            QToolTip.showText(
                QPoint(int(screen_pos.x()), int(screen_pos.y())),
                self.last_hover_text,
                self,
            )


__all__ = [
    "LIFE_SYMBOLS",
    "SESSION_BPM_HUE_CHART_MIN_HEIGHT",
    "SessionBpmHueChart",
    "actual_hue_color",
]
