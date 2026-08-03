"""Record-backed Stage 5C charts; relation decisions never run in the GUI."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

RELATION_MEMORY_PLOT_MIN_HEIGHT = 700
RELATION_MEMORY_CHART_MIN_HEIGHT = 2_120

LIFE_COLORS = {
    "life-red": "#FB7185",
    "life-green": "#34D399",
    "life-blue": "#60A5FA",
}
LIFE_ROLES = {
    "life-red": "red",
    "life-green": "green",
    "life-blue": "blue",
}


class RelationMemoryChart(QWidget):
    """Render F/T, W and bundle chronology from immutable component records."""

    def __init__(self, parent=None, *, duration_seconds: float = 240.0) -> None:
        super().__init__(parent)
        self.setObjectName("relationMemoryChart")
        self.setMinimumHeight(RELATION_MEMORY_CHART_MIN_HEIGHT)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.graphics = pg.GraphicsLayoutWidget(self)
        self.graphics.setObjectName("relationMemoryGraphics")
        self.graphics.setBackground("#111827")
        root.addWidget(self.graphics)

        self._build_ft_plot()
        self._build_w_plot()
        self._build_timeline_plot()
        self.set_duration_seconds(duration_seconds)
        self.clear()

    @property
    def plots(self) -> tuple[pg.PlotItem, ...]:
        return self.ft_plot, self.w_plot, self.timeline_plot

    def _build_ft_plot(self) -> None:
        self.ft_plot = self.graphics.addPlot(row=0, col=0)
        self.k_ft_plot = self.ft_plot
        self.ft_plot.setObjectName("relationMemoryFTPlot")
        _configure_plot(
            self.ft_plot,
            "連続kのF/T空間 — anchor / trial / current軌跡 / reflect01境界",
            "k_T",
            "k_F",
        )
        self.ft_plot.setAspectLocked(True, ratio=1.0)
        self.ft_plot.setXRange(-0.05, 1.05, padding=0)
        self.ft_plot.setYRange(-0.05, 1.05, padding=0)
        self.ft_plot.addLegend(offset=(8, 8), colCount=3)
        self.reflect_boundary_item = self.ft_plot.plot(
            [0.0, 1.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 1.0, 0.0],
            pen=pg.mkPen("#E5E7EB", width=2),
            name="reflect01 boundary",
        )
        self.anchor_items: dict[str, pg.PlotDataItem] = {}
        self.trial_items: dict[str, pg.PlotDataItem] = {}
        self.current_items: dict[str, pg.PlotDataItem] = {}
        self.initial_anchor_items: dict[str, pg.PlotDataItem] = {}
        self.final_anchor_items: dict[str, pg.PlotDataItem] = {}
        self.direction_items: dict[str, pg.PlotDataItem] = {}
        for life_id, color in LIFE_COLORS.items():
            role = LIFE_ROLES[life_id]
            self.current_items[life_id] = self.ft_plot.plot(
                pen=pg.mkPen(color, width=2),
                symbol="o",
                symbolSize=4,
                symbolBrush=color,
                name=f"{role} current trajectory",
            )
            self.anchor_items[life_id] = self.ft_plot.plot(
                pen=None,
                symbol="d",
                symbolSize=10,
                symbolBrush=color,
                name=f"{role} anchor",
            )
            self.trial_items[life_id] = self.ft_plot.plot(
                pen=None,
                symbol="t",
                symbolSize=11,
                symbolBrush=color,
                name=f"{role} trial",
            )
            self.initial_anchor_items[life_id] = self.ft_plot.plot(
                pen=None,
                symbol="star",
                symbolSize=15,
                symbolBrush=color,
                symbolPen=pg.mkPen("#FFFFFF", width=1),
                name=f"{role} initial anchor",
            )
            self.final_anchor_items[life_id] = self.ft_plot.plot(
                pen=None,
                symbol="+",
                symbolSize=17,
                symbolPen=pg.mkPen(color, width=3),
                name=f"{role} final anchor",
            )
            self.direction_items[life_id] = self.ft_plot.plot(
                pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine),
                connect="finite",
                name=f"{role} candidate vector",
            )
        self.optimum_item = self.ft_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=18,
            symbolPen=pg.mkPen("#FBBF24", width=3),
            name="diagnostic user optimum (non-input)",
        )

    def _build_w_plot(self) -> None:
        self.w_plot = self.graphics.addPlot(row=1, col=0)
        self.w_comparison_plot = self.w_plot
        self.w_plot.setObjectName("relationMemoryWComparisonPlot")
        _configure_plot(
            self.w_plot,
            "W比較 — anchor / trial 1 / trial 2 / 採用閾値",
            "W",
            "bundle",
        )
        self.w_plot.setYRange(-0.05, 1.05, padding=0)
        self.w_plot.setXRange(-0.4, 2.4, padding=0)
        self.w_plot.getAxis("bottom").setTicks(
            [[(0.0, "Bundle 0"), (1.0, "Bundle 1"), (2.0, "Bundle 2")]]
        )
        self.w_plot.addLegend(offset=(8, 8), colCount=3)
        self.baseline_w_line = pg.InfiniteLine(
            pos=0.5,
            angle=0,
            movable=False,
            pen=pg.mkPen("#E5E7EB", width=2, style=Qt.PenStyle.DotLine),
            label="baseline W=0.5",
            labelOpts={"color": "#E5E7EB"},
        )
        self.w_plot.addItem(self.baseline_w_line)
        self.w_observed_items: dict[str, pg.PlotDataItem] = {}
        self.w_anchor_items: dict[str, pg.PlotDataItem] = {}
        self.w_trial_1_items: dict[str, pg.PlotDataItem] = {}
        self.w_trial_2_items: dict[str, pg.PlotDataItem] = {}
        self.w_mean_items: dict[str, pg.PlotDataItem] = {}
        self.provisional_threshold_items: dict[str, pg.PlotDataItem] = {}
        self.confirmation_threshold_items: dict[str, pg.PlotDataItem] = {}
        for life_id, color in LIFE_COLORS.items():
            role = LIFE_ROLES[life_id]
            self.w_observed_items[life_id] = self.w_plot.plot(
                pen=pg.mkPen(color, width=2),
                symbol="o",
                symbolSize=7,
                symbolBrush=color,
                name=f"{role} evaluated W",
            )
            self.w_anchor_items[life_id] = self.w_plot.plot(
                pen=None,
                symbol="d",
                symbolSize=10,
                symbolBrush=color,
                name=f"{role} W anchor",
            )
            self.w_trial_1_items[life_id] = self.w_plot.plot(
                pen=None,
                symbol="t",
                symbolSize=11,
                symbolBrush=color,
                name=f"{role} W trial 1",
            )
            self.w_trial_2_items[life_id] = self.w_plot.plot(
                pen=None,
                symbol="t1",
                symbolSize=11,
                symbolBrush=color,
                name=f"{role} W trial 2",
            )
            self.w_mean_items[life_id] = self.w_plot.plot(
                pen=None,
                symbol="s",
                symbolSize=9,
                symbolBrush="#FBBF24",
                name=f"{role} stored trial mean",
            )
            self.provisional_threshold_items[life_id] = self.w_plot.plot(
                pen=None,
                symbol="+",
                symbolSize=14,
                symbolPen=pg.mkPen(color, width=2),
                name=f"{role} W anchor + epsilon",
            )
            self.confirmation_threshold_items[life_id] = self.w_plot.plot(
                pen=None,
                symbol="x",
                symbolSize=12,
                symbolPen=pg.mkPen(color, width=2),
                name=f"{role} confirmation > anchor",
            )

    def _build_timeline_plot(self) -> None:
        self.timeline_plot = self.graphics.addPlot(row=2, col=0)
        self.bundle_timeline_plot = self.timeline_plot
        self.timeline_plot.setObjectName("relationMemoryBundleTimelinePlot")
        _configure_plot(
            self.timeline_plot,
            "3Bundle timeline — 提示位置・next-signal有効化・adoption / rollback",
            "stage lane",
            "仮想時間",
            bottom_units="秒",
        )
        self.timeline_plot.setYRange(-0.5, 6.5, padding=0)
        self.timeline_plot.getAxis("left").setTicks(
            [[
                (0.0, "baseline / outside"),
                (1.0, "Bundle 0 anchor"),
                (2.0, "Bundle 1 anchor / trial"),
                (3.0, "Bundle 2 anchor / trial"),
                (4.0, "k effective"),
                (5.0, "qualified B / Hue-BPM"),
                (6.0, "adoption / rollback"),
            ]]
        )
        self.timeline_plot.addLegend(offset=(8, 8), colCount=3)
        self.bundle_items: dict[str, pg.PlotDataItem] = {}
        self.effective_items: dict[str, pg.PlotDataItem] = {}
        self.qualified_b_items: dict[str, pg.PlotDataItem] = {}
        self.hue_bpm_items: dict[str, pg.PlotDataItem] = {}
        self.adoption_items: dict[str, pg.PlotDataItem] = {}
        self.rollback_items: dict[str, pg.PlotDataItem] = {}
        for life_id, color in LIFE_COLORS.items():
            role = LIFE_ROLES[life_id]
            self.bundle_items[life_id] = self.timeline_plot.plot(
                pen=pg.mkPen(color, width=2),
                symbol="o",
                symbolSize=4,
                symbolBrush=color,
                name=f"{role} presented bundle",
            )
            self.effective_items[life_id] = self.timeline_plot.plot(
                pen=None,
                symbol="star",
                symbolSize=14,
                symbolBrush=color,
                name=f"{role} k effective next signal",
            )
            self.qualified_b_items[life_id] = self.timeline_plot.plot(
                pen=None,
                symbol="s",
                symbolSize=10,
                symbolBrush=color,
                name=f"{role} qualified B change",
            )
            self.hue_bpm_items[life_id] = self.timeline_plot.plot(
                pen=None,
                symbol="t",
                symbolSize=10,
                symbolBrush=color,
                name=f"{role} Hue/BPM change",
            )
            self.adoption_items[life_id] = self.timeline_plot.plot(
                pen=None,
                symbol="+",
                symbolSize=15,
                symbolPen=pg.mkPen("#34D399", width=3),
                name=f"{role} adoption",
            )
            self.rollback_items[life_id] = self.timeline_plot.plot(
                pen=None,
                symbol="x",
                symbolSize=14,
                symbolPen=pg.mkPen("#FB7185", width=3),
                name=f"{role} rollback / reject",
            )
        self.timeline_current_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen("#FFFFFF", width=1),
        )
        self.timeline_plot.addItem(self.timeline_current_line)

    def set_duration_seconds(self, duration_seconds: float) -> None:
        self._duration_seconds = float(duration_seconds)
        self.timeline_plot.setXRange(0.0, self._duration_seconds, padding=0.01)

    def set_records(
        self,
        transitions_by_id: Mapping[str, Sequence[Any]],
        signals_by_id: Mapping[str, Sequence[Any]],
        initial_states_by_id: Mapping[str, Any],
        final_states_by_id: Mapping[str, Any | None],
        current_time_us: int,
        *,
        diagnostic_optimum_ft: tuple[float, float] | None = None,
        qualified_b_records: Sequence[Any] = (),
        light_command_records: Sequence[Any] = (),
    ) -> None:
        """Copy record/state values only; no explore, candidate or adoption logic."""

        qualified_change_times = _formal_change_times_by_life(
            qualified_b_records,
            time_field="effective_time_us",
            signature_fields=("active", "qualification_holder_id", "b"),
        )
        command_change_times = _formal_change_times_by_life(
            light_command_records,
            time_field="command_effective_time_us",
            signature_fields=(
                "active",
                "qualification_holder_id",
                "hue_degree",
                "blink_bpm",
                "saturation",
                "value_center",
                "value_amplitude",
                "waveform",
            ),
        )
        for life_id in LIFE_COLORS:
            transitions = tuple(transitions_by_id.get(life_id, ()))
            signals = tuple(signals_by_id.get(life_id, ()))
            initial = initial_states_by_id.get(life_id)
            final = final_states_by_id.get(life_id)
            self._set_ft_records(life_id, transitions, signals, initial, final)
            self._set_w_records(life_id, transitions)
            self._set_timeline_records(
                life_id,
                transitions,
                signals,
                formal_qualified_b_times=qualified_change_times.get(life_id, ()),
                formal_hue_bpm_times=command_change_times.get(life_id, ()),
            )
        if diagnostic_optimum_ft is None:
            self.optimum_item.setData([], [])
            self.optimum_visible = False
        else:
            self.optimum_item.setData(
                [diagnostic_optimum_ft[0]],
                [diagnostic_optimum_ft[1]],
            )
            self.optimum_visible = True
        self.set_current_time_us(current_time_us)
        self.transition_count = sum(len(records) for records in transitions_by_id.values())
        self.signal_count = sum(len(records) for records in signals_by_id.values())
        self.qualified_b_change_count = sum(
            len(values) for values in qualified_change_times.values()
        )
        self.hue_bpm_change_count = sum(
            len(values) for values in command_change_times.values()
        )

    def _set_ft_records(
        self,
        life_id: str,
        transitions: tuple[Any, ...],
        signals: tuple[Any, ...],
        initial: Any | None,
        final: Any | None,
    ) -> None:
        initial_k = _vector_field(initial, "k_anchor")
        final_k = _vector_field(final, "k_anchor")
        if final_k is None and transitions:
            final_k = _last_vector(transitions, "k_anchor_after")

        anchors: list[tuple[float, ...]] = []
        if initial_k is not None:
            anchors.append(initial_k)
        for record in transitions:
            for field in ("k_anchor_before", "k_anchor_after"):
                value = _vector_field(record, field)
                if value is not None:
                    anchors.append(value)
        if final_k is not None:
            anchors.append(final_k)
        anchors = _unique_vectors(anchors)

        trials = _unique_vectors(
            value
            for record in transitions
            if (value := _vector_field(record, "k_trial")) is not None
        )
        current = [
            value
            for record in signals
            if (value := _vector_field(record, "k_presented")) is not None
        ]
        if not current:
            for record in transitions:
                before = _vector_field(record, "k_current_before")
                after = _vector_field(record, "k_current_after")
                if before is not None:
                    current.append(before)
                if after is not None:
                    current.append(after)
        current = _consecutive_unique_vectors(current)

        self.anchor_items[life_id].setData(*_ft_xy(anchors))
        self.trial_items[life_id].setData(*_ft_xy(trials))
        self.current_items[life_id].setData(*_ft_xy(current))
        self.initial_anchor_items[life_id].setData(*_ft_xy([initial_k] if initial_k else []))
        self.final_anchor_items[life_id].setData(*_ft_xy([final_k] if final_k else []))

        vector_x: list[float] = []
        vector_y: list[float] = []
        seen_vectors: set[tuple[tuple[float, ...], tuple[float, ...]]] = set()
        for record in transitions:
            anchor = _vector_field(record, "k_anchor_before")
            trial = _vector_field(record, "k_trial")
            if anchor is None or trial is None or (anchor, trial) in seen_vectors:
                continue
            seen_vectors.add((anchor, trial))
            vector_x.extend((anchor[0], trial[0], math.nan))
            vector_y.extend((anchor[2], trial[2], math.nan))
        self.direction_items[life_id].setData(vector_x, vector_y, connect="finite")

    def _set_w_records(self, life_id: str, transitions: tuple[Any, ...]) -> None:
        observed_x: list[float] = []
        observed_y: list[float] = []
        for record in transitions:
            bundle = getattr(record, "bundle_index", None)
            value = _number_field(record, "w")
            if bundle is not None and value is not None:
                observed_x.append(float(bundle))
                observed_y.append(value)
        self.w_observed_items[life_id].setData(observed_x, observed_y)

        anchor = _last_number(transitions, "w_anchor_session_after")
        trial_1 = _last_number(transitions, "w_trial_1_after")
        trial_2 = _last_number(transitions, "w_trial_2_after")
        trial_mean = _last_number(transitions, "candidate_mean_w")
        epsilon = _last_number(transitions, "epsilon_accept")
        self.w_anchor_items[life_id].setData(*_point(0.0, anchor))
        self.w_trial_1_items[life_id].setData(*_point(1.0, trial_1))
        self.w_trial_2_items[life_id].setData(*_point(2.0, trial_2))
        self.w_mean_items[life_id].setData(*_point(2.12, trial_mean))
        # This is a presentation transform of two stored values, not a decision.
        provisional = None if anchor is None or epsilon is None else anchor + epsilon
        self.provisional_threshold_items[life_id].setData(*_point(1.0, provisional))
        self.confirmation_threshold_items[life_id].setData(*_point(2.0, anchor))

    def _set_timeline_records(
        self,
        life_id: str,
        transitions: tuple[Any, ...],
        signals: tuple[Any, ...],
        *,
        formal_qualified_b_times: Sequence[float],
        formal_hue_bpm_times: Sequence[float],
    ) -> None:
        times = [us_to_seconds(record.signal_time_us) for record in signals]
        lanes = [_signal_lane(record) for record in signals]
        self.bundle_items[life_id].setData(times, lanes, stepMode="left")

        signal_time_by_index = {
            record.signal_index: record.signal_time_us for record in signals
        }
        effective_times = _unique_numbers(
            us_to_seconds(signal_time_by_index[index])
            for record in transitions
            if (index := getattr(record, "candidate_effective_signal_index", None))
            in signal_time_by_index
        )
        self.effective_items[life_id].setData(effective_times, [4.0] * len(effective_times))

        qualified_times = list(formal_qualified_b_times) or _optional_marker_times(
            signals,
            ("qualified_b_effective_time_us", "qualified_b_change_time_us"),
        )
        hue_bpm_times = list(formal_hue_bpm_times) or _optional_marker_times(
            signals,
            ("hue_bpm_change_time_us", "light_command_effective_time_us"),
        )
        self.qualified_b_items[life_id].setData(
            qualified_times,
            [5.0] * len(qualified_times),
        )
        self.hue_bpm_items[life_id].setData(
            hue_bpm_times,
            [5.35] * len(hue_bpm_times),
        )

        accepted = [
            us_to_seconds(record.signal_time_us)
            for record in transitions
            if getattr(record, "adoption_result", None) == "accepted"
        ]
        rollback = [
            us_to_seconds(record.signal_time_us)
            for record in transitions
            if getattr(record, "rollback_reason", None) is not None
            or str(getattr(record, "adoption_result", "")).startswith("rejected")
            or str(getattr(record, "adoption_result", "")).startswith("rolled_back")
        ]
        self.adoption_items[life_id].setData(accepted, [6.0] * len(accepted))
        self.rollback_items[life_id].setData(rollback, [6.0] * len(rollback))

    def set_current_time_us(self, current_time_us: int) -> None:
        self.timeline_current_line.setValue(us_to_seconds(current_time_us))

    def clear(self) -> None:
        for item_group in (
            self.anchor_items,
            self.trial_items,
            self.current_items,
            self.initial_anchor_items,
            self.final_anchor_items,
            self.direction_items,
            self.w_observed_items,
            self.w_anchor_items,
            self.w_trial_1_items,
            self.w_trial_2_items,
            self.w_mean_items,
            self.provisional_threshold_items,
            self.confirmation_threshold_items,
            self.bundle_items,
            self.effective_items,
            self.qualified_b_items,
            self.hue_bpm_items,
            self.adoption_items,
            self.rollback_items,
        ):
            for item in item_group.values():
                item.setData([], [])
        self.optimum_item.setData([], [])
        self.optimum_visible = False
        self.set_current_time_us(0)
        self.transition_count = 0
        self.signal_count = 0
        self.qualified_b_change_count = 0
        self.hue_bpm_change_count = 0


def _configure_plot(
    plot: pg.PlotItem,
    title: str,
    left: str,
    bottom: str,
    *,
    bottom_units: str | None = None,
) -> None:
    plot.setTitle(title, color="#E5E7EB", size="11pt")
    plot.setLabel("left", left)
    plot.setLabel("bottom", bottom, units=bottom_units)
    plot.showGrid(x=True, y=True, alpha=0.16)
    plot.setMinimumHeight(RELATION_MEMORY_PLOT_MIN_HEIGHT)
    plot.setPreferredHeight(RELATION_MEMORY_PLOT_MIN_HEIGHT)


def _vector_field(record: Any | None, field: str) -> tuple[float, ...] | None:
    if record is None:
        return None
    value = getattr(record, field, None)
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    return tuple(float(item) for item in value)


def _number_field(record: Any, field: str) -> float | None:
    value = getattr(record, field, None)
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _last_number(records: Sequence[Any], field: str) -> float | None:
    for record in reversed(records):
        if (value := _number_field(record, field)) is not None:
            return value
    return None


def _last_vector(records: Sequence[Any], field: str) -> tuple[float, ...] | None:
    for record in reversed(records):
        if (value := _vector_field(record, field)) is not None:
            return value
    return None


def _unique_vectors(values: Sequence[tuple[float, ...]] | Any) -> list[tuple[float, ...]]:
    result: list[tuple[float, ...]] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _consecutive_unique_vectors(values: Sequence[tuple[float, ...]]) -> list[tuple[float, ...]]:
    result: list[tuple[float, ...]] = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


def _ft_xy(values: Sequence[tuple[float, ...]]) -> tuple[list[float], list[float]]:
    return [value[0] for value in values], [value[2] for value in values]


def _point(x: float, value: float | None) -> tuple[list[float], list[float]]:
    return ([], []) if value is None else ([x], [value])


def _signal_lane(record: Any) -> float:
    bundle = getattr(record, "bundle_index", None)
    if bundle in (0, 1, 2):
        base = float(bundle + 1)
        relation_phase = str(getattr(record, "relation_phase_before", ""))
        if bundle in (1, 2) and relation_phase in {
            "trial",
            "confirmation",
            "trial_unconfirmed",
        }:
            return base + 0.12
        return base - 0.12 if bundle in (1, 2) else base
    return 0.0


def _unique_numbers(values: Any) -> list[float]:
    result: list[float] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _optional_marker_times(
    records: Sequence[Any],
    fields: tuple[str, ...],
) -> list[float]:
    values: list[float] = []
    for record in records:
        for field in fields:
            value = getattr(record, field, None)
            if isinstance(value, int) and not isinstance(value, bool):
                values.append(us_to_seconds(value))
                break
    return _unique_numbers(values)


def _formal_change_times_by_life(
    records: Sequence[Any],
    *,
    time_field: str,
    signature_fields: tuple[str, ...],
) -> dict[str, tuple[float, ...]]:
    """Project actual formal-output changes without deriving relation decisions."""

    result: dict[str, list[float]] = {}
    previous_signature: tuple[Any, ...] | None = None
    for record in records:
        signature = tuple(getattr(record, field, None) for field in signature_fields)
        changed = previous_signature is not None and signature != previous_signature
        previous_signature = signature
        if not changed or not bool(getattr(record, "active", False)):
            continue
        life_id = getattr(record, "qualification_holder_id", None)
        time_us = getattr(record, time_field, None)
        if (
            life_id not in LIFE_COLORS
            or isinstance(time_us, bool)
            or not isinstance(time_us, int)
        ):
            continue
        result.setdefault(life_id, []).append(us_to_seconds(time_us))
    return {
        life_id: tuple(_unique_numbers(values))
        for life_id, values in result.items()
    }


__all__ = [
    "LIFE_COLORS",
    "RELATION_MEMORY_CHART_MIN_HEIGHT",
    "RELATION_MEMORY_PLOT_MIN_HEIGHT",
    "RelationMemoryChart",
]
