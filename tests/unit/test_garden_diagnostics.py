"""Observation-only Stage 4 Garden diagnostic CSV tests."""

from __future__ import annotations

import csv
from pathlib import Path

from symbiotic_sim_v2.garden.input_layer.diagnostics import export_garden_input_diagnostics
from symbiotic_sim_v2.garden.input_layer.scenario import create_garden_input_simulation

EXPECTED_RRI_FIELDS = (
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
EXPECTED_EVALUATION_FIELDS = (
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
EXPECTED_SIGNAL_FIELDS = (
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


def read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return tuple(reader.fieldnames or ()), list(reader)


def test_all_csv_exports_have_exact_columns_rows_and_do_not_mutate_digests(tmp_path) -> None:
    simulation = create_garden_input_simulation()
    simulation.engine.run_until_end()
    component = simulation.garden_input_component
    records_before = (
        component.rri_records(),
        component.evaluation_records(),
        component.signal_records(),
    )
    digests_before = (
        component.artifact_digest(),
        component.evaluation_digest(),
        component.signal_digest(),
        simulation.engine.deterministic_digest(),
    )

    paths = export_garden_input_diagnostics(tmp_path, component)
    rri_fields, rri_rows = read_csv(paths.rri_classification)
    evaluation_fields, evaluation_rows = read_csv(paths.evaluations)
    signal_fields, signal_rows = read_csv(paths.signals)

    assert rri_fields == EXPECTED_RRI_FIELDS
    assert evaluation_fields == EXPECTED_EVALUATION_FIELDS
    assert signal_fields == EXPECTED_SIGNAL_FIELDS
    assert len(rri_rows) == 279
    assert len(evaluation_rows) == 4
    assert len(signal_rows) == 241
    assert rri_rows[0]["input_measurement_index"] == "0"
    assert rri_rows[-1]["input_measurement_index"] == "278"
    assert evaluation_rows[0]["reject_reasons"] == "[]"
    assert [row["n_revision"] for row in evaluation_rows] == ["1", "2", "3", "4"]
    assert signal_rows[0]["signal_time_seconds"] == "0.0"
    assert signal_rows[-1]["signal_time_seconds"] == "240.0"
    assert (
        component.rri_records(),
        component.evaluation_records(),
        component.signal_records(),
    ) == records_before
    assert (
        component.artifact_digest(),
        component.evaluation_digest(),
        component.signal_digest(),
        simulation.engine.deterministic_digest(),
    ) == digests_before
