"""Hand-calculated tests for developer-only true RRI and RMSSD diagnostics."""

from __future__ import annotations

import csv
import math

import pytest

from symbiotic_sim_v2.virtual_user.diagnostics import (
    DIAGNOSTIC_CSV_FILENAME,
    HeartbeatRecord,
    export_heartbeat_diagnostics_csv,
    full_run_rmssd_ms,
    instantaneous_hr_bpm,
    rmssd_ms,
    rolling_rmssd_ms,
    rolling_rmssd_series,
    true_rri_ms,
)


def make_records(times_us: list[int]) -> tuple[HeartbeatRecord, ...]:
    records: list[HeartbeatRecord] = []
    previous = None
    for index, heartbeat_time_us in enumerate(times_us):
        interval_us = None if previous is None else heartbeat_time_us - previous
        interval_ms = None if interval_us is None else interval_us / 1_000
        records.append(
            HeartbeatRecord(
                beat_index=index,
                heartbeat_time_us=heartbeat_time_us,
                previous_heartbeat_time_us=previous,
                true_rri_us=interval_us,
                true_rri_ms=interval_ms,
                instantaneous_hr_bpm=(
                    None if interval_ms is None else instantaneous_hr_bpm(interval_ms)
                ),
                respiratory_component_ms=None if index == 0 else 0.0,
                slow_wave_component_ms=None if index == 0 else 0.0,
                correlated_component_ms=None if index == 0 else 0.0,
                beat_jitter_component_ms=None if index == 0 else 0.0,
                unclamped_rri_ms=interval_ms,
                final_rri_ms=interval_ms,
                clamped=None if index == 0 else False,
            )
        )
        previous = heartbeat_time_us
    return tuple(records)


def test_true_rri_and_instantaneous_hr_hand_calculation() -> None:
    assert true_rri_ms(1_000_000, 1_800_000) == 800.0
    assert instantaneous_hr_bpm(800.0) == 75.0


def test_rmssd_hand_fixture() -> None:
    expected = math.sqrt((20.0**2 + (-30.0) ** 2) / 2.0)
    assert rmssd_ms((800.0, 820.0, 790.0)) == pytest.approx(expected)


def test_rmssd_is_undefined_with_fewer_than_two_rri_values() -> None:
    assert rmssd_ms(()) is None
    assert rmssd_ms((800.0,)) is None
    assert full_run_rmssd_ms(make_records([0, 800_000])) is None


def test_full_run_uses_all_true_rri_without_artifact_exclusion() -> None:
    records = make_records([0, 800_000, 3_800_000, 4_600_000])
    assert full_run_rmssd_ms(records) == rmssd_ms((800.0, 3000.0, 800.0))
    assert full_run_rmssd_ms(records) > 2000.0


def test_rolling_window_uses_rri_end_time_inclusive() -> None:
    records = make_records([0, 10_000_000, 20_000_000, 31_000_000, 41_000_000])
    # At 41 seconds the inclusive 30-second window starts at 11 seconds, so
    # RRIs ending at 20, 31, and 41 seconds are retained: 10s, 11s, 10s.
    assert rolling_rmssd_ms(records, 41_000_000) == pytest.approx(1000.0)


def test_rolling_series_marks_undefined_period_as_none() -> None:
    records = make_records([0, 1_000_000, 2_010_000])
    series = rolling_rmssd_series(records)
    assert series[:2] == (None, None)
    assert series[2] == pytest.approx(10.0)


def test_invalid_diagnostic_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        true_rri_ms(100, 100)
    with pytest.raises(ValueError):
        instantaneous_hr_bpm(0.0)
    with pytest.raises(ValueError):
        rolling_rmssd_ms((), -1)


def test_records_do_not_contain_n_nd_or_w_signals() -> None:
    fields = HeartbeatRecord.__dataclass_fields__
    assert "n" not in fields
    assert "nd" not in fields
    assert "w" not in fields


def test_csv_export_has_explicit_true_diagnostic_columns(tmp_path) -> None:
    records = make_records([0, 800_000, 1_620_000])
    output = export_heartbeat_diagnostics_csv(tmp_path, records)
    assert output.name == DIAGNOSTIC_CSV_FILENAME
    with output.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 3
    assert rows[0]["true_rri_ms"] == ""
    assert rows[1]["true_rri_ms"] == "800.0"
    assert rows[2]["rolling_rmssd_30s_ms"] == "20.0"
    assert "heartbeat_time_seconds" in rows[0]


def test_csv_export_does_not_mutate_records(tmp_path) -> None:
    records = make_records([0, 800_000, 1_620_000])
    before = tuple(record.to_dict() for record in records)
    export_heartbeat_diagnostics_csv(tmp_path / "diagnostics.csv", records)
    assert tuple(record.to_dict() for record in records) == before
