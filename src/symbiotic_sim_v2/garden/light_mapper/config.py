"""Immutable configuration for the Stage 6 Garden B-to-I mapper."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any

GARDEN_LIGHT_MAPPER_MODEL_VERSION = "relax_with_light_b_to_i_mapper_v0_1"
B_TO_I_MAPPING_VERSION = "relax_with_light_pc_hsv_sine_mapping_v0_1"
LIGHT_MAPPING_VERSION = B_TO_I_MAPPING_VERSION
GARDEN_QUALIFIED_B_INPUT_SCHEMA_VERSION = "garden_qualified_b_event_v2"
LIGHT_COMMAND_SCHEMA_VERSION = "light_command_event_v1"
CONTINUOUS_PHASE_POLICY_VERSION = "continuous_phase_integrator_v0_1"
PHASE_POLICY_VERSION = CONTINUOUS_PHASE_POLICY_VERSION
COMMAND_HOLD_POLICY_VERSION = "hold_until_next_command_v0_1"
INACTIVE_OUTPUT_POLICY_VERSION = "light_off_black_v0_1"

DEFAULT_HUE_SCALE_DEGREE = 360.0
HUE_RENDER_PERIOD_DEGREE = 360.0
DEFAULT_BLINK_BPM_MIN = 10.0
DEFAULT_BLINK_BPM_MAX = 165.0
DEFAULT_SATURATION = 1.0
DEFAULT_VALUE_CENTER = 0.425
DEFAULT_VALUE_AMPLITUDE = 0.075
DEFAULT_VALUE_MIN = 0.35
DEFAULT_VALUE_MAX = 0.50
ACTIVE_WAVEFORM = "sine"
INACTIVE_WAVEFORM = "off"


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


@dataclass(frozen=True, slots=True)
class GardenLightMapperConfig:
    """Exact, JSON-round-trippable Stage 6 Garden Light Mapper contract."""

    garden_id: str = "relax-with-light"
    model_version: str = GARDEN_LIGHT_MAPPER_MODEL_VERSION
    mapping_version: str = B_TO_I_MAPPING_VERSION
    input_schema_version: str = GARDEN_QUALIFIED_B_INPUT_SCHEMA_VERSION
    output_schema_version: str = LIGHT_COMMAND_SCHEMA_VERSION
    hue_scale_degree: float = DEFAULT_HUE_SCALE_DEGREE
    blink_bpm_min: float = DEFAULT_BLINK_BPM_MIN
    blink_bpm_max: float = DEFAULT_BLINK_BPM_MAX
    saturation: float = DEFAULT_SATURATION
    value_center: float = DEFAULT_VALUE_CENTER
    value_amplitude: float = DEFAULT_VALUE_AMPLITUDE
    value_min: float = DEFAULT_VALUE_MIN
    value_max: float = DEFAULT_VALUE_MAX
    waveform: str = ACTIVE_WAVEFORM
    use_f_axis: bool = True
    use_a_axis: bool = False
    use_t_axis: bool = True
    use_d_axis: bool = False
    phase_policy_version: str = CONTINUOUS_PHASE_POLICY_VERSION
    command_hold_policy_version: str = COMMAND_HOLD_POLICY_VERSION
    inactive_output_policy_version: str = INACTIVE_OUTPUT_POLICY_VERSION

    def __post_init__(self) -> None:
        _required_string("garden_id", self.garden_id)
        exact = {
            "model_version": GARDEN_LIGHT_MAPPER_MODEL_VERSION,
            "mapping_version": B_TO_I_MAPPING_VERSION,
            "input_schema_version": GARDEN_QUALIFIED_B_INPUT_SCHEMA_VERSION,
            "output_schema_version": LIGHT_COMMAND_SCHEMA_VERSION,
            "waveform": ACTIVE_WAVEFORM,
            "phase_policy_version": CONTINUOUS_PHASE_POLICY_VERSION,
            "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
            "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
        }
        for name, expected in exact.items():
            if getattr(self, name) != expected:
                raise ValueError(f"{name} must be {expected}")

        expected_axis_usage = {
            "use_f_axis": True,
            "use_a_axis": False,
            "use_t_axis": True,
            "use_d_axis": False,
        }
        for name, expected in expected_axis_usage.items():
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be boolean")
            if value is not expected:
                raise ValueError(f"{name} must be {expected}")

        numeric_names = (
            "hue_scale_degree",
            "blink_bpm_min",
            "blink_bpm_max",
            "saturation",
            "value_center",
            "value_amplitude",
            "value_min",
            "value_max",
        )
        values = {
            name: _finite_number(name, getattr(self, name)) for name in numeric_names
        }
        if values["hue_scale_degree"] <= 0.0:
            raise ValueError("hue_scale_degree must be positive")
        if values["blink_bpm_min"] <= 0.0:
            raise ValueError("blink_bpm_min must be positive")
        if values["blink_bpm_max"] <= values["blink_bpm_min"]:
            raise ValueError("blink_bpm_max must exceed blink_bpm_min")
        for name in ("saturation", "value_center", "value_min", "value_max"):
            if not 0.0 <= values[name] <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if values["value_amplitude"] < 0.0:
            raise ValueError("value_amplitude must be non-negative")
        if not math.isclose(
            values["value_center"] - values["value_amplitude"],
            values["value_min"],
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("value_center - value_amplitude must equal value_min")
        if not math.isclose(
            values["value_center"] + values["value_amplitude"],
            values["value_max"],
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("value_center + value_amplitude must equal value_max")
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> GardenLightMapperConfig:
        if not isinstance(values, dict):
            raise TypeError("config values must be a dictionary")
        expected = set(cls.__dataclass_fields__)
        actual = set(values)
        if missing := expected - actual:
            raise ValueError(f"missing config fields: {', '.join(sorted(missing))}")
        if unknown := actual - expected:
            raise ValueError(f"unknown config fields: {', '.join(sorted(unknown))}")
        return cls(**values)

    @classmethod
    def from_json(cls, encoded: str) -> GardenLightMapperConfig:
        if not isinstance(encoded, str):
            raise TypeError("encoded config must be a string")
        values = json.loads(encoded)
        if not isinstance(values, dict):
            raise ValueError("config JSON must contain an object")
        return cls.from_dict(values)
