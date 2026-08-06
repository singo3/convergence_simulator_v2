"""Factorial chart composition over the Stage 8A.3 SVG vocabulary."""

from __future__ import annotations

import html
import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.charts import (
    overall_delta_svg,
    participant_trajectory_svg,
    user_type_average_svg,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
)

from .conditions import (
    CONDITION_IDS,
    FULL_RECOVERY_SIGMA100_CONDITION,
    PROVISIONAL_CONDITION,
    V2_RECOVERY_SIGMA050_CONDITION,
    V2_REFERENCE_CONDITION,
)
from .config import FACTORIAL_ARMS

CONDITION_LABELS = {
    V2_REFERENCE_CONDITION: "A · gradual × σ1.0",
    V2_RECOVERY_SIGMA050_CONDITION: "B · gradual × σ0.5",
    FULL_RECOVERY_SIGMA100_CONDITION: "C · full × σ1.0",
    PROVISIONAL_CONDITION: "D · full × σ0.5",
}


def participant_factorial_grid(
    participant_id: str,
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
) -> str:
    panels = "".join(
        "<section class='factorial-condition-panel' "
        f"data-condition='{html.escape(condition_id)}'>"
        f"<h4>{html.escape(CONDITION_LABELS[condition_id])}</h4>"
        + participant_trajectory_svg(
            participant_id,
            condition_id,
            bundles,
            sessions,
            arms=FACTORIAL_ARMS,
        )
        + "</section>"
        for condition_id in CONDITION_IDS
    )
    return (
        "<div class='factorial-participant-grid' data-layout='4-conditions-by-2-arms' "
        "data-x-axis='session index' data-y-axis='blink BPM' "
        "data-fill='actual Hue' data-marker='life ID'>"
        f"{panels}</div>"
    )


def user_type_factorial_grid(
    trajectory_rows: Sequence[Mapping[str, Any]],
    *,
    user_type_id: str | None = None,
) -> str:
    selected = [
        row
        for row in trajectory_rows
        if user_type_id is None or row.get("user_type_id") == user_type_id
    ]
    panels = "".join(
        "<section class='factorial-condition-panel'>"
        f"<h4>{html.escape(CONDITION_LABELS[condition_id])}</h4>"
        + user_type_average_svg(
            selected,
            condition_id,
            arms=FACTORIAL_ARMS,
        )
        + "</section>"
        for condition_id in CONDITION_IDS
    )
    return f"<div class='factorial-user-type-grid'>{panels}</div>"


def overall_condition_grid(sessions: Sequence[SessionOutcome]) -> str:
    return (
        "<div class='factorial-overall-grid'>"
        + "".join(
            "<section class='factorial-condition-panel'>"
            f"<h4>{html.escape(CONDITION_LABELS[condition_id])}</h4>"
            + overall_delta_svg(sessions, condition_id, arms=FACTORIAL_ARMS)
            + "</section>"
            for condition_id in CONDITION_IDS
        )
        + "</div>"
    )


