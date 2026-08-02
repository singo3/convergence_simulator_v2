#!/usr/bin/env python3
"""Generate independent fixed Stage 6 light-boundary reference vectors."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SPEC_SIZE = 65_759
SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"
HUE_SCALE_DEGREE = 360.0
BLINK_BPM_MIN = 10.0
BLINK_BPM_SPAN = 155.0
VALUE_CENTER = 0.425
VALUE_AMPLITUDE = 0.075


def _map_b(f: float, t: float) -> tuple[float, float, float]:
    """Independently evaluate the two used B axes."""

    hue = HUE_SCALE_DEGREE * f
    return hue, hue % 360.0, BLINK_BPM_MIN + BLINK_BPM_SPAN * t


def _phase(*, elapsed_us: int, bpm: float, start_phase: float = 0.0) -> float:
    """Independently integrate cycles from integer-microsecond elapsed time."""

    return (start_phase + bpm * elapsed_us / 60_000_000) % 1.0


def _value(phase_cycles: float) -> float:
    return VALUE_CENTER + VALUE_AMPLITUDE * math.sin(2.0 * math.pi * phase_cycles)


def build_reference_vectors() -> dict[str, Any]:
    """Return fixed normative, mapping, timing, and standard-run expectations."""

    hue_vectors = [
        {
            "f": f,
            "formal_hue_degree": _map_b(f, 0.5)[0],
            "render_hue_degree": _map_b(f, 0.5)[1],
        }
        for f in (0.0, 0.5, 1.0)
    ]
    bpm_vectors = [
        {"t": t, "blink_bpm": _map_b(0.5, t)[2]}
        for t in (0.0, 0.5, 1.0)
    ]
    first_active_time_us = 60_551_540
    first_active_grid_time_us = 60_560_000
    first_grid_phase = _phase(
        elapsed_us=first_active_grid_time_us - first_active_time_us,
        bpm=87.5,
    )
    command_fields = sorted(
        (
            "active",
            "blink_bpm",
            "command_effective_time_us",
            "command_hold_policy_version",
            "garden_id",
            "hue_degree",
            "inactive_output_policy_version",
            "mapping_version",
            "phase_policy_version",
            "qualification_holder_id",
            "render_hue_degree",
            "saturation",
            "schema_version",
            "source_b_a",
            "source_b_d",
            "source_b_f",
            "source_b_t",
            "source_effective_time_us",
            "source_signal_index",
            "source_signal_time_us",
            "value_amplitude",
            "value_center",
            "value_max",
            "value_min",
            "waveform",
        )
    )
    state_fields = sorted(
        (
            "active",
            "blink_bpm",
            "command_equivalent_to_previous",
            "command_hold_policy_version",
            "device_id",
            "effective_time_us",
            "hue_degree",
            "inactive_output_policy_version",
            "mapping_version",
            "phase_cycles_at_start",
            "phase_policy_version",
            "physical_parameters_changed",
            "qualification_holder_id",
            "render_hue_degree",
            "saturation",
            "schema_version",
            "source_b_a",
            "source_b_d",
            "source_b_f",
            "source_b_t",
            "source_signal_index",
            "source_signal_time_us",
            "value_amplitude",
            "value_at_start",
            "value_center",
            "value_max",
            "value_min",
            "waveform",
            "phase_reset",
        )
    )
    return {
        "schema_version": "stage_06_reference_vectors_v1",
        "normative_source": {
            "document_version": "v2.0",
            "profile_version": "symbiotic_signal_loop_reference_v1_0",
            "algorithm_version": "adaptive_random_search_confirmed_v1",
            "state_schema_version": "relation_memory_state_v2",
            "size_bytes": SPEC_SIZE,
            "sha256": SPEC_SHA256,
        },
        "simulation_assumptions": {
            "project_version": "0.7.0",
            "garden_light_mapper_model_version": (
                "relax_with_light_b_to_i_mapper_v0_1"
            ),
            "mapping_version": "relax_with_light_pc_hsv_sine_mapping_v0_1",
            "light_command_schema_version": "light_command_event_v1",
            "virtual_light_device_model_version": "virtual_pc_light_device_v0_1",
            "light_stimulus_state_schema_version": (
                "light_stimulus_state_event_v1"
            ),
            "light_stimulus_segment_schema_version": "light_stimulus_segment_v1",
            "phase_policy_version": "continuous_phase_integrator_v0_1",
            "command_hold_policy_version": "hold_until_next_command_v0_1",
            "inactive_output_policy_version": "light_off_black_v0_1",
            "waveform_sample_policy_version": "fixed_virtual_grid_20ms_v0_1",
        },
        "mapping_vectors": {
            "hue": hue_vectors,
            "blink_bpm": bpm_vectors,
            "standard_green": {
                "source_b": [125.0 / 360.0, 0.5, 0.5, 0.5],
                "formal_hue_degree": 125.0,
                "render_hue_degree": 125.0,
                "blink_bpm": 87.5,
                "saturation": 1.0,
                "value_center": VALUE_CENTER,
                "value_amplitude": VALUE_AMPLITUDE,
                "value_min": 0.35,
                "value_max": 0.5,
                "waveform": "sine",
            },
            "a_d_invariance": {
                "first_b": [0.25, 0.0, 0.75, 0.0],
                "second_b": [0.25, 1.0, 0.75, 1.0],
                "expected_hue_degree": 90.0,
                "expected_blink_bpm": 126.25,
                "physical_output_equal": True,
            },
            "inactive": {
                "active": False,
                "holder_id": None,
                "source_b": None,
                "hue_degree": None,
                "render_hue_degree": None,
                "blink_bpm": None,
                "saturation": 0.0,
                "value_center": 0.0,
                "value_amplitude": 0.0,
                "value_min": 0.0,
                "value_max": 0.0,
                "waveform": "off",
            },
        },
        "phase_and_waveform_vectors": [
            {"phase_cycles": 0.0, "value": 0.425},
            {"phase_cycles": 0.25, "value": 0.50},
            {"phase_cycles": 0.50, "value": 0.425},
            {"phase_cycles": 0.75, "value": 0.35},
            {"phase_cycles": 1.0, "value": 0.425},
        ],
        "transition_vectors": {
            "first_inactive": {
                "phase_cycles_at_start": None,
                "value_at_start": 0.0,
                "phase_reset": False,
                "equivalent_to_previous": False,
                "physical_parameters_changed": True,
            },
            "inactive_reassertion": {
                "phase_cycles_at_start": None,
                "value_at_start": 0.0,
                "phase_reset": False,
                "equivalent_to_previous": True,
                "physical_parameters_changed": False,
            },
            "inactive_to_active": {
                "phase_cycles_at_start": 0.0,
                "value_at_start": 0.425,
                "phase_reset": True,
                "equivalent_to_previous": False,
                "physical_parameters_changed": True,
            },
            "same_active_command": {
                "phase_reset": False,
                "phase_continues": True,
                "equivalent_to_previous": True,
                "physical_parameters_changed": False,
            },
            "changed_bpm": {
                "phase_reset": False,
                "phase_continues": True,
                "equivalent_to_previous": False,
                "physical_parameters_changed": True,
            },
            "changed_hue": {
                "phase_reset": False,
                "phase_continues": True,
                "equivalent_to_previous": False,
                "physical_parameters_changed": True,
            },
            "active_to_inactive": {
                "phase_cycles_at_start": None,
                "value_at_start": 0.0,
                "phase_reset": False,
                "equivalent_to_previous": False,
                "physical_parameters_changed": True,
            },
            "inactive_to_active_again": {
                "phase_cycles_at_start": 0.0,
                "value_at_start": 0.425,
                "phase_reset": True,
            },
        },
        "formal_boundaries": {
            "qualified_b": {
                "event_type": "garden_qualified_b",
                "source": "garden_output",
                "schema_version": "garden_qualified_b_event_v2",
                "priority": 65,
            },
            "light_command": {
                "event_type": "light_command",
                "source": "garden_light_mapper",
                "schema_version": "light_command_event_v1",
                "priority": 66,
                "exact_payload_fields_sorted": command_fields,
            },
            "light_stimulus_state": {
                "event_type": "light_stimulus_state",
                "source": "virtual_light_device",
                "schema_version": "light_stimulus_state_event_v1",
                "priority": 67,
                "exact_payload_fields_sorted": state_fields,
                "formal_rgb_present": False,
            },
            "round_finalize_priority": 70,
            "active_ordered_priorities": [60, 65, 66, 67, 70, 80],
            "inactive_ordered_priorities": [31, 65, 66, 67, 80],
            "closing_ordered_priorities": [25, 30, 31, 65, 66, 67, 80, 90, 100],
        },
        "fixed_grid": {
            "sample_interval_us": 20_000,
            "sample_count": 12_001,
            "samples": [
                {
                    "sample_index": 0,
                    "time_us": 0,
                    "active": False,
                    "phase_cycles": None,
                    "value": 0.0,
                },
                {
                    "sample_index": 3_027,
                    "time_us": 60_540_000,
                    "active": False,
                    "phase_cycles": None,
                    "value": 0.0,
                },
                {
                    "sample_index": 3_028,
                    "time_us": first_active_grid_time_us,
                    "active": True,
                    "phase_cycles": first_grid_phase,
                    "value": _value(first_grid_phase),
                },
                {
                    "sample_index": 12_000,
                    "time_us": 240_000_000,
                    "active": False,
                    "phase_cycles": None,
                    "value": 0.0,
                },
            ],
            "engine_sample_event_count": 0,
        },
        "standard_scenario": {
            "qualified_b_input_count": 241,
            "light_command_count": 241,
            "light_stimulus_state_event_count": 241,
            "segment_count": 240,
            "active_command_count": 180,
            "inactive_command_count": 61,
            "active_segment_count": 180,
            "inactive_segment_count": 60,
            "first_active_effective_time_us": first_active_time_us,
            "last_active_effective_time_us": 239_589_850,
            "closing_inactive_effective_time_us": 240_000_000,
            "first_active_holder_id": "life-green",
            "first_active_phase_cycles": 0.0,
            "first_active_value": 0.425,
            "phase_reset_count": 1,
            "phase_continuation_count": 179,
            "equivalent_command_count": 238,
            "physical_parameter_change_count": 3,
            "final_active": False,
            "final_value": 0.0,
            "final_phase": None,
            "executed_event_count": 3_287,
            "command_digest": (
                "306648650d4b286a48b3f9188f7fd640764b05fb135c581c4b9d00b487d06020"
            ),
            "stimulus_state_digest": (
                "1dbf214e1448802a665031f73fb798cdbf04471210aeddf438c68b72b616265e"
            ),
            "segment_digest": (
                "9dabc1b018b52f9be603ba164655f3c5fa79ff4f6579ae8a6bfd48047d8fd763"
            ),
            "waveform_sample_digest": (
                "a075f488a588d7d2f78548e4ae339e7cac59c88f8e4508b2a89f0ca6e36cc0c0"
            ),
            "full_event_digest": (
                "f2ef166cd2bbea252d2c848b7f67d80cad1840534fe736d792087639b5b2a833"
            ),
        },
    }


def _encoded_vectors() -> str:
    return json.dumps(
        build_reference_vectors(),
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    default_output = project_root / "docs" / "conformance" / "stage-06-reference-vectors.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = _encoded_vectors()
    if args.stdout:
        sys.stdout.write(encoded)
        return 0
    if args.check:
        if not args.output.exists():
            return 1
        return 0 if args.output.read_text(encoding="utf-8") == encoded else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
