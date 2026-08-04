"""Stage 8A.1 CSV/manifest exports detached from simulation and digests."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .aggregation import aggregate_condition, replicate_result_from_single
from .canonical import canonical_json
from .grid_runner import FatigueSigmaGridSummary
from .result import FatigueSigmaSingleConditionResult

CONDITIONS_CSV = "stage_08a1_conditions.csv"
FATIGUE_CSV = "stage_08a1_fatigue_trajectory.csv"
SIGMA_CSV = "stage_08a1_sigma_trajectory.csv"
PATTERN_CSV = "stage_08a1_session_pattern_trajectory.csv"
STRUCTURED_CSV = "stage_08a1_structured_convergence_history.csv"
REPLICATES_CSV = "stage_08a1_replicate_results.csv"
SUMMARIES_CSV = "stage_08a1_condition_summaries.csv"
HEATMAP_CSV = "stage_08a1_grid_heatmap.csv"
MANIFEST_JSON = "stage_08a1_experiment_manifest.json"

_HEATMAP_METRICS = (
    "correct_structure_rate",
    "life_dominant_convergence_rate",
    "bpm_common_convergence_rate",
    "multi_attractor_convergence_rate",
    "diffuse_rate",
    "median_first_convergence_session",
    "post_convergence_outlier_rate",
    "return_within_1_rate",
    "holder_switch_rate",
    "mechanical_rotation_rate",
    "accepted_candidate_count",
    "w_ceiling_blocked_rate",
)


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return canonical_json(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    minimum_fields: Sequence[str],
) -> Path:
    fields = tuple(
        dict.fromkeys(
            (*minimum_fields, *sorted({key for row in rows for key in row}))
        )
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell(row.get(key)) for key in fields})
    return path


def _export(
    directory: Path,
    *,
    conditions: Sequence[Mapping[str, Any]],
    fatigue: Sequence[Mapping[str, Any]],
    sigma: Sequence[Mapping[str, Any]],
    patterns: Sequence[Mapping[str, Any]],
    structured: Sequence[Mapping[str, Any]],
    replicates: Sequence[Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> dict[str, Path]:
    if not isinstance(directory, Path):
        raise TypeError("directory must be a pathlib.Path")
    directory.mkdir(parents=True, exist_ok=True)
    heatmap = tuple(
        {
            "condition_id": row.get("condition_id"),
            "user_type_id": row.get("user_type_id"),
            "selected_session_fatigue_target": row.get(
                "selected_session_fatigue_target"
            ),
            "sigma_multiplier": row.get("sigma_multiplier"),
            "maximum_sessions": row.get("maximum_sessions"),
            "replicate_count": row.get("replicate_count"),
            "completed_replicate_count": row.get(
                "completed_replicate_count"
            ),
            "failed_replicate_count": row.get("failed_replicate_count"),
            "selected_life_mean_e": row.get("selected_life_mean_e"),
            "selected_life_max_e": row.get("selected_life_max_e"),
            "nonselected_full_recovery_count": row.get(
                "nonselected_full_recovery_count"
            ),
            "effective_sigma_mean": row.get("effective_sigma_mean"),
            "effective_sigma_min": row.get("effective_sigma_min"),
            "effective_sigma_max": row.get("effective_sigma_max"),
            "metric_name": metric_name,
            "metric_value": row.get(metric_name),
        }
        for row in summaries
        for metric_name in _HEATMAP_METRICS
    )
    paths = {
        "conditions": _write_csv(
            directory / CONDITIONS_CSV,
            conditions,
            minimum_fields=(
                "condition_id",
                "replicate_index",
                "replicate_master_seed",
                "user_type_id",
                "fatigue_policy_version",
                "selected_session_fatigue_target",
                "unselected_session_end_recovery_fraction",
                "sigma_scaling_policy_version",
                "sigma_multiplier",
                "maximum_sessions",
                "master_seed",
                "session_seed_policy",
                "structured_convergence_config_version",
                "formal_spec_adoption",
                "base_profile_version",
                "experiment_profile_version",
                "schema_version",
            ),
        ),
        "fatigue_trajectory": _write_csv(
            directory / FATIGUE_CSV,
            fatigue,
            minimum_fields=(
                "condition_id",
                "replicate_index",
                "replicate_master_seed",
                "session_index",
                "digital_life_id",
                "e_at_session_start",
                "e_after_baseline",
                "e_after_active",
                "e_before_session_end_policy",
                "e_after_session_end_policy",
                "selected_active_signal_count",
                "full_recovery_applied",
            ),
        ),
        "sigma_trajectory": _write_csv(
            directory / SIGMA_CSV,
            sigma,
            minimum_fields=(
                "condition_id",
                "replicate_index",
                "replicate_master_seed",
                "session_index",
                "digital_life_id",
                "reference_sigma_min",
                "reference_sigma_max",
                "reference_sigma_at_w",
                "sigma_multiplier",
                "effective_sigma",
                "candidate_delta_f",
                "candidate_delta_t",
                "resulting_delta_hue",
                "resulting_delta_bpm",
            ),
        ),
        "session_pattern_trajectory": _write_csv(
            directory / PATTERN_CSV,
            patterns,
            minimum_fields=(
                "condition_id",
                "replicate_index",
                "replicate_master_seed",
                "session_index",
                "point_kind",
                "digital_life_id",
                "hue_degree",
                "blink_bpm",
                "cluster_member",
                "outlier",
            ),
        ),
        "structured_convergence_history": _write_csv(
            directory / STRUCTURED_CSV,
            structured,
            minimum_fields=(
                "condition_id",
                "replicate_index",
                "replicate_master_seed",
                "evaluated_at_session_index",
                "early_single_life_pattern_signal",
                "life_dominant_converged",
                "bpm_common_converged",
                "multi_attractor_converged",
                "summary_classification",
            ),
        ),
        "replicate_results": _write_csv(
            directory / REPLICATES_CSV,
            replicates,
            minimum_fields=(
                "condition_id",
                "replicate_index",
                "replicate_master_seed",
                "completed",
                "failed",
                "summary_classification",
                "truth_classification",
            ),
        ),
        "condition_summaries": _write_csv(
            directory / SUMMARIES_CSV,
            summaries,
            minimum_fields=(
                "condition_id",
                "selected_session_fatigue_target",
                "sigma_multiplier",
                "completed_replicate_count",
                "failed_replicate_count",
            ),
        ),
        "grid_heatmap": _write_csv(
            directory / HEATMAP_CSV,
            heatmap,
            minimum_fields=(
                "condition_id",
                "selected_session_fatigue_target",
                "sigma_multiplier",
                "metric_name",
                "metric_value",
                "replicate_count",
                "completed_replicate_count",
                "failed_replicate_count",
                "selected_life_mean_e",
                "selected_life_max_e",
                "effective_sigma_mean",
                "effective_sigma_min",
                "effective_sigma_max",
            ),
        ),
    }
    manifest_path = directory / MANIFEST_JSON
    manifest_path.write_text(canonical_json(dict(manifest)) + "\n", encoding="utf-8")
    paths["experiment_manifest"] = manifest_path
    return paths


def export_single_condition_csv(
    directory: Path,
    result: FatigueSigmaSingleConditionResult,
) -> dict[str, Path]:
    if not isinstance(result, FatigueSigmaSingleConditionResult):
        raise TypeError("result must be a FatigueSigmaSingleConditionResult")
    replicate = replicate_result_from_single(
        result,
        replicate_index=0,
        replicate_master_seed=int(result.condition["master_seed"]),
    )
    summary = aggregate_condition((replicate,))
    annotation = {
        "condition_id": result.condition["condition_id"],
        "replicate_index": 0,
        "replicate_master_seed": int(result.condition["master_seed"]),
    }

    def annotated(
        rows: Sequence[Mapping[str, Any]],
    ) -> tuple[Mapping[str, Any], ...]:
        return tuple({**dict(row), **annotation} for row in rows)

    return _export(
        directory,
        conditions=({**dict(result.condition), **annotation},),
        fatigue=annotated(result.fatigue_trajectory),
        sigma=annotated(result.sigma_trajectory),
        patterns=annotated(result.session_pattern_trajectory),
        structured=annotated(result.structured_convergence_history),
        replicates=(replicate.to_dict(),),
        summaries=(summary.to_dict(),),
        manifest=result.experiment_manifest,
    )


def export_grid_csv(
    directory: Path,
    result: FatigueSigmaGridSummary,
) -> dict[str, Path]:
    if not isinstance(result, FatigueSigmaGridSummary):
        raise TypeError("result must be a FatigueSigmaGridSummary")
    return _export(
        directory,
        conditions=result.experiment_conditions,
        fatigue=result.fatigue_trajectory,
        sigma=result.sigma_trajectory,
        patterns=result.session_pattern_trajectory,
        structured=result.structured_convergence_history,
        replicates=tuple(item.to_dict() for item in result.replicate_results),
        summaries=tuple(item.to_dict() for item in result.condition_summaries),
        manifest=result.experiment_manifest,
    )


__all__ = [
    "CONDITIONS_CSV",
    "FATIGUE_CSV",
    "HEATMAP_CSV",
    "MANIFEST_JSON",
    "PATTERN_CSV",
    "REPLICATES_CSV",
    "SIGMA_CSV",
    "STRUCTURED_CSV",
    "SUMMARIES_CSV",
    "export_grid_csv",
    "export_single_condition_csv",
]
