"""Narrow projection of the formal Stage 6 light state into physical stimulus."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.devices.virtual_light.events import (
    LightStimulusStateInput,
    parse_light_stimulus_state_event,
)
from symbiotic_sim_v2.domain.events import SimulationEvent


@dataclass(frozen=True, slots=True)
class PhysicalLightStimulus:
    """Only physical stimulus values; deliberately excludes all provenance."""

    effective_time_us: int
    active: bool
    render_hue_degree: float | None
    saturation: float
    value_center: float
    value_amplitude: float
    value_min: float
    value_max: float
    blink_bpm: float | None
    waveform: str
    phase_cycles_at_start: float | None


type PhysicalLightParameterSignature = tuple[
    bool,
    float | None,
    float,
    float,
    float,
    float,
    float,
    float | None,
    str,
]


def physical_light_parameter_signature(
    stimulus: PhysicalLightStimulus,
) -> PhysicalLightParameterSignature:
    """Return only exact, continuous-light physical parameters.

    Effective time, phase-at-command-start, and every provenance value are
    deliberately absent.  Tuple equality is the versioned deterministic
    comparison; this helper applies no tolerance or normalization.
    """

    if not isinstance(stimulus, PhysicalLightStimulus):
        raise TypeError("stimulus must be a PhysicalLightStimulus")
    return (
        stimulus.active,
        stimulus.render_hue_degree,
        stimulus.saturation,
        stimulus.value_center,
        stimulus.value_amplitude,
        stimulus.value_min,
        stimulus.value_max,
        stimulus.blink_bpm,
        stimulus.waveform,
    )


def project_physical_light_stimulus(
    state: LightStimulusStateInput,
) -> PhysicalLightStimulus:
    if not isinstance(state, LightStimulusStateInput):
        raise TypeError("state must be a LightStimulusStateInput")
    return PhysicalLightStimulus(
        effective_time_us=state.effective_time_us,
        active=state.active,
        render_hue_degree=state.render_hue_degree,
        saturation=state.saturation,
        value_center=state.value_center,
        value_amplitude=state.value_amplitude,
        value_min=state.value_min,
        value_max=state.value_max,
        blink_bpm=state.blink_bpm,
        waveform=state.waveform,
        phase_cycles_at_start=state.phase_cycles_at_start,
    )


def physical_light_stimulus_from_event(event: SimulationEvent) -> PhysicalLightStimulus:
    return project_physical_light_stimulus(parse_light_stimulus_state_event(event))


def inactive_physical_light_stimulus(time_us: int = 0) -> PhysicalLightStimulus:
    if isinstance(time_us, bool) or not isinstance(time_us, int) or time_us < 0:
        raise ValueError("time_us must be a non-negative integer")
    return PhysicalLightStimulus(
        effective_time_us=time_us,
        active=False,
        render_hue_degree=None,
        saturation=0.0,
        value_center=0.0,
        value_amplitude=0.0,
        value_min=0.0,
        value_max=0.0,
        blink_bpm=None,
        waveform="off",
        phase_cycles_at_start=None,
    )
