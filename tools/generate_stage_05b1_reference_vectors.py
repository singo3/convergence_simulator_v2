#!/usr/bin/env python3
"""Generate fixed Stage 5B.1 boundary vectors without production imports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SPEC_SIZE = 65_759
SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"


def build_reference_vectors() -> dict[str, Any]:
    """Return fixed expectations for the corrected formal output boundary."""

    touch_fields = [
        "b_a",
        "b_d",
        "b_f",
        "b_t",
        "digital_life_id",
        "schema_version",
        "signal_index",
        "signal_time_us",
    ]
    qualified_b_fields = [
        "active",
        "b_a",
        "b_d",
        "b_f",
        "b_t",
        "effective_time_us",
        "emission_policy_version",
        "garden_id",
        "qualification_holder_id",
        "s",
        "schema_version",
        "signal_index",
        "signal_time_us",
    ]
    return {
        "schema_version": "stage_05b1_reference_vectors_v1",
        "normative_source": {
            "document_version": "v2.0",
            "profile_version": "symbiotic_signal_loop_reference_v1_0",
            "algorithm_version": "adaptive_random_search_confirmed_v1",
            "state_schema_version": "relation_memory_state_v2",
            "size_bytes": SPEC_SIZE,
            "sha256": SPEC_SHA256,
        },
        "simulation_assumptions": {
            "project_version": "0.6.1",
            "runtime_model_version": "three_digital_life_runtime_v0_2",
            "garden_output_model_version": (
                "relax_with_light_garden_output_qualification_v0_2"
            ),
            "touch_schema_version": "digital_life_touch_event_v2",
            "qualified_b_schema_version": "garden_qualified_b_event_v2",
            "qualified_b_emission_policy_version": (
                "qualified_b_on_holder_touch_v0_1"
            ),
            "tau_delivery_policy_version": "tau_to_microsecond_touch_delivery_v0_1",
            "feedback_schema_version": "garden_interoceptive_feedback_event_v1",
            "qualification_state_schema_version": "garden_qualification_state_v1",
            "second_round_record_schema_version": (
                "digital_life_second_round_record_v1"
            ),
        },
        "formal_boundaries": {
            "touch": {
                "event_type": "digital_life_touch",
                "source": "digital_life",
                "priority": 60,
                "exact_payload_fields_sorted": touch_fields,
                "forbidden_payload_fields": [
                    "E",
                    "G",
                    "N",
                    "Nd",
                    "P",
                    "V",
                    "W",
                    "birth_phase",
                    "candidate",
                    "evaluation_value",
                    "k",
                    "p_intrinsic",
                    "q",
                    "role",
                    "tau",
                    "touch_offset_us",
                    "trial",
                ],
            },
            "qualified_b": {
                "event_type": "garden_qualified_b",
                "source": "garden_output",
                "priority": 65,
                "exact_payload_fields_sorted": qualified_b_fields,
                "scheduled_time_equals_effective_time": True,
            },
            "round_finalize_priority": 70,
            "feedback_priority": 80,
            "holder_release_priority": 90,
        },
        "timing_vectors": {
            "first_active_holder_assignment": {
                "signal_index": 60,
                "signal_time_us": 60_000_000,
                "arrivals": [
                    {"digital_life_id": "life-green", "arrival_time_us": 60_551_540},
                    {"digital_life_id": "life-blue", "arrival_time_us": 60_617_297},
                    {"digital_life_id": "life-red", "arrival_time_us": 60_641_486},
                ],
                "expected_holder_id": "life-green",
                "expected_effective_time_us": 60_551_540,
                "expected_active_output_count": 1,
                "round_finalize_time_us": 60_999_999,
            },
            "subsequent_holder_first": {
                "signal_index": 61,
                "signal_time_us": 61_000_000,
                "holder_before": "life-green",
                "arrivals": [
                    {"digital_life_id": "life-green", "arrival_time_us": 61_551_763},
                    {"digital_life_id": "life-blue", "arrival_time_us": 61_617_297},
                    {"digital_life_id": "life-red", "arrival_time_us": 61_641_486},
                ],
                "expected_effective_time_us": 61_551_763,
                "expected_active_output_count": 1,
                "round_finalize_time_us": 61_999_999,
            },
            "subsequent_holder_second": {
                "signal_index": 62,
                "signal_time_us": 62_000_000,
                "holder_before": "life-green",
                "arrivals": [
                    {"digital_life_id": "life-red", "arrival_time_us": 62_100_000},
                    {"digital_life_id": "life-green", "arrival_time_us": 62_200_000},
                    {"digital_life_id": "life-blue", "arrival_time_us": 62_300_000},
                ],
                "non_holder_arrival_emits": False,
                "expected_effective_time_us": 62_200_000,
                "expected_active_output_count": 1,
                "round_finalize_time_us": 62_999_999,
            },
            "subsequent_holder_third": {
                "signal_index": 63,
                "signal_time_us": 63_000_000,
                "holder_before": "life-green",
                "arrivals": [
                    {"digital_life_id": "life-blue", "arrival_time_us": 63_100_000},
                    {"digital_life_id": "life-red", "arrival_time_us": 63_200_000},
                    {"digital_life_id": "life-green", "arrival_time_us": 63_300_000},
                ],
                "non_holder_arrival_emits": False,
                "expected_effective_time_us": 63_300_000,
                "expected_active_output_count": 1,
                "round_finalize_time_us": 63_999_999,
            },
            "exact_tie_assignment": {
                "signal_index": 64,
                "signal_time_us": 64_000_000,
                "arrival_time_us": 64_500_000,
                "registration_input": ["life-red", "life-blue", "life-green"],
                "expected_delivery_order": ["life-blue", "life-green", "life-red"],
                "expected_holder_id": "life-blue",
                "expected_effective_time_us": 64_500_000,
                "expected_active_output_count": 1,
            },
            "baseline_inactive": {
                "signal_index": 0,
                "signal_time_us": 0,
                "expected_effective_time_us": 0,
                "active": False,
                "qualification_holder_id": None,
                "b": None,
            },
            "closing_inactive": {
                "signal_index": 240,
                "signal_time_us": 240_000_000,
                "expected_effective_time_us": 240_000_000,
                "active": False,
                "qualification_holder_id": None,
                "b": None,
                "ordered_priorities": [31, 65, 80, 80, 80, 90, 100],
            },
        },
        "runtime_roster": {
            "injected_ids": ["life-zeta", "life-alpha", "life-mu"],
            "expected_normalized_ids": ["life-alpha", "life-mu", "life-zeta"],
            "garden_receives_role_mapping": False,
            "required_count": 3,
        },
        "standard_fixture_regression": {
            "touch_count": 540,
            "feedback_count": 723,
            "qualified_b_count": 241,
            "active_output_count": 180,
            "inactive_output_count": 61,
            "assignment_count": 1,
            "release_count": 1,
            "holder_id": "life-green",
            "holder_assignment_signal_index": 60,
            "holder_assignment_time_us": 60_551_540,
            "first_active_qualified_b_effective_time_us": 60_551_540,
            "last_active_qualified_b_effective_time_us": 239_589_850,
            "closing_inactive_effective_time_us": 240_000_000,
            "holder_touch_to_qualified_b_delay_us_max": 0,
            "active_qualified_b_at_holder_touch_count": 180,
            "active_qualified_b_at_round_finalize_count": 0,
            "per_life_first_round_count": 241,
            "per_life_second_round_count": 241,
            "green_q_update_count": 3,
            "other_q_update_count": 0,
            "final_holder_id": None,
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
    default_output = (
        project_root / "docs" / "conformance" / "stage-05b1-reference-vectors.json"
    )
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
        return 0 if args.output.read_text(encoding="utf-8") == encoded else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
