#!/usr/bin/env python3
"""Generate independent fixed Stage 8A.2 conformance vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "conformance" / "stage-08a2-reference-vectors.json"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def paired_seed(base: int, replicate: int) -> int:
    key = f"{base}:stage8a1:replicate:{replicate}"
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big")


def wilson(successes: int, total: int) -> dict[str, float]:
    z = 1.959963984540054
    rate = successes / total
    z2 = z * z
    denominator = 1 + z2 / total
    center = (rate + z2 / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z2 / (4 * total**2)) / denominator
    return {"rate": rate, "lower95": center - margin, "upper95": center + margin}


def neighborhood() -> list[dict[str, float]]:
    result = []
    for fatigue_delta in (Decimal("-0.015"), Decimal("0"), Decimal("0.015")):
        fatigue = Decimal("0.030") + fatigue_delta
        for sigma_delta in (Decimal("-0.125"), Decimal("0"), Decimal("0.125")):
            sigma = Decimal("1.000") + sigma_delta
            result.append(
                {
                    "selected_session_fatigue_target": float(fatigue),
                    "sigma_multiplier": float(sigma),
                }
            )
    return result


def vectors() -> dict[str, Any]:
    seed = paired_seed(20260802, 0)
    job_body = {
        "phase": "coarse",
        "user_type_id": "green_hue_dominant_broad_bpm",
        "selected_session_fatigue_target": 0.03,
        "sigma_multiplier": 1.0,
        "maximum_sessions": 4,
        "replicate_index": 0,
        "replicate_master_seed": seed,
        "arm": "experimental",
        "code_fingerprint": "a" * 64,
        "stage_08a1_model_version": "fatigue_exploration_convergence_lab_v0_1",
        "experiment_profile_version": "stage_08a1_fatigue_sigma_experiment_v0_1",
        "paired_seed_policy_version": "paired_replicate_seed_policy_v0_1",
        "document_version": "v2.0",
        "profile_version": "symbiotic_signal_loop_reference_v1_0",
        "algorithm_version": "adaptive_random_search_confirmed_v1",
        "state_schema_version": "relation_memory_state_v2",
        "schema_version": "fatigue_sigma_auto_search_job_v1",
    }
    reference_body = {
        "user_type_id": "green_hue_dominant_broad_bpm",
        "maximum_sessions": 4,
        "replicate_master_seed": seed,
        "code_fingerprint": "a" * 64,
        "stage_08a1_model_version": "fatigue_exploration_convergence_lab_v0_1",
        "profile_version": "symbiotic_signal_loop_reference_v1_0",
        "algorithm_version": "adaptive_random_search_confirmed_v1",
        "state_schema_version": "relation_memory_state_v2",
        "schema_version": "fatigue_sigma_reference_cache_v1",
    }
    result = {
        "schema_version": "stage_08a2_reference_vectors_v1",
        "production_implementation_imported": False,
        "versions": {
            "project_version": "0.12.0",
            "auto_search_model": "fatigue_sigma_auto_search_v0_1",
            "search_strategy": "coarse_refine_confirm_search_v0_1",
            "candidate_gate": "balanced_robust_candidate_gate_v0_1",
            "pareto": "multi_objective_pareto_frontier_v0_1",
            "ranking": "uncertainty_aware_robust_candidate_ranking_v0_1",
        },
        "plan_session_runs": {
            "smoke": 2 * 2 * 2 * 1 * 4,
            "quick": 6 * 3 * 3 * 2 * 12,
            "standard_phase_1": 6 * 6 * 5 * 3 * 24,
            "standard_maximum": 32_400,
            "robust_maximum": 122_400,
        },
        "condition_canonicalization": {
            "input": [0.0300001, 1.0000001],
            "canonical": [0.03, 1.0],
            "condition_key": "fatigue_0.030000__sigma_1.000000",
        },
        "phase_2_neighborhood": neighborhood(),
        "duplicate_removal": {
            "input_seed_count": 2,
            "identical_seed": [0.03, 1.0],
            "unique_neighborhood_count": 9,
        },
        "paired_seed": {
            "base_master_seed": 20260802,
            "replicate_index": 0,
            "replicate_master_seed": seed,
            "condition_in_seed": False,
        },
        "job_id": {"body": job_body, "sha256": digest(job_body)},
        "reference_cache_key": {
            "body": reference_body,
            "sha256": digest(reference_body),
        },
        "code_fingerprint_required_fields": [
            "git_head_sha",
            "working_tree_clean",
            "project_version",
            "package_version",
            "stage_08a1_experiment_version",
            "auto_search_version",
            "normative_spec_sha256",
            "python_version",
            "platform",
        ],
        "wilson": {
            "zero_of_ten": wilson(0, 10),
            "five_of_ten": wilson(5, 10),
            "ten_of_ten": wilson(10, 10),
        },
        "pareto": {
            "higher_good_lower_bad_dominates": True,
            "mixed_tradeoff_is_nondominated": True,
            "missing_metric_is_disadvantaged": True,
        },
        "candidate_gate": {
            "passing_fixture": True,
            "flat_spurious_0_26_fixture": False,
            "no_candidate_status": "no_robust_candidate",
        },
        "ranking_tie_break": {
            "lower_fatigue_first": True,
            "sigma_nearer_one_first": True,
            "single_opaque_score_used": False,
        },
        "specialist_categories": [
            "life_dominance_specialist",
            "bpm_common_specialist",
            "multi_attractor_specialist",
            "low_rotation_specialist",
            "conservative_compromise",
        ],
        "checkpoint_transition": [
            "pending",
            "running",
            "completed",
        ],
        "interrupted_running_recovery": "pending",
        "atomic_resume_skips_checksum_valid_completed_job": True,
        "report_recommendation_fixture": {
            "formal_spec_adoption": False,
            "external_resource_count": 0,
            "smoke_status": "smoke_diagnostic_only",
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
