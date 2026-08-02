"""Stage 4 Garden input configuration contract tests."""

from __future__ import annotations

import dataclasses
import json

import pytest

from symbiotic_sim_v2.garden.input_layer.config import (
    BASELINE_INVALID_POLICY,
    GARDEN_EVALUATION_SCHEMA_VERSION,
    GARDEN_INPUT_MODEL_VERSION,
    GARDEN_INPUT_SIGNAL_SCHEMA_VERSION,
    GARDEN_MANIFEST_VERSION,
    GARDEN_PHASE_SCHEMA_VERSION,
    RRI_WINDOW_MEMBERSHIP_POLICY,
    GardenInputConfig,
)


def test_standard_config_is_the_exact_fixed_stage4_contract() -> None:
    config = GardenInputConfig()

    assert config.to_dict() == {
        "garden_id": "relax-with-light",
        "garden_manifest_version": GARDEN_MANIFEST_VERSION,
        "model_version": GARDEN_INPUT_MODEL_VERSION,
        "signal_interval_us": 1_000_000,
        "baseline_discard_seconds": 30,
        "baseline_evaluation_seconds": 30,
        "main_session_seconds": 180,
        "bundle_count": 3,
        "bundle_discard_seconds": 30,
        "bundle_evaluation_seconds": 30,
        "rri_min_us": 300_000,
        "rri_max_us": 2_000_000,
        "median_history_min_valid_count": 5,
        "median_history_max_valid_count": 15,
        "median_relative_deviation_limit": 0.20,
        "low_confidence_artifact_rate": 0.05,
        "reject_artifact_rate": 0.10,
        "minimum_valid_rri_count": 5,
        "rmssd_min_ms": 15.0,
        "rmssd_max_ms": 80.0,
        "rri_window_membership_policy": RRI_WINDOW_MEMBERSHIP_POLICY,
        "baseline_invalid_policy": BASELINE_INVALID_POLICY,
        "signal_schema_version": GARDEN_INPUT_SIGNAL_SCHEMA_VERSION,
        "evaluation_schema_version": GARDEN_EVALUATION_SCHEMA_VERSION,
        "phase_schema_version": GARDEN_PHASE_SCHEMA_VERSION,
    }
    assert config.total_duration_seconds == 240
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.bundle_count = 4  # type: ignore[misc]


def test_config_json_round_trip_is_exact_and_canonical() -> None:
    config = GardenInputConfig()
    encoded = config.to_json()

    assert GardenInputConfig.from_json(encoded) == config
    assert json.loads(encoded) == config.to_dict()
    assert encoded == json.dumps(
        config.to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@pytest.mark.parametrize("mutation", ("missing", "unknown"))
def test_config_dictionary_rejects_missing_or_unknown_fields(mutation: str) -> None:
    values = GardenInputConfig().to_dict()
    if mutation == "missing":
        values.pop("garden_id")
    else:
        values["future_stage_field"] = True

    with pytest.raises(ValueError, match=mutation):
        GardenInputConfig.from_dict(values)


@pytest.mark.parametrize(
    "field",
    (
        "garden_manifest_version",
        "model_version",
        "rri_window_membership_policy",
        "baseline_invalid_policy",
        "signal_schema_version",
        "evaluation_schema_version",
        "phase_schema_version",
    ),
)
def test_every_version_or_policy_mismatch_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        GardenInputConfig(**{field: "different-version"})


@pytest.mark.parametrize(
    "field",
    (
        "signal_interval_us",
        "baseline_discard_seconds",
        "bundle_count",
        "rri_min_us",
        "median_history_min_valid_count",
        "minimum_valid_rri_count",
    ),
)
def test_bool_is_not_accepted_as_an_integer_config_value(field: str) -> None:
    with pytest.raises(TypeError, match=field):
        GardenInputConfig(**{field: True})


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("median_relative_deviation_limit", float("nan")),
        ("low_confidence_artifact_rate", float("inf")),
        ("reject_artifact_rate", float("-inf")),
        ("rmssd_min_ms", float("nan")),
        ("rmssd_max_ms", float("inf")),
    ),
)
def test_non_finite_numeric_config_values_are_rejected(field: str, value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        GardenInputConfig(**{field: value})


@pytest.mark.parametrize(
    "overrides",
    (
        {"baseline_discard_seconds": 29},
        {"baseline_evaluation_seconds": 31},
        {"main_session_seconds": 179},
        {"bundle_count": 2},
        {"bundle_discard_seconds": 29},
        {"bundle_evaluation_seconds": 31},
    ),
)
def test_fixed_time_structure_mismatches_are_rejected(overrides: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        GardenInputConfig(**overrides)


@pytest.mark.parametrize(
    "overrides",
    (
        {"rri_min_us": 2_000_000},
        {"rri_min_us": 2_000_001},
        {"rri_max_us": 300_000},
    ),
)
def test_invalid_rri_range_is_rejected(overrides: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="rri_min_us"):
        GardenInputConfig(**overrides)


@pytest.mark.parametrize(
    "overrides",
    (
        {"median_relative_deviation_limit": -0.01},
        {"median_relative_deviation_limit": 1.01},
        {"low_confidence_artifact_rate": -0.01},
        {"low_confidence_artifact_rate": 1.01},
        {"reject_artifact_rate": 0.04},
        {"reject_artifact_rate": 1.01},
        {"rmssd_min_ms": 80.0},
        {"rmssd_min_ms": 81.0},
    ),
)
def test_invalid_threshold_relationships_are_rejected(
    overrides: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        GardenInputConfig(**overrides)
