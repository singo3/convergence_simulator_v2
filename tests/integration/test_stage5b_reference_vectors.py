"""Conformance-vector freshness and selected production agreement checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from symbiotic_sim_v2.digital_life.math import calculate_e_next
from symbiotic_sim_v2.digital_life.second_round import calculate_g, decide_q_update
from symbiotic_sim_v2.runtime.multi_life.touch_delivery import tau_to_touch_offset_us


def project_root() -> Path:
    return Path(__file__).parents[2]


def vectors() -> dict[str, object]:
    path = project_root() / "docs" / "conformance" / "stage-05b-reference-vectors.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_independent_reference_vector_file_is_current() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(project_root() / "tools" / "generate_stage_05b_reference_vectors.py"),
            "--check",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == ""
    assert completed.stderr == ""


def test_reference_tau_g_e_and_q_vectors_match_production_boundaries() -> None:
    data = vectors()
    assumptions = data["simulation_assumptions"]
    core = data["core_vectors"]
    assert isinstance(assumptions, dict)
    assert isinstance(core, dict)

    tau_vectors = assumptions["tau_delivery"]["vectors"]
    for vector in tau_vectors:
        assert tau_to_touch_offset_us(vector["tau"]) == vector["expected_touch_offset_us"]

    for vector in core["g"]:
        assert calculate_g(
            vector["digital_life_id"], vector["qualification_holder_id"]
        ) == vector["expected"]

    e_vectors = core["e"]
    assert calculate_e_next(0.4, 1, 1) == pytest.approx(
        e_vectors["single_accumulation"]
    )
    assert calculate_e_next(0.4, 0, 1) == pytest.approx(e_vectors["single_recovery"])

    for vector in core["q"]:
        decision = decide_q_update(
            q=vector["q"],
            w=vector["w"],
            g=vector["g"],
            evaluation_present=True,
            is_new_valid_evaluation=True,
            evaluation_kind=("baseline" if vector["name"] == "baseline_skip" else "bundle"),
            evaluation_is_valid=True,
        )
        assert decision.q_after == pytest.approx(vector["expected"])
        assert decision.applied is vector["applied"]
        assert decision.skip_reason == vector["skip_reason"]
