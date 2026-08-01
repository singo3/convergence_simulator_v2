"""Developer-only true heartbeat diagnostics; not H10 or Garden signals."""

from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROLLING_RMSSD_WINDOW_US = 30_000_000
DIAGNOSTIC_CSV_FILENAME = "virtual_user_true_heartbeat_diagnostics.csv"


@dataclass(frozen=True, slots=True)
class HeartbeatRecord:
    """Immutable internal truth record retained only for development diagnostics."""

    beat_index: int
    heartbeat_time_us: int
    previous_heartbeat_time_us: int | None
    true_rri_us: int | None
    true_rri_ms: float | None
    instantaneous_hr_bpm: float | None
    respiratory_component_ms: float | None
    slow_wave_component_ms: float | None
    correlated_component_ms: float | None
    beat_jitter_component_ms: float | None
    unclamped_rri_ms: float | None
    final_rri_ms: float | None
    clamped: bool | None

    def to_dict(self) -> dict[str, Any]:
        """Return a detached diagnostic record mapping."""

        return asdict(self)


def true_rri_ms(previous_time_us: int, heartbeat_time_us: int) -> float:
    """Calculate true RRI from two strictly increasing heartbeat timestamps."""

    interval_us = heartbeat_time_us - previous_time_us
    if interval_us <= 0:
        raise ValueError("heartbeat times must be strictly increasing")
    return interval_us / 1_000.0


def instantaneous_hr_bpm(rri_ms: float) -> float:
    """Calculate diagnostic instantaneous heart rate from true RRI."""

    if not math.isfinite(rri_ms) or rri_ms <= 0:
        raise ValueError("rri_ms must be finite and positive")
    return 60_000.0 / rri_ms


def rmssd_ms(rri_values_ms: list[float] | tuple[float, ...]) -> float | None:
    """Calculate RMSSD, returning undefined for fewer than two RRIs."""

    if len(rri_values_ms) < 2:
        return None
    squared_differences = [
        (current - previous) ** 2
        for previous, current in zip(rri_values_ms, rri_values_ms[1:], strict=False)
    ]
    return math.sqrt(sum(squared_differences) / len(squared_differences))


def full_run_rmssd_ms(records: tuple[HeartbeatRecord, ...]) -> float | None:
    """Calculate developer-only full-run RMSSD from every true RRI without filtering."""

    values = tuple(record.true_rri_ms for record in records if record.true_rri_ms is not None)
    return rmssd_ms(values)


def rolling_rmssd_ms(
    records: tuple[HeartbeatRecord, ...],
    current_time_us: int,
    window_us: int = ROLLING_RMSSD_WINDOW_US,
) -> float | None:
    """Calculate RMSSD for RRIs ending within the inclusive trailing time window."""

    if current_time_us < 0 or window_us <= 0:
        raise ValueError("current_time_us and window_us must define a positive window")
    window_start_us = current_time_us - window_us
    values = tuple(
        record.true_rri_ms
        for record in records
        if record.true_rri_ms is not None
        and window_start_us <= record.heartbeat_time_us <= current_time_us
    )
    return rmssd_ms(values)


def rolling_rmssd_series(
    records: tuple[HeartbeatRecord, ...],
) -> tuple[float | None, ...]:
    """Return rolling 30-second RMSSD aligned one-to-one with heartbeat records."""

    return tuple(
        rolling_rmssd_ms(records[: index + 1], record.heartbeat_time_us)
        for index, record in enumerate(records)
    )


def export_heartbeat_diagnostics_csv(
    destination: str | Path,
    records: tuple[HeartbeatRecord, ...],
) -> Path:
    """Write explicitly named true-value diagnostics, never H10 measurement data."""

    path = Path(destination)
    if path.exists() and path.is_dir():
        path = path / DIAGNOSTIC_CSV_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    rolling_values = rolling_rmssd_series(records)
    fieldnames = (
        "beat_index",
        "heartbeat_time_us",
        "heartbeat_time_seconds",
        "true_rri_us",
        "true_rri_ms",
        "instantaneous_hr_bpm",
        "respiratory_component_ms",
        "slow_wave_component_ms",
        "correlated_component_ms",
        "beat_jitter_component_ms",
        "unclamped_rri_ms",
        "final_rri_ms",
        "clamped",
        "rolling_rmssd_30s_ms",
    )
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for record, rolling_value in zip(records, rolling_values, strict=True):
            diagnostic_values = record.to_dict()
            diagnostic_values.pop("previous_heartbeat_time_us")
            writer.writerow(
                {
                    **diagnostic_values,
                    "heartbeat_time_seconds": record.heartbeat_time_us / 1_000_000,
                    "rolling_rmssd_30s_ms": rolling_value,
                }
            )
    return path
