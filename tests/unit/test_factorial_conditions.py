"""Stage 8A.3.1 strict A/B/C/D condition and plan contracts."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from symbiotic_sim_v2.digital_life.math import ETA_E, RHO_E
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    CONDITION_IDS,
    EFFECTIVE_SELECTED_SESSION_FATIGUE_TARGET,
    FULL_RECOVERY_SIGMA100_CONDITION,
    GRADUAL_REFERENCE_ONLY,
    PROVISIONAL_CONDITION,
    UNSELECTED_FULL_RECOVERY,
    V2_RECOVERY_SIGMA050_CONDITION,
    V2_REFERENCE_CONDITION,
    FactorialValidationCondition,
    factorial_condition,
    factorial_conditions,
    validate_factorial_matrix,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.config import (
    FactorialValidationConfig,
    factorial_plan_projection,
)


@pytest.mark.parametrize(
    ("condition_id", "recovery", "sigma"),
    (
        (V2_REFERENCE_CONDITION, GRADUAL_REFERENCE_ONLY, 1.0),
        (V2_RECOVERY_SIGMA050_CONDITION, GRADUAL_REFERENCE_ONLY, 0.5),
        (FULL_RECOVERY_SIGMA100_CONDITION, UNSELECTED_FULL_RECOVERY, 1.0),
        (PROVISIONAL_CONDITION, UNSELECTED_FULL_RECOVERY, 0.5),
    ),
)
def test_fixed_condition_matrix(condition_id: str, recovery: str, sigma: float) -> None:
    condition = factorial_condition(condition_id)
    assert condition.session_end_recovery_policy == recovery
    assert condition.sigma_multiplier == sigma
    assert condition.formal_spec_adoption is False


def test_condition_ids_are_unique_and_ordered_a_b_c_d() -> None:
    values = factorial_conditions()
    assert tuple(item.condition_id for item in values) == CONDITION_IDS
    assert len(set(CONDITION_IDS)) == 4


@pytest.mark.parametrize(
    "field",
    ("eta_selected", "rho", "effective_selected_session_fatigue_target"),
)
def test_all_conditions_share_reference_fatigue_coefficients(field: str) -> None:
    values = {getattr(item, field) for item in factorial_conditions()}
    assert len(values) == 1
    assert values == {
        {
            "eta_selected": ETA_E,
            "rho": RHO_E,
            "effective_selected_session_fatigue_target": (
                EFFECTIVE_SELECTED_SESSION_FATIGUE_TARGET
            ),
        }[field]
    }


@pytest.mark.parametrize("condition_id", CONDITION_IDS)
def test_condition_json_round_trip(condition_id: str) -> None:
    value = factorial_condition(condition_id)
    assert FactorialValidationCondition.from_json(value.to_json()) == value


@pytest.mark.parametrize("mutation", ("unknown", "missing", "duplicate"))
def test_condition_json_rejects_field_shape_mutation(mutation: str) -> None:
    condition = factorial_condition(V2_REFERENCE_CONDITION)
    payload = condition.to_dict()
    if mutation == "unknown":
        payload["unknown"] = 1
        encoded = json.dumps(payload)
    elif mutation == "missing":
        payload.pop("rho")
        encoded = json.dumps(payload)
    else:
        encoded = condition.to_json()[:-1] + ',"rho":0.1}'
    with pytest.raises(ValueError):
        FactorialValidationCondition.from_json(encoded)


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("eta_selected", True),
        ("eta_selected", float("nan")),
        ("rho", False),
        ("rho", float("inf")),
        ("sigma_multiplier", True),
        ("sigma_multiplier", 0.75),
        ("effective_selected_session_fatigue_target", False),
        ("effective_selected_session_fatigue_target", 0.1500000001),
    ),
)
def test_condition_rejects_bool_nonfinite_and_silent_clip(
    field: str,
    invalid: object,
) -> None:
    condition = factorial_condition(V2_REFERENCE_CONDITION)
    with pytest.raises((TypeError, ValueError)):
        replace(condition, **{field: invalid})


def test_factorial_matrix_rejects_duplicate_condition() -> None:
    values = list(factorial_conditions())
    values[-1] = values[0]
    with pytest.raises(ValueError, match="A/B/C/D"):
        validate_factorial_matrix(values)


@pytest.mark.parametrize(
    ("preset", "autonomous", "random", "logical", "actual"),
    (
        ("smoke", 96, 24, 192, 120),
        ("standard", 8_640, 2_160, 17_280, 10_800),
        ("robust", 43_200, 10_800, 86_400, 54_000),
    ),
)
def test_plan_counts_separate_actual_and_logical(
    preset: str,
    autonomous: int,
    random: int,
    logical: int,
    actual: int,
) -> None:
    plan = factorial_plan_projection(
        FactorialValidationConfig.create(validation_preset=preset)
    )
    assert plan["autonomous_sessions"] == autonomous
    assert plan["shared_random_sessions"] == random
    assert plan["logical_comparison_sessions"] == logical
    assert plan["actual_simulation_sessions"] == actual
    assert plan["simulation_jobs_executed"] == 0


def test_config_round_trip_and_budget_rejection() -> None:
    config = FactorialValidationConfig.create(validation_preset="smoke")
    assert FactorialValidationConfig.from_dict(config.to_dict()) == config
    with pytest.raises(ValueError, match="not clipped"):
        replace(config, maximum_actual_session_runs=119)
