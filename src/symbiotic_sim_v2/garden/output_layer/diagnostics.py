"""Observation-only Stage 5B Garden output CSV exports."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from symbiotic_sim_v2.garden.output_layer.component import GardenOutputComponent
from symbiotic_sim_v2.garden.output_layer.records import (
    GardenQualificationRecord,
    GardenQualifiedBRecord,
    GardenTouchRecord,
)

TOUCH_CSV_FILENAME = "stage_05b_digital_life_touches.csv"
QUALIFICATION_CSV_FILENAME = "stage_05b_garden_qualification.csv"
QUALIFIED_B_CSV_FILENAME = "stage_05b_qualified_b_outputs.csv"

TOUCH_CSV_FIELDS = (
    "signal_index",
    "signal_time_us",
    "arrival_order",
    "arrival_time_us",
    "digital_life_id",
    "b_f",
    "b_a",
    "b_t",
    "b_d",
    "holder_before",
    "holder_after",
    "assigned",
    "exact_time_tie",
    "tie_break_policy",
    "touch_schema_version",
)
QUALIFICATION_CSV_FIELDS = (
    "signal_index",
    "signal_time_us",
    "s",
    "holder_before",
    "holder_after",
    "assigned_this_signal",
    "assignment_touch_time_us",
    "assignment_touch_id",
    "held_from_previous_signal",
    "released_after_second_round",
    "touch_order",
    "active_output",
    "qualified_b_f",
    "qualified_b_a",
    "qualified_b_t",
    "qualified_b_d",
)
QUALIFIED_B_CSV_FIELDS = (
    "signal_index",
    "signal_time_us",
    "effective_time_us",
    "s",
    "active",
    "holder_id",
    "b_f",
    "b_a",
    "b_t",
    "b_d",
    "emission_policy_version",
    "schema_version",
)


@dataclass(frozen=True, slots=True)
class GardenOutputCsvPaths:
    touches: Path
    qualification: Path
    qualified_b: Path


def export_touch_records_csv(
    destination: str | Path,
    records: tuple[GardenTouchRecord, ...],
) -> Path:
    path = _resolve_path(destination, TOUCH_CSV_FILENAME)
    rows = []
    for record in records:
        b_f, b_a, b_t, b_d = record.b
        rows.append(
            {
                "signal_index": record.signal_index,
                "signal_time_us": record.signal_time_us,
                "arrival_order": record.arrival_order,
                "arrival_time_us": record.arrival_time_us,
                "digital_life_id": record.digital_life_id,
                "b_f": b_f,
                "b_a": b_a,
                "b_t": b_t,
                "b_d": b_d,
                "holder_before": record.holder_before,
                "holder_after": record.holder_after,
                "assigned": record.assigned_holder_on_this_touch,
                "exact_time_tie": record.exact_time_tie,
                "tie_break_policy": record.tie_break_policy,
                "touch_schema_version": record.schema_version,
            }
        )
    _write_rows(path, TOUCH_CSV_FIELDS, rows)
    return path


def export_qualification_records_csv(
    destination: str | Path,
    records: tuple[GardenQualificationRecord, ...],
) -> Path:
    path = _resolve_path(destination, QUALIFICATION_CSV_FILENAME)
    rows = []
    for record in records:
        b = record.qualified_b
        rows.append(
            {
                "signal_index": record.signal_index,
                "signal_time_us": record.signal_time_us,
                "s": record.s,
                "holder_before": record.holder_before,
                "holder_after": record.holder_after,
                "assigned_this_signal": record.assigned_this_signal,
                "assignment_touch_time_us": record.assignment_touch_time_us,
                "assignment_touch_id": record.assignment_touch_id,
                "held_from_previous_signal": record.held_from_previous_signal,
                "released_after_second_round": record.released_after_second_round,
                "touch_order": json.dumps(
                    list(record.touch_order),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "active_output": record.active_output,
                "qualified_b_f": None if b is None else b[0],
                "qualified_b_a": None if b is None else b[1],
                "qualified_b_t": None if b is None else b[2],
                "qualified_b_d": None if b is None else b[3],
            }
        )
    _write_rows(path, QUALIFICATION_CSV_FIELDS, rows)
    return path


def export_qualified_b_records_csv(
    destination: str | Path,
    records: tuple[GardenQualifiedBRecord, ...],
) -> Path:
    path = _resolve_path(destination, QUALIFIED_B_CSV_FILENAME)
    rows = []
    for record in records:
        b = record.b
        rows.append(
            {
                "signal_index": record.signal_index,
                "signal_time_us": record.signal_time_us,
                "effective_time_us": record.effective_time_us,
                "s": record.s,
                "active": record.active,
                "holder_id": record.qualification_holder_id,
                "b_f": None if b is None else b[0],
                "b_a": None if b is None else b[1],
                "b_t": None if b is None else b[2],
                "b_d": None if b is None else b[3],
                "emission_policy_version": record.emission_policy_version,
                "schema_version": record.schema_version,
            }
        )
    _write_rows(path, QUALIFIED_B_CSV_FIELDS, rows)
    return path


def export_garden_output_diagnostics(
    destination_directory: str | Path,
    component: GardenOutputComponent,
) -> GardenOutputCsvPaths:
    directory = Path(destination_directory)
    directory.mkdir(parents=True, exist_ok=True)
    return GardenOutputCsvPaths(
        touches=export_touch_records_csv(directory, component.touch_records()),
        qualification=export_qualification_records_csv(
            directory, component.qualification_records()
        ),
        qualified_b=export_qualified_b_records_csv(
            directory, component.qualified_b_records()
        ),
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
