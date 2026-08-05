"""Deterministic compact Stage 8A.3 CSV/JSON exports and file digests."""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.checkpoint import (
    atomic_write_json,
    atomic_write_text,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import canonical_json

from .config import VALIDATION_SUMMARY_VERSION, ValidationCondition, ValidationParticipant
from .records import BundleOutcome, SessionOutcome

RESULT_CSV_FILENAMES = (
    "participant_profiles.csv",
    "yoke_map.csv",
    "bundle_outcomes.csv",
    "session_outcomes.csv",
    "contemporaneous_response.csv",
    "arm_pair_differences.csv",
    "lagged_coupling.csv",
    "prospective_selection_enrichment.csv",
    "prediction_metrics.csv",
    "permutation_null.csv",
    "participant_effects.csv",
    "user_type_summary.csv",
    "overall_summary.csv",
    "condition_summary.csv",
    "invalid_data.csv",
)


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return canonical_json(value)
    return value


def write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    preferred_fields: Sequence[str] = (),
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def invalid_data_rows(
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    baseline_diagnostics: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = [dict(item) for item in baseline_diagnostics]
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


def condition_summary_rows(
    conditions: Sequence[ValidationCondition],
    sessions: Sequence[SessionOutcome],
    overall: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    overall_by_id = {str(item["condition_id"]): item for item in overall}
    result = []
    for condition in conditions:
        values = [item for item in sessions if item.condition_id == condition.condition_id]
        result.append(
            {
                **condition.to_dict(),
                "target_session_count": len(values),
                "valid_session_count": sum(item.session_valid for item in values),
                "invalid_session_count": sum(not item.session_valid for item in values),
                "aggregate": overall_by_id.get(condition.condition_id, {}),
                "provisional_not_formally_adopted": True,
                "schema_version": VALIDATION_SUMMARY_VERSION,
            }
        )
    return tuple(result)


def export_validation_results(
    run_directory: Path,
    *,
    participants: Sequence[ValidationParticipant],
    conditions: Sequence[ValidationCondition],
    yoke_rows: Sequence[Mapping[str, Any]],
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    analysis: Mapping[str, Sequence[Mapping[str, Any]]],
    baseline_diagnostics: Sequence[Mapping[str, Any]],
) -> dict[str, Path]:
    """Write all required compact artifacts at the run-directory root."""

    named_rows: dict[str, Sequence[Mapping[str, Any]]] = {
        "participant_profiles.csv": tuple(item.to_dict() for item in participants),
        "yoke_map.csv": yoke_rows,
        "bundle_outcomes.csv": tuple(item.to_dict() for item in bundles),
        "session_outcomes.csv": tuple(item.to_dict() for item in sessions),
        "contemporaneous_response.csv": analysis.get("contemporaneous", ()),
        "arm_pair_differences.csv": analysis.get("paired", ()),
        "lagged_coupling.csv": analysis.get("lagged", ()),
        "prospective_selection_enrichment.csv": analysis.get("prospective", ()),
        "prediction_metrics.csv": analysis.get("prediction", ()),
        "permutation_null.csv": analysis.get("permutation", ()),
        "participant_effects.csv": analysis.get("participant_effects", ()),
        "user_type_summary.csv": analysis.get("user_type_summary", ()),
        "overall_summary.csv": analysis.get("overall_summary", ()),
        "condition_summary.csv": condition_summary_rows(
            conditions,
            sessions,
            analysis.get("overall_summary", ()),
        ),
        "invalid_data.csv": invalid_data_rows(
            bundles,
            sessions,
            baseline_diagnostics,
        ),
    }
    written = {
        filename: write_csv(run_directory / filename, rows)
        for filename, rows in named_rows.items()
    }
    digests = {
        filename: {
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for filename, path in sorted(written.items())
    }
    digest_path = run_directory / "digests.json"
    atomic_write_json(
        digest_path,
        {
            "algorithm": "sha256",
            "files": digests,
            "schema_version": "adaptive_placebo_artifact_digests_v1",
        },
    )
    written[digest_path.name] = digest_path
    return written


__all__ = [
    "RESULT_CSV_FILENAMES",
    "condition_summary_rows",
    "export_validation_results",
    "invalid_data_rows",
    "write_csv",
]
