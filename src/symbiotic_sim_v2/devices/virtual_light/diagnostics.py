"""Observation-only Stage 6 light command, state, segment, and grid CSVs."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from symbiotic_sim_v2.devices.virtual_light.component import (
    VirtualLightDeviceComponent,
)
from symbiotic_sim_v2.devices.virtual_light.records import (
    LightStimulusSegment,
    LightStimulusStateRecord,
    LightWaveformSample,
)

LIGHT_COMMANDS_CSV_FILENAME = "stage_06_light_commands.csv"
LIGHT_STIMULUS_STATES_CSV_FILENAME = "stage_06_light_stimulus_states.csv"
LIGHT_STIMULUS_SEGMENTS_CSV_FILENAME = "stage_06_light_stimulus_segments.csv"
LIGHT_WAVEFORM_SAMPLES_CSV_FILENAME = (
    "stage_06_light_waveform_samples_20ms.csv"
)

LIGHT_COMMAND_CSV_FIELDS = (
    "command_index",
    "effective_time_us",
    "effective_time_seconds",
    "source_signal_index",
    "source_signal_time_us",
    "active",
    "holder_id",
    "source_b_f",
    "source_b_a",
    "source_b_t",
    "source_b_d",
    "hue_degree",
    "render_hue_degree",
    "saturation",
    "value_center",
    "value_amplitude",
    "value_min",
    "value_max",
    "blink_bpm",
    "waveform",
    "phase_policy_version",
    "command_hold_policy_version",
    "inactive_output_policy_version",
    "mapping_version",
    "schema_version",
)
LIGHT_STIMULUS_STATE_CSV_FIELDS = (
    "state_index",
    "effective_time_us",
    "source_signal_index",
    "active",
    "holder_id",
    "hue_degree",
    "render_hue_degree",
    "saturation",
    "blink_bpm",
    "waveform",
    "phase_cycles_at_start",
    "value_at_start",
    "phase_reset",
    "physical_parameters_changed",
    "command_equivalent_to_previous",
    "schema_version",
)
LIGHT_STIMULUS_SEGMENT_CSV_FIELDS = (
    "segment_index",
    "start_time_us",
    "end_time_us",
    "duration_us",
    "active",
    "source_signal_index",
    "holder_id",
    "source_b_f",
    "source_b_a",
    "source_b_t",
    "source_b_d",
    "hue_degree",
    "render_hue_degree",
    "saturation",
    "blink_bpm",
    "waveform",
    "phase_cycles_at_start",
    "phase_cycles_at_end",
    "value_at_start",
    "value_at_end",
    "schema_version",
)
LIGHT_WAVEFORM_SAMPLE_CSV_FIELDS = (
    "sample_index",
    "time_us",
    "time_seconds",
    "active",
    "source_signal_index",
    "holder_id",
    "hue_degree",
    "render_hue_degree",
    "saturation",
    "blink_bpm",
    "phase_cycles",
    "value",
)


@dataclass(frozen=True, slots=True)
class LightDiagnosticCsvPaths:
    commands: Path
    stimulus_states: Path
    stimulus_segments: Path
    waveform_samples: Path


def export_light_commands_csv(
    destination: str | Path,
    records: Sequence[object],
) -> Path:
    """Write mapper or device command records through the same formal schema."""

    path = _resolve_path(destination, LIGHT_COMMANDS_CSV_FILENAME)
    rows: list[dict[str, object]] = []
    for record in records:
        effective_time_us = _command_effective_time_us(record)
        b = record.source_b
        rows.append(
            {
                "command_index": record.command_index,
                "effective_time_us": effective_time_us,
                "effective_time_seconds": effective_time_us / 1_000_000.0,
                "source_signal_index": record.source_signal_index,
                "source_signal_time_us": record.source_signal_time_us,
                "active": record.active,
                "holder_id": record.qualification_holder_id,
                "source_b_f": None if b is None else b[0],
                "source_b_a": None if b is None else b[1],
                "source_b_t": None if b is None else b[2],
                "source_b_d": None if b is None else b[3],
                "hue_degree": record.hue_degree,
                "render_hue_degree": record.render_hue_degree,
                "saturation": record.saturation,
                "value_center": record.value_center,
                "value_amplitude": record.value_amplitude,
                "value_min": record.value_min,
                "value_max": record.value_max,
                "blink_bpm": record.blink_bpm,
                "waveform": record.waveform,
                "phase_policy_version": record.phase_policy_version,
                "command_hold_policy_version": record.command_hold_policy_version,
                "inactive_output_policy_version": record.inactive_output_policy_version,
                "mapping_version": record.mapping_version,
                "schema_version": record.schema_version,
            }
        )
    _write_rows(path, LIGHT_COMMAND_CSV_FIELDS, rows)
    return path


def export_light_stimulus_states_csv(
    destination: str | Path,
    records: Sequence[LightStimulusStateRecord],
) -> Path:
    path = _resolve_path(destination, LIGHT_STIMULUS_STATES_CSV_FILENAME)
    rows = [
        {
            "state_index": record.state_index,
            "effective_time_us": record.effective_time_us,
            "source_signal_index": record.source_signal_index,
            "active": record.active,
            "holder_id": record.qualification_holder_id,
            "hue_degree": record.hue_degree,
            "render_hue_degree": record.render_hue_degree,
            "saturation": record.saturation,
            "blink_bpm": record.blink_bpm,
            "waveform": record.waveform,
            "phase_cycles_at_start": record.phase_cycles_at_start,
            "value_at_start": record.value_at_start,
            "phase_reset": record.phase_reset,
            "physical_parameters_changed": record.physical_parameters_changed,
            "command_equivalent_to_previous": (
                record.command_equivalent_to_previous
            ),
            "schema_version": record.schema_version,
        }
        for record in records
    ]
    _write_rows(path, LIGHT_STIMULUS_STATE_CSV_FIELDS, rows)
    return path


def export_light_stimulus_segments_csv(
    destination: str | Path,
    records: Sequence[LightStimulusSegment],
) -> Path:
    path = _resolve_path(destination, LIGHT_STIMULUS_SEGMENTS_CSV_FILENAME)
    rows: list[dict[str, object]] = []
    for record in records:
        b = record.source_b
        rows.append(
            {
                "segment_index": record.segment_index,
                "start_time_us": record.start_time_us,
                "end_time_us": record.end_time_us,
                "duration_us": record.duration_us,
                "active": record.active,
                "source_signal_index": record.source_signal_index,
                "holder_id": record.qualification_holder_id,
                "source_b_f": None if b is None else b[0],
                "source_b_a": None if b is None else b[1],
                "source_b_t": None if b is None else b[2],
                "source_b_d": None if b is None else b[3],
                "hue_degree": record.hue_degree,
                "render_hue_degree": record.render_hue_degree,
                "saturation": record.saturation,
                "blink_bpm": record.blink_bpm,
                "waveform": record.waveform,
                "phase_cycles_at_start": record.phase_cycles_at_start,
                "phase_cycles_at_end": record.phase_cycles_at_end,
                "value_at_start": record.value_at_start,
                "value_at_end": record.value_at_end,
                "schema_version": record.schema_version,
            }
        )
    _write_rows(path, LIGHT_STIMULUS_SEGMENT_CSV_FIELDS, rows)
    return path


def export_light_waveform_samples_csv(
    destination: str | Path,
    records: Sequence[LightWaveformSample],
) -> Path:
    path = _resolve_path(destination, LIGHT_WAVEFORM_SAMPLES_CSV_FILENAME)
    _write_rows(
        path,
        LIGHT_WAVEFORM_SAMPLE_CSV_FIELDS,
        [record.to_dict() for record in records],
    )
    return path


def export_light_diagnostics(
    destination_directory: str | Path,
    component: VirtualLightDeviceComponent,
    command_records: Sequence[object] | None = None,
) -> LightDiagnosticCsvPaths:
    """Export all four observational diagnostics without mutating device state."""

    if not isinstance(component, VirtualLightDeviceComponent):
        raise TypeError("component must be a VirtualLightDeviceComponent")
    directory = Path(destination_directory)
    directory.mkdir(parents=True, exist_ok=True)
    commands = component.command_records() if command_records is None else command_records
    return LightDiagnosticCsvPaths(
        commands=export_light_commands_csv(directory, commands),
        stimulus_states=export_light_stimulus_states_csv(
            directory, component.stimulus_state_records()
        ),
        stimulus_segments=export_light_stimulus_segments_csv(
            directory, component.stimulus_segments()
        ),
        waveform_samples=export_light_waveform_samples_csv(
            directory, component.waveform_samples()
        ),
    )


def _command_effective_time_us(record: object) -> int:
    if hasattr(record, "effective_time_us"):
        return int(record.effective_time_us)
    return int(record.command_effective_time_us)


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


# Backward-readable plural aliases for callers that mirror the filenames.
LIGHT_COMMANDS_CSV_FIELDS = LIGHT_COMMAND_CSV_FIELDS
LIGHT_STIMULUS_STATES_CSV_FIELDS = LIGHT_STIMULUS_STATE_CSV_FIELDS
LIGHT_STIMULUS_SEGMENTS_CSV_FIELDS = LIGHT_STIMULUS_SEGMENT_CSV_FIELDS
LIGHT_WAVEFORM_SAMPLES_CSV_FIELDS = LIGHT_WAVEFORM_SAMPLE_CSV_FIELDS
