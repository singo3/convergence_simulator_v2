"""Dependency-free inline SVG charts for the offline Stage 8A.3 report."""

# ruff: noqa: E501 -- SVG fragments stay legible as complete attributes.

from __future__ import annotations

import colorsys
import html
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .analysis import bootstrap_interval
from .config import ARM_IDS
from .records import BundleOutcome, SessionOutcome

ARM_LABELS = {
    "autonomous_closed_loop": "autonomous",
    "response_decoupled_yoked_replay": "yoked replay",
    "pure_random_open_loop": "pure random",
}
ARM_COLORS = {
    "autonomous_closed_loop": "#166b64",
    "response_decoupled_yoked_replay": "#8b5a2b",
    "pure_random_open_loop": "#555f78",
}


def hue_color(hue_degree: float | None, *, saturation: float = 0.78) -> str:
    if hue_degree is None:
        return "#a7afb8"
    red, green, blue = colorsys.hsv_to_rgb(
        (float(hue_degree) % 360.0) / 360.0,
        saturation,
        0.88,
    )
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def _marker(
    life_id: str | None,
    x: float,
    y: float,
    radius: float,
    fill: str,
    *,
    opacity: float = 1.0,
    stroke: str = "#17212b",
    stroke_width: float = 1.0,
    title: str = "",
) -> str:
    escaped = html.escape(title)
    common = (
        f"fill='{fill}' fill-opacity='{opacity:.2f}' stroke='{stroke}' "
        f"stroke-width='{stroke_width:.1f}'"
    )
    if life_id == "life-green":
        points = (
            f"{x:.2f},{y - radius:.2f} "
            f"{x - radius * 0.92:.2f},{y + radius * 0.8:.2f} "
            f"{x + radius * 0.92:.2f},{y + radius * 0.8:.2f}"
        )
        return f"<polygon points='{points}' {common}><title>{escaped}</title></polygon>"
    if life_id == "life-blue":
        return (
            f"<rect x='{x - radius:.2f}' y='{y - radius:.2f}' "
            f"width='{2 * radius:.2f}' height='{2 * radius:.2f}' {common}>"
            f"<title>{escaped}</title></rect>"
        )
    return (
        f"<circle cx='{x:.2f}' cy='{y:.2f}' r='{radius:.2f}' {common}>"
        f"<title>{escaped}</title></circle>"
    )


def _axes(
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    maximum_session: int,
    title: str,
) -> list[str]:
    parts = [
        f"<text x='{x0}' y='{y0 - 12}' class='panel-title'>{html.escape(title)}</text>",
        f"<line x1='{x0}' y1='{y0}' x2='{x0}' y2='{y0 + height}' class='axis'/>",
        f"<line x1='{x0}' y1='{y0 + height}' x2='{x0 + width}' y2='{y0 + height}' class='axis'/>",
    ]
    for bpm in (10, 50, 100, 150, 165):
        y = y0 + height - (bpm - 10.0) / 155.0 * height
        parts.extend(
            (
                f"<line x1='{x0}' y1='{y:.2f}' x2='{x0 + width}' y2='{y:.2f}' class='grid'/>",
                f"<text x='{x0 - 8}' y='{y + 4:.2f}' text-anchor='end'>{bpm}</text>",
            )
        )
    ticks = range(maximum_session) if maximum_session <= 12 else range(0, maximum_session, 4)
    for session_index in ticks:
        x = x0 + (session_index + 0.5) / maximum_session * width
        parts.append(
            f"<text x='{x:.2f}' y='{y0 + height + 17}' text-anchor='middle'>{session_index + 1}</text>"
        )
    return parts


