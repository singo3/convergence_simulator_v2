"""Switchable condition heatmap backed by aggregate records only."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QToolTip, QVBoxLayout, QWidget

from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import first_record_value

CONDITION_HEATMAP_MIN_HEIGHT = 600
HEATMAP_METRICS = (
    ("correct_structure_rate", "correct structure rate"),
    ("life_dominant_convergence_rate", "life dominance rate"),
    ("bpm_common_convergence_rate", "BPM common rate"),
    ("multi_attractor_convergence_rate", "multi-attractor rate"),
    ("diffuse_rate", "diffuse rate"),
    ("median_first_convergence_session", "median convergence session"),
    ("post_convergence_outlier_rate", "post-convergence outlier rate"),
    ("return_within_1_rate", "return-within-1 rate"),
    ("holder_switch_rate", "holder switch rate"),
    ("mechanical_rotation_rate", "mechanical rotation rate"),
    ("accepted_candidate_count", "accepted candidate count"),
    ("w_ceiling_blocked_rate", "W ceiling blocked rate"),
)


class ConditionHeatmap(QWidget):
    """Map selected aggregate metrics without creating a combined best score."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stage8a1ConditionHeatmap")
        self.setMinimumHeight(CONDITION_HEATMAP_MIN_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.PlotWidget(self)
        self.graphics.setBackground("#111827")
        self.plot = self.graphics.getPlotItem()
        self.plot.setTitle("fatigue target × sigma multiplier", color="#E5E7EB")
        self.plot.setLabel("bottom", "selected session fatigue target")
        self.plot.setLabel("left", "sigma multiplier")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.cells = pg.ScatterPlotItem()
        self.reference_item = pg.ScatterPlotItem(
            symbol="star",
            size=20,
            brush=pg.mkBrush("#FBBF24"),
            pen=pg.mkPen("#FFFFFF", width=2),
        )
        self.reference_label = pg.TextItem(
            "v2.0 reference arm\n(no full recovery)",
            color="#FDE68A",
            anchor=(0.0, 0.5),
        )
        self.plot.addItem(self.cells)
        self.plot.addItem(self.reference_item)
        self.plot.addItem(self.reference_label)
        self.cells.sigHovered.connect(self._hovered)
        self._records: tuple[object, ...] = ()
        self._metric = HEATMAP_METRICS[0][0]
        self.last_hover_text = ""
        self.cell_count = 0
        layout.addWidget(self.graphics)
        self.clear()

    @property
    def metric(self) -> str:
        return self._metric

    def set_metric(self, metric: str) -> None:
        if metric not in {name for name, _caption in HEATMAP_METRICS}:
            raise ValueError("unknown heatmap metric")
        self._metric = metric
        self._render()

    def set_records(self, summaries: Sequence[object]) -> None:
        self._records = tuple(summaries)
        self._render()

    def clear(self) -> None:
        self._records = ()
        self._clear_rendered_items()

    def _clear_rendered_items(self) -> None:
        self.cells.setData(spots=[])
        self.reference_item.setData([], [])
        self.reference_label.setVisible(False)
        self.cell_count = 0

    def _render(self) -> None:
        values = []
        for record in self._records:
            fatigue = first_record_value(
                record,
                ("selected_session_fatigue_target", "fatigue_target"),
            )
            sigma = first_record_value(record, ("sigma_multiplier",))
            metric = first_record_value(record, (self._metric,))
            if any(isinstance(value, bool) for value in (fatigue, sigma, metric)):
                continue
            if not all(isinstance(value, (int, float)) for value in (fatigue, sigma, metric)):
                continue
            converted = (float(fatigue), float(sigma), float(metric))
            if not all(math.isfinite(value) for value in converted):
                continue
            values.append((*converted, record))
        if not values:
            # Keep the aggregate records so switching from a currently-null
            # metric to another metric can render the same completed grid.
            self._clear_rendered_items()
            return
        metric_values = [value[2] for value in values]
        lower = min(metric_values)
        upper = max(metric_values)
        color_map = pg.colormap.get("viridis")
        spots: list[dict[str, Any]] = []
        for fatigue, sigma, metric, record in values:
            normalized = 0.5 if upper == lower else (metric - lower) / (upper - lower)
            color = color_map.map(normalized, mode="qcolor")
            payload = {
                "condition_id": first_record_value(record, ("condition_id",)),
                "fatigue_target": fatigue,
                "sigma_multiplier": sigma,
                "metric": self._metric,
                "value": metric,
                "replicate_count": first_record_value(record, ("replicate_count",)),
                "completed_replicate_count": first_record_value(
                    record,
                    ("completed_replicate_count",),
                ),
                "failed_replicate_count": first_record_value(
                    record,
                    ("failed_replicate_count",),
                ),
                "selected_life_mean_e": first_record_value(
                    record,
                    ("selected_life_mean_e",),
                ),
                "effective_sigma_min": first_record_value(record, ("effective_sigma_min",)),
                "effective_sigma_max": first_record_value(record, ("effective_sigma_max",)),
            }
            spots.append(
                {
                    "pos": (fatigue, sigma),
                    "symbol": "s",
                    "size": 42,
                    "brush": pg.mkBrush(color),
                    "pen": pg.mkPen("#E2E8F0", width=1),
                    "data": payload,
                }
            )
        self.cells.setData(spots=spots)
        fatigue_values = [value[0] for value in values]
        sigma_values = [value[1] for value in values]
        x_span = max(max(fatigue_values) - min(fatigue_values), 0.04)
        reference_x = max(fatigue_values) + 0.18 * x_span
        reference_y = 1.0
        self.reference_item.setData([reference_x], [reference_y])
        self.reference_label.setPos(reference_x, reference_y)
        self.reference_label.setVisible(True)
        self.plot.setXRange(
            min(fatigue_values) - 0.12 * x_span,
            reference_x + 0.42 * x_span,
            padding=0.01,
        )
        y_span = max(max(sigma_values) - min(sigma_values), 0.5)
        self.plot.setYRange(
            min(min(sigma_values), reference_y) - 0.12 * y_span,
            max(max(sigma_values), reference_y) + 0.12 * y_span,
            padding=0.01,
        )
        self.cell_count = len(spots)

    def _hovered(self, _item: object, points: object, event: object) -> None:
        selected = tuple(points) if points is not None else ()
        if not selected:
            return
        payload = selected[0].data()
        if not isinstance(payload, dict):
            return
        self.last_hover_text = (
            f"{payload['condition_id']}  |  fatigue {payload['fatigue_target']:.3f}  |  "
            f"sigma ×{payload['sigma_multiplier']:.3f}  |  "
            f"{payload['metric']}={payload['value']:.6g}  |  "
            f"replicates {payload['completed_replicate_count']}/{payload['replicate_count']}  |  "
            f"failures {payload['failed_replicate_count']}  |  "
            f"selected E {payload['selected_life_mean_e']}  |  "
            f"sigma range {payload['effective_sigma_min']}..{payload['effective_sigma_max']}"
        )
        screen_pos = getattr(event, "screenPos", lambda: None)()
        if screen_pos is not None:
            QToolTip.showText(
                QPoint(int(screen_pos.x()), int(screen_pos.y())),
                self.last_hover_text,
                self,
            )


__all__ = [
    "CONDITION_HEATMAP_MIN_HEIGHT",
    "HEATMAP_METRICS",
    "ConditionHeatmap",
]
