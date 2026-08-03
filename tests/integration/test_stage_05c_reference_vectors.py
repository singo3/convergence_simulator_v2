"""Freshness and production agreement for independent Stage 5C vectors."""

from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from symbiotic_sim_v2.digital_life.hash01 import HASH01_DENOMINATOR, hash01
from symbiotic_sim_v2.digital_life.relation_memory import direction as direction_module
from symbiotic_sim_v2.digital_life.relation_memory.candidate import generate_candidate
from symbiotic_sim_v2.digital_life.relation_memory.config import (
    ALGORITHM_VERSION,
    BUNDLE1_REJECT_POLICY_VERSION,
    DIRECTION_FALLBACK_POLICY_VERSION,
    DIRECTION_NEAR_ZERO_NORM_THRESHOLD,
    PROFILE_VERSION,
    RELATION_UPDATE_EFFECTIVE_POLICY_VERSION,
    STATE_SCHEMA_VERSION,
)
from symbiotic_sim_v2.digital_life.relation_memory.direction import (
    derive_search_direction,
)
from symbiotic_sim_v2.digital_life.relation_memory.intrinsic import (
    derive_relation_memory_intrinsic_profile,
    exploration_decision,
    exploration_probability,
    exploration_sigma,
    relation_search_radius,
)
from symbiotic_sim_v2.digital_life.relation_memory.reflect import (
    reflect01,
    reflect01_vector,
)

PROJECT_ROOT = Path(__file__).parents[2]
VECTOR_PATH = PROJECT_ROOT / "docs" / "conformance" / "stage-05c-reference-vectors.json"
GENERATOR_PATH = PROJECT_ROOT / "tools" / "generate_stage_05c_reference_vectors.py"


def vectors() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def test_reference_file_is_fresh_and_generator_has_no_product_dependency() -> None:
    completed = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == completed.stderr == ""

    source = GENERATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert "symbiotic_sim_v2" not in source
    assert all(not name.startswith("symbiotic_sim_v2") for name in imported_modules)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "__import__"
        for node in ast.walk(tree)
    )


def test_version_scope_and_canonical_digest_contract_are_exact() -> None:
    data = vectors()
    assert data["schema_version"] == "stage_05c_reference_vectors_v1"
    assert data["normative_source"] == {
        "algorithm_version": ALGORITHM_VERSION,
        "directly_read_sections": [25, 26, 27],
        "document_version": "v2.0",
        "profile_version": PROFILE_VERSION,
        "sha256": "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73",
        "size_bytes": 65_759,
        "state_schema_version": STATE_SCHEMA_VERSION,
    }
    assumptions = data["simulation_assumptions"]
    assert assumptions["project_version"] == "0.9.0"
    assert assumptions["adaptive_life_model_version"] == (
        "adaptive_relation_memory_connected_life_v0_1"
    )
    assert assumptions["relation_update_effective_policy_version"] == (
        RELATION_UPDATE_EFFECTIVE_POLICY_VERSION
    )
    assert assumptions["bundle1_reject_policy_version"] == (BUNDLE1_REJECT_POLICY_VERSION)
    assert assumptions["direction_fallback_policy_version"] == (DIRECTION_FALLBACK_POLICY_VERSION)
    assert assumptions["single_session_only"] is True
    assert assumptions["convergence_evaluated"] is False
    assert assumptions["multi_session_not_implemented"] is True
    assert data["canonical_digest_contract"] == {
        "allow_nan": False,
        "digest_names": [
            "intrinsic_profile_digest",
            "adaptive_signal_digest",
            "relation_memory_transition_digest",
            "final_persistent_state_digest",
            "session_summary_digest",
        ],
        "encoding": "UTF-8",
        "separators": [",", ":"],
        "sort_keys": True,
    }


def test_independent_hash_and_intrinsic_vectors_match_production_exactly() -> None:
    data = vectors()
    assert data["hash01"]["denominator"] == HASH01_DENOMINATOR
    for family in ("curiosity", "explore", "direction"):
        for vector in data["hash01"][family]:
            actual = hash01(*vector["parts"])
            assert actual == vector["expected"], vector["name"]
            assert actual.hex() == vector["expected_binary64_hex"], vector["name"]

    for expected in data["intrinsic_profiles"]:
        actual = derive_relation_memory_intrinsic_profile(expected["digital_life_id"]).to_dict()
        assert actual == expected
        assert 0.02 <= actual["sigma_min"] <= 0.06
        assert 0.25 <= actual["sigma_max"] <= 0.55
        assert 0.03 <= actual["epsilon_accept"] <= 0.07
        assert 0.10 <= actual["p_explore_min"] <= 0.30


