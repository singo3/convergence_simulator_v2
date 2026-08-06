"""Deterministic Stage 8A.3.1 CSV/JSON exports using Stage 8A.3 I/O."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    ValidationParticipant,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.exports import (
    write_csv,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.checkpoint import (
    atomic_write_json,
)

from .conditions import FactorialValidationCondition
from .config import FACTORIAL_ARTIFACT_DIGEST_VERSION

REQUIRED_RESULT_FILENAMES = (
    "validation_manifest.json",
    "validation_plan.json",
    "checkpoint.json",
    "conditions.csv",
    "participant_profiles.csv",
    "shared_random_sessions.csv",
    "autonomous_sessions.csv",
    "arm_pair_differences.csv",
    "factorial_participant_effects.csv",
    "factorial_user_type_effects.csv",
    "factorial_overall_effects.csv",
    "condition_summary.csv",
    "condition_recommendation.json",
    "invalid_data.csv",
    "digests.json",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _invalid_rows(
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    rows.extend(
        {
            "record_type": "session",
            "participant_id": item.participant_id,
            "user_type_id": item.user_type_id,
            "condition_id": item.condition_id,
            "arm": item.arm,
            "session_index": item.session_index,
            "bundle_index": None,
            "reason": item.invalid_reason,
        }
        for item in sessions
        if not item.session_valid
    )
    rows.extend(
        {
            "record_type": "bundle",
            "participant_id": item.participant_id,
            "user_type_id": item.user_type_id,
            "condition_id": item.condition_id,
            "arm": item.arm,
            "session_index": item.session_index,
            "bundle_index": item.bundle_index,
            "reason": item.evaluation_quality,
        }
        for item in bundles
        if not item.valid_for_analysis
    )
    return tuple(rows)


def export_factorial_results(
    run_directory: Path,
    *,
    participants: Sequence[ValidationParticipant],
    conditions: Sequence[FactorialValidationCondition],
    shared_random_bundles: Sequence[BundleOutcome],
    shared_random_sessions: Sequence[SessionOutcome],
    autonomous_bundles: Sequence[BundleOutcome],
    autonomous_sessions: Sequence[SessionOutcome],
    logical_bundles: Sequence[BundleOutcome],
    logical_sessions: Sequence[SessionOutcome],
    session_audits: Sequence[Mapping[str, Any]],
    shared_random_checksums: Mapping[str, str],
    analysis: Mapping[str, Sequence[Mapping[str, Any]]],
    condition_summaries: Sequence[Mapping[str, Any]],
    recommendation: Mapping[str, Any],
) -> dict[str, Path]:
    audit_by_key = {
        (
            str(item["participant_id"]),
            str(item["condition_id"]),
            int(item["session_index"]),
        ): item
        for item in session_audits
    }
    autonomous_rows = tuple(
        {
            **item.to_dict(),
            **dict(
                audit_by_key.get(
                    (item.participant_id, item.condition_id, item.session_index),
                    {},
                )
            ),
        }
        for item in autonomous_sessions
    )
    shared_rows = tuple(
        {
            **item.to_dict(),
            "shared_random_condition_independent": True,
            "shared_random_result_checksum": shared_random_checksums[item.participant_id],
            "logical_condition_reference_count": len(conditions),
        }
        for item in shared_random_sessions
    )
    rows_by_filename: dict[str, Sequence[Mapping[str, Any]]] = {
        "conditions.csv": tuple(item.to_dict() for item in conditions),
        "participant_profiles.csv": tuple(item.to_dict() for item in participants),
        "shared_random_sessions.csv": shared_rows,
        "autonomous_sessions.csv": autonomous_rows,
        "arm_pair_differences.csv": analysis.get("participant_condition_effects", ()),
        "factorial_participant_effects.csv": analysis.get("factorial_participant_effects", ()),
        "factorial_user_type_effects.csv": analysis.get("factorial_user_type_effects", ()),
        "factorial_overall_effects.csv": analysis.get("factorial_overall_effects", ()),
        "condition_summary.csv": condition_summaries,
        "invalid_data.csv": _invalid_rows(logical_bundles, logical_sessions),
        "bundle_outcomes.csv": tuple(item.to_dict() for item in logical_bundles),
        "logical_session_outcomes.csv": tuple(item.to_dict() for item in logical_sessions),
        "contemporaneous_response.csv": analysis.get("contemporaneous", ()),
        "prospective_selection_enrichment.csv": analysis.get("prospective", ()),
        "lagged_coupling.csv": analysis.get("lagged", ()),
        "prediction_metrics.csv": analysis.get("prediction", ()),
        "rmssd_benefits.csv": analysis.get("benefits", ()),
        "user_type_trajectory.csv": analysis.get("user_type_trajectory", ()),
    }
    written = {
        filename: write_csv(run_directory / filename, rows)
        for filename, rows in rows_by_filename.items()
    }
    recommendation_path = run_directory / "condition_recommendation.json"
    atomic_write_json(recommendation_path, dict(recommendation))
    written[recommendation_path.name] = recommendation_path
    return written


def write_artifact_digests(run_directory: Path) -> Path:
    excluded_roots = {"completed_jobs", "failed_jobs", "donor_sequences", "details"}
    files = []
    for path in sorted(run_directory.rglob("*")):
        if not path.is_file() or path.name == "digests.json":
            continue
        relative = path.relative_to(run_directory)
        if relative.parts[0] in excluded_roots or relative.parts[0] == "logs":
            continue
        if relative.name == ".run.lock" or relative.name == "checkpoint.json":
            continue
        files.append(path)
    payload = {
        str(path.relative_to(run_directory)): {
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in files
    }
    output = run_directory / "digests.json"
    atomic_write_json(
        output,
        {
            "algorithm": "sha256",
            "files": payload,
            "schema_version": FACTORIAL_ARTIFACT_DIGEST_VERSION,
        },
    )
    return output


__all__ = [
    "REQUIRED_RESULT_FILENAMES",
    "export_factorial_results",
    "write_artifact_digests",
]
