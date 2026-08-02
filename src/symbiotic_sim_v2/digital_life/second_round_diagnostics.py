"""Observation-only CSV export for immutable Stage 5B second-round records."""

from __future__ import annotations

import csv
from pathlib import Path

from symbiotic_sim_v2.digital_life.second_round_records import (
    DigitalLifeSecondRoundRecord,
)

SECOND_ROUND_CSV_FILENAME = "stage_05b_digital_life_second_round.csv"

SECOND_ROUND_CSV_FIELDS = (
    "signal_index",
    "signal_time_us",
    "digital_life_id",
    "role",
    "s",
    "holder_id",
    "g",
    "w",
    "e_before",
    "e_after",
    "q_before",
    "q_after",
    "q_update_applied",
    "q_skip_reason",
    "b_match",
    "attribution_source",
    "k_update_status",
    "closing_evaluation_attribution",
)


def export_second_round_diagnostics_csv(
    destination: str | Path,
    records: tuple[DigitalLifeSecondRoundRecord, ...],
) -> Path:
    """Write Stage 5B records without altering any live component state."""

    path = _resolve_path(destination)
    rows = [
        {
            "signal_index": record.signal_index,
            "signal_time_us": record.signal_time_us,
            "digital_life_id": record.digital_life_id,
            "role": record.role,
            "s": record.s,
            "holder_id": record.qualification_holder_id,
            "g": record.g,
            "w": record.w,
            "e_before": record.e_before,
            "e_after": record.e_after,
            "q_before": record.q_before,
            "q_after": record.q_after,
            "q_update_applied": record.q_update_applied,
            "q_skip_reason": record.q_skip_reason,
            "b_match": record.b_match,
            "attribution_source": record.attribution_source,
            "k_update_status": record.k_update_status,
            "closing_evaluation_attribution": (
                record.closing_evaluation_attribution
            ),
        }
        for record in records
    ]
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SECOND_ROUND_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _resolve_path(destination: str | Path) -> Path:
    path = Path(destination)
    if (path.exists() and path.is_dir()) or not path.suffix:
        path = path / SECOND_ROUND_CSV_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
