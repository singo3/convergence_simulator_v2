"""Stage 6 GUI-independent virtual PC light device."""

from .component import VirtualLightDeviceComponent
from .config import (
    LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION,
    LIGHT_STIMULUS_STATE_SCHEMA_VERSION,
    VIRTUAL_LIGHT_DEVICE_MODEL_VERSION,
    WAVEFORM_SAMPLE_POLICY_VERSION,
    VirtualLightDeviceConfig,
)
from .events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
    LightStimulusStateInput,
    parse_light_stimulus_state_event,
)
from .phase import phase_cycles_at
from .records import (
    LightCommandRecord,
    LightStimulusSegment,
    LightStimulusStateRecord,
    LightWaveformSample,
)
from .state import LightStateSnapshot
from .waveform import sine_value

__all__ = [
    "LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION",
    "LIGHT_STIMULUS_STATE_EVENT_PRIORITY",
    "LIGHT_STIMULUS_STATE_EVENT_SOURCE",
    "LIGHT_STIMULUS_STATE_EVENT_TYPE",
    "LIGHT_STIMULUS_STATE_SCHEMA_VERSION",
    "LightCommandRecord",
    "LightStateSnapshot",
    "LightStimulusSegment",
    "LightStimulusStateInput",
    "LightStimulusStateRecord",
    "LightWaveformSample",
    "VIRTUAL_LIGHT_DEVICE_MODEL_VERSION",
    "VirtualLightDeviceComponent",
    "VirtualLightDeviceConfig",
    "WAVEFORM_SAMPLE_POLICY_VERSION",
    "parse_light_stimulus_state_event",
    "phase_cycles_at",
    "sine_value",
]
