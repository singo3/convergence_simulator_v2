#!/usr/bin/env python3
"""Generate production-independent Stage 7 light-response reference vectors."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SPEC_SIZE = 65_759
SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"
FIRST_ACTIVE_TIME_US = 60_551_540
SIMULATION_END_TIME_US = 240_000_000
ONSET_TIME_CONSTANT_SECONDS = 8.0
RECOVERY_TIME_CONSTANT_SECONDS = 12.0
BASE_MEAN_RRI_MS = 60_000.0 / 70.0
BASE_RESPIRATORY_AMPLITUDE_MS = 35.0
MAXIMUM_MEAN_RRI_INCREASE_MS = 15.0
MAXIMUM_RESPIRATORY_AMPLITUDE_GAIN_MS = 30.0


def circular_hue_distance(first_degree: float, second_degree: float) -> float:
    """Evaluate the shortest independent distance on a 360-degree circle."""

    raw_difference = abs(first_degree - second_degree)
    return min(raw_difference, 360.0 - raw_difference)


def gaussian_match(difference: float, sigma: float) -> float:
    """Evaluate the fixed zero-centered Gaussian preference function."""

    return math.exp(-0.5 * (difference / sigma) ** 2)


def first_order_response(
    *,
    target: float,
    response_at_start: float,
    elapsed_seconds: float,
    time_constant_seconds: float,
) -> float:
    """Evaluate one analytic first-order response interval."""

    return target + (response_at_start - target) * math.exp(
        -elapsed_seconds / time_constant_seconds
    )


def aligned_response_at(time_us: int) -> float:
    """Evaluate the aligned standard onset from its formal effective time."""

    if time_us <= FIRST_ACTIVE_TIME_US:
        return 0.0
    elapsed_seconds = (time_us - FIRST_ACTIVE_TIME_US) / 1_000_000
    return first_order_response(
        target=1.0,
        response_at_start=0.0,
        elapsed_seconds=elapsed_seconds,
        time_constant_seconds=ONSET_TIME_CONSTANT_SECONDS,
    )


def build_reference_vectors() -> dict[str, Any]:
    """Return fixed formula, boundary, causality, and control expectations."""

    hue_359_to_1 = circular_hue_distance(359.0, 1.0)
    hue_match = gaussian_match(4.0, 5.0)
    bpm_match = gaussian_match(37.5, 30.0)
    response_90s = aligned_response_at(90_000_000)
    response_120s = aligned_response_at(120_000_000)
    response_180s = aligned_response_at(180_000_000)
    response_240s_before_closing = aligned_response_at(SIMULATION_END_TIME_US)
    onset_after_eight_seconds = first_order_response(
        target=1.0,
        response_at_start=0.0,
        elapsed_seconds=8.0,
        time_constant_seconds=ONSET_TIME_CONSTANT_SECONDS,
    )
    recovery_after_twelve_seconds = first_order_response(
        target=0.0,
        response_at_start=onset_after_eight_seconds,
        elapsed_seconds=12.0,
        time_constant_seconds=RECOVERY_TIME_CONSTANT_SECONDS,
    )
    responsive_fixture_level = 0.5
    responsive_fixture_mean = (
        BASE_MEAN_RRI_MS
        + MAXIMUM_MEAN_RRI_INCREASE_MS * responsive_fixture_level
    )
    responsive_fixture_amplitude = (
        BASE_RESPIRATORY_AMPLITUDE_MS
        + MAXIMUM_RESPIRATORY_AMPLITUDE_GAIN_MS * responsive_fixture_level
    )
    responsive_fixture_components = {
        "mean_rri_ms": responsive_fixture_mean,
        "respiratory_component_ms": responsive_fixture_amplitude,
        "slow_wave_component_ms": 8.0,
        "correlated_component_ms": -3.0,
        "beat_jitter_component_ms": 1.25,
    }
    responsive_fixture_unclamped = sum(responsive_fixture_components.values())

    return {
        "schema_version": "stage_07_reference_vectors_v1",
        "normative_source": {
            "document_version": "v2.0",
            "profile_version": "symbiotic_signal_loop_reference_v1_0",
            "algorithm_version": "adaptive_random_search_confirmed_v1",
            "state_schema_version": "relation_memory_state_v2",
            "size_bytes": SPEC_SIZE,
            "sha256": SPEC_SHA256,
        },
        "simulation_assumptions": {
            "project_version": "0.8.0",
            "light_responsive_user_model_version": (
                "stationary_light_responsive_virtual_user_v0_1"
            ),
            "physical_projection_version": "physical_light_stimulus_projection_v0_1",
            "preference_model_version": (
                "stationary_hue_bpm_gaussian_preference_v0_1"
            ),
            "response_dynamics_version": "first_order_light_response_v0_1",
            "physiology_coupling_version": (
                "light_response_rsa_mean_rri_coupling_v0_1"
            ),
            "heartbeat_causality_policy_version": (
                "sample_light_response_at_heartbeat_start_v0_1"
            ),
            "input_schema_version": "light_stimulus_state_event_v1",
            "response_segment_schema_version": "light_response_segment_v1",
            "responsive_heartbeat_schema_version": (
                "light_responsive_heartbeat_record_v1"
            ),
            "diagnostic_sampling_policy_version": "fixed_virtual_grid_100ms_v0_1",
        },
        "preference_vectors": {
            "circular_hue_distance": [
                {"first_degree": 0.0, "second_degree": 360.0, "distance": 0.0},
                {
                    "first_degree": 359.0,
                    "second_degree": 1.0,
                    "distance": hue_359_to_1,
                },
                {"first_degree": 125.0, "second_degree": 125.0, "distance": 0.0},
            ],
            "aligned": {
                "render_hue_degree": 125.0,
                "preferred_hue_degree": 125.0,
                "blink_bpm": 87.5,
                "preferred_blink_bpm": 87.5,
                "hue_match": 1.0,
                "bpm_match": 1.0,
                "preference_match": 1.0,
                "response_target": 1.0,
            },
            "off_center": {
                "hue_difference_degree": 4.0,
                "hue_sigma_degree": 5.0,
                "hue_match": hue_match,
                "bpm_difference": 37.5,
                "blink_sigma_bpm": 30.0,
                "bpm_match": bpm_match,
                "preference_match": hue_match * bpm_match,
            },
            "inactive": {
                "hue_match": None,
                "bpm_match": None,
                "preference_match": 0.0,
                "response_target": 0.0,
            },
        },
        "response_vectors": {
            "initial_response": 0.0,
            "onset_after_one_tau": onset_after_eight_seconds,
            "recovery_after_one_tau": recovery_after_twelve_seconds,
            "continuity_at_target_change": {
                "response_before": onset_after_eight_seconds,
                "response_after_same_time": onset_after_eight_seconds,
            },
            "same_target_continues_without_new_segment": True,
            "checkpoints": {
                "response_at_90s": response_90s,
                "response_at_120s": response_120s,
                "response_at_180s": response_180s,
                "response_at_240s_before_closing": response_240s_before_closing,
            },
        },
        "physiology_vectors": {
            "base_mean_rri_ms": BASE_MEAN_RRI_MS,
            "base_respiratory_amplitude_ms": BASE_RESPIRATORY_AMPLITUDE_MS,
            "response_zero": {
                "effective_mean_rri_ms": BASE_MEAN_RRI_MS,
                "effective_respiratory_amplitude_ms": (
                    BASE_RESPIRATORY_AMPLITUDE_MS
                ),
                "stage_2_formula_exact": True,
            },
            "response_one": {
                "effective_mean_rri_ms": (
                    BASE_MEAN_RRI_MS + MAXIMUM_MEAN_RRI_INCREASE_MS
                ),
                "effective_respiratory_amplitude_ms": (
                    BASE_RESPIRATORY_AMPLITUDE_MS
                    + MAXIMUM_RESPIRATORY_AMPLITUDE_GAIN_MS
                ),
            },
            "response_at_90s": {
                "response_level": response_90s,
                "effective_mean_rri_ms": (
                    BASE_MEAN_RRI_MS
                    + MAXIMUM_MEAN_RRI_INCREASE_MS * response_90s
                ),
                "effective_respiratory_amplitude_ms": (
                    BASE_RESPIRATORY_AMPLITUDE_MS
                    + MAXIMUM_RESPIRATORY_AMPLITUDE_GAIN_MS * response_90s
                ),
            },
            "responsive_rri_manual_fixture": {
                "response_level": responsive_fixture_level,
                "components": responsive_fixture_components,
                "unclamped_rri_ms": responsive_fixture_unclamped,
                "final_rri_ms": responsive_fixture_unclamped,
                "rri_us_half_up": math.floor(responsive_fixture_unclamped * 1_000 + 0.5),
            },
        },
        "causality_vectors": {
            "policy": "sample_light_response_at_heartbeat_start_v0_1",
            "heartbeat_priority": 40,
            "light_stimulus_state_priority": 67,
            "same_time_order": ["heartbeat", "light_stimulus_state"],
            "pending_heartbeat_rescheduled": False,
            "first_active_effective_time_us": FIRST_ACTIVE_TIME_US,
            "first_light_affected_interval_rule": (
                "first heartbeat after active is the interval start"
            ),
        },
        "projection_boundary": {
            "allowed_fields": sorted(
                (
                    "active",
                    "blink_bpm",
                    "effective_time_us",
                    "phase_cycles_at_start",
                    "render_hue_degree",
                    "saturation",
                    "value_amplitude",
                    "value_center",
                    "value_max",
                    "value_min",
                    "waveform",
                )
            ),
            "excluded_provenance_fields": sorted(
                (
                    "qualification_holder_id",
                    "source_b",
                    "source_signal_index",
                )
            ),
            "provenance_used_by_physiology": False,
        },
        "control": {
            "maximum_respiratory_amplitude_gain_ms": 0.0,
            "maximum_mean_rri_increase_ms": 0.0,
            "stage_6_heartbeat_digest": (
                "dfc32d05a372482a81a40ffbb9dc721aed8edcada4709a4dcb86e76719ddf17b"
            ),
            "formal_event_stream_equals_stage_6": True,
            "light_receipts_recorded": True,
        },
        "standard_scenario": {
            "preset": "aligned_green_center",
            "first_active_effective_time_us": FIRST_ACTIVE_TIME_US,
            "first_active_hue_degree": 125.0,
            "first_active_blink_bpm": 87.5,
            "first_active_preference_match": 1.0,
            "light_stimulus_input_count": 241,
            "response_sample_interval_us": 100_000,
            "response_sample_count": 2_401,
            "simulation_end_time_us": SIMULATION_END_TIME_US,
            "preference_stationary": True,
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
    default_output = project_root / "docs" / "conformance" / "stage-07-reference-vectors.json"
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
