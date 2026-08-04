#!/usr/bin/env python3
"""Generate production-independent Stage 8A.1 reference vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

SPEC_SIZE = 65_759
SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"
PROJECT_VERSION = "0.11.0"
ACTIVE_SIGNALS = 180
ETA_REFERENCE = 1.0 - 0.85 ** (1.0 / ACTIVE_SIGNALS)
RHO_REFERENCE = 1.0 - 0.90 ** (1.0 / ACTIVE_SIGNALS)
HASH01_DENOMINATOR = (1 << 48) - 1


def clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def selected_eta(target: float) -> float:
    return 1.0 - (1.0 - target) ** (1.0 / ACTIVE_SIGNALS)


def e_next(e: float, s: int, g: int, *, eta: float, rho: float) -> float:
    return clip01(e + eta * s * g * (1.0 - e) - rho * (1 - s * g) * e)


def repeat_e(e: float, count: int, *, s: int, g: int, eta: float, rho: float) -> float:
    result = e
    for _ in range(count):
        result = e_next(result, s, g, eta=eta, rho=rho)
    return result


def hash01(*parts: object) -> float:
    joined = ":".join(str(part) for part in parts).encode("utf-8")
    numerator = int.from_bytes(hashlib.sha256(joined).digest()[:6], "big")
    return numerator / HASH01_DENOMINATOR


def reflect01(value: float) -> float:
    return 1.0 - abs(1.0 - (value % 2.0))


def relation_radius(w: float) -> float:
    return clip01(2.0 * w - 1.0)


def intrinsic(life_id: str) -> dict[str, float]:
    curiosity = hash01(life_id, "curiosity")
    return {
        "curiosity": curiosity,
        "sigma_min_reference": 0.02 + 0.04 * curiosity,
        "sigma_max_reference": 0.25 + 0.30 * curiosity,
        "epsilon_accept": 0.07 - 0.04 * curiosity,
        "p_explore_min": 0.10 + 0.20 * curiosity,
    }


def sigma_at_w(profile: dict[str, float], w: float) -> float:
    radius = relation_radius(w)
    return profile["sigma_min_reference"] + (
        profile["sigma_max_reference"] - profile["sigma_min_reference"]
    ) * (1.0 - radius)


def p_explore_at_w(profile: dict[str, float], w: float) -> float:
    radius = relation_radius(w)
    return profile["p_explore_min"] + (1.0 - profile["p_explore_min"]) * (1.0 - radius)


def direction(life_id: str, trial_index: int) -> tuple[float, float]:
    u_f = 2.0 * hash01(life_id, "C", "direction", trial_index, "F") - 1.0
    u_t = 2.0 * hash01(life_id, "C", "direction", trial_index, "T") - 1.0
    norm = math.hypot(u_f, u_t)
    if norm <= 1.0e-12:
        return 1.0, 0.0
    return u_f / norm, u_t / norm


def circular_hue_distance(first: float, second: float) -> float:
    raw = abs(first - second) % 360.0
    return min(raw, 360.0 - raw)


def gaussian(distance: float, sigma: float) -> float:
    return math.exp(-0.5 * (distance / sigma) ** 2)


def peak_match(
    hue: float,
    bpm: float,
    *,
    preferred_hue: float | None,
    hue_sigma: float | None,
    preferred_bpm: float | None,
    bpm_sigma: float | None,
    weight: float,
) -> float:
    hue_term = (
        1.0
        if preferred_hue is None
        else gaussian(circular_hue_distance(hue, preferred_hue), float(hue_sigma))
    )
    bpm_term = (
        1.0 if preferred_bpm is None else gaussian(abs(bpm - preferred_bpm), float(bpm_sigma))
    )
    return weight * hue_term * bpm_term


def paired_master_seed(base_master_seed: int, replicate_index: int) -> dict[str, Any]:
    key = f"{base_master_seed}:stage8a1:replicate:{replicate_index}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return {
        "base_master_seed": base_master_seed,
        "replicate_index": replicate_index,
        "key_utf8": key,
        "sha256_hex": digest.hex(),
        "prefix32_hex": digest[:4].hex(),
        "expected_master_seed_unsigned32": int.from_bytes(digest[:4], "big"),
    }


def session_seed(master_seed: int, user_type_id: str, session_index: int) -> dict[str, Any]:
    key = f"{master_seed}:stage8a:{user_type_id}:{session_index}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return {
        "replicate_master_seed": master_seed,
        "user_type_id": user_type_id,
        "session_index": session_index,
        "key_utf8": key,
        "sha256_hex": digest.hex(),
        "expected_root_seed_unsigned32": int.from_bytes(digest[:4], "big"),
    }


def observation(index: int, life_id: str, bpm: float, hue: float) -> dict[str, Any]:
    return {"session_index": index, "holder_id": life_id, "bpm": bpm, "hue": hue}


def longest_run(flags: tuple[bool, ...], target: bool) -> int:
    longest = current = 0
    for flag in flags:
        if flag is target:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def tolerant_longest(flags: tuple[bool, ...]) -> int:
    longest = start = outliers = 0
    for end, flag in enumerate(flags):
        if not flag:
            outliers += 1
        while outliers > 1:
            if not flags[start]:
                outliers -= 1
            start += 1
        longest = max(longest, end - start + 1)
    return longest


def life_dominance(holders: list[str]) -> dict[str, Any]:
    indices = tuple(range(len(holders)))

    def metrics(life_id: str) -> tuple[int, int, int]:
        flags = tuple(holder == life_id for holder in holders)
        return (
            sum(flags),
            tolerant_longest(flags),
            max(index for index, holder in enumerate(holders) if holder == life_id),
        )

    dominant = min(
        sorted(set(holders)),
        key=lambda life_id: (
            -metrics(life_id)[0],
            -metrics(life_id)[1],
            -metrics(life_id)[2],
            life_id,
        ),
    )
    flags = tuple(holder == dominant for holder in holders)
    opportunities = within_one = within_two = 0
    position = 0
    while position < len(flags):
        if flags[position]:
            position += 1
            continue
        start = position
        while position < len(flags) and not flags[position]:
            position += 1
        if start == 0 or not flags[start - 1]:
            continue
        opportunities += 1
        if position < len(flags):
            outlier_length = position - start
            within_one += outlier_length <= 1
            within_two += outlier_length <= 2
    count = sum(flags)
    maximum_outliers = longest_run(flags, False)
    return {
        "holders": holders,
        "valid_window_session_indices": list(indices),
        "dominant_life_id": dominant,
        "dominant_count": count,
        "share": count / len(flags),
        "strict_consecutive_run": longest_run(flags, True),
        "one_outlier_tolerant_longest_run": tolerant_longest(flags),
        "maximum_consecutive_outliers": maximum_outliers,
        "latest_session_outlier": not flags[-1],
        "return_opportunity_count": opportunities,
        "return_within_one_session_count": within_one,
        "return_within_one_session_rate": 0.0 if not opportunities else within_one / opportunities,
        "return_within_two_sessions_count": within_two,
        "return_within_two_sessions_rate": 0.0 if not opportunities else within_two / opportunities,
        "confirmed": len(flags) == 8 and count >= 6 and maximum_outliers <= 1,
    }


def bpm_candidate(items: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    values = tuple(float(item["bpm"]) for item in items)
    median = float(statistics.median(values))
    return {
        "members": items,
        "indices": tuple(int(item["session_index"]) for item in items),
        "range": max(values) - min(values),
        "median": median,
        "mad": statistics.fmean(abs(value - median) for value in values),
    }


def candidate_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    newest_first = tuple(sorted(candidate["indices"], reverse=True))
    return (
        -len(candidate["members"]),
        candidate["range"],
        candidate["mad"],
        tuple(-index for index in newest_first),
        candidate["indices"],
    )


def candidate_medoid(candidate: dict[str, Any]) -> dict[str, Any]:
    return min(
        candidate["members"],
        key=lambda item: (
            sum(abs(item["bpm"] - other["bpm"]) for other in candidate["members"]),
            -item["session_index"],
            item["bpm"],
        ),
    )


def common_bpm(items: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        bpm_candidate(subset)
        for size in range(6, len(items) + 1)
        for subset in combinations(items, size)
        if max(item["bpm"] for item in subset) - min(item["bpm"] for item in subset) <= 20.0
    ]
    selected = min(candidates, key=candidate_key)
    medoid = candidate_medoid(selected)
    members = set(selected["indices"])
    life_ids = sorted({item["holder_id"] for item in selected["members"]})
    return {
        "observations": items,
        "support": len(selected["members"]),
        "member_session_indices": list(selected["indices"]),
        "outlier_session_indices": [
            item["session_index"] for item in items if item["session_index"] not in members
        ],
        "medoid_bpm": medoid["bpm"],
        "median_bpm": selected["median"],
        "bpm_range": selected["range"],
        "mean_absolute_deviation": selected["mad"],
        "participating_life_ids": life_ids,
        "cross_life": len(life_ids) >= 2,
        "confirmed": True,
    }


def per_life_attractor(life_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(items, key=lambda item: (item["bpm"], item["session_index"]))
    candidates: dict[tuple[int, ...], dict[str, Any]] = {}
    for start in range(len(ordered)):
        for end in range(start + 2, len(ordered)):
            if ordered[end]["bpm"] - ordered[start]["bpm"] > 20.0:
                break
            candidate = bpm_candidate(tuple(ordered[start : end + 1]))
            candidate["indices"] = tuple(sorted(candidate["indices"]))
            candidates[candidate["indices"]] = candidate
    selected = min(candidates.values(), key=candidate_key)
    medoid = candidate_medoid(selected)
    member_indices = set(selected["indices"])
    support = len(selected["members"])
    fraction = support / len(items)
    return {
        "life_id": life_id,
        "occurrence_count": len(items),
        "support": support,
        "support_fraction": fraction,
        "member_session_indices": list(selected["indices"]),
        "outlier_session_indices": [
            item["session_index"] for item in items if item["session_index"] not in member_indices
        ],
        "medoid_bpm": medoid["bpm"],
        "median_bpm": selected["median"],
        "bpm_range": selected["range"],
        "mean_absolute_deviation": selected["mad"],
        "valid_attractor": bool(
            len(items) >= 3 and support >= 3 and fraction >= 0.70 and selected["range"] <= 20.0
        ),
    }


def multi_attractor(items: list[dict[str, Any]]) -> dict[str, Any]:
    records = [
        per_life_attractor(
            life_id,
            [item for item in items if item["holder_id"] == life_id],
        )
        for life_id in sorted({item["holder_id"] for item in items})
    ]
    valid = [record for record in records if record["valid_attractor"]]
    separation = min(
        abs(first["medoid_bpm"] - second["medoid_bpm"]) for first, second in combinations(valid, 2)
    )
    confirmed = len(valid) >= 2 and separation >= 20.0
    return {
        "observations": items,
        "life_attractors": records,
        "attractor_count": len(valid),
        "attractor_separation": separation,
        "two_attractor_flag": confirmed,
        "three_attractor_flag": confirmed and len(valid) >= 3,
        "confirmed": confirmed,
    }


def rate(count: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else count / denominator


def mechanical_rotation(holders: list[str]) -> dict[str, Any]:
    switches = sum(first != second for first, second in zip(holders, holders[1:], strict=False))
    triples = list(zip(holders, holders[1:], holders[2:], strict=False))
    quadruples = list(zip(holders, holders[1:], holders[2:], holders[3:], strict=False))
    distinct = sum(len(set(values)) == 3 for values in triples)
    aba = sum(first == third and first != second for first, second, third in triples)
    abca = sum(
        first == fourth and len({first, second, third}) == 3
        for first, second, third, fourth in quadruples
    )
    counts = Counter(holders)
    latest = {
        life_id: max(i for i, value in enumerate(holders) if value == life_id) for life_id in counts
    }
    dominant = min(counts, key=lambda life_id: (-counts[life_id], -latest[life_id], life_id))
    opportunities = returns = 0
    for position, holder in enumerate(holders[:-1]):
        if holder == dominant:
            continue
        opportunities += 1
        returns += holders[position + 1] == dominant
    prior: dict[str, int] = {}
    intervals: list[int] = []
    for position, holder in enumerate(holders):
        if holder in prior:
            intervals.append(position - prior[holder])
        prior[holder] = position
    return {
        "holders": holders,
        "dominant_life_id": dominant,
        "holder_switch_rate": rate(switches, len(holders) - 1),
        "three_distinct_life_window_rate": rate(distinct, len(triples)),
        "immediate_return_rate": rate(aba, len(triples)),
        "three_life_cycle_rate": rate(abca, len(quadruples)),
        "dominant_life_return_rate": rate(returns, opportunities),
        "mean_sessions_between_same_life_selections": (
            None if not intervals else statistics.fmean(intervals)
        ),
    }


def w_ceiling(items: list[dict[str, Any]]) -> dict[str, Any]:
    impossible = sum(item["anchor"] + item["epsilon"] >= 1.0 for item in items)
    anchor_ceiling = sum(math.isclose(item["anchor"], 1.0, abs_tol=1.0e-12) for item in items)
    trials = [value for item in items for value in item["trials"]]
    trial_ceiling = sum(math.isclose(value, 1.0, abs_tol=1.0e-12) for value in trials)
    if items and impossible == len(items):
        classification = "exploration_blocked_by_W_ceiling"
    elif impossible or anchor_ceiling or trial_ceiling:
        classification = "exploration_partly_saturated"
    else:
        classification = "exploration_identifiable"
    return {
        "observations": items,
        "anchor_evaluation_count": len(items),
        "w_anchor_session_ceiling_count": anchor_ceiling,
        "w_anchor_session_ge_one_minus_epsilon_count": sum(
            item["anchor"] >= 1.0 - item["epsilon"] for item in items
        ),
        "mathematically_impossible_provisional_adoption_count": impossible,
        "w_trial_ceiling_count": trial_ceiling,
        "classification": classification,
    }


def build_vectors() -> dict[str, Any]:
    fatigue_vectors = []
    for target in (0.0, 0.03, 0.05, 0.15, 0.20):
        eta = selected_eta(target)
        fatigue_vectors.append(
            {
                "selected_session_fatigue_target": target,
                "eta_selected": eta,
                "e_from_zero_after_180_active_signals": repeat_e(
                    0.0, ACTIVE_SIGNALS, s=1, g=1, eta=eta, rho=RHO_REFERENCE
                ),
            }
        )
    profile = intrinsic("life-green")
    w_anchor = 0.6
    reference_sigma = sigma_at_w(profile, w_anchor)
    xi_f, xi_t = direction("life-green", 0)
    sigma_vectors = []
    for multiplier in (0.25, 0.50, 1.0, 1.50):
        effective = multiplier * reference_sigma
        candidate_f = reflect01(0.5 + effective * xi_f)
        candidate_t = reflect01(0.5 + effective * xi_t)
        sigma_vectors.append(
            {
                "multiplier": multiplier,
                "reference_sigma": reference_sigma,
                "effective_sigma": effective,
                "candidate_delta_f": candidate_f - 0.5,
                "candidate_delta_t": candidate_t - 0.5,
                "resulting_delta_hue_degree": 360.0 * (candidate_f - 0.5),
                "resulting_delta_bpm": 155.0 * (candidate_t - 0.5),
                "p_explore": p_explore_at_w(profile, w_anchor),
                "epsilon_accept": profile["epsilon_accept"],
            }
        )
    bpm_items = [
        observation(
            index,
            ("life-red", "life-green", "life-blue")[index % 3],
            bpm,
            10.0 + 120.0 * (index % 3),
        )
        for index, bpm in enumerate((94.0, 96.0, 98.0, 100.0, 102.0, 114.0, 140.0, 160.0))
    ]
    per_life_bpms = {
        "life-red": (54.0, 55.0, 56.0, 54.0, 55.0, 80.0),
        "life-green": (99.0, 100.0, 101.0, 99.0, 100.0, 130.0),
        "life-blue": (144.0, 145.0, 146.0, 144.0, 145.0, 110.0),
    }
    hue_by_life = {"life-red": 5.0, "life-green": 125.0, "life-blue": 250.0}
    life_order = ("life-red", "life-green", "life-blue")
    multi_items = [
        observation(
            index,
            life_id,
            per_life_bpms[life_id][index // 3],
            hue_by_life[life_id],
        )
        for index in range(18)
        for life_id in (life_order[index % 3],)
    ]
    replicate_vectors = [paired_master_seed(20260802, index) for index in range(3)]
    first_replicate_seed = replicate_vectors[0]["expected_master_seed_unsigned32"]
    aggregate_replicates = [
        {
            "classification": "life_dominant_convergence",
            "truth": "correct_structure",
            "life": True,
            "bpm": False,
            "multi": False,
            "first_life": 8,
            "accepted": 2,
        },
        {
            "classification": "single_life_pattern_convergence",
            "truth": "partially_correct_structure",
            "life": True,
            "bpm": True,
            "multi": False,
            "first_life": 10,
            "accepted": 1,
        },
        {
            "classification": "diffuse_or_unresolved",
            "truth": "not_converged",
            "life": False,
            "bpm": False,
            "multi": False,
            "first_life": None,
            "accepted": 0,
        },
    ]
    return {
        "schema_version": "stage_08a1_reference_vectors_v1",
        "normative_source": {
            "size_bytes": SPEC_SIZE,
            "sha256": SPEC_SHA256,
            "document_version": "v2.0",
            "profile_version": "symbiotic_signal_loop_reference_v1_0",
            "algorithm_version": "adaptive_random_search_confirmed_v1",
            "state_schema_version": "relation_memory_state_v2",
            "directly_read_sections": [
                1,
                8,
                "20.6",
                "22.2",
                "25.2",
                "25.6",
                "25.7",
                "25.8",
                "25.18",
                27,
                30,
                "EOF",
                "change_history",
            ],
        },
        "simulation_assumptions": {
            "project_version": PROJECT_VERSION,
            "lab_model_version": "fatigue_exploration_convergence_lab_v0_1",
            "experiment_profile_version": "stage_08a1_fatigue_sigma_experiment_v0_1",
            "fatigue_policy_version": "unselected_full_recovery_at_session_end_v0_1",
            "selected_fatigue_policy_version": "selected_session_saturating_fatigue_v0_1",
            "sigma_scaling_policy_version": "scaled_reference_sigma_v0_1",
            "stationary_landscape_version": "stationary_preference_landscape_v0_2",
            "stationary_user_profile_version": "stationary_user_type_profile_v2",
            "structured_convergence_version": "structured_convergence_diagnostics_v0_1",
            "paired_replicate_seed_version": "paired_replicate_seed_policy_v0_1",
            "formal_spec_adoption": False,
            "stationary_preference": True,
            "moving_preference": False,
            "convergence_is_diagnostic_only": True,
            "exploration_continues_after_convergence": True,
            "p_explore_modified": False,
            "epsilon_accept_modified": False,
            "q_coefficients_modified": False,
            "Monte_Carlo": False,
        },
        "experiment_manifest": {
            "formal_spec_adoption": False,
            "base_profile_version": "symbiotic_signal_loop_reference_v1_0",
            "experiment_profile_version": "stage_08a1_fatigue_sigma_experiment_v0_1",
            "reference_coefficients_modified": True,
            "modified_fields": [
                "selected fatigue accumulation target",
                "unselected session-end recovery policy",
                "exploration width multiplier",
            ],
            "unchanged_reference_fields": [
                "p_explore_min",
                "epsilon_accept",
                "q coefficients",
                "P mapping",
                "V mapping",
                "tau mapping",
                "RMSSD to N",
                "delta_N",
                "Bundle structure",
                "candidate confirmation rule",
            ],
        },
        "fatigue": {
            "active_signal_count": ACTIVE_SIGNALS,
            "eta_reference": ETA_REFERENCE,
            "rho_reference": RHO_REFERENCE,
            "target_vectors": fatigue_vectors,
            "nonzero_saturation": {
                "initial_e": 0.4,
                "target": 0.05,
                "e_after_180_active_signals": repeat_e(
                    0.4,
                    ACTIVE_SIGNALS,
                    s=1,
                    g=1,
                    eta=selected_eta(0.05),
                    rho=RHO_REFERENCE,
                ),
            },
            "baseline_reference_recovery": {
                "initial_e": 0.1,
                "signals": 60,
                "expected_e": repeat_e(
                    0.1,
                    60,
                    s=0,
                    g=0,
                    eta=selected_eta(0.05),
                    rho=RHO_REFERENCE,
                ),
            },
            "session_end_policy": {
                "unselected": {
                    "selected_active_signal_count": 0,
                    "e_before": 0.12,
                    "e_after": 0.0,
                    "full_recovery_applied": True,
                },
                "selected": {
                    "selected_active_signal_count": 1,
                    "e_before": 0.12,
                    "e_after": 0.12,
                    "full_recovery_applied": False,
                },
                "q_k_and_counters_unchanged": True,
                "error_or_incomplete_commits": False,
                "runner_postprocesses_e": False,
            },
            "reference_arm": {
                "eta": ETA_REFERENCE,
                "rho": RHO_REFERENCE,
                "unselected_full_recovery": False,
                "sigma_multiplier": 1.0,
            },
        },
        "sigma": {
            "digital_life_id": "life-green",
            "W_anchor_session": w_anchor,
            **profile,
            "direction_trial_index": 0,
            "direction_f": xi_f,
            "direction_t": xi_t,
            "vectors": sigma_vectors,
            "condition_in_direction_hash": False,
            "explores_f_t_only": True,
            "a_d_unchanged": True,
        },
        "preference": {
            "green_hue_bpm_neutral": {
                "at_bpm_10": peak_match(
                    125.0,
                    10.0,
                    preferred_hue=125.0,
                    hue_sigma=3.0,
                    preferred_bpm=None,
                    bpm_sigma=None,
                    weight=1.0,
                ),
                "at_bpm_165": peak_match(
                    125.0,
                    165.0,
                    preferred_hue=125.0,
                    hue_sigma=3.0,
                    preferred_bpm=None,
                    bpm_sigma=None,
                    weight=1.0,
                ),
            },
            "bpm_common_hue_neutral": {
                "at_hue_0_bpm_100": peak_match(
                    0.0,
                    100.0,
                    preferred_hue=None,
                    hue_sigma=None,
                    preferred_bpm=100.0,
                    bpm_sigma=12.0,
                    weight=1.0,
                ),
                "at_hue_300_bpm_112": peak_match(
                    300.0,
                    112.0,
                    preferred_hue=None,
                    hue_sigma=None,
                    preferred_bpm=100.0,
                    bpm_sigma=12.0,
                    weight=1.0,
                ),
            },
            "three_equal_peak_centers": [
                peak_match(
                    hue,
                    bpm,
                    preferred_hue=hue,
                    hue_sigma=3.0,
                    preferred_bpm=bpm,
                    bpm_sigma=10.0,
                    weight=1.0,
                )
                for hue, bpm in ((5.0, 55.0), (125.0, 100.0), (250.0, 145.0))
            ],
            "flat_control_match": 0.0,
        },
        "paired_replicate_seed": {
            "policy_version": "paired_replicate_seed_policy_v0_1",
            "replicate_vectors": replicate_vectors,
            "session_vectors": [
                session_seed(first_replicate_seed, "green_hue_dominant_broad_bpm", session_index)
                for session_index in (0, 1)
            ],
            "excluded_key_fields": [
                "fatigue_target",
                "sigma_multiplier",
                "condition_id",
                "condition_hash",
                "convergence_result",
            ],
        },
        "life_dominance": {
            "one_outlier": life_dominance(
                [
                    "life-green",
                    "life-green",
                    "life-red",
                    "life-green",
                    "life-green",
                    "life-green",
                    "life-green",
                    "life-green",
                ]
            ),
            "two_consecutive_outliers": life_dominance(
                [
                    "life-green",
                    "life-green",
                    "life-red",
                    "life-blue",
                    "life-green",
                    "life-green",
                    "life-green",
                    "life-green",
                ]
            ),
            "latest_outlier": life_dominance(["life-green"] * 7 + ["life-red"]),
            "hue_match_required": False,
        },
        "bpm_common": common_bpm(bpm_items),
        "multi_attractor": multi_attractor(multi_items),
        "mechanical_rotation": {
            "three_life_cycle": mechanical_rotation(
                [
                    "life-red",
                    "life-green",
                    "life-blue",
                    "life-red",
                    "life-green",
                    "life-blue",
                    "life-red",
                ]
            ),
            "immediate_return": mechanical_rotation(
                ["life-red", "life-green", "life-red", "life-green", "life-red"]
            ),
            "is_primary_convergence_rule": False,
        },
        "w_ceiling": {
            "identifiable": w_ceiling([{"anchor": 0.6, "epsilon": 0.05, "trials": [0.7]}]),
            "partly_saturated": w_ceiling([{"anchor": 0.96, "epsilon": 0.03, "trials": [1.0]}]),
            "blocked": w_ceiling(
                [
                    {"anchor": 0.95, "epsilon": 0.05, "trials": [0.98]},
                    {"anchor": 1.0, "epsilon": 0.03, "trials": [1.0]},
                ]
            ),
            "coefficients_auto_changed": False,
        },
        "condition_grid_aggregation": {
            "replicate_results": aggregate_replicates,
            "replicate_count": 3,
            "life_dominant_convergence_rate": 2 / 3,
            "bpm_common_convergence_rate": 1 / 3,
            "multi_attractor_convergence_rate": 0.0,
            "diffuse_rate": 1 / 3,
            "correct_structure_rate": 1 / 3,
            "partial_structure_rate": 1 / 3,
            "median_first_life_convergence_session": 9.0,
            "accepted_count": 3,
            "single_forced_best_score_present": False,
        },
        "canonical_digest_contract": {
            "encoding": "UTF-8",
            "sort_keys": True,
            "allow_nan": False,
            "separators": [",", ":"],
        },
    }


def canonical_text(values: dict[str, Any]) -> str:
    return (
        json.dumps(
            values,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path(__file__).parents[1] / "docs" / "conformance" / "stage-08a1-reference-vectors.json"
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
