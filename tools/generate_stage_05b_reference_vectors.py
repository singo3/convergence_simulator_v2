#!/usr/bin/env python3
"""Generate Stage 5B vectors independently of production modules."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

SPEC_SIZE = 65_759
SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"
HASH01_DENOMINATOR = (1 << 48) - 1
ETA_E = 1.0 - 0.85 ** (1.0 / 180.0)
RHO_E = 1.0 - 0.90 ** (1.0 / 180.0)


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _touch_offset_us(tau: float) -> int:
    return 1 + math.floor(_clip01(tau) * 999_997)


def _calculate_g(life_id: str, holder_id: str | None) -> int:
    return int(holder_id is not None and life_id == holder_id)


def _calculate_e_next(e: float, s: int, g: int) -> float:
    sg = s * g
    return _clip01(e + ETA_E * sg * (1.0 - e) - RHO_E * (1 - sg) * e)


def _w_plus(w: float) -> float:
    return _clip01((w - 0.55) / 0.45)


def _w_minus(w: float) -> float:
    return _clip01((0.45 - w) / 0.45)


def _calculate_q_next(q: float, w: float, g: int) -> float:
    return _clip01(
        q
        + g
        * (
            0.20 * _w_plus(w) * (1.0 - q)
            - 0.20 * _w_minus(w) * q
        )
    )


def _hash01(*parts: object) -> float:
    encoded = ":".join(str(part) for part in parts).encode()
    numerator = int.from_bytes(hashlib.sha256(encoded).digest()[:6], "big")
    return numerator / HASH01_DENOMINATOR


def _initial_tau(life_id: str, n: float) -> float:
    p_intrinsic = 0.35 + 0.30 * _hash01(life_id, "handle-distance")
    birth_phase = 0.000001 * _hash01(life_id, "birth-phase")
    v = (n + 0.5) / 2.0
    return _clip01(p_intrinsic / (p_intrinsic + v + 0.000001) + birth_phase)


def build_reference_vectors() -> dict[str, Any]:
    e_after_active = 0.0
    for _ in range(180):
        e_after_active = _calculate_e_next(e_after_active, 1, 1)
    e_after_closing = _calculate_e_next(e_after_active, 0, 1)

    baseline_n = 0.1641195720593294
    initial_arrivals = []
    for life_id in ("life-blue", "life-green", "life-red"):
        tau = _initial_tau(life_id, baseline_n)
        initial_arrivals.append(
            {
                "digital_life_id": life_id,
                "tau": tau,
                "touch_offset_us": _touch_offset_us(tau),
            }
        )
    actual_order = sorted(
        initial_arrivals,
        key=lambda item: (item["touch_offset_us"], item["digital_life_id"]),
    )

    b = [0.3472222222222222, 0.5, 0.5, 0.5]
    return {
        "schema_version": "stage_05b_reference_vectors_v1",
        "normative_source": {
            "document_version": "v2.0",
            "profile_version": "symbiotic_signal_loop_reference_v1_0",
            "algorithm_version": "adaptive_random_search_confirmed_v1",
            "state_schema_version": "relation_memory_state_v2",
            "size_bytes": SPEC_SIZE,
            "sha256": SPEC_SHA256,
        },
        "simulation_assumptions": {
            "runtime_model_version": "three_digital_life_runtime_v0_1",
            "garden_output_model_version": (
                "relax_with_light_garden_output_qualification_v0_1"
            ),
            "tau_delivery_policy_version": "tau_to_microsecond_touch_delivery_v0_1",
            "tau_delivery": {
                "formula": "1 + floor(clip01(tau) * 999997)",
                "round_finalize_offset_us": 999_999,
                "vectors": [
                    {"tau": value, "expected_touch_offset_us": _touch_offset_us(value)}
                    for value in (0.0, 0.25, 0.5, 0.75, 1.0)
                ],
            },
            "equal_arrival_tie_break": {
                "policy": "lexicographic_digital_life_id_on_equal_arrival_us",
                "arrival_time_us": 60_500_000,
                "registration_input": ["life-red", "life-blue", "life-green"],
                "expected_order": ["life-blue", "life-green", "life-red"],
            },
        },
        "core_vectors": {
            "g": [
                {
                    "digital_life_id": life_id,
                    "qualification_holder_id": holder_id,
                    "expected": _calculate_g(life_id, holder_id),
                }
                for life_id, holder_id in (
                    ("life-green", "life-green"),
                    ("life-red", "life-green"),
                    ("life-blue", None),
                )
            ],
            "e": {
                "eta_e": ETA_E,
                "rho_e": RHO_E,
                "single_accumulation": _calculate_e_next(0.4, 1, 1),
                "single_recovery": _calculate_e_next(0.4, 0, 1),
                "g_zero_recovery": _calculate_e_next(0.4, 1, 0),
                "after_180_active_holder_signals": e_after_active,
                "after_closing_s_zero": e_after_closing,
            },
            "q": [
                {
                    "name": name,
                    "q": 0.5,
                    "w": w,
                    "g": g,
                    "expected": _calculate_q_next(0.5, w, g) if applied else 0.5,
                    "applied": applied,
                    "skip_reason": reason,
                }
                for name, w, g, applied, reason in (
                    ("positive", 1.0, 1, True, "applied"),
                    ("neutral", 0.5, 1, True, "applied"),
                    ("negative", 0.0, 1, True, "applied"),
                    ("g_zero", 1.0, 0, False, "g_zero"),
                    (
                        "baseline_skip",
                        1.0,
                        1,
                        False,
                        "baseline_not_intervention_evaluation",
                    ),
                )
            ],
            "b_round_trip_identity": {
                "first_round_b": b,
                "touch_intent_b": b,
                "touch_event_b": b,
                "garden_record_b": b,
                "returned_b": b,
                "expected_exact_match": True,
            },
            "qualification": [
                {
                    "name": "first_touch_assignment",
                    "holder_before": None,
                    "first_arrival_id": "life-green",
                    "s": 1,
                    "expected_holder_after": "life-green",
                },
                {
                    "name": "hold_during_active_session",
                    "holder_before": "life-green",
                    "first_arrival_id": "life-red",
                    "s": 1,
                    "expected_holder_after": "life-green",
                },
                {
                    "name": "release_after_closing_second_round",
                    "holder_before": "life-green",
                    "s": 0,
                    "closing_second_round_complete": True,
                    "expected_holder_after": None,
                },
            ],
        },
        "standard_fixture": {
            "baseline_n": baseline_n,
            "initial_arrivals": initial_arrivals,
            "expected_first_touch_order": [
                item["digital_life_id"] for item in actual_order
            ],
            "expected_holder": actual_order[0]["digital_life_id"],
            "expected_touch_count": 540,
            "expected_feedback_count": 723,
            "expected_active_output_count": 180,
            "expected_inactive_output_count": 61,
            "expected_final_green_e": e_after_closing,
            "expected_final_green_q": 0.5041270950772643,
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
    default_output = project_root / "docs" / "conformance" / "stage-05b-reference-vectors.json"
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