def test_independent_radius_sigma_probability_and_strict_decision_vectors() -> None:
    data = vectors()
    for vector in data["relation_search_radius"]:
        assert relation_search_radius(vector["W_anchor_session"]) == vector["expected"]

    profile = derive_relation_memory_intrinsic_profile("life-green")
    for vector in data["sigma_and_probability"]:
        assert vector["digital_life_id"] == "life-green"
        w_anchor = vector["W_anchor_session"]
        assert exploration_sigma(w_anchor, profile.sigma_min, profile.sigma_max) == vector["sigma"]
        assert exploration_probability(w_anchor, profile.p_explore_min) == vector["p_explore"]
    assert data["sigma_and_probability"][0]["sigma"] == profile.sigma_max
    assert data["sigma_and_probability"][0]["p_explore"] == 1.0
    assert data["sigma_and_probability"][-1]["sigma"] == profile.sigma_min
    assert data["sigma_and_probability"][-1]["p_explore"] == profile.p_explore_min

    for vector in data["strict_exploration_decision"]:
        assert exploration_decision(vector["u_explore"], vector["p_explore"]) == vector["expected"]


def test_independent_reflect_direction_fallback_and_candidate_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = vectors()
    for vector in data["reflect01"]["scalar_vectors"]:
        actual = reflect01(vector["input"])
        assert actual == vector["expected"]
        assert actual.hex() == vector["expected_binary64_hex"]
    reflect_vector = data["reflect01"]["vector"]
    assert reflect01_vector(reflect_vector["input"]) == pytest.approx(reflect_vector["expected"])

    for expected in data["direction"]["vectors"]:
        actual = derive_search_direction(expected["digital_life_id"], expected["trial_index_used"])
        assert actual.u_f == expected["u_f"]
        assert actual.u_t == expected["u_t"]
        assert actual.norm == expected["norm"]
        assert actual.xi == pytest.approx(expected["xi"])
        assert actual.fallback_used is expected["fallback_used"]
        assert math.hypot(actual.xi[0], actual.xi[2]) == pytest.approx(1.0)
        assert actual.xi[1] == actual.xi[3] == 0.0

    seen_keys: list[tuple[object, ...]] = []

    def zero_direction_hash(*parts: object) -> float:
        seen_keys.append(parts)
        return 0.5

    monkeypatch.setattr(direction_module, "hash01", zero_direction_hash)
    fallback = direction_module.derive_search_direction("life-green", 7)
    assert seen_keys == [
        ("life-green", "C", "direction", 7, "F"),
        ("life-green", "C", "direction", 7, "T"),
    ]
    assert fallback.norm == 0.0
    assert fallback.norm <= DIRECTION_NEAR_ZERO_NORM_THRESHOLD
    assert fallback.xi == tuple(data["direction"]["fallback"]["xi"])
    assert fallback.fallback_used is True
    assert fallback.fallback_policy_version == DIRECTION_FALLBACK_POLICY_VERSION
    monkeypatch.undo()

    candidate = data["candidate"]
    direction = derive_search_direction(candidate["digital_life_id"], candidate["trial_index_used"])
    actual_candidate = generate_candidate(candidate["k_anchor"], candidate["sigma"], direction)
    assert actual_candidate == tuple(candidate["k_trial"])
    assert actual_candidate[1] == candidate["k_anchor"][1]
    assert actual_candidate[3] == candidate["k_anchor"][3]
    assert all(0.0 <= item <= 1.0 for item in actual_candidate)
    assert candidate["trial_count_after"] == candidate["trial_count_before"] + 1
    assert candidate["k_anchor_changed_during_generation"] is False


def test_strict_threshold_and_incremental_improvement_vectors_are_unambiguous() -> None:
    thresholds = vectors()["strict_thresholds"]
    anchor = thresholds["anchor"]
    epsilon = thresholds["epsilon_accept"]
    for vector in thresholds["provisional"]:
        assert (vector["W_trial_1"] > anchor + epsilon) is vector["expected"]
    for vector in thresholds["confirmation_condition_1"]:
        assert (vector["W_trial_2"] > anchor) is vector["expected"]

    mean_condition = thresholds["confirmation_condition_2"]
    actual_mean = (mean_condition["W_trial_1"] + mean_condition["W_trial_2"]) / 2.0
    assert actual_mean == mean_condition["mean"] == mean_condition["threshold"]
    assert (actual_mean > mean_condition["threshold"]) is False

    incremental = thresholds["incremental_improvement"]
    assert incremental["W_trial_1"] > (incremental["W_anchor"] + incremental["epsilon_accept"])
    assert incremental["W_trial_2"] > incremental["W_anchor"]
    assert incremental["mean"] > (incremental["W_anchor"] + incremental["epsilon_accept"])
    assert incremental["W_trial_1"] < 0.5
    assert incremental["W_trial_2"] < 0.5
    assert incremental["accepted"] is True


