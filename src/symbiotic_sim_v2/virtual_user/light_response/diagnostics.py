"""CSV exports for explicitly diagnostic Stage 7 light-response records."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from symbiotic_sim_v2.simulation.time_utils import us_to_seconds
from symbiotic_sim_v2.virtual_user.light_response.records import (
    LightResponseDynamicsEpochRecord,
    LightResponseSample,
    LightResponseSegment,
    LightResponsiveHeartbeatRecord,
    LightStimulusReceiptRecord,
)

LIGHT_STIMULUS_RECEIPTS_CSV_FILENAME = "stage_07_light_stimulus_receipts.csv"
LIGHT_RESPONSE_SEGMENTS_CSV_FILENAME = "stage_07_light_response_segments.csv"
LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FILENAME = (
    "stage_07_response_dynamics_epochs.csv"
)
LIGHT_RESPONSIVE_HEARTBEATS_CSV_FILENAME = "stage_07_light_responsive_heartbeats.csv"
LIGHT_RESPONSE_SAMPLES_CSV_FILENAME = "stage_07_light_response_samples_100ms.csv"

LIGHT_STIMULUS_RECEIPTS_CSV_FIELDS = (
    "receipt_index",
    "event_time_us",
    "event_time_seconds",
    "active",
    "physical_render_hue_degree",
    "physical_saturation",
    "physical_value_center",
    "physical_value_amplitude",
    "physical_value_min",
    "physical_value_max",
    "physical_blink_bpm",
    "physical_waveform",
    "hue_match",
    "bpm_match",
    "preference_match",
    "response_target",
    "physical_parameters_changed",
    "target_changed",
    "audit_segment_index",
    "response_dynamics_epoch_index",
    "audit_split_reason",
    "response_before",
    "response_after_at_same_time",
    "provenance_used_by_physiology",
    "projection_version",
    "preference_model_version",
    "physical_stimulus_change_policy_version",
    "physical_light_parameter_signature_version",
    "segment_split_policy_version",
)
LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS = (
    "segment_index",
    "start_time_us",
    "end_time_us",
    "duration_us",
    "light_active",
    "render_hue_degree",
    "saturation",
    "value_center",
    "value_amplitude",
    "value_min",
    "value_max",
    "blink_bpm",
    "waveform",
    "hue_match",
    "bpm_match",
    "preference_match",
    "response_target",
    "response_dynamics_epoch_index",
    "physical_parameters_changed_at_start",
    "target_changed_at_start",
    "split_reason",
    "physical_stimulus_change_policy_version",
    "physical_light_parameter_signature_version",
    "segment_split_policy_version",
    "preference_model_version",
    "schema_version",
)
LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FIELDS = (
    "epoch_index",
    "start_time_us",
    "end_time_us",
    "duration_us",
    "response_target",
    "response_at_start",
    "response_at_end",
    "time_constant_seconds",
    "target_changed_at_start",
    "response_dynamics_version",
    "schema_version",
)
LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS = (
    "beat_index",
    "heartbeat_time_us",
    "previous_heartbeat_time_us",
    "true_rri_us",
    "true_rri_ms",
    "instantaneous_hr_bpm",
    "light_active_at_heartbeat",
    "perceived_render_hue_degree",
    "perceived_blink_bpm",
    "preference_match",
    "response_target",
    "response_level",
    "base_mean_rri_ms",
    "effective_mean_rri_ms",
    "mean_rri_increase_ms",
    "base_respiratory_amplitude_ms",
    "effective_respiratory_amplitude_ms",
    "respiratory_amplitude_gain_ms",
    "respiratory_component_ms",
    "slow_wave_component_ms",
    "correlated_component_ms",
    "beat_jitter_component_ms",
    "final_rri_ms",
    "clamped",
    "causality_policy_version",
    "schema_version",
)
LIGHT_RESPONSE_SAMPLES_CSV_FIELDS = (
    "sample_index",
    "time_us",
    "time_seconds",
    "light_active",
    "render_hue_degree",
    "blink_bpm",
    "preference_match",
    "response_target",
    "response_level",
    "effective_respiratory_amplitude_ms",
    "effective_mean_rri_ms",
)


class LightResponseDiagnosticSource(Protocol):
    def light_receipt_records(self) -> tuple[LightStimulusReceiptRecord, ...]: ...

    def response_segments(self) -> tuple[LightResponseSegment, ...]: ...

    def response_dynamics_epoch_records(
        self,
    ) -> tuple[LightResponseDynamicsEpochRecord, ...]: ...

    def responsive_heartbeat_records(
        self,
    ) -> tuple[LightResponsiveHeartbeatRecord, ...]: ...

    def response_samples(self) -> tuple[LightResponseSample, ...]: ...


def export_light_stimulus_receipts_csv(
    destination: str | Path,
    records: Sequence[LightStimulusReceiptRecord],
) -> Path:
    path = _output_path(destination, LIGHT_STIMULUS_RECEIPTS_CSV_FILENAME)
    rows = (
        {
            "receipt_index": record.receipt_index,
            "event_time_us": record.event_time_us,
            "event_time_seconds": us_to_seconds(record.event_time_us),
            "active": record.active,
            "physical_render_hue_degree": record.physical_stimulus.render_hue_degree,
            "physical_saturation": record.physical_stimulus.saturation,
            "physical_value_center": record.physical_stimulus.value_center,
            "physical_value_amplitude": record.physical_stimulus.value_amplitude,
            "physical_value_min": record.physical_stimulus.value_min,
            "physical_value_max": record.physical_stimulus.value_max,
            "physical_blink_bpm": record.physical_stimulus.blink_bpm,
            "physical_waveform": record.physical_stimulus.waveform,
            "hue_match": record.hue_match,
            "bpm_match": record.bpm_match,
            "preference_match": record.preference_match,
            "response_target": record.response_target,
            "physical_parameters_changed": record.physical_parameters_changed,
            "target_changed": record.target_changed,
            "audit_segment_index": record.audit_segment_index,
            "response_dynamics_epoch_index": record.response_dynamics_epoch_index,
            "audit_split_reason": record.audit_split_reason,
            "response_before": record.response_before,
            "response_after_at_same_time": record.response_after_at_same_time,
            "provenance_used_by_physiology": record.provenance_used_by_physiology,
            "projection_version": record.physical_projection_version,
            "preference_model_version": record.preference_model_version,
            "physical_stimulus_change_policy_version": (
                record.physical_stimulus_change_policy_version
            ),
            "physical_light_parameter_signature_version": (
                record.physical_light_parameter_signature_version
            ),
            "segment_split_policy_version": record.segment_split_policy_version,
        }
        for record in records
    )
    return _write_rows(path, LIGHT_STIMULUS_RECEIPTS_CSV_FIELDS, rows)


def export_light_response_segments_csv(
    destination: str | Path,
    records: Sequence[LightResponseSegment],
) -> Path:
    path = _output_path(destination, LIGHT_RESPONSE_SEGMENTS_CSV_FILENAME)
    rows = (
        {
            field: getattr(record, field)
            for field in LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS
        }
        for record in records
    )
    return _write_rows(path, LIGHT_RESPONSE_SEGMENTS_CSV_FIELDS, rows)


def export_light_response_dynamics_epochs_csv(
    destination: str | Path,
    records: Sequence[LightResponseDynamicsEpochRecord],
) -> Path:
    path = _output_path(destination, LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FILENAME)
    rows = (
        {
            field: getattr(record, field)
            for field in LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FIELDS
        }
        for record in records
    )
    return _write_rows(path, LIGHT_RESPONSE_DYNAMICS_EPOCHS_CSV_FIELDS, rows)


def export_light_responsive_heartbeats_csv(
    destination: str | Path,
    records: Sequence[LightResponsiveHeartbeatRecord],
) -> Path:
    path = _output_path(destination, LIGHT_RESPONSIVE_HEARTBEATS_CSV_FILENAME)
    rows = (
        {
            field: getattr(record, field)
            for field in LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS
        }
        for record in records
    )
    return _write_rows(path, LIGHT_RESPONSIVE_HEARTBEATS_CSV_FIELDS, rows)


def export_light_response_samples_csv(
    destination: str | Path,
    records: Sequence[LightResponseSample],
) -> Path:
    path = _output_path(destination, LIGHT_RESPONSE_SAMPLES_CSV_FILENAME)
    rows = (
        {field: getattr(record, field) for field in LIGHT_RESPONSE_SAMPLES_CSV_FIELDS}
        for record in records
    )
    return _write_rows(path, LIGHT_RESPONSE_SAMPLES_CSV_FIELDS, rows)


def export_light_response_diagnostics(
    destination: str | Path,
    source: LightResponseDiagnosticSource,
) -> tuple[Path, Path, Path, Path, Path]:
    """Export all five files without mutating component state or digests."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    return (
        export_light_stimulus_receipts_csv(root, source.light_receipt_records()),
        export_light_response_segments_csv(root, source.response_segments()),
        export_light_response_dynamics_epochs_csv(
            root,
            source.response_dynamics_epoch_records(),
        ),
        export_light_responsive_heartbeats_csv(
            root,
            source.responsive_heartbeat_records(),
        ),
        export_light_response_samples_csv(root, source.response_samples()),
    )


def _output_path(destination: str | Path, filename: str) -> Path:
    path = Path(destination)
    if path.exists() and path.is_dir():
        path = path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_rows(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: Iterable[Mapping[str, object]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path
