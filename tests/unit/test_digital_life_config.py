"""Exact Stage 5A Digital Life configuration contract tests."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from symbiotic_sim_v2.digital_life.config import (
    DigitalLifeConfig,
    digital_life_config_for_role,
)

EXPECTED_COMMON = {
    "model_version": "single_digital_life_first_round_v0_1",
    "config_schema_version": "digital_life_config_v1",
    "document_version": "v2.0",
    "profile_version": "symbiotic_signal_loop_reference_v1_0",
    "algorithm_version": "adaptive_random_search_confirmed_v1",
    "state_schema_version": "relation_memory_state_v2",
    "delta_n": 0.10,
    "epsilon_tau": 0.000001,
    "initial_e": 0.0,
    "initial_q": 0.5,
    "initial_k_anchor": (0.5, 0.5, 0.5, 0.5),
    "a_fixed": 0.5,
    "t_min": 0.0,
    "t_max": 1.0,
    "d_fixed": 0.5,
}


@pytest.mark.parametrize(
    ("role", "digital_life_id", "f_min", "f_max"),
    (
        ("red", "life-red", 0 / 360, 10 / 360),
        ("green", "life-green", 120 / 360, 130 / 360),
        ("blue", "life-blue", 245 / 360, 255 / 360),
    ),
)
def test_authoritative_role_presets_are_exact_and_immutable(
    role: str,
    digital_life_id: str,
    f_min: float,
    f_max: float,
) -> None:
    config = digital_life_config_for_role(role)

    assert config.to_dict() == {
        "digital_life_id": digital_life_id,
        "role": role,
        **EXPECTED_COMMON,
        "f_min": f_min,
        "f_max": f_max,
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.role = "green"  # type: ignore[misc]


def test_default_config_is_the_standard_green_preset() -> None:
    assert DigitalLifeConfig() == digital_life_config_for_role("green")


@pytest.mark.parametrize("role", ("red", "green", "blue"))
def test_config_json_round_trip_preserves_tuple_and_every_field(role: str) -> None:
    config = digital_life_config_for_role(role)

    restored = DigitalLifeConfig.from_json(config.to_json())

    assert restored == config
    assert isinstance(restored.initial_k_anchor, tuple)
    assert restored.to_json() == config.to_json()


@pytest.mark.parametrize("mutation", ("missing", "unknown"))
def test_config_dictionary_requires_the_exact_schema(mutation: str) -> None:
    values = DigitalLifeConfig().to_dict()
    if mutation == "missing":
        values.pop("digital_life_id")
    else:
        values["future_stage_field"] = True

    with pytest.raises(ValueError, match=mutation):
        DigitalLifeConfig.from_dict(values)


@pytest.mark.parametrize(
    "field",
    (
        "model_version",
        "config_schema_version",
        "document_version",
        "profile_version",
        "algorithm_version",
        "state_schema_version",
    ),
)
def test_every_version_mismatch_is_rejected(field: str) -> None:
    values = DigitalLifeConfig().to_dict()
    values[field] = "different-version"

    with pytest.raises(ValueError, match=field):
        DigitalLifeConfig.from_dict(values)


@pytest.mark.parametrize("role", ("", "RED", "yellow", 1, True))
def test_unknown_or_non_string_role_is_rejected(role: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        digital_life_config_for_role(role)  # type: ignore[arg-type]


def test_role_and_f_range_must_match_the_authoritative_preset() -> None:
    green = DigitalLifeConfig().to_dict()
    green["role"] = "red"

    with pytest.raises(ValueError, match="role and F range"):
        DigitalLifeConfig.from_dict(green)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("delta_n", True),
        ("epsilon_tau", False),
        ("initial_e", True),
        ("initial_q", False),
        ("f_min", True),
        ("a_fixed", False),
        ("t_max", True),
        ("d_fixed", False),
    ),
)
def test_bool_is_not_accepted_as_a_numeric_config_value(field: str, value: bool) -> None:
    values = DigitalLifeConfig().to_dict()
    values[field] = value

    with pytest.raises(TypeError, match=field):
        DigitalLifeConfig.from_dict(values)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("delta_n", float("nan")),
        ("epsilon_tau", float("inf")),
        ("initial_e", float("-inf")),
        ("initial_q", float("nan")),
        ("f_min", float("inf")),
        ("t_max", float("nan")),
    ),
)
def test_non_finite_config_values_are_rejected(field: str, value: float) -> None:
    values = DigitalLifeConfig().to_dict()
    values[field] = value

    with pytest.raises(ValueError, match="finite"):
        DigitalLifeConfig.from_dict(values)


@pytest.mark.parametrize(
    "initial_k_anchor",
    (
        (),
        (0.5, 0.5, 0.5),
        (0.5, 0.5, 0.5, 0.5, 0.5),
        "0.5,0.5,0.5,0.5",
    ),
)
def test_initial_k_anchor_requires_exactly_four_numeric_values(
    initial_k_anchor: object,
) -> None:
    values = DigitalLifeConfig().to_dict()
    values["initial_k_anchor"] = initial_k_anchor

    with pytest.raises((TypeError, ValueError)):
        DigitalLifeConfig.from_dict(values)


@pytest.mark.parametrize(
    "initial_k_anchor",
    (
        (-0.01, 0.5, 0.5, 0.5),
        (0.5, 1.01, 0.5, 0.5),
        (0.5, 0.5, True, 0.5),
        (0.5, 0.5, float("nan"), 0.5),
    ),
)
def test_initial_k_anchor_values_must_be_finite_unit_values(
    initial_k_anchor: tuple[object, ...],
) -> None:
    values = DigitalLifeConfig().to_dict()
    values["initial_k_anchor"] = initial_k_anchor

    with pytest.raises((TypeError, ValueError)):
        DigitalLifeConfig.from_dict(values)


@pytest.mark.parametrize(
    ("field", "value"),
    (("delta_n", 0.0), ("delta_n", -0.01), ("epsilon_tau", 0.0), ("epsilon_tau", -1.0)),
)
def test_delta_n_and_epsilon_tau_must_be_positive(field: str, value: float) -> None:
    values = DigitalLifeConfig().to_dict()
    values[field] = value

    with pytest.raises(ValueError, match="positive"):
        DigitalLifeConfig.from_dict(values)


@pytest.mark.parametrize(
    "updates",
    (
        {"initial_e": -0.01},
        {"initial_q": 1.01},
        {"a_fixed": -0.01},
        {"d_fixed": 1.01},
        {"t_min": 1.0},
        {"t_max": 0.0},
        {"f_min": 0.5, "f_max": 0.4},
    ),
)
def test_invalid_ranges_are_rejected_without_silent_clipping(
    updates: dict[str, Any],
) -> None:
    values = DigitalLifeConfig().to_dict()
    values.update(updates)

    with pytest.raises(ValueError):
        DigitalLifeConfig.from_dict(values)


@pytest.mark.parametrize("digital_life_id", ("", "   ", 1, True))
def test_digital_life_id_must_be_a_nonempty_string(digital_life_id: object) -> None:
    values = DigitalLifeConfig().to_dict()
    values["digital_life_id"] = digital_life_id

    with pytest.raises(ValueError, match="digital_life_id"):
        DigitalLifeConfig.from_dict(values)