def participant_trajectory_svg(
    participant_id: str,
    condition_id: str,
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    *,
    arms: Sequence[str] = ARM_IDS,
) -> str:
    selected_arms = tuple(arms)
    if not selected_arms or any(arm not in ARM_IDS for arm in selected_arms):
        raise ValueError("arms must be a non-empty subset of Stage 8A.3 arms")
    if len(set(selected_arms)) != len(selected_arms):
        raise ValueError("arms must be unique")
    selected_bundles = [
        item
        for item in bundles
        if item.participant_id == participant_id and item.condition_id == condition_id
    ]
    selected_sessions = [
        item
        for item in sessions
        if item.participant_id == participant_id and item.condition_id == condition_id
    ]
    maximum_session = max((item.session_index for item in selected_sessions), default=0) + 1
    panel_width = 300.0
    panel_height = 170.0
    gap = 38.0
    left = 50.0
    top = 48.0
    total_width = left + len(selected_arms) * panel_width + (len(selected_arms) - 1) * gap + 20
    total_height = top + panel_height + 48
    parts = [
        f"<svg class='trajectory participant-trajectory' viewBox='0 0 {total_width:.0f} {total_height:.0f}' "
        "role='img' aria-label='session by blink BPM, actual Hue fill and life marker'>",
        "<style>.axis{stroke:#52616e;stroke-width:1}.grid{stroke:#dbe2e7;stroke-width:.7}.panel-title{font-weight:700}text{font:10px system-ui,sans-serif;fill:#26333e}</style>",
        f"<text x='{left}' y='18' font-size='13' font-weight='700'>{html.escape(participant_id)} · {html.escape(condition_id)}</text>",
        f"<text x='12' y='{top + panel_height / 2}' transform='rotate(-90 12 {top + panel_height / 2})'>blink BPM</text>",
    ]
    for panel_index, arm in enumerate(selected_arms):
        x0 = left + panel_index * (panel_width + gap)
        parts.extend(
            _axes(
                x0=x0,
                y0=top,
                width=panel_width,
                height=panel_height,
                maximum_session=max(1, maximum_session),
                title=ARM_LABELS[arm],
            )
        )
        for row in selected_bundles:
            if row.arm != arm or row.displayed_blink_bpm is None:
                continue
            x = (
                x0
                + (row.session_index + 0.5 + (-0.20, 0.0, 0.20)[row.bundle_index])
                / maximum_session
                * panel_width
            )
            y = top + panel_height - (row.displayed_blink_bpm - 10.0) / 155.0 * panel_height
            is_trial = row.anchor_or_trial is not None and "trial" in row.anchor_or_trial
            stroke = "#16885e" if row.adoption_result == "accepted" else "#17212b"
            if row.adoption_result and "reject" in row.adoption_result:
                stroke = "#b62f3d"
            parts.append(
                _marker(
                    row.displayed_life_id,
                    x,
                    y,
                    3.4,
                    hue_color(row.displayed_hue_degree),
                    opacity=0.42 if is_trial else 0.88,
                    stroke=stroke,
                    title=(
                        f"session {row.session_index + 1}, bundle {row.bundle_index}, "
                        f"{row.displayed_life_id}, Hue {row.displayed_hue_degree}, "
                        f"BPM {row.displayed_blink_bpm}, ΔRMSSD {row.delta_rmssd_ms}"
                    ),
                )
            )
        for row in selected_sessions:
            if row.arm != arm:
                continue
            x = x0 + (row.session_index + 0.5) / maximum_session * panel_width
            if not row.session_valid or row.representative_blink_bpm is None:
                y = top + panel_height - 8
                parts.append(
                    f"<path d='M{x - 5:.2f},{y - 5:.2f} L{x + 5:.2f},{y + 5:.2f} "
                    f"M{x + 5:.2f},{y - 5:.2f} L{x - 5:.2f},{y + 5:.2f}' "
                    "stroke='#b62f3d' stroke-width='2'><title>invalid session</title></path>"
                )
                continue
            y = top + panel_height - (row.representative_blink_bpm - 10.0) / 155.0 * panel_height
            parts.append(
                _marker(
                    row.representative_life_id,
                    x,
                    y,
                    6.0,
                    hue_color(row.representative_hue_degree),
                    stroke="#fff",
                    stroke_width=1.8,
                    title=(
                        (
                            "final committed anchor"
                            if arm == "autonomous_closed_loop"
                            else "Bundle 2 actual representative"
                        )
                        + f" session {row.session_index + 1}, "
                        f"{row.representative_life_id}, Hue {row.representative_hue_degree}, "
                        f"BPM {row.representative_blink_bpm}"
                    ),
                )
            )
    parts.append(
        f"<text x='{total_width / 2:.2f}' y='{total_height - 5}' text-anchor='middle'>session index</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def user_type_average_svg(
    rows: Sequence[Mapping[str, Any]],
    condition_id: str,
    *,
    arms: Sequence[str] = ARM_IDS,
) -> str:
    selected_arms = tuple(arms)
    if not selected_arms or any(arm not in ARM_IDS for arm in selected_arms):
        raise ValueError("arms must be a non-empty subset of Stage 8A.3 arms")
    if len(set(selected_arms)) != len(selected_arms):
        raise ValueError("arms must be unique")
    selected = [item for item in rows if item.get("condition_id") == condition_id]
    types = sorted({str(item["user_type_id"]) for item in selected})
    max_session = max((int(item["session_index"]) for item in selected), default=0) + 1
    row_height = 142.0
    width = 980.0
    left = 190.0
    plot_width = width - left - 25
    height = 35 + len(types) * row_height
    parts = [
        f"<svg class='trajectory user-type-trajectory' viewBox='0 0 {width:.0f} {height:.0f}' role='img' aria-label='user type average trajectory'>",
        "<style>.grid{stroke:#dfe5e8;stroke-width:.7}text{font:10px system-ui,sans-serif;fill:#26333e}</style>",
    ]
    for type_index, user_type_id in enumerate(types):
        y0 = 28 + type_index * row_height
        parts.append(
            f"<text x='4' y='{y0 + 16:.2f}' font-weight='700'>{html.escape(user_type_id)}</text>"
        )
        for arm_index, arm in enumerate(selected_arms):
            y_base = y0 + 30 + arm_index * 34
            parts.append(
                f"<text x='{left - 8}' y='{y_base + 5:.2f}' text-anchor='end'>{html.escape(ARM_LABELS[arm])}</text>"
            )
            arm_rows = [
                item
                for item in selected
                if item["user_type_id"] == user_type_id and item["arm"] == arm
            ]
            for item in arm_rows:
                if item.get("median_bpm") is None:
                    continue
                x = left + (int(item["session_index"]) + 0.5) / max_session * plot_width
                bpm = float(item["median_bpm"])
                y = y_base + 12 - (bpm - 87.5) / 155.0 * 24
                concentration = float(item.get("modal_life_circular_concentration") or 0.0)
                fill = (
                    "#fff"
                    if concentration < 0.25
                    else hue_color(item.get("modal_life_circular_mean_hue_degree"))
                )
                parts.append(
                    _marker(
                        item.get("modal_life_id"),
                        x,
                        y,
                        2.5 + 3.5 * float(item.get("modal_life_share") or 0.0),
                        fill,
                        opacity=0.35 if concentration < 0.25 else 0.9,
                        stroke=ARM_COLORS[arm],
                        title=(
                            f"median BPM {bpm:.2f}, Hue concentration {concentration:.3f}, "
                            f"modal share {item.get('modal_life_share')}"
                        ),
                    )
                )
                q1 = item.get("bpm_q1")
                q3 = item.get("bpm_q3")
                if q1 is not None and q3 is not None:
                    y1 = y_base + 12 - (float(q1) - 87.5) / 155.0 * 24
                    y3 = y_base + 12 - (float(q3) - 87.5) / 155.0 * 24
                    parts.append(
                        f"<line x1='{x:.2f}' y1='{y1:.2f}' x2='{x:.2f}' y2='{y3:.2f}' stroke='{ARM_COLORS[arm]}'/>"
                    )
                lower95 = item.get("bpm_lower95")
                upper95 = item.get("bpm_upper95")
                if lower95 is not None and upper95 is not None:
                    y_lower = y_base + 12 - (float(lower95) - 87.5) / 155.0 * 24
                    y_upper = y_base + 12 - (float(upper95) - 87.5) / 155.0 * 24
                    parts.append(
                        f"<line x1='{x - 1.8:.2f}' y1='{y_lower:.2f}' x2='{x - 1.8:.2f}' y2='{y_upper:.2f}' stroke='{ARM_COLORS[arm]}' stroke-opacity='.4' stroke-width='2'/>"
                    )
            for item in arm_rows:
                session_index = int(item["session_index"])
                cell_width = plot_width / max_session
                x_cursor = left + session_index * cell_width
                for life, color in (
                    ("red", "#d05a56"),
                    ("green", "#54a86a"),
                    ("blue", "#557fd1"),
                ):
                    block = cell_width * float(item.get(f"life_{life}_share") or 0.0)
                    parts.append(
                        f"<rect x='{x_cursor:.2f}' y='{y_base + 19:.2f}' width='{block:.2f}' height='4' fill='{color}'/>"
                    )
                    x_cursor += block
    parts.append("</svg>")
    return "".join(parts)


