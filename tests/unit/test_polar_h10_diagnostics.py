"""Tests for the explicitly development-only H10/truth comparison adapter."""

from __future__ import annotations

import csv
import dataclasses

import pytest

from symbiotic_sim_v2.devices.polar_h10.diagnostics import (
    H10_DIAGNOSTIC_CSV_FIELDS,
    H10_DIAGNOSTIC_CSV_FILENAME,
    H10_DIAGNOSTIC_NOTICE,
    compare_rri_measurements,
    export_rri_measurement_diagnostics_csv,
)
from symbiotic_sim_v2.devices.polar_h10.records import RriMeasurementRecord
from symbiotic_sim_v2.virtual_user.diagnostics import HeartbeatRecord


def make_truth(
    beat_index: int,
    heartbeat_time_us: int,
    previous_time_us: int | None,
    true_rri_us: int | None,
) -> HeartbeatRecord:
    true_rri_ms = None if true_rri_us is None else true_rri_us / 1_000.0
    return HeartbeatRecord(
        beat_index=beat_index,
        heartbeat_time_us=heartbeat_time_us,
        previous_heartbeat_time_us=previous_time_us,
        true_rri_us=true_rri_us,
        true_rri_ms=true_rri_ms,
        instantaneous_hr_bpm=(
            None if true_rri_ms is None else 60_000.0 / true_rri_ms
        ),
        respiratory_component_ms=None,
        slow_wave_component_ms=None,
        correlated_component_ms=None,
        beat_jitter_component_ms=None,
        unclamped_rri_ms=None,
        final_rri_ms=None,
        clamped=None,
    )


def make_measurement(
    measurement_index: int,
    previous_beat_index: int,
    current_beat_index: int,
    previous_time_us: int,
    current_time_us: int,
) -> RriMeasurementRecord:
    rri_us = current_time_us - previous_time_us
    return RriMeasurementRecord(
        measurement_index=measurement_index,
        event_id=f"evt-rri-{measurement_index}",
        device_id="polar-h10-sim-001",
        user_id="virtual-user-001",
        previous_beat_index=previous_beat_index,
        current_beat_index=current_beat_index,
        previous_heartbeat_time_us=previous_time_us,
        current_heartbeat_time_us=current_time_us,
        rri_us=rri_us,
        rri_ms=rri_us / 1_000.0,
        event_schema_version="rri_measurement_event_v1",
    )


def test_comparison_joins_by_current_beat_index_not_tuple_position() -> None:
    measurements = (
        make_measurement(0, 0, 1, 0, 800_000),
        make_measurement(1, 1, 2, 800_000, 1_620_000),
    )
    truths = (
        make_truth(2, 1_620_000, 800_000, 820_000),
        make_truth(0, 0, None, None),
        make_truth(1, 800_000, 0, 800_000),
    )

    comparisons = compare_rri_measurements(measurements, truths)

    assert [record.current_beat_index for record in comparisons] == [1, 2]
    assert [record.diagnostic_true_rri_us for record in comparisons] == [800_000, 820_000]
    assert [record.absolute_error_us for record in comparisons] == [0, 0]
    assert all(record.match for record in comparisons)
    assert comparisons[0].event_time_us == 800_000
    assert comparisons[0].event_time_seconds == 0.8
    assert H10_DIAGNOSTIC_NOTICE.endswith(
        "Gardenへ渡す正式信号はRriMeasurementEventだけです。"
    )


def test_comparison_reports_mismatch_without_changing_raw_measurement() -> None:
    measurement = make_measurement(0, 0, 1, 0, 820_000)
    truth = make_truth(1, 820_000, 0, 800_000)
    comparison = compare_rri_measurements((measurement,), (truth,))[0]
    assert measurement.rri_us == 820_000
    assert comparison.diagnostic_true_rri_us == 800_000
    assert comparison.absolute_error_us == 20_000
    assert not comparison.match


@pytest.mark.parametrize(
    "truths",
    (
        (),
        (make_truth(2, 820_000, 0, 820_000),),
        (make_truth(1, 820_000, None, None),),
    ),
)
def test_comparison_rejects_missing_or_undefined_truth(
    truths: tuple[HeartbeatRecord, ...],
) -> None:
    measurement = make_measurement(0, 0, 1, 0, 820_000)
    with pytest.raises(ValueError, match="missing diagnostic truth"):
        compare_rri_measurements((measurement,), truths)


def test_diagnostic_records_are_immutable_and_inputs_are_unchanged() -> None:
    measurement = make_measurement(0, 0, 1, 0, 800_000)
    truth = make_truth(1, 800_000, 0, 800_000)
    before_measurement = measurement.to_dict()
    before_truth = truth.to_dict()
    comparison = compare_rri_measurements((measurement,), (truth,))[0]
    assert measurement.to_dict() == before_measurement
    assert truth.to_dict() == before_truth
    with pytest.raises(dataclasses.FrozenInstanceError):
        comparison.match = False  # type: ignore[misc]


def test_csv_has_exact_raw_and_diagnostic_columns_and_preserves_mismatches(tmp_path) -> None:
    measurements = (
        make_measurement(0, 0, 1, 0, 800_000),
        make_measurement(1, 1, 2, 800_000, 1_620_000),
    )
    truths = (
        make_truth(1, 800_000, 0, 800_000),
        make_truth(2, 1_620_000, 800_000, 800_000),
    )
    before_measurements = tuple(record.to_dict() for record in measurements)
    before_truths = tuple(record.to_dict() for record in truths)

    output = export_rri_measurement_diagnostics_csv(tmp_path, measurements, truths)

    assert output.name == H10_DIAGNOSTIC_CSV_FILENAME
    with output.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        assert tuple(reader.fieldnames or ()) == H10_DIAGNOSTIC_CSV_FIELDS
    assert len(rows) == len(measurements)
    assert rows[0]["rri_us"] == "800000"
    assert rows[0]["diagnostic_true_rri_us"] == "800000"
    assert rows[0]["absolute_error_us"] == "0"
    assert rows[0]["match"] == "True"
    assert rows[1]["rri_us"] == "820000"
    assert rows[1]["diagnostic_true_rri_us"] == "800000"
    assert rows[1]["absolute_error_us"] == "20000"
    assert rows[1]["match"] == "False"
    assert all(row["diagnostic_notice"] == H10_DIAGNOSTIC_NOTICE for row in rows)
    assert tuple(record.to_dict() for record in measurements) == before_measurements
    assert tuple(record.to_dict() for record in truths) == before_truths


def test_csv_accepts_an_explicit_file_path(tmp_path) -> None:
    measurement = make_measurement(0, 0, 1, 0, 800_000)
    truth = make_truth(1, 800_000, 0, 800_000)
    destination = tmp_path / "explicit-h10-diagnostics.csv"
    assert (
        export_rri_measurement_diagnostics_csv(
            destination,
            (measurement,),
            (truth,),
        )
        == destination
    )
    assert destination.exists()
