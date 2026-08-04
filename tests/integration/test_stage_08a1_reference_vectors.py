"""Freshness and production agreement for independent Stage 8A.1 vectors."""

from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.convergence.structured import (
    StructuredConvergenceConfig,
    StructuredSessionObservation,
    WCeilingObservation,
    evaluate_bpm_common,
    evaluate_life_dominance,
    evaluate_mechanical_rotation,
    evaluate_multi_attractor,
    evaluate_w_ceiling,
)
from symbiotic_sim_v2.digital_life.math import ETA_E, RHO_E, calculate_e_next
from symbiotic_sim_v2.digital_life.relation_memory.candidate import generate_candidate
from symbiotic_sim_v2.digital_life.relation_memory.direction import (
    derive_search_direction,
)
from symbiotic_sim_v2.digital_life.relation_memory.intrinsic import (
    derive_relation_memory_intrinsic_profile,
    exploration_probability,
    exploration_sigma,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.aggregation import (
    FatigueSigmaReplicateResult,
    aggregate_condition,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    SelectedSessionFatiguePolicy,
    selected_session_eta,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.manifest import (
    FatigueSigmaExperimentManifest,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.replicate_seed import (
    paired_physiology_root_seed,
    paired_replicate_master_seed,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.sigma_policy import (
    ScaledReferenceSigmaPolicy,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    evaluate_stationary_preference_v2,
    stationary_user_type_profile_v2,
)

PROJECT_ROOT = Path(__file__).parents[2]
VECTOR_PATH = PROJECT_ROOT / "docs" / "conformance" / "stage-08a1-reference-vectors.json"
GENERATOR_PATH = PROJECT_ROOT / "tools" / "generate_stage_08a1_reference_vectors.py"


def vectors() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def normalized(value: object) -> object:
    return json.loads(json.dumps(value, allow_nan=False, sort_keys=True))


def structured_observations(
    values: list[dict[str, Any]],
) -> tuple[StructuredSessionObservation, ...]:
    return tuple(
        StructuredSessionObservation(
            session_index=value["session_index"],
            valid_for_convergence=True,
            holder_id=value["holder_id"],
            hue_degree=value["hue"],
            blink_bpm=value["bpm"],
        )
        for value in values
    )


def holder_observations(holders: list[str]) -> tuple[StructuredSessionObservation, ...]:
    return tuple(
        StructuredSessionObservation(
            session_index=index,
            valid_for_convergence=True,
            holder_id=holder,
            hue_degree={"life-red": 5.0, "life-green": 125.0, "life-blue": 250.0}[holder],
            blink_bpm=100.0,
        )
        for index, holder in enumerate(holders)
    )


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


def test_reference_versions_and_scope_are_exact() -> None:
    data = vectors()
    assert data["schema_version"] == "stage_08a1_reference_vectors_v1"
    assert data["normative_source"] == {
        "algorithm_version": "adaptive_random_search_confirmed_v1",
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
        "document_version": "v2.0",
        "profile_version": "symbiotic_signal_loop_reference_v1_0",
        "sha256": "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73",
        "size_bytes": 65_759,
        "state_schema_version": "relation_memory_state_v2",
    }
    assumptions = data["simulation_assumptions"]
    assert assumptions["project_version"] == "0.11.0"
    assert assumptions["formal_spec_adoption"] is False
    assert assumptions["moving_preference"] is False
    assert assumptions["convergence_is_diagnostic_only"] is True
    assert assumptions["p_explore_modified"] is False
    assert assumptions["epsilon_accept_modified"] is False
    assert assumptions["q_coefficients_modified"] is False
    assert assumptions["Monte_Carlo"] is False
    manifest = FatigueSigmaExperimentManifest().to_dict()
    expected_manifest = data["experiment_manifest"]
    for field, expected in expected_manifest.items():
        assert manifest[field] == expected


def test_independent_fatigue_vectors_match_reference_and_experiment() -> None:
    fatigue = vectors()["fatigue"]
    assert fatigue["eta_reference"] == ETA_E
    assert fatigue["rho_reference"] == RHO_E
    for vector in fatigue["target_vectors"]:
        target = vector["selected_session_fatigue_target"]
        assert selected_session_eta(target) == vector["eta_selected"]
        policy = SelectedSessionFatiguePolicy(target)
        e = 0.0
        for _ in range(fatigue["active_signal_count"]):
            e = policy.calculate_e_next(e, 1, 1)
        assert e == vector["e_from_zero_after_180_active_signals"]
    assert selected_session_eta(0.15) == ETA_E

    saturation = fatigue["nonzero_saturation"]
    policy = SelectedSessionFatiguePolicy(saturation["target"])
    e = saturation["initial_e"]
    for _ in range(180):
        e = policy.calculate_e_next(e, 1, 1)
    assert e == saturation["e_after_180_active_signals"]

    recovery = fatigue["baseline_reference_recovery"]
    e = recovery["initial_e"]
    for _ in range(recovery["signals"]):
        e = policy.calculate_e_next(e, 0, 0)
    assert e == recovery["expected_e"]
    reference_policy = SelectedSessionFatiguePolicy(0.15)
    assert reference_policy.calculate_e_next(0.4, 1, 1) == calculate_e_next(0.4, 1, 1)

    session_end = fatigue["session_end_policy"]
    for name in ("unselected", "selected"):
        expected = session_end[name]
        decision = policy.decide_session_end(
            expected["e_before"], expected["selected_active_signal_count"]
        )
        assert decision.e_after_policy == expected["e_after"]
        assert decision.full_recovery_applied is expected["full_recovery_applied"]
    assert fatigue["reference_arm"]["unselected_full_recovery"] is False
    assert session_end["runner_postprocesses_e"] is False


def test_independent_scaled_sigma_vectors_preserve_all_other_search_values() -> None:
    expected = vectors()["sigma"]
    profile = derive_relation_memory_intrinsic_profile(expected["digital_life_id"])
    assert profile.curiosity == expected["curiosity"]
    assert profile.sigma_min == expected["sigma_min_reference"]
    assert profile.sigma_max == expected["sigma_max_reference"]
    assert profile.epsilon_accept == expected["epsilon_accept"]
    assert profile.p_explore_min == expected["p_explore_min"]
    reference = exploration_sigma(
        expected["W_anchor_session"], profile.sigma_min, profile.sigma_max
    )
    probability = exploration_probability(expected["W_anchor_session"], profile.p_explore_min)
    direction = derive_search_direction(
        expected["digital_life_id"], expected["direction_trial_index"]
    )
    assert direction.xi[0] == expected["direction_f"]
    assert direction.xi[2] == expected["direction_t"]
    for vector in expected["vectors"]:
        decision = ScaledReferenceSigmaPolicy(vector["multiplier"]).scale(reference)
        assert decision.reference_sigma == vector["reference_sigma"]
        assert decision.effective_sigma == vector["effective_sigma"]
        assert vector["p_explore"] == probability
        assert vector["epsilon_accept"] == profile.epsilon_accept
        candidate = generate_candidate((0.5, 0.5, 0.5, 0.5), decision.effective_sigma, direction)
        assert candidate[0] - 0.5 == vector["candidate_delta_f"]
        assert candidate[2] - 0.5 == vector["candidate_delta_t"]
        assert candidate[1] == candidate[3] == 0.5
    assert expected["condition_in_direction_hash"] is False
    assert expected["explores_f_t_only"] is expected["a_d_unchanged"] is True


def test_independent_axis_neutral_and_three_peak_vectors_match() -> None:
    expected = vectors()["preference"]
    green = stationary_user_type_profile_v2("green_hue_dominant_broad_bpm")
    for bpm, name in ((10.0, "at_bpm_10"), (165.0, "at_bpm_165")):
        result = evaluate_stationary_preference_v2(
            green, active=True, hue_degree=125.0, blink_bpm=bpm
        )
        assert result.preference_match == expected["green_hue_bpm_neutral"][name]

    common = stationary_user_type_profile_v2("bpm_common_100_hue_neutral")
    for hue, bpm, name in (
        (0.0, 100.0, "at_hue_0_bpm_100"),
        (300.0, 112.0, "at_hue_300_bpm_112"),
    ):
        result = evaluate_stationary_preference_v2(
            common, active=True, hue_degree=hue, blink_bpm=bpm
        )
        assert result.preference_match == expected["bpm_common_hue_neutral"][name]

    equal = stationary_user_type_profile_v2("three_life_bpm_equal")
    for peak, expected_match in zip(equal.peaks, expected["three_equal_peak_centers"], strict=True):
        result = evaluate_stationary_preference_v2(
            equal,
            active=True,
            hue_degree=peak.preferred_hue_degree,
            blink_bpm=peak.preferred_blink_bpm,
        )
        assert result.preference_match == expected_match
    flat = evaluate_stationary_preference_v2(
        stationary_user_type_profile_v2("flat_control"),
        active=True,
        hue_degree=125.0,
        blink_bpm=100.0,
    )
    assert flat.preference_match == expected["flat_control_match"]


def test_independent_paired_replicate_and_session_seed_vectors_match() -> None:
    expected = vectors()["paired_replicate_seed"]
    for vector in expected["replicate_vectors"]:
        assert (
            paired_replicate_master_seed(vector["base_master_seed"], vector["replicate_index"])
            == vector["expected_master_seed_unsigned32"]
        )
    for vector in expected["session_vectors"]:
        assert (
            paired_physiology_root_seed(
                base_master_seed=20260802,
                replicate_index=0,
                user_type_id=vector["user_type_id"],
                session_index=vector["session_index"],
            )
            == vector["expected_root_seed_unsigned32"]
        )
    assert expected["excluded_key_fields"] == [
        "fatigue_target",
        "sigma_multiplier",
        "condition_id",
        "condition_hash",
        "convergence_result",
    ]


def test_independent_life_dominance_vectors_match_without_hue_requirement() -> None:
    config = StructuredConvergenceConfig()
    expected = vectors()["life_dominance"]
    fields = (
        "dominant_life_id",
        "dominant_count",
        "share",
        "strict_consecutive_run",
        "one_outlier_tolerant_longest_run",
        "maximum_consecutive_outliers",
        "latest_session_outlier",
        "return_opportunity_count",
        "return_within_one_session_count",
        "return_within_one_session_rate",
        "return_within_two_sessions_count",
        "return_within_two_sessions_rate",
        "confirmed",
    )
    for name in ("one_outlier", "two_consecutive_outliers", "latest_outlier"):
        vector = expected[name]
        actual = evaluate_life_dominance(holder_observations(vector["holders"]), config)
        for field in fields:
            assert getattr(actual, field) == vector[field], (name, field)
    assert expected["hue_match_required"] is False


def test_independent_common_bpm_and_multi_attractor_vectors_match() -> None:
    config = StructuredConvergenceConfig()
    common_expected = vectors()["bpm_common"]
    common = evaluate_bpm_common(structured_observations(common_expected["observations"]), config)
    for field in (
        "support",
        "member_session_indices",
        "outlier_session_indices",
        "medoid_bpm",
        "median_bpm",
        "bpm_range",
        "mean_absolute_deviation",
        "participating_life_ids",
        "cross_life",
        "confirmed",
    ):
        assert normalized(getattr(common, field)) == common_expected[field], field

    multi_expected = vectors()["multi_attractor"]
    multi = evaluate_multi_attractor(
        structured_observations(multi_expected["observations"]), config
    )
    assert (
        normalized([item.to_dict() for item in multi.life_attractors])
        == multi_expected["life_attractors"]
    )
    assert multi.attractor_count == multi_expected["attractor_count"]
    assert multi.attractor_separation == multi_expected["attractor_separation"]
    assert multi.two_attractor_flag is multi_expected["two_attractor_flag"]
    assert multi.three_attractor_flag is multi_expected["three_attractor_flag"]
    assert multi.confirmed is multi_expected["confirmed"]


def test_independent_mechanical_rotation_and_w_ceiling_vectors_match() -> None:
    rotation = vectors()["mechanical_rotation"]
    for name in ("three_life_cycle", "immediate_return"):
        expected = rotation[name]
        actual = evaluate_mechanical_rotation(holder_observations(expected["holders"]))
        for field in (
            "dominant_life_id",
            "holder_switch_rate",
            "three_distinct_life_window_rate",
            "immediate_return_rate",
            "three_life_cycle_rate",
            "dominant_life_return_rate",
            "mean_sessions_between_same_life_selections",
        ):
            assert getattr(actual, field) == expected[field], (name, field)
    assert rotation["is_primary_convergence_rule"] is False

    for name in ("identifiable", "partly_saturated", "blocked"):
        expected = vectors()["w_ceiling"][name]
        observations = tuple(
            WCeilingObservation(
                session_index=index,
                w_anchor_session=item["anchor"],
                epsilon_accept=item["epsilon"],
                w_trial_1=item["trials"][0] if item["trials"] else None,
                w_trial_2=item["trials"][1] if len(item["trials"]) > 1 else None,
                candidate_generated=bool(item["trials"]),
                candidate_accepted=False,
            )
            for index, item in enumerate(expected["observations"])
        )
        actual = evaluate_w_ceiling(observations)
        for field in (
            "anchor_evaluation_count",
            "w_anchor_session_ceiling_count",
            "w_anchor_session_ge_one_minus_epsilon_count",
            "mathematically_impossible_provisional_adoption_count",
            "w_trial_ceiling_count",
            "classification",
        ):
            assert getattr(actual, field) == expected[field], (name, field)


def test_aggregation_vector_has_tradeoffs_and_no_forced_best_score() -> None:
    aggregate = vectors()["condition_grid_aggregation"]
    replicates = aggregate["replicate_results"]
    assert aggregate["replicate_count"] == len(replicates)
    assert aggregate["life_dominant_convergence_rate"] == sum(
        item["life"] for item in replicates
    ) / len(replicates)
    assert aggregate["bpm_common_convergence_rate"] == sum(
        item["bpm"] for item in replicates
    ) / len(replicates)
    assert aggregate["multi_attractor_convergence_rate"] == sum(
        item["multi"] for item in replicates
    ) / len(replicates)
    assert aggregate["accepted_count"] == sum(item["accepted"] for item in replicates)
    assert aggregate["single_forced_best_score_present"] is False

    production_replicates = tuple(
        FatigueSigmaReplicateResult(
            condition_id="fixture",
            user_type_id="green_hue_dominant_broad_bpm",
            selected_session_fatigue_target=0.05,
            sigma_multiplier=1.0,
            replicate_index=index,
            replicate_master_seed=index,
            sessions_completed=24,
            sessions_expected=24,
            completed=True,
            failed=False,
            failure_reason=None,
            summary_classification=item["classification"],
            truth_classification=item["truth"],
            life_dominant_converged=item["life"],
            bpm_common_converged=item["bpm"],
            multi_attractor_converged=item["multi"],
            single_life_pattern_converged=item["life"] and item["bpm"],
            first_life_convergence_session=item["first_life"],
            first_bpm_convergence_session=(item["first_life"] if item["bpm"] else None),
            first_multi_attractor_session=None,
            dominant_life_share=0.75 if item["life"] else None,
            bpm_cluster_width=10.0 if item["bpm"] else None,
            post_convergence_outlier_rate=0.0,
            return_within_1_rate=1.0 if item["life"] else 0.0,
            return_within_2_rate=1.0 if item["life"] else 0.0,
            mechanical_rotation={
                "holder_switch_rate": 0.0,
                "three_distinct_life_window_rate": 0.0,
                "immediate_return_rate": 0.0,
                "three_life_cycle_rate": 0.0,
                "dominant_life_return_rate": 0.0,
            },
            w_ceiling={"classification": "exploration_identifiable"},
            explore_count=1,
            candidate_count=1,
            accepted_count=item["accepted"],
            selected_life_mean_e=0.05,
            selected_life_max_e=0.05,
            nonselected_full_recovery_count=2,
            effective_sigma_mean=0.1,
            effective_sigma_min=0.1,
            effective_sigma_max=0.1,
            candidate_delta_hue=(),
            candidate_delta_bpm=(),
            result_digest=f"digest-{index}",
        )
        for index, item in enumerate(replicates)
    )
    summary = aggregate_condition(production_replicates)
    assert summary.replicate_count == aggregate["replicate_count"]
    assert summary.life_dominant_convergence_rate == aggregate["life_dominant_convergence_rate"]
    assert summary.bpm_common_convergence_rate == aggregate["bpm_common_convergence_rate"]
    assert summary.multi_attractor_convergence_rate == aggregate["multi_attractor_convergence_rate"]
    assert summary.diffuse_rate == aggregate["diffuse_rate"]
    assert summary.correct_structure_rate == aggregate["correct_structure_rate"]
    assert summary.partial_structure_rate == aggregate["partial_structure_rate"]
    assert (
        summary.median_first_life_convergence_session
        == aggregate["median_first_life_convergence_session"]
    )
    assert summary.accepted_count == aggregate["accepted_count"]


def test_reference_vectors_contain_no_nonfinite_numbers() -> None:
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
