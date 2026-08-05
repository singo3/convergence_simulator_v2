#!/usr/bin/env python3
"""Generate independent fixed Stage 8A.3 conformance vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "conformance" / "stage-08a3-reference-vectors.json"
LIFE_DATA = (
    ("red", "life-red", 0.0, 1.0 / 36.0),
    ("green", "life-green", 1.0 / 3.0, 13.0 / 36.0),
    ("blue", "life-blue", 49.0 / 72.0, 17.0 / 24.0),
)


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


def hash_bytes(*parts: object) -> bytes:
    return hashlib.sha256(":".join(str(part) for part in parts).encode()).digest()


def hash01(*parts: object) -> float:
    return int.from_bytes(hash_bytes(*parts)[:8], "big") / float(1 << 64)


def random_outputs(
    seed: int,
    participant_id: str,
    session_index: int,
) -> list[dict[str, Any]]:
    holder = min(
        int(
            hash01(
                seed,
                participant_id,
                session_index,
                "random-output",
                "holder",
            )
            * 3
        ),
        2,
    )
    role, life_id, f_min, f_max = LIFE_DATA[holder]
    result = []
    for bundle_index in range(3):
        key = (
            seed,
            participant_id,
            session_index,
            bundle_index,
            "random-output",
        )
        f = f_min + (f_max - f_min) * hash01(*key, "hue")
        t = hash01(*key, "bpm")
        result.append(
            {
                "bundle_index": bundle_index,
                "role": role,
                "life_id": life_id,
                "hue_degree": 360.0 * f,
                "blink_bpm": 10.0 + 155.0 * t,
                "f": f,
                "t": t,
                "output_seed": int.from_bytes(hash_bytes(*key, "seed")[:4], "big"),
            }
        )
    return result


def circular_distance(first: float, second: float) -> float:
    direct = abs(first % 360.0 - second % 360.0)
    return min(direct, 360.0 - direct)


def circular(values: list[float]) -> tuple[float | None, float]:
    radians = [math.radians(value % 360.0) for value in values]
    mean_cos = statistics.fmean(math.cos(value) for value in radians)
    mean_sin = statistics.fmean(math.sin(value) for value in radians)
    concentration = math.hypot(mean_cos, mean_sin)
    if concentration <= 1e-15:
        return None, 0.0
    return math.degrees(math.atan2(mean_sin, mean_cos)) % 360.0, concentration


def kernel(distance: float, bandwidth: float) -> float:
    return math.exp(-0.5 * (distance / bandwidth) ** 2)


def percentile(actual: float, candidates: list[float]) -> float:
    less = sum(value < actual for value in candidates)
    equal = sum(value == actual for value in candidates)
    return 100.0 * (less + 0.5 * equal) / len(candidates)


def rank(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average = (index + 1 + end) / 2.0
        for original, _value in ordered[index:end]:
            result[original] = average
        index = end
    return result


def pearson(first: list[float], second: list[float]) -> float:
    mean_first = statistics.fmean(first)
    mean_second = statistics.fmean(second)
    numerator = sum(
        (left - mean_first) * (right - mean_second)
        for left, right in zip(first, second, strict=True)
    )
    denominator = math.sqrt(
        sum((value - mean_first) ** 2 for value in first)
        * sum((value - mean_second) ** 2 for value in second)
    )
    return numerator / denominator


def bootstrap(values: list[float]) -> tuple[float, float]:
    generator = random.Random(
        int.from_bytes(
            hashlib.sha256(
                b"stage8a3-bootstrap:reference-vector:participant"
            ).digest()[:8],
            "big",
        )
    )
    means = sorted(
        statistics.fmean(generator.choice(values) for _index in range(len(values)))
        for _replicate in range(1_000)
    )
    return means[math.floor(0.025 * 999)], means[math.ceil(0.975 * 999)]


def vectors() -> dict[str, Any]:
    random_fixture = [
        {
            "session_index": index,
            "outputs": random_outputs(20260806, "fixture__p001", index),
        }
        for index in range(6)
    ]
    bpm_history = [(80.0, 1.0), (100.0, 3.0), (120.0, 1.0)]
    bpm_weights = [kernel(abs(bpm - 100.0), 15.0) for bpm, _value in bpm_history]
    bpm_score = sum(
        weight * value
        for weight, (_bpm, value) in zip(bpm_weights, bpm_history, strict=True)
    ) / sum(bpm_weights)
    life_values = [2.0, 4.0, 3.0]
    candidate_values = [1.0, 2.0, 3.0, 4.0, 5.0]
    late_early = statistics.fmean([4.0, 5.0]) - statistics.fmean([1.0, 2.0])
    bootstrap_lower, bootstrap_upper = bootstrap([0.5, 1.0, 1.5, 2.0])
    hue_mean, hue_concentration = circular([359.0, 1.0, 0.0])
    same_life_response = [1.0, 2.0, 3.0, 4.0]
    same_life_next = [0.0, 0.0, 1.0, 1.0]
    result = {
        "schema_version": "stage_08a3_reference_vectors_v1",
        "production_implementation_imported": False,
        "versions": {
            "project_version": "0.13.0",
            "validation_model": "adaptive_placebo_rmssd_validation_v0_1",
            "arm_contract": "adaptive_placebo_arm_contract_v0_1",
        },
        "cyclic_yoke_map": {
            "participants": ["p001", "p002", "p003"],
            "assignments": [
                ["p001", "p002"],
                ["p002", "p003"],
                ["p003", "p001"],
            ],
            "all_donor_differ": True,
            "single_participant": ["p001", "p001__hidden_donor"],
        },
        "random_output": {
            "master_seed": 20260806,
            "participant_id": "fixture__p001",
            "sessions": random_fixture,
            "holder_fixed_within_session": True,
            "hue_ranges_degree": {
                "red": [0.0, 10.0],
                "green": [120.0, 130.0],
                "blue": [245.0, 255.0],
            },
            "bpm_range": [10.0, 165.0],
            "condition_in_key": False,
            "rmssd_in_key": False,
        },
        "delta_rmssd": {
            "baseline_rmssd_ms": 22.5,
            "bundle_rmssd_ms": 27.75,
            "delta_rmssd_ms": 5.25,
        },
        "past_only_history": {
            "current_session_index": 4,
            "included_sessions": [0, 1, 2, 3],
            "excluded_sessions": [4, 5],
        },
        "life_history_score": {
            "values": life_values,
            "mean": statistics.fmean(life_values),
        },
        "bpm_kernel": {
            "history": bpm_history,
            "query_bpm": 100.0,
            "bandwidth": 15.0,
            "score": bpm_score,
        },
        "circular_hue_distance": {
            "first": 359.0,
            "second": 1.0,
            "distance": circular_distance(359.0, 1.0),
        },
        "counterfactual": {
            "candidate_count": 3 * 5 * 11,
            "values": candidate_values,
            "actual": 4.0,
            "percentile": percentile(4.0, candidate_values),
            "selection_enrichment": 4.0 - statistics.fmean(candidate_values),
        },
        "lag1_same_life_correlation": pearson(
            rank(same_life_response),
            rank(same_life_next),
        ),
        "pattern_closeness": {
            "same_life": True,
            "hue_distance": 2.0,
            "bpm_distance": 3.0,
            "closeness": 1.0 / (1.0 + 2.0 / 5.0 + 3.0 / 15.0),
            "different_life_closeness": 0.0,
        },
        "rmssd_effect": {
            "early": [1.0, 2.0],
            "middle": [2.5, 3.0],
            "late": [4.0, 5.0],
            "late_minus_early": late_early,
            "autonomous_late": 4.5,
            "yoked_late": 2.5,
            "paired_difference": 2.0,
        },
        "participant_bootstrap": {
            "values": [0.5, 1.0, 1.5, 2.0],
            "lower95": bootstrap_lower,
            "upper95": bootstrap_upper,
            "replicates": 1_000,
        },
        "circular_hue": {
            "values": [359.0, 1.0, 0.0],
            "mean_degree": hue_mean,
            "concentration": hue_concentration,
            "low_concentration_fixture": circular([0.0, 180.0]),
        },
        "participant_classification": {
            "clear_positive": "clear_positive_adaptation",
            "partial": "partial_adaptation_signal",
            "no_clear": "no_clear_effect",
            "negative": "negative_or_unstable",
            "insufficient": "insufficient_data",
            "binary_is_primary": False,
        },
        "flat_null_fixture": {
            "response_strength_scale": 0.0,
            "expected_effect_center": 0.0,
            "life_selection_structure_may_exist": True,
        },
        "report_trajectory_fixture": {
            "x": "session_index",
            "y": "displayed_blink_bpm",
            "fill": "actual_hue_hsv",
            "shapes": {
                "life-red": "circle",
                "life-green": "triangle",
                "life-blue": "square",
            },
            "bundle_x_offsets": [-0.2, 0.0, 0.2],
            "trial_is_translucent": True,
            "invalid_marker": "x",
        },
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
        return 0 if TARGET.is_file() and TARGET.read_text(encoding="utf-8") == expected else 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
