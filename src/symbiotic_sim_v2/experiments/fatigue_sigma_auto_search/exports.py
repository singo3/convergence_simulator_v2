"""Deterministic compact CSV/JSON exports for Stage 8A.2."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .checkpoint import atomic_write_json, atomic_write_text
from .job import canonical_json

PHASE_CSV_NAMES = {
    "coarse": "phase_1_coarse_results.csv",
    "refine": "phase_2_refined_results.csv",
    "confirm": "phase_3_confirmation_results.csv",
}


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return canonical_json(value)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    preferred_fields: tuple[str, ...] = (),
) -> Path:
    available = {key for row in rows for key in row}
    fields = list(preferred_fields)
    fields.extend(sorted(available - set(fields)))
    if not fields:
        fields = ["status"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _cell(row.get(field)) for field in fields})
    atomic_write_text(path, buffer.getvalue())
    return path


def _flatten_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in summary.items()
        if key not in {"user_type_breakdown", "uncertainty"}
    } | {
        "user_type_breakdown": summary.get("user_type_breakdown", {}),
        "uncertainty": summary.get("uncertainty", {}),
    }


def export_search_results(
    run_directory: Path,
    *,
    phase_summaries: Mapping[str, tuple[Mapping[str, Any], ...]],
    replicate_results: tuple[Mapping[str, Any], ...],
    pareto_records: tuple[Mapping[str, Any], ...],
    recommendations: Mapping[str, Any],
    reference_results: tuple[Mapping[str, Any], ...],
) -> dict[str, Path]:
    results = run_directory / "results"
    results.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    summary_fields = (
        "candidate_id",
        "condition_key",
        "phase",
        "selected_session_fatigue_target",
        "sigma_multiplier",
        "maximum_sessions",
    )
    for phase, filename in PHASE_CSV_NAMES.items():
        path = _write_csv(
            results / filename,
            tuple(_flatten_summary(item) for item in phase_summaries.get(phase, ())),
            preferred_fields=summary_fields,
        )
        written[filename] = path
    all_summaries = tuple(
        item for phase in ("coarse", "refine", "confirm") for item in phase_summaries.get(phase, ())
    )
    named_rows: dict[str, tuple[Mapping[str, Any], ...]] = {
        "all_replicate_results.csv": replicate_results,
        "all_condition_summaries.csv": tuple(_flatten_summary(item) for item in all_summaries),
        "user_type_breakdown.csv": tuple(
            {
                "candidate_id": summary["candidate_id"],
                "condition_key": summary["condition_key"],
                "phase": summary["phase"],
                **dict(breakdown),
            }
            for summary in all_summaries
            for breakdown in summary.get("user_type_breakdown", {}).values()
        ),
        "flat_control_diagnostics.csv": tuple(
            {
                "candidate_id": summary["candidate_id"],
                "flat_spurious_structure_rate": summary.get("flat_spurious_structure_rate"),
                "flat_spurious_structure_upper95": summary.get("flat_spurious_structure_upper95"),
                "flat_mechanical_rotation_warning_rate": summary.get(
                    "flat_mechanical_rotation_warning_rate"
                ),
                "flat_rotation_upper95": summary.get("flat_rotation_upper95"),
                "flat_holder_switch_rate": summary.get("flat_holder_switch_rate"),
            }
            for summary in all_summaries
        ),
        "mechanical_rotation_diagnostics.csv": tuple(
            {
                "condition_id": item.get("condition_id"),
                "user_type_id": item.get("user_type_id"),
                "replicate_index": item.get("replicate_index"),
                **dict(item.get("mechanical_rotation", {})),
            }
            for item in replicate_results
        ),
        "w_ceiling_diagnostics.csv": tuple(
            {
                "condition_id": item.get("condition_id"),
                "user_type_id": item.get("user_type_id"),
                "replicate_index": item.get("replicate_index"),
                **dict(item.get("w_ceiling", {})),
            }
            for item in replicate_results
        ),
        "pareto_frontier.csv": pareto_records,
        "robust_candidates.csv": tuple(recommendations.get("robust_candidates", ())),
        "specialist_candidates.csv": tuple(
            {"category": category, **dict(candidate)}
            for category, candidate in recommendations.get("specialist_candidates", {}).items()
            if candidate is not None
        ),
        "reference_arm_comparison.csv": reference_results,
        "candidate_blockers.csv": tuple(
            {
                "candidate_id": item["candidate_id"],
                "blocker": blocker,
            }
            for item in pareto_records
            for blocker in item.get("blockers", ())
        ),
    }
    for filename, rows in named_rows.items():
        written[filename] = _write_csv(results / filename, rows)
    recommendation_path = results / "recommended_conditions.json"
    atomic_write_json(recommendation_path, recommendations)
    written[recommendation_path.name] = recommendation_path
    return written


__all__ = ["PHASE_CSV_NAMES", "export_search_results"]
