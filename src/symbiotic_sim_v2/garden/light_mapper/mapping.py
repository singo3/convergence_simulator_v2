"""Pure Relax with Light B-to-I mapping functions."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .config import (
    ACTIVE_WAVEFORM,
    HUE_RENDER_PERIOD_DEGREE,
    INACTIVE_WAVEFORM,
    GardenLightMapperConfig,
)

type BVector = tuple[float, float, float, float]


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def validate_b_vector(value: object) -> BVector:
    """Validate and detach one formal four-axis B vector without clipping."""

    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("B must be a four-element sequence")
    if len(value) != 4:
        raise ValueError("B must contain exactly four axes")
    return tuple(_unit(f"B[{index}]", axis) for index, axis in enumerate(value))  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class LightMapping:
    """Mapped logical HSV/sine parameters; never an RGB or calibrated output."""

    active: bool
    source_b: BVector | None
    hue_degree: float | None
    render_hue_degree: float | None
    saturation: float
    value_center: float
    value_amplitude: float
    value_min: float
    value_max: float
    blink_bpm: float | None
    waveform: str


def map_active_b_to_light(
    b: object,
    config: GardenLightMapperConfig,
) -> LightMapping:
    """Map F to formal Hue and T to BPM while retaining but ignoring A/D."""

    if not isinstance(config, GardenLightMapperConfig):
        raise TypeError("config must be a GardenLightMapperConfig")
    source_b = validate_b_vector(b)
    f, _a, t, _d = source_b
    hue_degree = config.hue_scale_degree * f
    blink_bpm = config.blink_bpm_min + (
        config.blink_bpm_max - config.blink_bpm_min
    ) * t
    return LightMapping(
        active=True,
        source_b=source_b,
        hue_degree=hue_degree,
        render_hue_degree=hue_degree % HUE_RENDER_PERIOD_DEGREE,
        saturation=config.saturation,
        value_center=config.value_center,
        value_amplitude=config.value_amplitude,
        value_min=config.value_min,
        value_max=config.value_max,
        blink_bpm=blink_bpm,
        waveform=ACTIVE_WAVEFORM,
    )


def map_inactive_light(config: GardenLightMapperConfig) -> LightMapping:
    """Return the explicit black/off mapping for an inactive qualified output."""

    if not isinstance(config, GardenLightMapperConfig):
        raise TypeError("config must be a GardenLightMapperConfig")
    return LightMapping(
        active=False,
        source_b=None,
        hue_degree=None,
        render_hue_degree=None,
        saturation=0.0,
        value_center=0.0,
        value_amplitude=0.0,
        value_min=0.0,
        value_max=0.0,
        blink_bpm=None,
        waveform=INACTIVE_WAVEFORM,
    )


def map_b_to_i(
    *,
    active: bool,
    b: object | None,
    config: GardenLightMapperConfig,
) -> LightMapping:
    """Map one qualified B envelope to I without consulting hidden life state."""

    if not isinstance(active, bool):
        raise TypeError("active must be boolean")
    if active:
        if b is None:
            raise ValueError("active mapping requires B")
        return map_active_b_to_light(b, config)
    if b is not None:
        raise ValueError("inactive mapping cannot carry B")
    return map_inactive_light(config)


map_active_b_to_i = map_active_b_to_light
