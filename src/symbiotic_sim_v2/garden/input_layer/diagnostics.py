"""Observation-only CSV exports for Stage 4 Garden input records."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from symbiotic_sim_v2.garden.input_layer.component import GardenInputComponent
from symbiotic_sim_v2.garden.input_layer.records import (
    GardenEvaluationRecord,
    GardenInputSignalRecord,
    GardenRriRecord,
)
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

GARDEN_RRI_CSV_FILENAME = "garden_input_rri_classification_diagnostics.csv"
GARDEN_EVALUATION_CSV_FILENAME = "garden_input_evaluations.csv"
GARDEN_SIGNAL_CSV_FILENAME = "garden_input_signals.csv"

GARDEN_RRI_CSV_FIELDS = (
    "input_measurement_index",
    "input_event_id",
    "event_time_us",
    "event_time_seconds",
    "device_id",
    "user_id",
    "raw_rri_us",
    "raw_rri_ms",
    "phase",
    "bundle_index",
    "window_role",
    "evaluation_id",
    "artifact",
    "artifact_reason",
    "median_history_count_before",
    "median_rri_us_before",
    "relative_deviation",
    "accepted_into_valid_history",
    "included_in_evaluation_window",
    "membership_policy",
)
GARDEN_EVALUATION_CSV_FIELDS = (
    "evaluation_id",
    "evaluation_kind",
    "bundle_index",
    "window_start_us",
    "window_end_us",
    "total_rri_count",
    "artifact_rri_count",
    "valid_rri_count",
    "artifact_rate",
    "rmssd_ms",
    "n",
    "quality",
    "is_valid",
    "reject_reasons",
    "n_revision",
    "baseline_id",
)
GARDEN_SIGNAL_CSV_FIELDS = (
    "signal_index",
    "signal_time_us",
    "signal_time_seconds",
    "s",
    "phase",
    "bundle_index",
    "window_role",
    "n_current",
    "n_available",
    "n_baseline_session",
    "baseline_available",
    "latest_valid_evaluation_id",
    "valid_evaluation_revision",
    "session_status",
)


@dataclass(frozen=True, slots=True)
class GardenDiagnosticCsvPaths:
    rri_classification: Path
    evaluations: Path
    signals: Path


def export_garden_rri_csv(
    destination: str | Path,
    records: tuple[GardenRriRecord, ...],
) -> Path:
    path = _resolve_path(destination, GARDEN_RRI_CSV_FILENAME)
    rows = []
    for record in records:
        row = record.to_dict()
        row["event_time_seconds"] = us_to_seconds(record.event_time_us)
        rows.append(row)
    _write_rows(path, GARDEN_RRI_CSV_FIELDS, rows)
    return path


def export_garden_evaluations_csv(
    destination: str | Path,
    records: tuple[GardenEvaluationRecord, ...],
) -> Path:
    path = _resolve_path(destination, GARDEN_EVALUATION_CSV_FILENAME)
    rows = []
    for record in records:
        row = record.to_dict()
        row.pop("schema_version")
        row["reject_reasons"] = json.dumps(
            list(record.reject_reasons),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        rows.append(row)
    _write_rows(path, GARDEN_EVALUATION_CSV_FIELDS, rows)
    return path


def export_garden_signals_csv(
    destination: str | Path,
    records: tuple[GardenInputSignalRecord, ...],
) -> Path:
    path = _resolve_path(destination, GARDEN_SIGNAL_CSV_FILENAME)
    rows = []
    for record in records:
        row = record.to_dict()
        row.pop("garden_id")
        row.pop("session_id")
        row.pop("schema_version")
        row["signal_time_seconds"] = us_to_seconds(record.signal_time_us)
        rows.append(row)
    _write_rows(path, GARDEN_SIGNAL_CSV_FIELDS, rows)
    return path


def export_garden_input_diagnostics(
    destination_directory: str | Path,
    component: GardenInputComponent,
) -> GardenDiagnosticCsvPaths:
    """Write all three CSVs without mutating component state or digests."""

    directory = Path(destination_directory)
    directory.mkdir(parents=True, exist_ok=True)
    return GardenDiagnosticCsvPaths(
        rri_classification=export_garden_rri_csv(directory, component.rri_records()),
        evaluations=export_garden_evaluations_csv(directory, component.evaluation_records()),
        signals=export_garden_signals_csv(directory, component.signal_records()),
    )


def _resolve_path(destination: str | Path, filename: str) -> Path:
    path = Path(destination)
    if (path.exists() and path.is_dir()) or not path.suffix:
        path = path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_rows(
    path: Path,
    fields: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
