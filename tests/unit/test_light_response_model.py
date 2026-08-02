"""Pure config, projection, preference, dynamics, and physiology tests."""

from __future__ import annotations

import dataclasses
import math

import pytest

from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.light_mapper.config import (
    COMMAND_HOLD_POLICY_VERSION,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_MAPPING_VERSION,
    PHASE_POLICY_VERSION,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.config import (
    LIGHT_RESPONSE_MODEL_VERSION,
    LightResponseConfig,
)
from symbiotic_sim_v2.virtual_user.light_response.dynamics import (
    first_order_response_at,
    transition_time_constant_seconds,
)
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
    physical_light_stimulus_from_event,
)
from symbiotic_sim_v2.virtual_user.light_response.physiology import (
    calculate_light_responsive_next_rri,
    effective_physiology,
)
from symbiotic_sim_v2.virtual_user.light_response.preference import (
    circular_hue_distance,
    evaluate_light_preference,
    response_target_for,
)
from symbiotic_sim_v2.virtual_user.light_response.presets import (
    LIGHT_RESPONSE_PRESET_NAMES,
    aligned_green_center,
    light_insensitive_control,
    light_response_config_for_preset,
    off_center_green,
)
from symbiotic_sim_v2.virtual_user.physiology import calculate_next_rri


def active_stimulus(hue: float = 125.0, bpm: float = 87.5) -> PhysicalLightStimulus:
    return PhysicalLightStimulus(
        effective_time_us=10,
        active=True,
        render_hue_degree=hue,
        saturation=1.0,
        value_center=0.425,
        value_amplitude=0.075,
        value_min=0.35,
        value_max=0.5,
        blink_bpm=bpm,
        waveform="sine",
        phase_cycles_at_start=0.0,
    )


def state_event(*, active: bool = True) -> SimulationEvent:
    payload = {
        "device_id": "virtual-pc-light-001",
        "source_signal_index": 1,
        "source_signal_time_us": 10,
        "effective_time_us": 10,
        "active": active,
        "qualification_holder_id": "life-green" if active else None,
        "source_b_f": 125 / 360 if active else None,
        "source_b_a": 0.5 if active else None,
        "source_b_t": 0.5 if active else None,
        "source_b_d": 0.5 if active else None,
        "hue_degree": 125.0 if active else None,
        "render_hue_degree": 125.0 if active else None,
        "saturation": 1.0 if active else 0.0,
        "value_center": 0.425 if active else 0.0,
        "value_amplitude": 0.075 if active else 0.0,
        "value_min": 0.35 if active else 0.0,
        "value_max": 0.5 if active else 0.0,
        "blink_bpm": 87.5 if active else None,
        "waveform": "sine" if active else "off",
        "phase_cycles_at_start": 0.0 if active else None,
        "value_at_start": 0.425 if active else 0.0,
        "phase_reset": active,
        "physical_parameters_changed": True,
        "command_equivalent_to_previous": False,
        "mapping_version": LIGHT_MAPPING_VERSION,
        "phase_policy_version": PHASE_POLICY_VERSION,
        "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
        "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
        "schema_version": "light_stimulus_state_event_v1",
    }
    return SimulationEvent(
        event_id="state-1",
        event_type=LIGHT_STIMULUS_STATE_EVENT_TYPE,
        source=LIGHT_STIMULUS_STATE_EVENT_SOURCE,
        scheduled_time_us=10,
        priority=LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
        sequence=0,
        payload=payload,
    )


def test_config_defaults_presets_and_strict_json_round_trip() -> None:
    config = LightResponseConfig()
    assert config.model_version == LIGHT_RESPONSE_MODEL_VERSION
    assert config.preferred_hue_degree == 125.0
    assert config.preferred_blink_bpm == 87.5
    assert config.preference_stationary
    assert LightResponseConfig.from_json(config.to_json()) == config
    assert LIGHT_RESPONSE_PRESET_NAMES == (
        "aligned_green_center",
        "off_center_green",
        "light_insensitive_control",
    )
    assert aligned_green_center() == config
    assert off_center_green().preferred_hue_degree == 129.0
    assert off_center_green().preferred_blink_bpm == 125.0
    assert light_insensitive_control().maximum_respiratory_amplitude_gain_ms == 0.0
    assert light_insensitive_control().maximum_mean_rri_increase_ms == 0.0
    assert light_response_config_for_preset("aligned_green_center") == config
    with pytest.raises(ValueError):
        light_response_config_for_preset("unknown")


