#!/usr/bin/env python3
"""Generate Stage 5A conformance vectors without importing product code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any

getcontext().prec = 80

HASH01_DENOMINATOR = (1 << 48) - 1
SPEC_SIZE = 65_759
SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"


def _hash01_entry(name: str, *parts: object) -> dict[str, Any]:
    joined = ":".join(str(part) for part in parts)
    encoded = joined.encode("utf-8")
    digest = hashlib.sha256(encoded).digest()
    numerator = int.from_bytes(digest[:6], byteorder="big", signed=False)
    exact = Decimal(numerator) / Decimal(HASH01_DENOMINATOR)
    expected = numerator / HASH01_DENOMINATOR
    return {
        "name": name,
        "parts": list(parts),
        "joined_text": joined,
        "utf8_hex": encoded.hex(),
        "sha256_hex": digest.hex(),
        "prefix48_hex": digest[:6].hex(),
        "numerator": numerator,
        "denominator": HASH01_DENOMINATOR,
        "exact_decimal": str(exact),
        "expected": expected,
        "expected_binary64_hex": expected.hex(),
    }


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _calculate_nd(current: str, baseline: str, delta_n: str = "0.10") -> float:
    result = Decimal("0.5") + (
        Decimal(current) - Decimal(baseline)
    ) / (Decimal(2) * Decimal(delta_n))
    return float(min(Decimal(1), max(Decimal(0), result)))


def _calculate_p(s: int, p_intrinsic: float) -> float:
    return 1.0 - s * (1.0 - p_intrinsic)


def _calculate_v(n_current: float | None, q: float, e: float) -> float | None:
    if n_current is None:
        return None
    return _clip01(((n_current + q) / 2.0) * (1.0 - e))


def _intrinsic_b(
    k: tuple[float, float, float, float],
    *,
    f_min: float,
    f_max: float,
    a_fixed: float = 0.5,
    t_min: float = 0.0,
    t_max: float = 1.0,
    d_fixed: float = 0.5,
) -> list[float]:
    return [
        f_min + (f_max - f_min) * k[0],
        a_fixed,
        t_min + (t_max - t_min) * k[2],
        d_fixed,
    ]


def _calculate_tau(
    s: int,
    p: float,
    v: float | None,
    epsilon_tau: float,
    birth_phase: float,
) -> float | None:
    if s == 0 or v is None:
        return None
    return _clip01(p / (p + v + epsilon_tau) + birth_phase)


ETA_E = 1.0 - math.pow(0.85, 1.0 / 180.0)
RHO_E = 1.0 - math.pow(0.90, 1.0 / 180.0)


def _calculate_e_next(e: float, s: int, g: int) -> float:
    return _clip01(e + ETA_E * s * g * (1.0 - e) - RHO_E * (1 - s * g) * e)


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


def _life_presets() -> dict[str, dict[str, Any]]:
    return {
        "red": {
            "digital_life_id": "life-red",
            "role": "red",
            "f_min": 0 / 360,
            "f_max": 10 / 360,
        },
        "green": {
            "digital_life_id": "life-green",
            "role": "green",
            "f_min": 120 / 360,
            "f_max": 130 / 360,
        },
        "blue": {
            "digital_life_id": "life-blue",
            "role": "blue",
            "f_min": 245 / 360,
            "f_max": 255 / 360,
        },
    }


def build_reference_vectors() -> dict[str, Any]:
    presets = _life_presets()
    hash_vectors: list[dict[str, Any]] = []
    p_vectors: list[dict[str, Any]] = []
    birth_vectors: list[dict[str, Any]] = []
    for role, preset in presets.items():
        life_id = preset["digital_life_id"]
        handle = _hash01_entry(f"{role}_handle_distance", life_id, "handle-distance")
        birth = _hash01_entry(f"{role}_birth_phase", life_id, "birth-phase")
        hash_vectors.extend((handle, birth))
        p_intrinsic = 0.35 + 0.30 * handle["expected"]
        birth_phase = 0.000001 * birth["expected"]
        p_vectors.append(
            {
                "role": role,
                "digital_life_id": life_id,
                "hash01": handle["expected"],
                "expected": p_intrinsic,
                "expected_binary64_hex": p_intrinsic.hex(),
            }
        )
        birth_vectors.append(
            {
                "role": role,
                "digital_life_id": life_id,
                "hash01": birth["expected"],
                "expected": birth_phase,
                "expected_binary64_hex": birth_phase.hex(),
            }
        )
    hash_vectors.append(_hash01_entry("unicode_colon_join", "生命", "赤", "距離"))

    clip_vectors = [
        {"input": value, "expected": _clip01(value)}
        for value in (-0.25, 0.0, 0.5, 1.0, 1.25)
    ]
    nd_vectors = [
        {
            "name": name,
            "n_current": float(current),
            "n_baseline_session": float(baseline),
            "delta_n": float(delta_n),
            "expected": _calculate_nd(current, baseline, delta_n),
        }
        for name, current, baseline, delta_n in (
            ("plus_0_10", "0.60", "0.50", "0.10"),
            ("plus_0_05", "0.55", "0.50", "0.10"),
            ("same_as_baseline", "0.50", "0.50", "0.10"),
            ("minus_0_05", "0.45", "0.50", "0.10"),
            ("minus_0_10", "0.40", "0.50", "0.10"),
            ("upper_clip", "1.00", "0.50", "0.10"),
            ("lower_clip", "0.00", "0.50", "0.10"),
        )
    ]
    w_vectors = [
        {"nd": value, "expected": value} for value in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    p_activity_vectors = [
        {
            "role": item["role"],
            "s": s,
            "p_intrinsic": item["expected"],
            "expected": _calculate_p(s, item["expected"]),
        }
        for item in p_vectors
        for s in (0, 1)
    ]
    v_vectors = [
        {
            "name": name,
            "n_current": n_current,
            "q": q,
            "e": e,
            "expected": _calculate_v(n_current, q, e),
        }
        for name, n_current, q, e in (
            ("unavailable_n", None, 0.5, 0.0),
            ("stage_5a_holding_values", 0.2, 0.5, 0.0),
            ("nonzero_e", 0.2, 0.5, 0.2),
            ("upper_endpoint", 1.0, 1.0, 0.0),
        )
    ]
    phi_b_vectors = [
        {
            "role": role,
            "k": [0.5, 0.5, 0.5, 0.5],
            "f_min": preset["f_min"],
            "f_max": preset["f_max"],
            "a_fixed": 0.5,
            "t_min": 0.0,
            "t_max": 1.0,
            "d_fixed": 0.5,
            "expected": _intrinsic_b(
                (0.5, 0.5, 0.5, 0.5),
                f_min=preset["f_min"],
                f_max=preset["f_max"],
            ),
        }
        for role, preset in presets.items()
    ]
    phi_b_vectors.append(
        {
            "role": "green_custom_k",
            "k": [1.0, 0.0, 0.0, 1.0],
            "f_min": presets["green"]["f_min"],
            "f_max": presets["green"]["f_max"],
            "a_fixed": 0.5,
            "t_min": 0.0,
            "t_max": 1.0,
            "d_fixed": 0.5,
            "expected": _intrinsic_b(
                (1.0, 0.0, 0.0, 1.0),
                f_min=presets["green"]["f_min"],
                f_max=presets["green"]["f_max"],
            ),
        }
    )
    tau_inputs = (
        ("s_zero", 0, 0.5, 0.25, 0.000001, 0.0000001),
        ("formula", 1, 0.5, 0.25, 0.000001, 0.0000001),
        ("upper_clip", 1, 1.0, 0.0, 0.000001, 0.000001),
        ("lower_p", 1, 0.25, 0.25, 0.000001, 0.0),
        ("higher_p", 1, 0.75, 0.25, 0.000001, 0.0),
        ("higher_v", 1, 0.5, 0.75, 0.000001, 0.0),
    )
    tau_vectors = [
        {
            "name": name,
            "s": s,
            "p": p,
            "v": v,
            "epsilon_tau": epsilon_tau,
            "birth_phase": birth_phase,
            "expected": _calculate_tau(s, p, v, epsilon_tau, birth_phase),
        }
        for name, s, p, v, epsilon_tau, birth_phase in tau_inputs
    ]
    e_inputs = (
        ("first_accumulation", 0.0, 1, 1),
        ("accumulation", 0.4, 1, 1),
        ("recovery", 0.4, 0, 1),
        ("g_zero_recovery", 0.4, 1, 0),
        ("upper_endpoint", 1.0, 1, 1),
        ("lower_endpoint", 0.0, 0, 1),
    )
    e_vectors = [
        {
            "name": name,
            "e": e,
            "s": s,
            "g": g,
            "expected": _calculate_e_next(e, s, g),
        }
        for name, e, s, g in e_inputs
    ]
    w_shape_vectors = [
        {
            "w": value,
            "w_plus": _w_plus(value),
            "w_minus": _w_minus(value),
        }
        for value in (0.0, 0.225, 0.45, 0.5, 0.55, 0.775, 1.0)
    ]
    q_inputs = (
        ("positive_w", 0.5, 1.0, 1),
        ("neutral_w", 0.5, 0.5, 1),
        ("negative_w", 0.5, 0.0, 1),
        ("g_zero", 0.5, 1.0, 0),
        ("upper_endpoint", 1.0, 1.0, 1),
        ("lower_endpoint", 0.0, 0.0, 1),
    )
    q_vectors = [
        {
            "name": name,
            "q": q,
            "w": w,
            "g": g,
            "expected": _calculate_q_next(q, w, g),
        }
        for name, q, w, g in q_inputs
    ]

    stage4_n = [
        0.1641195720593294,
        0.17783395762886722,
        0.16342965068696474,
        0.17184501115930495,
    ]
    green_p = next(item["expected"] for item in p_vectors if item["role"] == "green")
    green_birth = next(
        item["expected"] for item in birth_vectors if item["role"] == "green"
    )
    green_boundaries = []
    baseline_n = stage4_n[0]
    for revision, (time_us, n_current) in enumerate(
        zip(
            (60_000_000, 120_000_000, 180_000_000, 240_000_000),
            stage4_n,
            strict=True,
        ),
        start=1,
    ):
        s = 0 if time_us == 240_000_000 else 1
        nd = 0.5 if revision == 1 else _clip01(
            0.5 + (n_current - baseline_n) / (2.0 * 0.10)
        )
        p = _calculate_p(s, green_p)
        v = _calculate_v(n_current, 0.5, 0.0)
        green_boundaries.append(
            {
                "time_us": time_us,
                "revision": revision,
                "s": s,
                "n_current": n_current,
                "n_baseline_session": baseline_n,
                "nd": nd,
                "w": nd,
                "p": p,
                "e": 0.0,
                "q": 0.5,
                "v": v,
                "tau": _calculate_tau(s, p, v, 0.000001, green_birth),
            }
        )

    return {
        "schema_version": "stage_05a_reference_vectors_v1",
        "normative_source": {
            "document_version": "v2.0",
            "profile_version": "symbiotic_signal_loop_reference_v1_0",
            "algorithm_version": "adaptive_random_search_confirmed_v1",
            "state_schema_version": "relation_memory_state_v2",
            "size_bytes": SPEC_SIZE,
            "sha256": SPEC_SHA256,
        },
        "normative_vectors": {
            "hash01": {
                "denominator": HASH01_DENOMINATOR,
                "vectors": hash_vectors,
            },
            "p_intrinsic": p_vectors,
            "birth_phase": birth_vectors,
            "clip01": clip_vectors,
            "nd": nd_vectors,
            "w": w_vectors,
            "p": p_activity_vectors,
            "v": v_vectors,
            "phi_b": phi_b_vectors,
            "tau": tau_vectors,
            "e_update": {
                "eta_e": ETA_E,
                "rho_e": RHO_E,
                "vectors": e_vectors,
            },
            "w_shape": w_shape_vectors,
            "q_update": q_vectors,
        },
        "simulation_fixture_vectors": {
            "fixture_scope": (
                "life IDs and Stage 4 deterministic N values are simulation fixtures, "
                "not v2.0 normative constants"
            ),
            "life_presets": presets,
            "stage4_standard_n": stage4_n,
            "stage5a_green_evaluation_boundaries": green_boundaries,
            "stage4_csv_byte_regression": {
                "rri": {
                    "size_bytes": 55_216,
                    "sha256": (
                        "7caa4953887d3dee9b9dbb1ad8ae992a0f5c12ac190cdac24ba1d022985618fc"
                    ),
                },
                "evaluation": {
                    "size_bytes": 755,
                    "sha256": (
                        "e54567bf2257bdf90856b9e8acce5b389e005cdc4ef729b3b71f99a9f9d19865"
                    ),
                },
                "signal": {
                    "size_bytes": 28_376,
                    "sha256": (
                        "b694fd74137540e7b6a90563c5a8f5cfa95dc6595ccaaf61220bb03701b7bd17"
                    ),
                },
            },
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
    default_output = project_root / "docs" / "conformance" / "stage-05a-reference-vectors.json"
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