def factor_plot_svg(
    condition_summaries: Sequence[Mapping[str, Any]],
    *,
    metric: str = "nonflat_mean_effect_ms",
) -> str:
    allowed = {
        "nonflat_mean_effect_ms": "late ΔRMSSD advantage (ms)",
        "nonflat_positive_rate": "positive participant rate",
        "worst_user_type_effect_ms": "worst-type effect (ms)",
        "selection_enrichment_advantage": "selection enrichment",
        "holder_switch_rate": "holder switch rate",
    }
    if metric not in allowed:
        raise ValueError(f"unsupported factor-plot metric: {metric}")
    values_by_id = {str(row["condition_id"]): row.get(metric) for row in condition_summaries}
    points = {
        "gradual": (
            values_by_id.get(V2_REFERENCE_CONDITION),
            values_by_id.get(V2_RECOVERY_SIGMA050_CONDITION),
        ),
        "full recovery": (
            values_by_id.get(FULL_RECOVERY_SIGMA100_CONDITION),
            values_by_id.get(PROVISIONAL_CONDITION),
        ),
    }
    finite = [float(value) for pair in points.values() for value in pair if value is not None]
    y_min, y_max = min(finite, default=-1.0), max(finite, default=1.0)
    if math.isclose(y_min, y_max):
        y_min -= 0.5
        y_max += 0.5
    margin = max(0.05, (y_max - y_min) * 0.12)
    y_min -= margin
    y_max += margin
    width, height, left, top = 560.0, 300.0, 70.0, 32.0
    plot_width, plot_height = 450.0, 210.0

    def y(value: float) -> float:
        return top + plot_height - (value - y_min) / (y_max - y_min) * plot_height

    parts = [
        f"<svg class='factor-plot' data-metric='{html.escape(metric)}' "
        f"viewBox='0 0 {width:.0f} {height:.0f}' role='img' "
        "aria-label='two by two fatigue recovery sigma factor plot'>",
        f"<text x='{left}' y='16' font-weight='700'>{html.escape(allowed[metric])}</text>",
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + plot_height}' stroke='#52616e'/>",
        f"<line x1='{left}' y1='{top + plot_height}' "
        f"x2='{left + plot_width}' y2='{top + plot_height}' "
        "stroke='#52616e'/>",
    ]
    x_values = (left + plot_width * 0.25, left + plot_width * 0.75)
    colors = {"gradual": "#376f9f", "full recovery": "#ba5c45"}
    for label, pair in points.items():
        valid = [
            (x, float(value)) for x, value in zip(x_values, pair, strict=True) if value is not None
        ]
        if len(valid) == 2:
            parts.append(
                f"<line x1='{valid[0][0]:.2f}' y1='{y(valid[0][1]):.2f}' "
                f"x2='{valid[1][0]:.2f}' y2='{y(valid[1][1]):.2f}' "
                f"stroke='{colors[label]}' stroke-width='3'/>"
            )
        for x_value, value in valid:
            parts.append(
                f"<circle cx='{x_value:.2f}' cy='{y(value):.2f}' r='5' "
                f"fill='{colors[label]}'><title>{html.escape(label)}: {value}</title></circle>"
            )
    parts.extend(
        (
            f"<text x='{x_values[0]:.2f}' y='{height - 30}' text-anchor='middle'>σ 1.0</text>",
            f"<text x='{x_values[1]:.2f}' y='{height - 30}' text-anchor='middle'>σ 0.5</text>",
            f"<text x='{left}' y='{height - 8}' fill='{colors['gradual']}'>gradual recovery</text>",
            f"<text x='{left + 190}' y='{height - 8}' "
            f"fill='{colors['full recovery']}'>full recovery</text>",
            "</svg>",
        )
    )
    return "".join(parts)


def user_type_heatmap_svg(
    participant_rows: Sequence[Mapping[str, Any]],
    *,
    metric: str = "late_delta_rmssd_advantage_ms",
) -> str:
    allowed = {
        "late_delta_rmssd_advantage_ms",
        "positive_participant_rate",
        "full_pattern_selection_enrichment_advantage",
        "lagged_pattern_advantage",
    }
    if metric not in allowed:
        raise ValueError(f"unsupported heatmap metric: {metric}")
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in participant_rows:
        if metric == "positive_participant_rate":
            value = row.get("late_delta_rmssd_advantage_ms")
            if value is not None:
                grouped[(str(row["user_type_id"]), str(row["condition_id"]))].append(
                    float(float(value) > 0.0)
                )
        elif row.get(metric) is not None:
            grouped[(str(row["user_type_id"]), str(row["condition_id"]))].append(float(row[metric]))
    user_types = sorted({key[0] for key in grouped})
    means = {key: statistics.fmean(values) for key, values in grouped.items() if values}
    finite = list(means.values())
    scale = max((abs(value) for value in finite), default=1.0) or 1.0
    left, top, cell_w, cell_h = 250.0, 52.0, 150.0, 34.0
    width = left + cell_w * 4 + 20
    height = top + cell_h * len(user_types) + 30
    parts = [
        f"<svg class='user-type-heatmap' data-metric='{html.escape(metric)}' "
        f"viewBox='0 0 {width:.0f} {height:.0f}' role='img' "
        "aria-label='user type by condition heatmap'>",
        f"<text x='4' y='17' font-weight='700'>{html.escape(metric)}</text>",
    ]
    for column, condition_id in enumerate(CONDITION_IDS):
        parts.append(
            f"<text x='{left + (column + 0.5) * cell_w:.2f}' y='40' "
            f"text-anchor='middle'>{html.escape(condition_id)}</text>"
        )
    for row_index, user_type_id in enumerate(user_types):
        y = top + row_index * cell_h
        parts.append(
            f"<text x='{left - 8}' y='{y + 22:.2f}' text-anchor='end'>"
            f"{html.escape(user_type_id)}</text>"
        )
        for column, condition_id in enumerate(CONDITION_IDS):
            value = means.get((user_type_id, condition_id))
            ratio = 0.0 if value is None else min(1.0, abs(value) / scale)
            if value is None:
                fill = "#e8ecef"
            elif value >= 0:
                fill = f"rgba(38,151,102,{0.16 + 0.74 * ratio:.3f})"
            else:
                fill = f"rgba(190,71,71,{0.16 + 0.74 * ratio:.3f})"
            x = left + column * cell_w
            label = "NA" if value is None else f"{value:.3f}"
            parts.append(
                f"<rect x='{x:.2f}' y='{y:.2f}' width='{cell_w - 2:.2f}' "
                f"height='{cell_h - 2:.2f}' fill='{fill}'/>"
                f"<text x='{x + cell_w / 2:.2f}' y='{y + 22:.2f}' "
                f"text-anchor='middle'>{label}</text>"
            )
    parts.append("</svg>")
    return "".join(parts)


