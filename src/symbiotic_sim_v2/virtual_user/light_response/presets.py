"""Named immutable Stage 7 stationary-response presets."""

from __future__ import annotations

from typing import Literal

from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig

ALIGNED_GREEN_CENTER = "aligned_green_center"
OFF_CENTER_GREEN = "off_center_green"
LIGHT_INSENSITIVE_CONTROL = "light_insensitive_control"
DEFAULT_LIGHT_RESPONSE_PRESET = ALIGNED_GREEN_CENTER
LIGHT_RESPONSE_PRESET_NAMES = (
    ALIGNED_GREEN_CENTER,
    OFF_CENTER_GREEN,
    LIGHT_INSENSITIVE_CONTROL,
)
type LightResponsePresetName = Literal[
    "aligned_green_center",
    "off_center_green",
    "light_insensitive_control",
]


def aligned_green_center() -> LightResponseConfig:
    return LightResponseConfig()


def off_center_green() -> LightResponseConfig:
    return LightResponseConfig(
        preferred_hue_degree=129.0,
        preferred_blink_bpm=125.0,
    )


def light_insensitive_control() -> LightResponseConfig:
    return LightResponseConfig(
        maximum_respiratory_amplitude_gain_ms=0.0,
        maximum_mean_rri_increase_ms=0.0,
    )


def light_response_config_for_preset(name: str) -> LightResponseConfig:
    factories = {
        ALIGNED_GREEN_CENTER: aligned_green_center,
        OFF_CENTER_GREEN: off_center_green,
        LIGHT_INSENSITIVE_CONTROL: light_insensitive_control,
    }
    try:
        factory = factories[name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unknown light-response preset: {name!r}") from exc
    return factory()


def light_response_preset_names() -> tuple[str, ...]:
    return LIGHT_RESPONSE_PRESET_NAMES