def overall_delta_svg(
    sessions: Sequence[SessionOutcome],
    condition_id: str,
    *,
    arms: Sequence[str] = ARM_IDS,
) -> str:
    selected_arms = tuple(arms)
    if not selected_arms or any(arm not in ARM_IDS for arm in selected_arms):
        raise ValueError("arms must be a non-empty subset of Stage 8A.3 arms")
    if len(set(selected_arms)) != len(selected_arms):
        raise ValueError("arms must be unique")
    selected = [item for item in sessions if item.condition_id == condition_id]
    max_session = max((item.session_index for item in selected), default=0) + 1
    width, height, left, top = 760.0, 300.0, 58.0, 25.0
    plot_width, plot_height = width - left - 24, height - top - 48
    groups: dict[tuple[str, int], list[float]] = defaultdict(list)
    for item in selected:
        if item.mean_valid_bundle_delta_rmssd_ms is not None:
            groups[(item.arm, item.session_index)].append(item.mean_valid_bundle_delta_rmssd_ms)
    all_values = [value for values in groups.values() for value in values]
    y_min = min(all_values, default=-1.0)
    y_max = max(all_values, default=1.0)
    padding = max(1.0, (y_max - y_min) * 0.15)
    y_min -= padding
    y_max += padding

    def point(arm: str, index: int) -> tuple[float, float] | None:
        values = groups.get((arm, index))
        if not values:
            return None
        x = left + (index + 0.5) / max_session * plot_width
        y = top + plot_height - (statistics.fmean(values) - y_min) / (y_max - y_min) * plot_height
        return x, y

    parts = [
        f"<svg class='overall-delta' viewBox='0 0 {width:.0f} {height:.0f}' role='img' aria-label='participant-aggregated delta RMSSD trajectory'>",
        "<style>text{font:10px system-ui,sans-serif;fill:#26333e}</style>",
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + plot_height}' stroke='#52616e'/>",
        f"<line x1='{left}' y1='{top + plot_height}' x2='{left + plot_width}' y2='{top + plot_height}' stroke='#52616e'/>",
    ]
    if y_min <= 0 <= y_max:
        y_zero = top + plot_height - (0 - y_min) / (y_max - y_min) * plot_height
        parts.append(
            f"<line x1='{left}' y1='{y_zero:.2f}' x2='{left + plot_width}' y2='{y_zero:.2f}' stroke='#c9d0d5' stroke-dasharray='3 3'/>"
        )
    for arm in selected_arms:
        points = [point(arm, index) for index in range(max_session)]
        path = " ".join(
            ("M" if first else "L") + f"{value[0]:.2f},{value[1]:.2f}"
            for first, value in enumerate(item for item in points if item is not None)
        )
        if path:
            parts.append(
                f"<path d='{path}' fill='none' stroke='{ARM_COLORS[arm]}' stroke-width='2'/>"
            )
        for value in points:
            if value is not None:
                parts.append(
                    f"<circle cx='{value[0]:.2f}' cy='{value[1]:.2f}' r='3' fill='{ARM_COLORS[arm]}'/>"
                )
        for index in range(max_session):
            values = groups.get((arm, index), [])
            if not values:
                continue
            lower95, upper95 = bootstrap_interval(
                values,
                seed_parts=(condition_id, arm, index, "overall-delta"),
            )
            if lower95 is None or upper95 is None:
                continue
            x = left + (index + 0.5) / max_session * plot_width
            y_lower = top + plot_height - (lower95 - y_min) / (y_max - y_min) * plot_height
            y_upper = top + plot_height - (upper95 - y_min) / (y_max - y_min) * plot_height
            parts.append(
                f"<line x1='{x:.2f}' y1='{y_lower:.2f}' x2='{x:.2f}' y2='{y_upper:.2f}' stroke='{ARM_COLORS[arm]}' stroke-opacity='.35' stroke-width='3'/>"
            )
    for index, arm in enumerate(selected_arms):
        parts.append(
            f"<rect x='{left + index * 150}' y='{height - 18}' width='10' height='3' fill='{ARM_COLORS[arm]}'/>"
            f"<text x='{left + index * 150 + 15}' y='{height - 13}'>{html.escape(ARM_LABELS[arm])}</text>"
        )
    parts.append(
        f"<text x='12' y='{top + plot_height / 2}' transform='rotate(-90 12 {top + plot_height / 2})'>mean ΔRMSSD (ms)</text></svg>"
    )
    return "".join(parts)


