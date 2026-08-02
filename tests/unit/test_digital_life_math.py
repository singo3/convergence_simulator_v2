"""Pure Stage 5A mappings checked against independent fixed vectors."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from symbiotic_sim_v2.digital_life.math import (
    ETA_E,
    RHO_E,
    calculate_e_next,
    calculate_nd,
    calculate_p,
    calculate_q_next,
    calculate_tau,
    calculate_v,
    clip01,
    evaluate_w,
    intrinsic_b_mapping,
    w_minus,
    w_plus,
)

VECTOR_PATH = (
    Path(__file__).parents[2]
    / "docs"
    / "conformance"
    / "stage-05a-reference-vectors.json"
)


def reference_vectors() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def normative_vectors() -> dict[str, Any]:
    return reference_vectors()["normative_vectors"]


def test_reference_file_pins_the_verified_normative_source_identity() -> None:
    source = reference_vectors()["normative_source"]

    assert source == {
        "algorithm_version": "adaptive_random_search_confirmed_v1",
        "document_version": "v2.0",
        "profile_version": "symbiotic_signal_loop_reference_v1_0",
        "sha256": "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73",
        "size_bytes": 65_759,
        "state_schema_version": "relation_memory_state_v2",
    }


def test_clip01_matches_all_fixed_boundaries() -> None:
    for vector in normative_vectors()["clip01"]:
        assert clip01(vector["input"]) == vector["expected"]


@pytest.mark.parametrize("value", (True, False, "0.5", None))
def test_clip01_rejects_non_numeric_or_boolean_values(value: object) -> None:
    with pytest.raises(TypeError):
        clip01(value)


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_clip01_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        clip01(value)


def test_nd_matches_fixed_baseline_relative_vectors() -> None:
    for vector in normative_vectors()["nd"]:
        actual = calculate_nd(
            vector["n_current"],
            vector["n_baseline_session"],
            vector["delta_n"],
        )
        assert actual == pytest.approx(vector["expected"], abs=1e-15), vector["name"]


def test_nd_api_has_no_previous_n_input() -> None:
    assert set(inspect.signature(calculate_nd).parameters) == {
        "n_current",
        "n_baseline_session",
        "delta_n",
    }
    baseline = 0.4
    current = 0.5
    assert calculate_nd(current, baseline, 0.1) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "values",
    (
        (True, 0.5, 0.1),
        (0.5, False, 0.1),
        (0.5, 0.5, True),
        (-0.01, 0.5, 0.1),
        (0.5, 1.01, 0.1),
        (0.5, 0.5, 0.0),
        (0.5, 0.5, float("nan")),
    ),
)
def test_nd_rejects_invalid_inputs_without_silent_clipping(
    values: tuple[object, object, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        calculate_nd(*values)


def test_w_is_a_separate_pure_mapping_with_fixed_identity_values() -> None:
    assert evaluate_w is not calculate_nd
    assert set(inspect.signature(evaluate_w).parameters) == {"nd"}
    for vector in normative_vectors()["w"]:
        assert evaluate_w(vector["nd"]) == vector["expected"]


@pytest.mark.parametrize("nd", (True, -0.01, 1.01, float("nan")))
def test_w_rejects_non_unit_inputs(nd: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        evaluate_w(nd)


def test_phi_p_matches_s_zero_and_s_one_vectors_for_all_lives() -> None:
    for vector in normative_vectors()["p"]:
        actual = calculate_p(vector["s"], vector["p_intrinsic"])
        assert actual == vector["expected"], vector["role"]
        if vector["s"] == 0:
            assert actual == 1.0
        else:
            assert actual == vector["p_intrinsic"]


@pytest.mark.parametrize(
    "values",
    ((True, 0.5), (False, 0.5), (2, 0.5), (1.0, 0.5), (1, True), (1, -0.01)),
)
def test_phi_p_accepts_only_integer_s_and_unit_intrinsic_p(
    values: tuple[object, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        calculate_p(*values)


def test_v_matches_fixed_vectors_and_is_null_before_n_is_available() -> None:
    for vector in normative_vectors()["v"]:
        actual = calculate_v(vector["n_current"], vector["q"], vector["e"])
        expected = vector["expected"]
        if expected is None:
            assert actual is None
        else:
            assert actual == pytest.approx(expected, abs=1e-15), vector["name"]


def test_v_changes_with_n_and_has_no_holding_state() -> None:
    assert calculate_v(0.2, 0.5, 0.0) == 0.35
    assert calculate_v(0.4, 0.5, 0.0) == 0.45
    assert calculate_v(0.2, 0.5, 0.2) == pytest.approx(0.28)


@pytest.mark.parametrize(
    "values",
    (
        (True, 0.5, 0.0),
        (-0.01, 0.5, 0.0),
        (0.2, True, 0.0),
        (0.2, 1.01, 0.0),
        (0.2, 0.5, float("nan")),
    ),
)
def test_v_rejects_invalid_available_inputs(values: tuple[object, object, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        calculate_v(*values)


def test_phi_b_matches_role_midpoints_and_custom_k_without_w() -> None:
    assert "w" not in inspect.signature(intrinsic_b_mapping).parameters
    for vector in normative_vectors()["phi_b"]:
        actual = intrinsic_b_mapping(
            vector["k"],
            f_min=vector["f_min"],
            f_max=vector["f_max"],
            a_fixed=vector["a_fixed"],
            t_min=vector["t_min"],
            t_max=vector["t_max"],
            d_fixed=vector["d_fixed"],
        )
        assert actual == pytest.approx(tuple(vector["expected"]), abs=1e-15)
        assert actual[1] == vector["a_fixed"]
        assert actual[3] == vector["d_fixed"]


@pytest.mark.parametrize(
    "k",
    (
        (),
        (0.5, 0.5, 0.5),
        (0.5, 0.5, 0.5, 0.5, 0.5),
        (0.5, True, 0.5, 0.5),
        (-0.01, 0.5, 0.5, 0.5),
        "0.5,0.5,0.5,0.5",
    ),
)
def test_phi_b_rejects_invalid_k(k: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        intrinsic_b_mapping(
            k,  # type: ignore[arg-type]
            f_min=120 / 360,
            f_max=130 / 360,
            a_fixed=0.5,
            t_min=0.0,
            t_max=1.0,
            d_fixed=0.5,
        )


def test_tau_matches_fixed_formula_birth_epsilon_clip_and_monotonic_vectors() -> None:
    results: dict[str, float | None] = {}
    for vector in normative_vectors()["tau"]:
        actual = calculate_tau(
            vector["s"],
            vector["p"],
            vector["v"],
            vector["epsilon_tau"],
            vector["birth_phase"],
        )
        expected = vector["expected"]
        if expected is None:
            assert actual is None
        else:
            assert actual == pytest.approx(expected, abs=1e-15), vector["name"]
        results[vector["name"]] = actual

    assert isinstance(results["lower_p"], float)
    assert isinstance(results["higher_p"], float)
    assert isinstance(results["higher_v"], float)
    assert isinstance(results["formula"], float)
    assert results["lower_p"] < results["higher_p"]
    assert results["higher_v"] < results["formula"]
    assert results["upper_clip"] == 1.0


@pytest.mark.parametrize(
    "values",
    (
        (True, 0.5, 0.5, 0.000001, 0.0),
        (2, 0.5, 0.5, 0.000001, 0.0),
        (1, True, 0.5, 0.000001, 0.0),
        (1, 0.5, -0.01, 0.000001, 0.0),
        (1, 0.5, 0.5, 0.0, 0.0),
        (1, 0.5, 0.5, 0.000001, float("nan")),
    ),
)
def test_tau_rejects_invalid_inputs(values: tuple[object, ...]) -> None:
    with pytest.raises((TypeError, ValueError)):
        calculate_tau(*values)


def test_e_update_coefficients_and_vectors_match_the_independent_oracle() -> None:
    oracle = normative_vectors()["e_update"]
    assert pytest.approx(oracle["eta_e"], abs=1e-15) == ETA_E
    assert pytest.approx(oracle["rho_e"], abs=1e-15) == RHO_E
    for vector in oracle["vectors"]:
        assert calculate_e_next(vector["e"], vector["s"], vector["g"]) == pytest.approx(
            vector["expected"],
            abs=1e-15,
        )


@pytest.mark.parametrize(
    "function,values",
    (
        (calculate_e_next, (0.5, 1, 2)),
        (calculate_e_next, (0.5, True, 1)),
        (calculate_e_next, (True, 1, 1)),
        (calculate_q_next, (0.5, 0.5, 2)),
        (calculate_q_next, (True, 0.5, 1)),
        (calculate_q_next, (0.5, float("nan"), 1)),
    ),
)
def test_future_e_and_q_mappings_validate_binary_and_unit_inputs(
    function: Callable[..., float],
    values: tuple[object, ...],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        function(*values)


def test_w_plus_and_w_minus_match_fixed_neutral_band_vectors() -> None:
    for vector in normative_vectors()["w_shape"]:
        assert w_plus(vector["w"]) == pytest.approx(vector["w_plus"], abs=1e-15)
        assert w_minus(vector["w"]) == pytest.approx(vector["w_minus"], abs=1e-15)


@pytest.mark.parametrize("function", (w_plus, w_minus))
@pytest.mark.parametrize("value", (True, -0.01, 1.01, float("nan")))
def test_w_shape_functions_reject_invalid_values(
    function: Callable[[object], float],
    value: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        function(value)


def test_q_update_matches_positive_neutral_negative_g_zero_and_clamp_vectors() -> None:
    for vector in normative_vectors()["q_update"]:
        actual = calculate_q_next(vector["q"], vector["w"], vector["g"])
        assert actual == pytest.approx(vector["expected"], abs=1e-15), vector["name"]


def test_standard_green_boundaries_match_independent_simulation_fixture_vectors() -> None:
    fixture = reference_vectors()["simulation_fixture_vectors"]
    normative = normative_vectors()
    green_p = next(item["expected"] for item in normative["p_intrinsic"] if item["role"] == "green")
    green_birth = next(
        item["expected"] for item in normative["birth_phase"] if item["role"] == "green"
    )
    assert "not v2.0 normative constants" in fixture["fixture_scope"]
    for boundary in fixture["stage5a_green_evaluation_boundaries"]:
        if boundary["revision"] == 1:
            assert boundary["nd"] == 0.5
        else:
            assert calculate_nd(
                boundary["n_current"],
                boundary["n_baseline_session"],
                0.10,
            ) == pytest.approx(boundary["nd"], abs=1e-15)
        assert evaluate_w(boundary["nd"]) == pytest.approx(boundary["w"], abs=1e-15)
        assert calculate_p(boundary["s"], green_p) == pytest.approx(
            boundary["p"],
            abs=1e-15,
        )
        assert calculate_v(boundary["n_current"], 0.5, 0.0) == pytest.approx(
            boundary["v"],
            abs=1e-15,
        )
        actual_tau = calculate_tau(
            boundary["s"],
            boundary["p"],
            boundary["v"],
            0.000001,
            green_birth,
        )
        if boundary["tau"] is None:
            assert actual_tau is None
        else:
            assert actual_tau == pytest.approx(boundary["tau"], abs=1e-15)
