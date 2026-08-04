"""Self-contained report and recommendation projection tests."""

from __future__ import annotations

import html

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.gates import GateResult
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.html_report import (
    build_html_report,
    write_html_report,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.recommendations import (
    build_recommendations,
)


def _summary(candidate_id="coarse__one"):
    return {
        "candidate_id": candidate_id,
        "condition_key": "one",
        "selected_session_fatigue_target": 0.03,
        "sigma_multiplier": 1.0,
        "worst_nonflat_correct_structure_lower95": 0.4,
        "mean_nonflat_correct_structure_lower95": 0.5,
        "flat_spurious_structure_upper95": 0.2,
        "flat_rotation_upper95": 0.2,
        "W_ceiling_blocked_upper95": 0.3,
        "return_within_2_rate": 0.5,
        "median_first_structure_session": 8.0,
        "post_convergence_outlier_rate": 0.1,
        "life_dominance_specialist_rate": 0.4,
        "bpm_common_specialist_rate": 0.4,
        "multi_attractor_specialist_rate": 0.4,
        "valid_session_rate": 1.0,
        "flat_spurious_structure_rate": 0.1,
        "flat_mechanical_rotation_warning_rate": 0.1,
        "flat_holder_switch_rate": 0.2,
        "W_ceiling_blocked_rate": 0.1,
        "accepted_candidate_count": 2,
        "provisional_success_count": 3,
        "convergence_rate": 0.5,
        "user_type_breakdown": {
            "green_hue_dominant_broad_bpm": {
                "completed_replicate_count": 5,
                "correct_structure": {
                    "rate": 0.6,
                    "lower95": 0.3,
                    "upper95": 0.8,
                },
                "diffuse": {"rate": 0.2},
            }
        },
        "uncertainty": {"small_sample_warning": True},
    }


def _gate(candidate_id="coarse__one", passed=True):
    return GateResult(
        candidate_id,
        passed,
        () if passed else ("flat_spurious_structure_rate:0.5>0.25",),
        "balanced",
        "v",
    )


def _pareto(candidate_id="coarse__one", gate_pass=True):
    return {
        "candidate_id": candidate_id,
        "condition_key": "one",
        "pareto_rank": 1,
        "dominated_by": [],
        "dominates": [],
        "objective_vector": {},
        "gate_pass": gate_pass,
        "blockers": [],
    }


def test_recommendation_has_robust_and_specialist_candidates_without_adoption() -> None:
    summary = _summary()
    recommendations = build_recommendations(
        summaries=(summary,),
        gates={summary["candidate_id"]: _gate()},
        pareto_records=(_pareto(),),
        generated_at="fixed",
        code_fingerprint={"fingerprint_digest": "a"},
        search_preset="standard",
        reproduction_commands=("command",),
    )
    assert recommendations["status"] == "robust_candidates_found"
    assert recommendations["robust_candidate"]["candidate_id"] == summary["candidate_id"]
    assert recommendations["robust_compromise"] == recommendations["robust_candidate"]
    assert recommendations["formal_spec_adoption"] is False
    assert recommendations["single_opaque_score_used"] is False


def test_no_candidate_is_explicit_and_preserves_blocker_counts() -> None:
    summary = _summary()
    recommendations = build_recommendations(
        summaries=(summary,),
        gates={summary["candidate_id"]: _gate(passed=False)},
        pareto_records=(_pareto(gate_pass=False),),
        generated_at="fixed",
        code_fingerprint={},
        search_preset="standard",
        reproduction_commands=(),
    )
    assert recommendations["status"] == "no_robust_candidate"
    assert recommendations["robust_candidate"] is None
    assert recommendations["robust_compromise"] is None
    assert recommendations["no_candidate_blockers"] == {"flat_spurious_structure_rate": 1}


def test_smoke_never_claims_a_robust_candidate() -> None:
    summary = _summary()
    recommendations = build_recommendations(
        summaries=(summary,),
        gates={summary["candidate_id"]: _gate()},
        pareto_records=(_pareto(),),
        generated_at="fixed",
        code_fingerprint={},
        search_preset="smoke",
        reproduction_commands=(),
    )
    assert recommendations["status"] == "smoke_diagnostic_only"
    assert recommendations["robust_candidate"] is None
    assert recommendations["robust_compromise"] is None
    assert recommendations["smoke_does_not_establish_candidate_validity"] is True


def _html_values(candidate_id="coarse__one"):
    summary = _summary(candidate_id)
    recommendations = build_recommendations(
        summaries=(summary,),
        gates={candidate_id: _gate(candidate_id)},
        pareto_records=(_pareto(candidate_id),),
        generated_at="fixed",
        code_fingerprint={},
        search_preset="smoke",
        reproduction_commands=("python -m local",),
    )
    return {
        "manifest": {
            "config": {"search_preset": "smoke"},
            "code_fingerprint": {"git_head_sha": "abc"},
        },
        "runtime_summary": {
            "final_phase": "coarse",
            "completed_jobs": 1,
            "failed_jobs": 0,
            "elapsed_seconds": 1.0,
            "reference_cache_entries": 0,
        },
        "summaries": (summary,),
        "pareto_records": (_pareto(candidate_id),),
        "recommendations": recommendations,
        "phase_selection_history": (),
        "reproduction_commands": ("python -m local",),
    }


@pytest.mark.parametrize(
    "required",
    (
        "formal_spec_adoption=false",
        "Pareto frontier",
        "疲労 × sigma heatmap",
        "95% Wilson",
        "再現コマンド",
        "Smoke is an implementation check only",
    ),
)
def test_html_contains_required_offline_report_sections(required) -> None:
    assert required in build_html_report(**_html_values())


def test_html_has_all_twenty_numbered_sections() -> None:
    document = build_html_report(**_html_values())
    assert all(f">{number}." in document for number in range(1, 21))


def test_html_has_no_external_url_or_external_script(tmp_path) -> None:
    path = write_html_report(tmp_path / "report.html", **_html_values())
    document = path.read_text(encoding="utf-8").lower()
    assert "http://" not in document
    assert "https://" not in document
    assert "<script src" not in document
    assert "google fonts" not in document


def test_html_exposes_user_weakness_safety_and_adoption_evidence() -> None:
    document = build_html_report(**_html_values())
    for evidence in (
        "green_hue_dominant_broad_bpm",
        "Flat control安全診断",
        "Mechanical rotation",
        "formal adoptions observed",
        "median first structure session",
        "return within 2 rate",
        "small-sample candidates",
    ):
        assert evidence in document


def test_html_escapes_untrusted_candidate_identity() -> None:
    candidate_id = "<script>alert(1)</script>"
    document = build_html_report(**_html_values(candidate_id))
    assert candidate_id not in document
    assert html.escape(candidate_id) in document