def overall_adaptation_metrics_svg(
    prospective: Sequence[Mapping[str, Any]],
    sessions: Sequence[SessionOutcome],
    condition_id: str,
) -> str:
    """Show selection percentile, enrichment, and cumulative paired benefit."""

    selected = [item for item in prospective if item.get("condition_id") == condition_id]
    max_session = (
        max(
            (item.session_index for item in sessions if item.condition_id == condition_id),
            default=0,
        )
        + 1
    )
    late_start = math.floor(2 * max_session / 3)
    session_lookup = {
        (item.participant_id, item.arm, item.session_index): item
        for item in sessions
        if item.condition_id == condition_id
    }
    cumulative: dict[tuple[str, int], list[float]] = defaultdict(list)
    participants = sorted(
        {item.participant_id for item in sessions if item.condition_id == condition_id}
    )
    for comparator in ("response_decoupled_yoked_replay", "pure_random_open_loop"):
        for participant_id in participants:
            running: list[float] = []
            for index in range(max_session):
                auto = session_lookup.get((participant_id, "autonomous_closed_loop", index))
                other = session_lookup.get((participant_id, comparator, index))
                if (
                    index >= late_start
                    and auto is not None
                    and other is not None
                    and auto.mean_valid_bundle_delta_rmssd_ms is not None
                    and other.mean_valid_bundle_delta_rmssd_ms is not None
                ):
                    running.append(
                        auto.mean_valid_bundle_delta_rmssd_ms
                        - other.mean_valid_bundle_delta_rmssd_ms
                    )
                if running:
                    cumulative[(comparator, index)].append(statistics.fmean(running))
    metrics: tuple[tuple[str, str], ...] = (
        ("full_pattern_selection_percentile", "selection percentile"),
        ("full_pattern_selection_enrichment", "prospective enrichment"),
    )
    width, height = 940.0, 470.0
    left, plot_width, panel_height = 64.0, 840.0, 105.0
    parts = [
        f"<svg class='overall-adaptation-metrics' viewBox='0 0 {width:.0f} {height:.0f}' role='img' aria-label='selection percentile enrichment cumulative advantage'>",
        "<style>text{font:10px system-ui,sans-serif;fill:#26333e}.grid{stroke:#dfe5e8;stroke-width:.7}</style>",
    ]
    for panel_index, (field, label) in enumerate(metrics):
        top = 25.0 + panel_index * 140.0
        values_by_arm_index: dict[tuple[str, int], list[float]] = defaultdict(list)
        for row in selected:
            value = row.get(field)
            if value is not None:
                values_by_arm_index[(str(row["arm"]), int(row["session_index"]))].append(
                    float(value)
                )
        finite = [value for values in values_by_arm_index.values() for value in values]
        y_min, y_max = (
            (0.0, 100.0)
            if field.endswith("percentile")
            else (min(finite, default=-1.0), max(finite, default=1.0))
        )
        if math.isclose(y_min, y_max):
            y_min -= 0.5
            y_max += 0.5
        parts.append(
            f"<text x='{left}' y='{top - 8}' font-weight='700'>{html.escape(label)}</text>"
        )
        parts.append(
            f"<line x1='{left}' y1='{top + panel_height}' x2='{left + plot_width}' y2='{top + panel_height}' stroke='#52616e'/>"
        )
        for arm in ARM_IDS:
            coordinates: list[tuple[float, float]] = []
            for index in range(max_session):
                values = values_by_arm_index.get((arm, index), [])
                if not values:
                    continue
                x = left + (index + 0.5) / max_session * plot_width
                mean = statistics.fmean(values)
                y = top + panel_height - (mean - y_min) / (y_max - y_min) * panel_height
                coordinates.append((x, y))
            if coordinates:
                path = " ".join(
                    ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
                    for index, (x, y) in enumerate(coordinates)
                )
                parts.append(
                    f"<path d='{path}' fill='none' stroke='{ARM_COLORS[arm]}' stroke-width='2'/>"
                )
    top = 305.0
    parts.append(
        f"<text x='{left}' y='{top - 8}' font-weight='700'>cumulative late autonomous advantage (participant mean)</text>"
    )
    parts.append(
        f"<line x1='{left}' y1='{top + panel_height}' x2='{left + plot_width}' y2='{top + panel_height}' stroke='#52616e'/>"
    )
    finite_cumulative = [value for values in cumulative.values() for value in values]
    y_min, y_max = min(finite_cumulative, default=-1.0), max(finite_cumulative, default=1.0)
    if math.isclose(y_min, y_max):
        y_min -= 0.5
        y_max += 0.5
    for comparator, color in (
        ("response_decoupled_yoked_replay", "#8b5a2b"),
        ("pure_random_open_loop", "#555f78"),
    ):
        coordinates = []
        for index in range(max_session):
            values = cumulative.get((comparator, index), [])
            if values:
                x = left + (index + 0.5) / max_session * plot_width
                y = (
                    top
                    + panel_height
                    - (statistics.fmean(values) - y_min) / (y_max - y_min) * panel_height
                )
                coordinates.append((x, y))
        if coordinates:
            path = " ".join(
                ("M" if index == 0 else "L") + f"{x:.2f},{y:.2f}"
                for index, (x, y) in enumerate(coordinates)
            )
            parts.append(f"<path d='{path}' fill='none' stroke='{color}' stroke-width='2'/>")
    parts.append(
        f"<text x='{left}' y='{height - 14}' fill='#8b5a2b'>vs yoked replay</text>"
        f"<text x='{left + 150}' y='{height - 14}' fill='#555f78'>vs pure random</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def correlation_scatter_svg(
    rows: Sequence[Mapping[str, Any]],
    *,
    x_field: str,
    y_field: str,
    title: str,
) -> str:
    values = [
        (float(item[x_field]), float(item[y_field]), str(item.get("arm", "")))
        for item in rows
        if item.get(x_field) is not None and item.get(y_field) is not None
    ]
    width, height, left, top = 500.0, 250.0, 52.0, 28.0
    plot_width, plot_height = width - left - 18, height - top - 40
    if not values:
        return (
            f"<svg class='correlation-scatter' viewBox='0 0 {width:.0f} {height:.0f}'>"
            f"<text x='20' y='28'>{html.escape(title)}</text><text x='20' y='60'>insufficient participant-session data</text></svg>"
        )
    xs = [item[0] for item in values]
    ys = [item[1] for item in values]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if math.isclose(x_min, x_max):
        x_min -= 0.5
        x_max += 0.5
    if math.isclose(y_min, y_max):
        y_min -= 0.5
        y_max += 0.5
    parts = [
        f"<svg class='correlation-scatter' viewBox='0 0 {width:.0f} {height:.0f}' role='img' aria-label='{html.escape(title)}'>",
        f"<text x='{left}' y='16' font-size='12' font-weight='700'>{html.escape(title)}</text>",
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + plot_height}' stroke='#52616e'/>",
        f"<line x1='{left}' y1='{top + plot_height}' x2='{left + plot_width}' y2='{top + plot_height}' stroke='#52616e'/>",
    ]
    for x_value, y_value, arm in values:
        x = left + (x_value - x_min) / (x_max - x_min) * plot_width
        y = top + plot_height - (y_value - y_min) / (y_max - y_min) * plot_height
        parts.append(
            f"<circle cx='{x:.2f}' cy='{y:.2f}' r='3' fill='{ARM_COLORS.get(arm, '#66727e')}' fill-opacity='.65'><title>{x_value:.4f}, {y_value:.4f}, {html.escape(arm)}</title></circle>"
        )
    parts.append("</svg>")
    return "".join(parts)


