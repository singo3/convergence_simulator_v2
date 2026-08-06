#!/usr/bin/env python3
"""Generate fixed Stage 8A.3.1 vectors without importing production code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "conformance" / "stage-08a31-reference-vectors.json"


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def participant_seed(base_seed: int, user_type_id: str, index: int) -> int:
    key = (
        f"{base_seed}:stage8a3:participant-physiology:{user_type_id}:{index}"
    ).encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big")


def vectors() -> dict[str, Any]:
    eta_target = 1.0 - (1.0 - 0.15) ** (1.0 / 180.0)
    eta_reference = 1.0 - 0.85 ** (1.0 / 180.0)
    rho_reference = 1.0 - 0.90 ** (1.0 / 180.0)
    a, b, c, d = 1.0, 2.0, 4.0, 8.0
    sigma_gradual = b - a
    sigma_full = d - c
    recovery_sigma100 = c - a
    recovery_sigma050 = d - b
    interaction = sigma_full - sigma_gradual
    interaction_alt = recovery_sigma050 - recovery_sigma100
    conditions = [
        ["v2_reference", "gradual_reference_only", 1.0],
        ["v2_recovery_sigma050", "gradual_reference_only", 0.5],
        ["full_recovery_sigma100", "unselected_full_recovery", 1.0],
        ["provisional_f15_sigma050", "unselected_full_recovery", 0.5],
    ]
    result = {
        "schema_version": "stage_08a31_reference_vectors_v1",
        "production_implementation_imported": False,
        "versions": {
            "project_version": "0.14.0",
            "validation_model": (
                "fatigue_recovery_sigma_factorial_validation_v0_1"
            ),
            "condition": "fatigue_recovery_sigma_factorial_condition_v1",
            "analysis": "participant_paired_two_by_two_factorial_analysis_v0_1",
        },
        "eta_equivalence": {
            "target": 0.15,
            "active_signal_count": 180,
            "target_derived_eta": eta_target,
            "v2_reference_eta": eta_reference,
            "equal": eta_target == eta_reference,
            "hex": eta_reference.hex(),
            "rho_reference": rho_reference,
            "rho_hex": rho_reference.hex(),
        },
        "conditions": [
            {
                "condition_id": condition_id,
                "session_end_recovery_policy": recovery,
                "sigma_multiplier": sigma,
                "effective_selected_session_fatigue_target": 0.15,
                "eta_selected": eta_reference,
                "rho": rho_reference,
                "formal_spec_adoption": False,
            }
            for condition_id, recovery, sigma in conditions
        ],
        "factorial_effect_fixture": {
            "values": {"A": a, "B": b, "C": c, "D": d},
            "sigma_effect_gradual_B_minus_A": sigma_gradual,
            "sigma_effect_full_D_minus_C": sigma_full,
            "recovery_effect_sigma100_C_minus_A": recovery_sigma100,
            "recovery_effect_sigma050_D_minus_B": recovery_sigma050,
            "interaction": interaction,
            "interaction_alt": interaction_alt,
            "interaction_identity": interaction == interaction_alt,
        },
        "random_cache": {
            "fields": [
                "participant_id",
                "user_type_id",
                "physiology_seed",
                "maximum_sessions",
                "random_output_version",
                "code_fingerprint",
            ],
            "condition_id_in_key": False,
            "recovery_in_key": False,
            "sigma_in_key": False,
            "shared_condition_count": 4,
        },
        "participant_pairing": {
            "base_master_seed": 20260806,
            "user_type_id": "green_hue_dominant_broad_bpm",
            "participant_index": 0,
            "physiology_seed": participant_seed(
                20260806,
                "green_hue_dominant_broad_bpm",
                0,
            ),
            "condition_in_seed": False,
            "arm_in_seed": False,
        },
        "positive_participant_count": {
            "effects_ms": [1.0, -0.25, 0.0, 2.0, 0.5],
            "strict_positive_count": 3,
            "strict_positive_rate": 0.6,
        },
        "type_failure_detection": {
            "means_ms": {"type-a": 0.5, "type-b": -0.1, "type-c": 0.0},
            "failed_types": ["type-b", "type-c"],
            "strict_positive": True,
        },
        "recommendation": {
            "baseline": "v2_reference",
            "passing_alternative": "v2_recovery_sigma050",
            "preferred_result": "alternative_preferred_for_human_mvp",
            "no_passing_alternative_result": "v2_reference_remains_preferred",
            "opaque_score": False,
            "formal_spec_adoption": False,
        },
        "participant_chart_fixture": {
            "layout": "4_conditions_by_2_arms",
            "panel_count": 8,
            "x": "session_index",
            "y": "blink_bpm",
            "fill": "actual_hue",
            "shapes": {
                "life-red": "circle",
                "life-green": "triangle",
                "life-blue": "square",
            },
            "bundle_offsets": [-0.2, 0.0, 0.2],
            "trial_translucent": True,
        },
        "user_type_heatmap_fixture": {
            "rows": 9,
            "columns": 4,
            "condition_order": [item[0] for item in conditions],
            "metrics": [
                "late_delta_rmssd_advantage_ms",
                "positive_participant_rate",
                "selection_enrichment",
                "lagged_coupling",
            ],
        },
        "plan_counts": {
            "smoke": {
                "autonomous": 96,
                "shared_random": 24,
                "logical": 192,
                "actual": 120,
            },
            "standard": {
                "autonomous": 8640,
                "shared_random": 2160,
                "logical": 17280,
                "actual": 10800,
            },
            "robust": {
                "autonomous": 43200,
                "shared_random": 10800,
                "logical": 86400,
                "actual": 54000,
            },
        },
        "finite_values": all(
            math.isfinite(value)
            for value in (eta_target, eta_reference, rho_reference, interaction)
        ),
    }
    result["reference_vector_digest"] = digest(result)
    return result


def encoded() -> str:
    return json.dumps(vectors(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = encoded()
    if args.check:
        return (
            0
            if TARGET.is_file()
            and TARGET.read_text(encoding="utf-8") == expected
            else 1
        )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