def test_full_synthetic_branch_vectors_cover_counters_rollbacks_and_timing() -> None:
    data = vectors()
    branches = {vector["name"]: vector for vector in data["state_machine_branches"]}
    assert set(branches) == {
        "accepted",
        "bundle0_evaluation_reject",
        "bundle1_evaluation_reject",
        "bundle1_threshold_fail",
        "bundle2_evaluation_reject",
        "confirmation_condition1_fail",
        "confirmation_mean_fail",
        "g_zero",
        "hold",
        "incremental_improvement_below_neutral",
    }
    for branch in branches.values():
        assert branch["session_count_after_closing"] == (branch["session_count_used"] + 1)
        assert branch["candidate_generation_count"] in (0, 1)
        assert branch["active_k_trial_after_closing"] is None
        assert branch["session_finalized"] is True
        if branch["candidate_generated"]:
            assert branch["trial_count_after"] == branch["trial_count_before"] + 1
            assert branch["candidate_generation_trial_index"] == branch["trial_count_before"]
            assert branch["candidate_effective_signal_index"] == 121
        else:
            assert branch["trial_count_after"] == branch["trial_count_before"]

    assert branches["hold"]["exploration_decision"] == "hold"
    assert branches["hold"]["candidate_generated"] is False
    assert branches["accepted"]["adoption_result"] == "accepted"
    assert branches["accepted"]["k_anchor_update_count"] == 1
    assert (
        branches["accepted"]["presented_k_by_bundle"]["bundle_1"]
        == branches["accepted"]["presented_k_by_bundle"]["bundle_2"]
    )
    assert branches["bundle1_threshold_fail"]["provisional_condition"] is False
    assert (
        branches["bundle1_threshold_fail"]["presented_k_by_bundle"]["bundle_2"]
        == branches["bundle1_threshold_fail"]["initial_k_anchor"]
    )
    assert branches["confirmation_condition1_fail"]["confirmation_condition_1"] is False
    assert branches["confirmation_mean_fail"]["confirmation_condition_1"] is True
    assert branches["confirmation_mean_fail"]["confirmation_condition_2"] is False
    assert branches["bundle1_evaluation_reject"]["phase_after_bundle_1"] == ("trial_unconfirmed")
    assert branches["bundle1_evaluation_reject"]["valid_trial_evaluation_count"] == 1
    assert (
        branches["bundle2_evaluation_reject"]["final_k_anchor"]
        == branches["bundle2_evaluation_reject"]["initial_k_anchor"]
    )
    assert branches["bundle0_evaluation_reject"]["W_anchor_session_after"] is None
    assert branches["g_zero"]["candidate_generated"] is False
    assert branches["g_zero"]["W_anchor_session_after"] is None
    assert branches["g_zero"]["adoption_result"] == "non_holder_no_adaptation"
    assert branches["incremental_improvement_below_neutral"]["adoption_result"] == "accepted"

    timing = data["counter_and_timing_policy"]
    assert timing["candidate_generated_at_signal"] == 120
    assert timing["candidate_first_presented_at_signal"] == 121
    assert timing["bundle1_decision_at_signal"] == 180
    assert timing["bundle2_selection_first_presented_at_signal"] == 181
    assert timing["final_decision_at_signal"] == 240
    assert timing["same_signal_b_recomputed_after_relation_update"] is False
    assert timing["policy_version"] == RELATION_UPDATE_EFFECTIVE_POLICY_VERSION


def test_pre_stage5c_digest_and_csv_baseline_manifest_is_complete() -> None:
    regression = vectors()["pre_stage5c_regression"]
    assert regression["baseline_commit"] == ("c10d55460d4c9ec009397ec62a8a81f20cfaecc7")
    assert set(regression["headless_digests"]) == {
        "stage_1",
        "stage_2",
        "stage_3",
        "stage_4",
        "stage_5a",
        "stage_5b1",
        "stage_6",
        "stage_71_aligned",
        "stage_71_control",
        "stage_71_off_center",
    }
    csv_regression = regression["csv_byte_regression"]
    assert len(csv_regression) == 28
    for filename, (size_bytes, sha256) in csv_regression.items():
        assert filename.endswith(".csv")
        assert isinstance(size_bytes, int) and size_bytes > 0
        assert len(sha256) == 64
        int(sha256, 16)
