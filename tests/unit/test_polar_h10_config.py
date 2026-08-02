"""Validation and serialization tests for the fixed ideal-H10 contract."""

from __future__ import annotations

import dataclasses
import json

import pytest

from symbiotic_sim_v2.devices.polar_h10.config import (
    POLAR_H10_MODEL_VERSION,
    RRI_EVENT_SCHEMA_VERSION,
    PolarH10Config,
)

EXPECTED_CONFIG = {
    "device_id": "polar-h10-sim-001",
    "expected_user_id": "virtual-user-001",
    "model_version": "ideal_polar_h10_rri_device_v0_1",
    "event_schema_version": "rri_measurement_event_v1",
}


def test_standard_config_is_exact_fixed_and_immutable() -> None:
    config = PolarH10Config()
    assert config.to_dict() == EXPECTED_CONFIG
    assert config.model_version == POLAR_H10_MODEL_VERSION
    assert config.event_schema_version == RRI_EVENT_SCHEMA_VERSION
    assert set(config.to_dict()) == {
        "device_id",
        "expected_user_id",
        "model_version",
        "event_schema_version",
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.device_id = "replacement"  # type: ignore[misc]


def test_config_json_and_dictionary_round_trips_are_exact() -> None:
    config = PolarH10Config(device_id="h10-development-fixture")
    encoded = config.to_json()
    assert json.loads(encoded) == config.to_dict()
    assert PolarH10Config.from_json(encoded) == config
    assert PolarH10Config.from_dict(config.to_dict()) == config


@pytest.mark.parametrize("missing_field", tuple(EXPECTED_CONFIG))
def test_from_dict_rejects_each_missing_field(missing_field: str) -> None:
    values = dict(EXPECTED_CONFIG)
    values.pop(missing_field)
    with pytest.raises(ValueError, match="missing config fields"):
        PolarH10Config.from_dict(values)


@pytest.mark.parametrize(
    "unknown_field",
    ("root_seed", "noise", "latency", "packet_loss", "min_rri_ms", "rmssd"),
)
def test_from_dict_rejects_unknown_or_future_stage_fields(unknown_field: str) -> None:
    values = {**EXPECTED_CONFIG, unknown_field: 0}
    with pytest.raises(ValueError, match="unknown config fields"):
        PolarH10Config.from_dict(values)


@pytest.mark.parametrize("field", ("device_id", "expected_user_id"))
@pytest.mark.parametrize("value", ("", "   ", None, False, 17))
def test_identifiers_reject_empty_values_and_implicit_conversion(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValueError, match=field):
        PolarH10Config(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("model_version", "future_h10_model"),
        ("model_version", True),
        ("event_schema_version", "rri_measurement_event_v2"),
        ("event_schema_version", None),
    ),
)
def test_contract_versions_cannot_be_substituted(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        PolarH10Config(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("value", (None, [], "not-an-object", 3))
def test_from_dict_rejects_non_mapping_input(value: object) -> None:
    with pytest.raises(TypeError, match="dictionary"):
        PolarH10Config.from_dict(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("encoded", ("[]", '"string"', "null", "1"))
def test_from_json_rejects_non_object_documents(encoded: str) -> None:
    with pytest.raises(ValueError, match="object"):
        PolarH10Config.from_json(encoded)