def overall_classification_bars(rows: Sequence[Mapping[str, Any]]) -> str:
    classifications = (
        "clear_positive_adaptation",
        "partial_adaptation_signal",
        "no_clear_effect",
        "negative_or_unstable",
        "insufficient_data",
    )
    counts = Counter(str(item.get("classification")) for item in rows)
    total = max(1, sum(counts.values()))
    colors = ("#16885e", "#75a85c", "#83909d", "#bf6c52", "#c4cbd1")
    parts = [
        "<svg class='classification-bars' viewBox='0 0 700 145' role='img' aria-label='responder classification proportions'>"
    ]
    x = 20.0
    for label, color in zip(classifications, colors, strict=True):
        width = 660.0 * counts[label] / total
        parts.append(
            f"<rect x='{x:.2f}' y='24' width='{width:.2f}' height='26' fill='{color}'><title>{html.escape(label)}: {counts[label]}</title></rect>"
        )
        x += width
    for index, (label, color) in enumerate(zip(classifications, colors, strict=True)):
        y = 70 + index * 14
        parts.append(
            f"<rect x='20' y='{y - 9}' width='9' height='9' fill='{color}'/><text x='35' y='{y}' font-size='10'>{html.escape(label)}: {counts[label]} ({counts[label] / total:.1%})</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


__all__ = [
    "correlation_scatter_svg",
    "hue_color",
    "overall_classification_bars",
    "overall_adaptation_metrics_svg",
    "overall_delta_svg",
    "participant_trajectory_svg",
    "user_type_average_svg",
]
