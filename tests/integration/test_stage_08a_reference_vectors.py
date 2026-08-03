"""Freshness and production agreement for independent Stage 8A vectors."""

from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.convergence import (
    ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION,
    RollingConvergenceConfig,
    SessionPatternObservation,
    evaluate_convergence_history,
    evaluate_truth_alignment,
    pattern_distance,
    select_dominant_cluster,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.session_state import (
    RelationMemorySessionState,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    global_time_offset_us_for_session,
    global_time_us,
    physiology_root_seed_for_session,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION,
    STATIONARY_GAUSSIAN_PEAK_VERSION,
    STATIONARY_PREFERENCE_LANDSCAPE_VERSION,
    evaluate_stationary_preference,
    stationary_user_type_profile,
)

PROJECT_ROOT = Path(__file__).parents[2]
VECTOR_PATH = PROJECT_ROOT / "docs" / "conformance" / "stage-08a-reference-vectors.json"
GENERATOR_PATH = PROJECT_ROOT / "tools" / "generate_stage_08a_reference_vectors.py"


def vectors() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def observation(values: dict[str, Any]) -> SessionPatternObservation:
    return SessionPatternObservation(
        session_index=values["session_index"],
        valid_for_convergence=True,
        invalid_reason=None,
        holder_id=values["holder_id"],
        hue_degree=values["hue"],
        blink_bpm=values["bpm"],
        exploration_decision="hold",
        candidate_generated=False,
        candidate_accepted=False,
    )


def test_reference_file_is_fresh_and_generator_imports_no_product_code() -> None:
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
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert "symbiotic_sim_v2" not in source
    assert all(not name.startswith("symbiotic_sim_v2") for name in imports)


def test_reference_versions_and_stationary_preference_vectors_match() -> None:
    data = vectors()
    assert data["schema_version"] == "stage_08a_reference_vectors_v1"
    assumptions = data["simulation_assumptions"]
    assert assumptions["stationary_landscape_version"] == (
        STATIONARY_PREFERENCE_LANDSCAPE_VERSION
    )
    assert assumptions["peak_model_version"] == STATIONARY_GAUSSIAN_PEAK_VERSION
    assert assumptions["multi_peak_combination_version"] == (
        MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION
    )
    assert assumptions["convergence_evaluator_version"] == (
        ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION
    )
    assert assumptions["moving_preference"] is False
    assert assumptions["convergence_is_diagnostic_only"] is True

    green = stationary_user_type_profile("green_narrow_moderate")
    center = evaluate_stationary_preference(
        green,
        active=True,
        hue_degree=129.0,
        blink_bpm=125.0,
    )
    assert center.preference_match == data["preference"]["single_peak_center"]
    dual = evaluate_stationary_preference(
        stationary_user_type_profile("red_blue_dual_peak"),
        active=True,
        hue_degree=6.0,
        blink_bpm=70.0,
    )
    assert dual.preference_match == data["preference"]["multi_peak_at_red"][
        "expected_max_match"
    ]
    flat = evaluate_stationary_preference(
        stationary_user_type_profile("flat_control"),
        active=True,
        hue_degree=129.0,
        blink_bpm=125.0,
    )
    assert flat.preference_match == data["preference"]["flat_control_match"]


def test_independent_seed_and_global_time_vectors_match_exactly() -> None:
    data = vectors()
    assert data["simulation_assumptions"]["session_seed_policy_version"] == (
        DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION
    )
    for vector in data["session_seed"]:
        assert physiology_root_seed_for_session(
            master_seed=vector["master_seed"],
            stationary_user_type_id=vector["user_type_id"],
            session_index=vector["session_index"],
        ) == vector["expected_root_seed_unsigned32"]
    time = data["global_time"]
    assert global_time_offset_us_for_session(time["session_index"]) == time[
        "global_time_offset_us"
    ]
    assert global_time_us(time["session_index"], time["local_time_us"]) == time[
        "expected_global_time_us"
    ]


def test_independent_pattern_cluster_tie_break_and_medoid_match() -> None:
    data = vectors()
    config = RollingConvergenceConfig()
    same = SessionPatternObservation(
        session_index=0,
        valid_for_convergence=True,
        invalid_reason=None,
        holder_id="life-green",
        hue_degree=100.0,
        blink_bpm=100.0,
        exploration_decision="hold",
        candidate_generated=False,
        candidate_accepted=False,
    )
    hue_boundary = replace(
        same,
        session_index=1,
        hue_degree=102.0,
        global_time_us=None,
    )
    bpm_boundary = replace(
        same,
        session_index=1,
        blink_bpm=120.0,
        global_time_us=None,
    )
    diagonal = replace(
        same,
        session_index=1,
        hue_degree=102.0,
        blink_bpm=120.0,
        global_time_us=None,
    )
    expected_distance = data["pattern_distance"]
    assert pattern_distance(same, hue_boundary, config) == expected_distance["hue_boundary"]
    assert pattern_distance(same, bpm_boundary, config) == expected_distance["bpm_boundary"]
    assert pattern_distance(same, diagonal, config) == expected_distance["ellipse_outside"]

    three_window = (
        SessionPatternObservation(0, True, None, "life-green", 128.0, 118.0, "hold", False, False),
        SessionPatternObservation(1, True, None, "life-green", 129.0, 121.0, "hold", False, False),
        SessionPatternObservation(2, True, None, "life-green", 128.0, 120.0, "hold", False, False),
        SessionPatternObservation(3, True, None, "life-red", 4.0, 65.0, "hold", False, False),
    )
    cluster = select_dominant_cluster(three_window, config)
    assert cluster is not None
    expected_cluster = data["clustering"]["three_of_four"]
    assert cluster.support_count == expected_cluster["support_count"]
    assert list(cluster.member_session_indices) == expected_cluster["member_session_indices"]
    assert list(cluster.outlier_session_indices) == expected_cluster["outlier_session_indices"]
    assert cluster.medoid_session_index == expected_cluster["medoid_session_index"]
    assert cluster.maximum_pairwise_distance == expected_cluster[
        "maximum_pairwise_distance"
    ]


def test_independent_truth_and_normative_state_handoff_vectors_match() -> None:
    data = vectors()
    config = RollingConvergenceConfig()
    observations = [
        SessionPatternObservation(
            index,
            True,
            None,
            "life-green",
            129.0,
            125.0,
            "hold",
            False,
            False,
        )
        for index in range(4)
    ]
    convergence = evaluate_convergence_history(observations, config)[-1]
    truth = evaluate_truth_alignment(
        convergence,
        stationary_user_type_profile("green_narrow_moderate"),
        config,
    )
    expected_truth = data["truth_alignment"]["correct_convergence"]
    assert truth.truth_classification == expected_truth["classification"]
    assert truth.preference_match_at_medoid == expected_truth["preference_match"]
    assert truth.response_gap == expected_truth["response_gap"]

    retained = data["state_handoff"]["retained_across_sessions"]
    persistent = replace(
        RelationMemoryPersistentState.fresh("life-green"),
        k_anchor=(0.1, 0.2, 0.3, 0.4),
        q=0.7,
        e=0.2,
        trial_count=4,
        session_count=8,
    )
    session = RelationMemorySessionState.fresh(persistent)
    assert set(("k_anchor", "q", "e", "trial_count", "session_count")).issubset(retained)
    assert session.initial_k_anchor == persistent.k_anchor
    reset = data["state_handoff"]["reset_or_reacquired_each_session"]
    assert session.w_anchor_session == reset["W_anchor_session"] is None
    assert session.k_trial == reset["k_trial"] is None
    assert session.w_trial_1 == reset["W_trial_1"] is None
    assert session.w_trial_2 == reset["W_trial_2"] is None
    assert session.adaptation_phase == reset["adaptation_phase"]
    assert session.exploration_decision == reset["exploration_decision"] is None


def test_reference_math_contains_no_nonfinite_values() -> None:
    def walk(value: object) -> None:
        if isinstance(value, float):
            assert math.isfinite(value)
        elif isinstance(value, dict):
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(vectors())
