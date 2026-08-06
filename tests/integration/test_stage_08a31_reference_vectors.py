"""Independent Stage 8A.3.1 reference-vector conformance."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    REFERENCE_ETA,
    REFERENCE_RHO,
    factorial_conditions,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.factorial_effects import (
    two_by_two_effects,
)

ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / "docs/conformance/stage-08a31-reference-vectors.json"
GENERATOR = ROOT / "tools/generate_stage_08a31_reference_vectors.py"


@pytest.fixture(scope="module")
def vectors() -> dict[str, object]:
    return json.loads(VECTORS.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "key",
    (
        "eta_equivalence",
        "conditions",
        "factorial_effect_fixture",
        "random_cache",
        "participant_pairing",
        "positive_participant_count",
        "type_failure_detection",
        "recommendation",
        "participant_chart_fixture",
        "user_type_heatmap_fixture",
        "plan_counts",
    ),
)
def test_reference_vector_has_required_fixture(vectors, key: str) -> None:
    assert vectors["production_implementation_imported"] is False
    assert key in vectors


def test_reference_vector_generator_is_fresh_and_independent() -> None:
    source = GENERATOR.read_text(encoding="utf-8")
    assert "symbiotic_sim_v2" not in source
    completed = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(GENERATOR), "--check"],
        cwd=ROOT,
        check=False,
    )
    assert completed.returncode == 0


def test_eta_and_rho_vectors_match_production(vectors) -> None:
    fixture = vectors["eta_equivalence"]
    assert fixture["equal"] is True
    assert fixture["target_derived_eta"] == REFERENCE_ETA
    assert fixture["v2_reference_eta"] == REFERENCE_ETA
    assert fixture["rho_reference"] == REFERENCE_RHO


def test_condition_vectors_match_production(vectors) -> None:
    expected = [
        {
            "condition_id": item.condition_id,
            "session_end_recovery_policy": item.session_end_recovery_policy,
            "sigma_multiplier": item.sigma_multiplier,
            "effective_selected_session_fatigue_target": (
                item.effective_selected_session_fatigue_target
            ),
            "eta_selected": item.eta_selected,
            "rho": item.rho,
            "formal_spec_adoption": item.formal_spec_adoption,
        }
        for item in factorial_conditions()
    ]
    assert vectors["conditions"] == expected


def test_factorial_effect_vector_matches_production(vectors) -> None:
    fixture = vectors["factorial_effect_fixture"]
    values = fixture["values"]
    actual = two_by_two_effects(
        a=values["A"],
        b=values["B"],
        c=values["C"],
        d=values["D"],
    )
    assert actual["sigma_effect_gradual_b_minus_a"] == fixture[
        "sigma_effect_gradual_B_minus_A"
    ]
    assert actual["sigma_effect_full_d_minus_c"] == fixture["sigma_effect_full_D_minus_C"]
    assert actual["recovery_effect_sigma100_c_minus_a"] == fixture[
        "recovery_effect_sigma100_C_minus_A"
    ]
    assert actual["recovery_effect_sigma050_d_minus_b"] == fixture[
        "recovery_effect_sigma050_D_minus_B"
    ]
    assert actual["interaction_sigma_by_recovery"] == fixture["interaction"]
    assert actual["interaction_recovery_by_sigma"] == fixture["interaction_alt"]


def test_cache_vector_excludes_condition_fatigue_and_sigma(vectors) -> None:
    fixture = vectors["random_cache"]
    assert fixture["condition_id_in_key"] is False
    assert fixture["recovery_in_key"] is False
    assert fixture["sigma_in_key"] is False
    assert fixture["shared_condition_count"] == 4


def test_participant_chart_and_heatmap_vectors(vectors) -> None:
    participant = vectors["participant_chart_fixture"]
    heatmap = vectors["user_type_heatmap_fixture"]
    assert participant["panel_count"] == 8
    assert participant["x"] == "session_index"
    assert participant["y"] == "blink_bpm"
    assert participant["fill"] == "actual_hue"
    assert participant["shapes"] == {
        "life-red": "circle",
        "life-green": "triangle",
        "life-blue": "square",
    }
    assert heatmap["rows"] == 9
    assert heatmap["columns"] == 4
