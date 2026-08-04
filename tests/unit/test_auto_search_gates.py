"""Balanced/coarse gate transparency tests."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    CandidateGateConfig,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.gates import (
    evaluate_candidate_gate,
)


def _passing() -> dict[str, float | str]:
    return {
        "candidate_id": "candidate",
        "failed_replicate_rate": 0.0,
        "valid_session_rate": 1.0,
        "flat_spurious_structure_rate": 0.0,
        "flat_mechanical_rotation_warning_rate": 0.0,
        "W_ceiling_blocked_rate": 0.0,
        "worst_nonflat_correct_structure_rate": 0.6,
        "mean_nonflat_correct_structure_rate": 0.7,
        "mean_nonflat_diffuse_rate": 0.1,
    }


def test_balanced_gate_passes_all_thresholds() -> None:
    result = evaluate_candidate_gate(_passing(), CandidateGateConfig())
    assert result.passed
    assert result.blockers == ()
    assert result.gate_kind == "balanced_robust"


@pytest.mark.parametrize(
    ("field", "value", "blocker"),
    (
        ("failed_replicate_rate", 0.1, "failed_replicate_rate"),
        ("valid_session_rate", 0.94, "valid_session_rate"),
        ("flat_spurious_structure_rate", 0.26, "flat_spurious_structure_rate"),
        (
            "flat_mechanical_rotation_warning_rate",
            0.26,
            "flat_mechanical_rotation_warning_rate",
        ),
        ("W_ceiling_blocked_rate", 0.51, "W_ceiling_blocked_rate"),
        (
            "worst_nonflat_correct_structure_rate",
            0.29,
            "worst_nonflat_correct_structure_rate",
        ),
        ("mean_nonflat_diffuse_rate", 0.51, "mean_nonflat_diffuse_rate"),
    ),
)
def test_each_balanced_gate_blocker_is_explicit(field, value, blocker) -> None:
    summary = _passing()
    summary[field] = value
    result = evaluate_candidate_gate(summary, CandidateGateConfig())
    assert not result.passed
    assert result.blockers[0].startswith(blocker + ":")


def test_missing_metric_is_not_treated_as_favorable() -> None:
    summary = _passing()
    summary.pop("W_ceiling_blocked_rate")
    result = evaluate_candidate_gate(summary, CandidateGateConfig())
    assert result.blockers == ("W_ceiling_blocked_rate:missing",)


def test_coarse_gate_is_deliberately_looser() -> None:
    summary = _passing()
    summary["flat_spurious_structure_rate"] = 0.7
    summary["W_ceiling_blocked_rate"] = 0.8
    summary["worst_nonflat_correct_structure_rate"] = 0.01
    assert evaluate_candidate_gate(summary, CandidateGateConfig(), coarse=True).passed
    assert not evaluate_candidate_gate(summary, CandidateGateConfig()).passed


def test_coarse_mean_correct_is_strictly_greater_than_zero() -> None:
    summary = _passing()
    summary["mean_nonflat_correct_structure_rate"] = 0.0
    result = evaluate_candidate_gate(summary, CandidateGateConfig(), coarse=True)
    assert not result.passed
    assert "<=" in result.blockers[0]


def test_candidate_gate_is_configurable() -> None:
    summary = _passing()
    summary["worst_nonflat_correct_structure_rate"] = 0.2
    relaxed = CandidateGateConfig(worst_nonflat_correct_structure_rate_min=0.2)
    assert evaluate_candidate_gate(summary, relaxed).passed
