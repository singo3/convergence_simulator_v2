#!/usr/bin/env python3
"""Generate production-independent Stage 8A reference vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

SPEC_SIZE = 65_759
SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"
PROJECT_VERSION = "0.10.0"
SESSION_DURATION_US = 240_000_000
LANDSCAPE_VERSION = "stationary_preference_landscape_v0_1"
PEAK_VERSION = "stationary_gaussian_peak_v0_1"
COMBINATION_VERSION = "maximum_weighted_peak_response_v0_1"
SEED_POLICY_VERSION = "deterministic_per_session_physiology_seed_v0_1"
CONVERGENCE_VERSION = "rolling_majority_pattern_convergence_v0_1"
TRUTH_VERSION = "stationary_landscape_truth_alignment_v0_1"


def circular_hue_distance(first: float, second: float) -> float:
    raw = abs(first - second)
    return min(raw, 360.0 - raw)


def peak_match(
    hue: float,
    bpm: float,
    *,
    preferred_hue: float,
    hue_sigma: float,
    preferred_bpm: float,
    bpm_sigma: float,
    weight: float,
) -> float:
    hue_distance = circular_hue_distance(hue, preferred_hue)
    return (
        weight
        * math.exp(-0.5 * (hue_distance / hue_sigma) ** 2)
        * math.exp(-0.5 * ((bpm - preferred_bpm) / bpm_sigma) ** 2)
    )


def session_seed(master_seed: int, user_type_id: str, session_index: int) -> dict[str, Any]:
    key = f"{master_seed}:stage8a:{user_type_id}:{session_index}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return {
        "master_seed": master_seed,
        "user_type_id": user_type_id,
        "session_index": session_index,
        "key_utf8": key,
        "sha256_hex": digest.hex(),
        "prefix32_hex": digest[:4].hex(),
        "expected_root_seed_unsigned32": int.from_bytes(digest[:4], "big", signed=False),
    }


def pattern_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    if first["holder_id"] != second["holder_id"]:
        raise ValueError("different life")
    return math.hypot(
        circular_hue_distance(first["hue"], second["hue"]) / 2.0,
        (first["bpm"] - second["bpm"]) / 20.0,
    )


def cluster_candidate(members: tuple[dict[str, Any], ...]) -> dict[str, Any] | None:
    if len({member["holder_id"] for member in members}) != 1:
        return None
    distances = tuple(
        pattern_distance(first, second) for first, second in combinations(members, 2)
    )
    if any(distance > 1.0 for distance in distances):
        return None
    indices = tuple(member["session_index"] for member in members)
    return {
        "members": members,
        "indices": indices,
        "holder_id": members[0]["holder_id"],
        "maximum_distance": max(distances),
        "mean_distance": statistics.fmean(distances),
    }


def select_cluster(window: list[dict[str, Any]], required: int) -> dict[str, Any] | None:
    candidates = tuple(
        candidate
        for size in range(required, len(window) + 1)
        for subset in combinations(window, size)
        for candidate in (cluster_candidate(subset),)
        if candidate is not None
    )
    if not candidates:
        return None

    def key(candidate: dict[str, Any]) -> tuple[Any, ...]:
        newest_first = tuple(sorted(candidate["indices"], reverse=True))
        return (
            -len(candidate["members"]),
            candidate["maximum_distance"],
            candidate["mean_distance"],
            tuple(-index for index in newest_first),
            candidate["holder_id"],
            candidate["indices"],
        )

    selected = min(candidates, key=key)

    def medoid_key(member: dict[str, Any]) -> tuple[float, int]:
        total = sum(
            0.0 if other is member else pattern_distance(member, other)
            for other in selected["members"]
        )
        return total, -member["session_index"]

    medoid = min(selected["members"], key=medoid_key)
    return {
        "support_count": len(selected["members"]),
        "holder_id": selected["holder_id"],
        "member_session_indices": list(selected["indices"]),
        "outlier_session_indices": [
            item["session_index"]
            for item in window
            if item["session_index"] not in set(selected["indices"])
        ],
        "maximum_pairwise_distance": selected["maximum_distance"],
        "mean_pairwise_distance": selected["mean_distance"],
        "medoid_session_index": medoid["session_index"],
        "medoid_hue_degree": medoid["hue"],
        "medoid_blink_bpm": medoid["bpm"],
    }


def build_vectors() -> dict[str, Any]:
    single_center = peak_match(
        129.0,
        125.0,
        preferred_hue=129.0,
        hue_sigma=1.5,
        preferred_bpm=125.0,
        bpm_sigma=12.0,
        weight=1.0,
    )
    weighted_red = peak_match(
        6.0,
        70.0,
        preferred_hue=6.0,
        hue_sigma=2.5,
        preferred_bpm=70.0,
        bpm_sigma=25.0,
        weight=0.75,
    )
    blue_at_red = peak_match(
        6.0,
        70.0,
        preferred_hue=252.0,
        hue_sigma=2.5,
        preferred_bpm=120.0,
        bpm_sigma=20.0,
        weight=1.0,
    )
    three_of_four_window = [
        {"session_index": 0, "holder_id": "life-green", "hue": 128.0, "bpm": 118.0},
        {"session_index": 1, "holder_id": "life-green", "hue": 129.0, "bpm": 121.0},
        {"session_index": 2, "holder_id": "life-green", "hue": 128.0, "bpm": 120.0},
        {"session_index": 3, "holder_id": "life-red", "hue": 4.0, "bpm": 65.0},
    ]
    no_cluster_window = [
        {"session_index": 0, "holder_id": "life-red", "hue": 7.0, "bpm": 70.0},
        {"session_index": 1, "holder_id": "life-green", "hue": 129.0, "bpm": 125.0},
        {"session_index": 2, "holder_id": "life-blue", "hue": 252.0, "bpm": 120.0},
        {"session_index": 3, "holder_id": "life-red", "hue": 7.0, "bpm": 150.0},
    ]
    tie_window = [
        {"session_index": 0, "holder_id": "life-red", "hue": 7.0, "bpm": 70.0},
        {"session_index": 1, "holder_id": "life-red", "hue": 7.0, "bpm": 70.0},
        {"session_index": 2, "holder_id": "life-blue", "hue": 252.0, "bpm": 120.0},
        {"session_index": 3, "holder_id": "life-blue", "hue": 252.0, "bpm": 120.0},
    ]
    green_suboptimal = peak_match(
        125.0,
        80.0,
        preferred_hue=129.0,
        hue_sigma=1.5,
        preferred_bpm=125.0,
        bpm_sigma=12.0,
        weight=1.0,
    )
    return {
        "schema_version": "stage_08a_reference_vectors_v1",
        "normative_source": {
            "size_bytes": SPEC_SIZE,
            "sha256": SPEC_SHA256,
            "document_version": "v2.0",
            "profile_version": "symbiotic_signal_loop_reference_v1_0",
            "algorithm_version": "adaptive_random_search_confirmed_v1",
            "state_schema_version": "relation_memory_state_v2",
            "directly_read_sections": [20, "20.6", 25, "25.4", "25.7", "25.18", 27, "29.6"],
        },
        "simulation_assumptions": {
            "project_version": PROJECT_VERSION,
            "stationary_landscape_version": LANDSCAPE_VERSION,
            "peak_model_version": PEAK_VERSION,
            "multi_peak_combination_version": COMBINATION_VERSION,
            "session_seed_policy_version": SEED_POLICY_VERSION,
            "convergence_evaluator_version": CONVERGENCE_VERSION,
            "truth_alignment_version": TRUTH_VERSION,
            "stationary_preference": True,
            "moving_preference": False,
            "convergence_is_diagnostic_only": True,
            "exploration_continues_after_convergence": True,
            "v2_coefficients_modified": False,
            "monte_carlo": False,
        },
        "preference": {
            "single_peak_center": single_center,
            "circular_hue_distance_359_to_1": circular_hue_distance(359.0, 1.0),
            "weighted_peak_center": weighted_red,
            "multi_peak_at_red": {
                "red_local_match": weighted_red,
                "blue_global_match": blue_at_red,
                "expected_max_match": max(weighted_red, blue_at_red),
            },
            "flat_control_match": 0.0,
            "inactive_match": 0.0,
        },
        "session_seed": [
            session_seed(20260802, "green_narrow_moderate", 0),
            session_seed(20260802, "green_narrow_moderate", 1),
            session_seed(20260802, "flat_control", 0),
        ],
        "global_time": {
            "session_index": 3,
            "local_time_us": 120_000_000,
            "global_time_offset_us": 3 * SESSION_DURATION_US,
            "expected_global_time_us": 3 * SESSION_DURATION_US + 120_000_000,
        },
        "pattern_distance": {
            "same_pattern": 0.0,
            "hue_boundary": pattern_distance(
                {"holder_id": "life-green", "hue": 100.0, "bpm": 100.0},
                {"holder_id": "life-green", "hue": 102.0, "bpm": 100.0},
            ),
            "bpm_boundary": pattern_distance(
                {"holder_id": "life-green", "hue": 100.0, "bpm": 100.0},
                {"holder_id": "life-green", "hue": 100.0, "bpm": 120.0},
            ),
            "ellipse_outside": pattern_distance(
                {"holder_id": "life-green", "hue": 100.0, "bpm": 100.0},
                {"holder_id": "life-green", "hue": 102.0, "bpm": 120.0},
            ),
            "same_life_required": True,
            "near_boundary_inclusive": True,
        },
        "clustering": {
            "three_of_four": select_cluster(three_of_four_window, 3),
            "latest_outlier_converged": True,
            "no_cluster": select_cluster(no_cluster_window, 3),
            "deterministic_recency_tie_break": select_cluster(tie_window, 2),
            "selection_order": [
                "larger_subset",
                "lower_maximum_pairwise_distance",
                "lower_mean_pairwise_distance",
                "newer_session_vector",
                "holder_id_lexical",
                "session_index_tuple_lexical",
            ],
            "medoid_tie_break": "newest_session_index",
        },
        "truth_alignment": {
            "correct_convergence": {
                "preference_match": single_center,
                "global_maximum": 1.0,
                "response_gap": 1.0 - single_center,
                "classification": "correct_convergence",
            },
            "stable_suboptimal": {
                "preference_match": green_suboptimal,
                "global_maximum": 1.0,
                "response_gap": 1.0 - green_suboptimal,
                "classification": "stable_suboptimal",
            },
            "flat_control": {
                "global_maximum": 0.0,
                "response_gap": None,
                "classification": "no_preference_control",
            },
        },
        "state_handoff": {
            "retained_across_sessions": [
                "k_anchor",
                "q",
                "e",
                "trial_count",
                "session_count",
                "version_metadata",
                "intrinsic_elements",
            ],
            "reset_or_reacquired_each_session": {
                "N_baseline_session": None,
                "N_current": None,
                "Nd": 0.5,
                "W": 0.5,
                "W_anchor_session": None,
                "k_trial": None,
                "W_trial_1": None,
                "W_trial_2": None,
                "adaptation_phase": "anchor_evaluation",
                "exploration_decision": None,
                "Garden_holder": None,
            },
            "error_session_commits_state": False,
        },
    }


def canonical_text(values: dict[str, Any]) -> str:
    return json.dumps(
        values,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path(__file__).parents[1]
            / "docs"
            / "conformance"
            / "stage-08a-reference-vectors.json"
        ),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = canonical_text(build_vectors())
    if args.check:
        try:
            actual = args.output.read_text(encoding="utf-8")
        except FileNotFoundError:
            return 1
        return 0 if actual == expected else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
