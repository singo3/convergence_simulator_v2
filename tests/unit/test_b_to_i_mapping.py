"""Pure B-to-I mapping tests for the Relax with Light Stage 6 profile."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.mapping import (
    map_active_b_to_light,
    map_b_to_i,
)


@pytest.mark.parametrize(
    ("f", "expected_hue", "expected_render_hue"),
    (
        (0.0, 0.0, 0.0),
        (0.5, 180.0, 180.0),
        (1.0, 360.0, 0.0),
    ),
)
def test_f_maps_to_formal_and_render_hue(
    f: float,
    expected_hue: float,
    expected_render_hue: float,
) -> None:
    result = map_active_b_to_light(
        (f, 0.5, 0.5, 0.5),
        GardenLightMapperConfig(),
    )
    assert result.hue_degree == expected_hue
    assert result.render_hue_degree == expected_render_hue


def test_render_hue_always_uses_degree_modulo_without_rewriting_formal_hue() -> None:
    config = replace(GardenLightMapperConfig(), hue_scale_degree=720.0)
    result = map_active_b_to_light((0.5, 0.5, 0.5, 0.5), config)
    assert result.hue_degree == 360.0
    assert result.render_hue_degree == 0.0


@pytest.mark.parametrize(
    ("t", "expected_bpm"),
    ((0.0, 10.0), (0.5, 87.5), (1.0, 165.0)),
)
def test_t_maps_to_blink_bpm(t: float, expected_bpm: float) -> None:
    result = map_active_b_to_light(
        (125 / 360, 0.5, t, 0.5),
        GardenLightMapperConfig(),
    )
    assert result.blink_bpm == expected_bpm


def test_a_and_d_are_retained_but_do_not_change_physical_output() -> None:
    config = GardenLightMapperConfig()
    low = map_active_b_to_light((0.25, 0.0, 0.75, 0.0), config)
    high = map_active_b_to_light((0.25, 1.0, 0.75, 1.0), config)
    assert low.source_b != high.source_b
    assert replace(low, source_b=high.source_b) == high


def test_active_mapping_has_reference_hsv_and_sine_parameters() -> None:
    result = map_b_to_i(
        active=True,
        b=(125 / 360, 0.5, 0.5, 0.5),
        config=GardenLightMapperConfig(),
    )
    assert result.active
    assert result.hue_degree == pytest.approx(125.0)
    assert result.blink_bpm == 87.5
    assert result.saturation == 1.0
    assert (result.value_min, result.value_center, result.value_max) == (
        0.35,
        0.425,
        0.50,
    )
    assert result.value_amplitude == 0.075
    assert result.waveform == "sine"


def test_inactive_mapping_is_explicit_black_off() -> None:
    result = map_b_to_i(
        active=False,
        b=None,
        config=GardenLightMapperConfig(),
    )
    assert not result.active
    assert result.source_b is None
    assert result.hue_degree is result.render_hue_degree is result.blink_bpm is None
    assert result.saturation == result.value_center == result.value_amplitude == 0.0
    assert result.value_min == result.value_max == 0.0
    assert result.waveform == "off"


@pytest.mark.parametrize(
    "b",
    (
        (-0.1, 0.5, 0.5, 0.5),
        (1.1, 0.5, 0.5, 0.5),
        (0.5, True, 0.5, 0.5),
        (0.5, 0.5, float("nan"), 0.5),
        (0.5, 0.5, 0.5),
    ),
)
def test_b_mapping_rejects_invalid_values_without_clipping(b: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        map_active_b_to_light(b, GardenLightMapperConfig())


def test_active_and_inactive_envelopes_reject_inconsistent_b_presence() -> None:
    config = GardenLightMapperConfig()
    with pytest.raises(ValueError, match="requires B"):
        map_b_to_i(active=True, b=None, config=config)
    with pytest.raises(ValueError, match="cannot carry B"):
        map_b_to_i(active=False, b=(0.5, 0.5, 0.5, 0.5), config=config)
