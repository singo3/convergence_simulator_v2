"""Production Stage 8A.2 behavior against independent fixed vectors."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    AutoSearchConfig,
    AutoSearchVersionMetadata,
    CandidateGateConfig,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.gates import (
    evaluate_candidate_gate,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import (
    AutoSearchJob,
    reference_cache_key,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.plan import (
    ConditionPoint,
    build_search_plan,
    local_neighborhood,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.uncertainty import (
    wilson_interval,
)

ROOT = Path(__file__).resolve().parents[2]
VECTOR_PATH = ROOT / "docs" / "conformance" / "stage-08a2-reference-vectors.json"


@pytest.fixture(scope="module")
def vectors():
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def test_reference_file_is_fresh_and_generator_is_production_independent() -> None:
    generator = ROOT / "tools" / "generate_stage_08a2_reference_vectors.py"
    completed = subprocess.run(
        [sys.executable, str(generator), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == completed.stderr == ""
    assert "symbiotic_sim_v2" not in generator.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("preset", "vector_field"),
    (
        ("smoke", "smoke"),
        ("quick", "quick"),
        ("standard", "standard_maximum"),
        ("robust", "robust_maximum"),
    ),
)
def test_plan_counts_match_reference(vectors, preset, vector_field) -> None:
    plan = build_search_plan(AutoSearchConfig.create(search_preset=preset))
    assert plan.maximum_planned_session_runs == vectors["plan_session_runs"][vector_field]


def test_standard_phase1_count_matches_reference(vectors) -> None:
    phase = build_search_plan(AutoSearchConfig.create(search_preset="standard")).phase("coarse")
    assert phase.planned_session_runs == vectors["plan_session_runs"]["standard_phase_1"]


def test_condition_canonicalization_matches_reference(vectors) -> None:
    fixture = vectors["condition_canonicalization"]
    point = ConditionPoint(*fixture["input"])
    assert [point.selected_session_fatigue_target, point.sigma_multiplier] == fixture["canonical"]
    assert point.condition_key == fixture["condition_key"]


def test_phase2_neighborhood_and_dedup_match_reference(vectors) -> None:
    expected = tuple(
        ConditionPoint(
            item["selected_session_fatigue_target"],
            item["sigma_multiplier"],
        )
        for item in vectors["phase_2_neighborhood"]
    )
    actual = local_neighborhood((ConditionPoint(0.03, 1.0),), maximum_conditions=12)
    duplicate = local_neighborhood(
        (ConditionPoint(0.03, 1.0), ConditionPoint(0.03, 1.0)),
        maximum_conditions=12,
    )
    assert actual == expected
    assert duplicate == actual
    assert len(actual) == vectors["duplicate_removal"]["unique_neighborhood_count"]


def _vector_job(vectors, *, point=None, arm="experimental"):
    point = ConditionPoint(0.03, 1.0) if point is None else point
    return AutoSearchJob.create(
        phase="coarse",
        user_type_id="green_hue_dominant_broad_bpm",
        point=point,
        maximum_sessions=4,
        replicate_index=0,
        base_master_seed=20260802,
        arm=arm,
        code_fingerprint="a" * 64,
        versions=AutoSearchVersionMetadata(),
    )


def test_job_id_and_paired_seed_match_reference(vectors) -> None:
    job = _vector_job(vectors)
    assert job.job_id == vectors["job_id"]["sha256"]
    assert job.replicate_master_seed == vectors["paired_seed"]["replicate_master_seed"]
    other = _vector_job(vectors, point=ConditionPoint(0.15, 1.5))
    assert other.replicate_master_seed == job.replicate_master_seed


def test_reference_cache_key_matches_reference(vectors) -> None:
    job = _vector_job(vectors, point=ConditionPoint(0.0, 1.0), arm="reference")
    assert reference_cache_key(job) == vectors["reference_cache_key"]["sha256"]


@pytest.mark.parametrize(
    ("key", "successes"),
    (("zero_of_ten", 0), ("five_of_ten", 5), ("ten_of_ten", 10)),
)
def test_wilson_vectors(vectors, key, successes) -> None:
    expected = vectors["wilson"][key]
    actual = wilson_interval(successes, 10)
    assert actual["rate"] == expected["rate"]
    assert actual["lower95"] == pytest.approx(expected["lower95"])
    assert actual["upper95"] == pytest.approx(expected["upper95"])


def test_gate_pass_and_flat_failure_match_reference(vectors) -> None:
    summary = {
        "candidate_id": "fixture",
        "failed_replicate_rate": 0.0,
        "valid_session_rate": 1.0,
        "flat_spurious_structure_rate": 0.0,
        "flat_mechanical_rotation_warning_rate": 0.0,
        "W_ceiling_blocked_rate": 0.0,
        "worst_nonflat_correct_structure_rate": 0.5,
        "mean_nonflat_correct_structure_rate": 0.5,
        "mean_nonflat_diffuse_rate": 0.0,
    }
    assert (
        evaluate_candidate_gate(summary, CandidateGateConfig()).passed
        is vectors["candidate_gate"]["passing_fixture"]
    )
    summary["flat_spurious_structure_rate"] = 0.26
    assert (
        evaluate_candidate_gate(summary, CandidateGateConfig()).passed
        is vectors["candidate_gate"]["flat_spurious_0_26_fixture"]
    )


def test_reference_vectors_explicitly_preserve_non_adoption_and_tradeoffs(vectors) -> None:
    assert vectors["report_recommendation_fixture"]["formal_spec_adoption"] is False
    assert vectors["report_recommendation_fixture"]["external_resource_count"] == 0
    assert vectors["ranking_tie_break"]["single_opaque_score_used"] is False
    assert len(vectors["specialist_categories"]) == 5
    assert vectors["checkpoint_transition"] == ["pending", "running", "completed"]
    assert vectors["interrupted_running_recovery"] == "pending"