def participant_paired_lines_svg(
    participant_rows: Sequence[Mapping[str, Any]],
    *,
    metric: str = "late_delta_rmssd_advantage_ms",
) -> str:
    by_participant: dict[str, dict[str, float]] = defaultdict(dict)
    for row in participant_rows:
        value = row.get(metric)
        if value is not None:
            by_participant[str(row["participant_id"])][str(row["condition_id"])] = float(value)
    pairs = (
        (V2_REFERENCE_CONDITION, V2_RECOVERY_SIGMA050_CONDITION, "A→B"),
        (FULL_RECOVERY_SIGMA100_CONDITION, PROVISIONAL_CONDITION, "C→D"),
        (V2_REFERENCE_CONDITION, FULL_RECOVERY_SIGMA100_CONDITION, "A→C"),
        (V2_RECOVERY_SIGMA050_CONDITION, PROVISIONAL_CONDITION, "B→D"),
    )
    all_values = [value for mapping in by_participant.values() for value in mapping.values()]
    y_min, y_max = min(all_values, default=-1.0), max(all_values, default=1.0)
    if math.isclose(y_min, y_max):
        y_min -= 0.5
        y_max += 0.5
    width, height, top, plot_h = 760.0, 300.0, 30.0, 220.0

    def y(value: float) -> float:
        return top + plot_h - (value - y_min) / (y_max - y_min) * plot_h

    parts = [
        f"<svg class='participant-paired-lines' data-metric='{html.escape(metric)}' "
        f"viewBox='0 0 {width:.0f} {height:.0f}' role='img' "
        "aria-label='participant paired condition changes'>"
    ]
    for pair_index, (first, second, label) in enumerate(pairs):
        x1 = 55.0 + pair_index * 180.0
        x2 = x1 + 75.0
        parts.append(
            f"<text x='{(x1 + x2) / 2:.2f}' y='{height - 12}' text-anchor='middle'>{label}</text>"
        )
        for participant_id, values in sorted(by_participant.items()):
            if first not in values or second not in values:
                continue
            parts.append(
                f"<line x1='{x1:.2f}' y1='{y(values[first]):.2f}' "
                f"x2='{x2:.2f}' y2='{y(values[second]):.2f}' "
                "stroke='#586b7a' stroke-opacity='.28'>"
                f"<title>{html.escape(participant_id)} {label}: "
                f"{values[first]:.4f} → {values[second]:.4f}</title></line>"
            )
    parts.append("</svg>")
    return "".join(parts)


__all__ = [
    "CONDITION_LABELS",
    "factor_plot_svg",
    "overall_condition_grid",
    "participant_factorial_grid",
    "participant_paired_lines_svg",
    "user_type_factorial_grid",
    "user_type_heatmap_svg",
]
