"""Development-only comparison of raw H10 output with virtual-user truth."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.devices.polar_h10.records import RriMeasurementRecord
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds
from symbiotic_sim_v2.virtual_user.diagnostics import HeartbeatRecord

H10_DIAGNOSTIC_CSV_FILENAME = "polar_h10_rri_measurement_diagnostics.csv"
H10_DIAGNOSTIC_NOTICE = (
    "仮想ユーザー内部真値との比較は、理想H10が心拍時刻差を正しく測定しているか"
    "確認する開発用診断です。Gardenへ渡す正式信号はRriMeasurementEventだけです。"
)

H10_DIAGNOSTIC_CSV_FIELDS = (
    "measurement_index",
    "event_id",
    "event_time_us",
    "event_time_seconds",
    "device_id",
    "user_id",
    "previous_beat_index",
    "current_beat_index",
    "previous_heartbeat_time_us",
    "current_heartbeat_time_us",
    "rri_us",
    "rri_ms",
    "diagnostic_true_rri_us",
    "diagnostic_true_rri_ms",
    "absolute_error_us",
    "match",
    "event_schema_version",
    "diagnostic_notice",
)


@dataclass(frozen=True, slots=True)
class RriMeasurementDiagnostic:
    """One explicit join between raw device output and development-only truth."""

    measurement_index: int
    event_id: str
    event_time_us: int
    event_time_seconds: float
    device_id: str
    user_id: str
    previous_beat_index: int
    current_beat_index: int
    previous_heartbeat_time_us: int
    current_heartbeat_time_us: int
    rri_us: int
    rri_ms: float
    diagnostic_true_rri_us: int
    diagnostic_true_rri_ms: float
    absolute_error_us: int
    match: bool
    event_schema_version: str
    diagnostic_notice: str

    def to_dict(self) -> dict[str, Any]:
        """Return a detached mapping matching the diagnostic CSV schema."""

        return asdict(self)


def compare_rri_measurements(
    measurements: tuple[RriMeasurementRecord, ...],
    heartbeat_records: tuple[HeartbeatRecord, ...],
) -> tuple[RriMeasurementDiagnostic, ...]:
    """Join by current beat index without changing either component's records."""

    truth_by_index = {record.beat_index: record for record in heartbeat_records}
    diagnostics: list[RriMeasurementDiagnostic] = []
    for measurement in measurements:
        truth = truth_by_index.get(measurement.current_beat_index)
        if truth is None or truth.true_rri_us is None or truth.true_rri_ms is None:
            raise ValueError(
                f"missing diagnostic truth for beat {measurement.current_beat_index}"
            )
        absolute_error_us = abs(measurement.rri_us - truth.true_rri_us)
        diagnostics.append(
            RriMeasurementDiagnostic(
                measurement_index=measurement.measurement_index,
                event_id=measurement.event_id,
                event_time_us=measurement.event_time_us,
                event_time_seconds=us_to_seconds(measurement.event_time_us),
                device_id=measurement.device_id,
                user_id=measurement.user_id,
                previous_beat_index=measurement.previous_beat_index,
                current_beat_index=measurement.current_beat_index,
                previous_heartbeat_time_us=measurement.previous_heartbeat_time_us,
                current_heartbeat_time_us=measurement.current_heartbeat_time_us,
                rri_us=measurement.rri_us,
                rri_ms=measurement.rri_ms,
                diagnostic_true_rri_us=truth.true_rri_us,
                diagnostic_true_rri_ms=truth.true_rri_ms,
                absolute_error_us=absolute_error_us,
                match=absolute_error_us == 0,
                event_schema_version=measurement.event_schema_version,
                diagnostic_notice=H10_DIAGNOSTIC_NOTICE,
            )
        )
    return tuple(diagnostics)


def export_rri_measurement_diagnostics_csv(
    destination: str | Path,
    measurements: tuple[RriMeasurementRecord, ...],
    heartbeat_records: tuple[HeartbeatRecord, ...],
) -> Path:
    """Write raw device columns beside clearly named development diagnostics."""

    path = Path(destination)
    if path.exists() and path.is_dir():
        path = path / H10_DIAGNOSTIC_CSV_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = compare_rri_measurements(measurements, heartbeat_records)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=H10_DIAGNOSTIC_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(record.to_dict() for record in diagnostics)
    return path
