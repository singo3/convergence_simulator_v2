"""Observation-only CSV exports for immutable Stage 5A records."""

from __future__ import annotations

import csv
from pathlib import Path

from symbiotic_sim_v2.digital_life.records import (
    DigitalLifeEvaluationUpdateRecord,
    DigitalLifeFirstRoundRecord,
)
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds

FIRST_ROUND_CSV_FILENAME = "single_digital_life_first_round_diagnostics.csv"
EVALUATION_UPDATE_CSV_FILENAME = "single_digital_life_evaluation_updates.csv"

FIRST_ROUND_CSV_FIELDS = (
    "signal_index",
    "signal_time_us",
    "signal_time_seconds",
    "digital_life_id",
    "role",
    "phase",
    "bundle_index",
    "S",
    "N_current",
    "N_baseline_session",
    "revision",
    "is_new_valid_evaluation",
    "source_evaluation_id",
    "Nd",
    "W",
    "P",
    "p_intrinsic",
    "E",
    "q",
    "V",
    "k_F",
    "k_A",
    "k_T",
    "k_D",
    "B_F",
    "B_A",
    "B_T",
    "B_D",
    "tau",
    "birth_phase",
    "G_status",
    "touch_dispatched",
)

EVALUATION_UPDATE_CSV_FIELDS = (
    "evaluation_id",
    "evaluation_kind",
    "bundle_index",
    "event_time_us",
    "quality",
    "is_valid",
    "n_revision",
    "N",
    "N_baseline_session",
    "previous_Nd",
    "new_Nd",
    "previous_W",
    "new_W",
    "applied",
    "skip_reason",
)


def export_first_round_diagnostics_csv(
    destination: str | Path,
    records: tuple[DigitalLifeFirstRoundRecord, ...],
) -> Path:
    """Write one row per formal signal without changing component state."""

    path = _resolve_path(destination, FIRST_ROUND_CSV_FILENAME)
    rows = []
    for record in records:
        k_f, k_a, k_t, k_d = record.k_current
        rows.append(
            {
                "signal_index": record.signal_index,
                "signal_time_us": record.signal_time_us,
                "signal_time_seconds": us_to_seconds(record.signal_time_us),
                "digital_life_id": record.digital_life_id,
                "role": record.role,
                "phase": record.phase,
                "bundle_index": record.bundle_index,
                "S": record.s,
                "N_current": record.n_current,
                "N_baseline_session": record.n_baseline_session,
                "revision": record.valid_evaluation_revision,
                "is_new_valid_evaluation": record.is_new_valid_evaluation,
                "source_evaluation_id": record.source_evaluation_id,
                "Nd": record.nd,
                "W": record.w,
                "P": record.p,
                "p_intrinsic": record.p_intrinsic,
                "E": record.e,
                "q": record.q,
                "V": record.v,
                "k_F": k_f,
                "k_A": k_a,
                "k_T": k_t,
                "k_D": k_d,
                "B_F": record.b_f,
                "B_A": record.b_a,
                "B_T": record.b_t,
                "B_D": record.b_d,
                "tau": record.tau,
                "birth_phase": record.birth_phase,
                "G_status": record.g_status,
                "touch_dispatched": record.touch_dispatched,
            }
        )
    _write_rows(path, FIRST_ROUND_CSV_FIELDS, rows)
    return path


def export_evaluation_updates_csv(
    destination: str | Path,
    records: tuple[DigitalLifeEvaluationUpdateRecord, ...],
) -> Path:
    """Write evaluation applications and rejections without mutating records."""

    path = _resolve_path(destination, EVALUATION_UPDATE_CSV_FILENAME)
    rows = [
        {
            "evaluation_id": record.evaluation_id,
            "evaluation_kind": record.evaluation_kind,
            "bundle_index": record.bundle_index,
            "event_time_us": record.event_time_us,
            "quality": record.quality,
            "is_valid": record.is_valid,
            "n_revision": record.n_revision,
            "N": record.n,
            "N_baseline_session": record.n_baseline_session,
            "previous_Nd": record.previous_nd,
            "new_Nd": record.new_nd,
            "previous_W": record.previous_w,
            "new_W": record.new_w,
            "applied": record.applied,
            "skip_reason": record.skip_reason,
        }
        for record in records
    ]
    _write_rows(path, EVALUATION_UPDATE_CSV_FIELDS, rows)
    return path


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