def test_config_from_dict_rejects_missing_unknown_and_wrong_version() -> None:
    values = LightResponseConfig().to_dict()
    missing = dict(values)
    missing.pop("enabled")
    with pytest.raises(ValueError, match="missing"):
        LightResponseConfig.from_dict(missing)
    with pytest.raises(ValueError, match="unknown"):
        LightResponseConfig.from_dict({**values, "new_field": 1})
    with pytest.raises(ValueError, match="model_version"):
        LightResponseConfig(model_version="future")


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("enabled", 1),
        ("preference_stationary", False),
        ("preferred_hue_degree", -0.1),
        ("preferred_hue_degree", 360.1),
        ("hue_sigma_degree", 0.0),
        ("hue_sigma_degree", 180.1),
        ("preferred_blink_bpm", 9.9),
        ("preferred_blink_bpm", 165.1),
        ("blink_sigma_bpm", 0.0),
        ("maximum_mean_rri_increase_ms", -0.1),
        ("maximum_respiratory_amplitude_gain_ms", -0.1),
        ("response_onset_time_constant_seconds", 0.0),
        ("response_recovery_time_constant_seconds", -1.0),
        ("response_min", 0.1),
        ("response_max", 0.9),
        ("diagnostic_sample_interval_us", True),
        ("simulation_end_time_us", 239_000_000),
    ),
)
def test_config_rejects_invalid_values_without_clipping(field: str, invalid: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        LightResponseConfig(**{field: invalid})


@pytest.mark.parametrize("invalid", (math.inf, -math.inf, math.nan))
def test_config_rejects_non_finite_numbers(invalid: float) -> None:
    with pytest.raises(ValueError):
        LightResponseConfig(preferred_hue_degree=invalid)


def test_projection_contains_only_physical_fields_and_is_immutable() -> None:
    projected = physical_light_stimulus_from_event(state_event())
    assert projected == active_stimulus()
    forbidden = {"qualification_holder_id", "source_b", "source_signal_index"}
    assert forbidden.isdisjoint(projected.__dataclass_fields__)
    with pytest.raises(dataclasses.FrozenInstanceError):
        projected.active = False  # type: ignore[misc]


def test_projection_rejects_nonformal_source_and_schema() -> None:
    valid = state_event()
    with pytest.raises(ValueError, match="source"):
        physical_light_stimulus_from_event(
            dataclasses.replace(valid, source="not-the-device")
        )
    payload = dict(valid.payload)
    payload["schema_version"] = "future"
    with pytest.raises(ValueError, match="schema_version"):
        physical_light_stimulus_from_event(dataclasses.replace(valid, payload=payload))


def test_circular_gaussian_preference_is_stationary_and_wraps_hue() -> None:
    config = LightResponseConfig()
    assert circular_hue_distance(0.0, 360.0) == 0.0
    assert circular_hue_distance(359.0, 1.0) == 2.0
    aligned = evaluate_light_preference(active_stimulus(), config)
    assert aligned.hue_match == 1.0
    assert aligned.bpm_match == 1.0
    assert aligned.preference_match == 1.0
    off_center = evaluate_light_preference(active_stimulus(130.0, 117.5), config)
    assert off_center.hue_match == pytest.approx(math.exp(-0.5))
    assert off_center.bpm_match == pytest.approx(math.exp(-0.5))
    assert off_center.preference_match == pytest.approx(math.exp(-1.0))
    assert 0.0 <= off_center.preference_match <= 1.0


def test_inactive_and_disabled_targets_are_zero_without_negative_effect() -> None:
    inactive = dataclasses.replace(active_stimulus(), active=False)
    inactive_match = evaluate_light_preference(inactive, LightResponseConfig())
    assert inactive_match.hue_match is None
    assert inactive_match.bpm_match is None
    assert response_target_for(inactive, inactive_match, LightResponseConfig()) == 0.0
    active = active_stimulus()
    match = evaluate_light_preference(active, LightResponseConfig(enabled=False))
    assert response_target_for(active, match, LightResponseConfig(enabled=False)) == 0.0


def test_first_order_onset_recovery_continuity_and_exact_formula() -> None:
    config = LightResponseConfig()
    assert transition_time_constant_seconds(0.0, 1.0, config) == 8.0
    onset = first_order_response_at(
        8_000_000,
        start_time_us=0,
        response_at_start=0.0,
        target=1.0,
        time_constant_seconds=8.0,
    )
    assert onset == pytest.approx(1.0 - math.exp(-1.0))
    assert first_order_response_at(
        8_000_000,
        start_time_us=8_000_000,
        response_at_start=onset,
        target=0.0,
        time_constant_seconds=12.0,
    ) == onset
    recovery = first_order_response_at(
        20_000_000,
        start_time_us=8_000_000,
        response_at_start=onset,
        target=0.0,
        time_constant_seconds=12.0,
    )
    assert recovery == pytest.approx(onset * math.exp(-1.0))
    assert 0.0 <= recovery < onset <= 1.0


def test_response_zero_and_insensitive_control_are_exact_stage2_physiology() -> None:
    virtual_config = VirtualUserConfig()
    response_config = LightResponseConfig()
    stage2 = calculate_next_rri(virtual_config, 12_345_678, 19, -0.25)
    response_zero = calculate_light_responsive_next_rri(
        virtual_config,
        response_config,
        12_345_678,
        19,
        -0.25,
        0.0,
    )
    control = calculate_light_responsive_next_rri(
        virtual_config,
        light_insensitive_control(),
        12_345_678,
        19,
        -0.25,
        1.0,
    )
    assert response_zero.computation == stage2
    assert control.computation == stage2


def test_response_one_changes_only_mean_and_respiratory_amplitude_inputs() -> None:
    values = effective_physiology(VirtualUserConfig(), LightResponseConfig(), 1.0)
    base_mean, effective_mean, mean_gain, base_rsa, effective_rsa, rsa_gain = values
    assert base_mean == pytest.approx(60_000 / 70)
    assert effective_mean == pytest.approx(base_mean + 15.0)
    assert mean_gain == 15.0
    assert base_rsa == 35.0
    assert effective_rsa == 65.0
    assert rsa_gain == 30.0
