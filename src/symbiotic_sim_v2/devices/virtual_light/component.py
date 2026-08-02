"""GUI-independent virtual PC light driven only by formal light commands."""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right

from symbiotic_sim_v2.devices.virtual_light.config import VirtualLightDeviceConfig
from symbiotic_sim_v2.devices.virtual_light.events import (
    LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
    LIGHT_STIMULUS_STATE_EVENT_SOURCE,
    LIGHT_STIMULUS_STATE_EVENT_TYPE,
    light_stimulus_state_payload,
)
from symbiotic_sim_v2.devices.virtual_light.phase import phase_cycles_at
from symbiotic_sim_v2.devices.virtual_light.records import (
    LightCommandRecord,
    LightStimulusSegment,
    LightStimulusStateRecord,
    LightWaveformSample,
)
from symbiotic_sim_v2.devices.virtual_light.state import LightStateSnapshot
from symbiotic_sim_v2.devices.virtual_light.waveform import sine_value
from symbiotic_sim_v2.domain.event_priorities import SIMULATION_COMPLETE_EVENT_PRIORITY
from symbiotic_sim_v2.domain.event_types import SIMULATION_COMPLETE_EVENT_TYPE
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.light_mapper.events import (
    LightCommandInput,
    parse_light_command_event,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine


class VirtualLightDeviceComponent:
    """Hold I commands and evaluate logical HSV stimulus from virtual time."""

    def __init__(self, config: VirtualLightDeviceConfig) -> None:
        if not isinstance(config, VirtualLightDeviceConfig):
            raise TypeError("config must be a VirtualLightDeviceConfig")
        self.config = config
        self.reset()

    def reset(self) -> None:
        """Clear every command, state event, segment, and lifecycle counter."""

        self._command_records: list[LightCommandRecord] = []
        self._state_records: list[LightStimulusStateRecord] = []
        self._segments: list[LightStimulusSegment] = []
        self._command_times_us: list[int] = []
        self._latest_observed_time_us = 0
        self._completed = False

    def handle_light_command(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Apply one command, close the prior segment, and emit one p67 state."""

        if self._completed:
            raise RuntimeError("completed light device cannot accept commands")
        command = parse_light_command_event(event)
        self._validate_next_command(command)
        previous_command = self._command_records[-1] if self._command_records else None
        previous_state = self._state_records[-1] if self._state_records else None
        equivalent = (
            previous_command is not None
            and self._physical_key(previous_command)
            == self._physical_key_for_input(command)
        )
        physical_changed = previous_command is None or not equivalent

        if command.active:
            if previous_command is not None and previous_command.active:
                assert previous_state is not None
                assert previous_state.phase_cycles_at_start is not None
                assert previous_command.blink_bpm is not None
                phase_at_start = phase_cycles_at(
                    command.command_effective_time_us,
                    start_time_us=previous_command.effective_time_us,
                    phase_cycles_at_start=previous_state.phase_cycles_at_start,
                    blink_bpm=previous_command.blink_bpm,
                )
                phase_reset = False
            else:
                phase_at_start = 0.0
                phase_reset = True
            value_at_start = sine_value(
                phase_at_start,
                value_center=command.value_center,
                value_amplitude=command.value_amplitude,
            )
        else:
            phase_at_start = None
            value_at_start = 0.0
            phase_reset = False

        command_record = self._command_record(command)
        state_record = LightStimulusStateRecord(
            state_index=len(self._state_records),
            device_id=self.config.device_id,
            source_signal_index=command.source_signal_index,
            source_signal_time_us=command.source_signal_time_us,
            effective_time_us=command.command_effective_time_us,
            active=command.active,
            qualification_holder_id=command.qualification_holder_id,
            source_b=command.source_b,
            hue_degree=command.hue_degree,
            render_hue_degree=command.render_hue_degree,
            saturation=command.saturation,
            value_center=command.value_center,
            value_amplitude=command.value_amplitude,
            value_min=command.value_min,
            value_max=command.value_max,
            blink_bpm=command.blink_bpm,
            waveform=command.waveform,
            phase_cycles_at_start=phase_at_start,
            value_at_start=value_at_start,
            phase_reset=phase_reset,
            physical_parameters_changed=physical_changed,
            command_equivalent_to_previous=equivalent,
            mapping_version=command.mapping_version,
            phase_policy_version=command.phase_policy_version,
            command_hold_policy_version=command.command_hold_policy_version,
            inactive_output_policy_version=command.inactive_output_policy_version,
            schema_version=self.config.output_schema_version,
        )
        pending_segment = (
            None
            if previous_command is None
            else self._segment_for(
                previous_command,
                previous_state,
                end_time_us=command.command_effective_time_us,
            )
        )
        engine.schedule_at(
            command.command_effective_time_us,
            LIGHT_STIMULUS_STATE_EVENT_TYPE,
            source=LIGHT_STIMULUS_STATE_EVENT_SOURCE,
            priority=LIGHT_STIMULUS_STATE_EVENT_PRIORITY,
            payload=light_stimulus_state_payload(state_record),
        )
        if pending_segment is not None:
            self._segments.append(pending_segment)
        self._command_records.append(command_record)
        self._state_records.append(state_record)
        self._command_times_us.append(command.command_effective_time_us)
        self._latest_observed_time_us = command.command_effective_time_us

    def handle_simulation_complete(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Close the final positive-duration segment at the configured end."""

        if event.event_type != SIMULATION_COMPLETE_EVENT_TYPE:
            raise ValueError("completion handler received the wrong event type")
        if event.priority != SIMULATION_COMPLETE_EVENT_PRIORITY:
            raise ValueError("completion priority does not match the stable boundary")
        if event.scheduled_time_us != self.config.simulation_end_time_us:
            raise ValueError("completion time does not match simulation_end_time_us")
        if self._completed:
            raise RuntimeError("light device is already completed")
        if self._command_records:
            current = self._command_records[-1]
            state = self._state_records[-1]
            if current.effective_time_us < event.scheduled_time_us:
                self._segments.append(
                    self._segment_for(
                        current,
                        state,
                        end_time_us=event.scheduled_time_us,
                    )
                )
            elif current.effective_time_us > event.scheduled_time_us:
                raise RuntimeError("current light command starts after simulation end")
        self._validate_segment_history()
        self._latest_observed_time_us = event.scheduled_time_us
        self._completed = True

    def state_at(self, time_us: int) -> LightStateSnapshot:
        """Return deterministic physical state at any retained virtual timestamp."""

        if isinstance(time_us, bool) or not isinstance(time_us, int):
            raise TypeError("time_us must be an integer")
        if not 0 <= time_us <= self.config.simulation_end_time_us:
            raise ValueError("time_us must be within the configured simulation interval")
        prefix_count = bisect_right(self._command_times_us, time_us)
        command = (
            None if prefix_count == 0 else self._command_records[prefix_count - 1]
        )
        state = None if prefix_count == 0 else self._state_records[prefix_count - 1]
        if command is None:
            active = False
            holder = None
            source_signal_index = None
            effective_time_us = None
            command_age_us = None
            source_b = None
            hue = None
            render_hue = None
            saturation = 0.0
            bpm = None
            waveform = "off"
            phase = None
            value = 0.0
        else:
            active = command.active
            holder = command.qualification_holder_id
            source_signal_index = command.source_signal_index
            effective_time_us = command.effective_time_us
            command_age_us = time_us - command.effective_time_us
            source_b = command.source_b
            hue = command.hue_degree
            render_hue = command.render_hue_degree
            saturation = command.saturation
            bpm = command.blink_bpm
            waveform = command.waveform
            if active:
                assert state is not None
                assert state.phase_cycles_at_start is not None
                assert bpm is not None
                phase = phase_cycles_at(
                    time_us,
                    start_time_us=command.effective_time_us,
                    phase_cycles_at_start=state.phase_cycles_at_start,
                    blink_bpm=bpm,
                )
                value = sine_value(
                    phase,
                    value_center=command.value_center,
                    value_amplitude=command.value_amplitude,
                )
            else:
                phase = None
                value = 0.0

        states = self._state_records[:prefix_count]
        return LightStateSnapshot(
            device_id=self.config.device_id,
            model_version=self.config.model_version,
            current_time_us=time_us,
            active=active,
            current_holder_id=holder,
            source_signal_index=source_signal_index,
            command_effective_time_us=effective_time_us,
            command_age_us=command_age_us,
            source_b=source_b,
            hue_degree=hue,
            render_hue_degree=render_hue,
            saturation=saturation,
            blink_bpm=bpm,
            waveform=waveform,
            phase_cycles=phase,
            current_value=value,
            command_count=prefix_count,
            state_event_count=prefix_count,
            closed_segment_count=sum(
                segment.end_time_us <= time_us for segment in self._segments
            ),
            active_command_count=sum(record.active for record in states),
            inactive_command_count=sum(not record.active for record in states),
            phase_reset_count=sum(record.phase_reset for record in states),
            phase_continuation_count=sum(
                record.active and not record.phase_reset and index > 0
                and states[index - 1].active
                for index, record in enumerate(states)
            ),
            physical_parameter_change_count=sum(
                record.physical_parameters_changed for record in states
            ),
            equivalent_command_count=sum(
                record.command_equivalent_to_previous for record in states
            ),
            completed=self._completed and time_us == self.config.simulation_end_time_us,
        )

    def snapshot(self, time_us: int | None = None) -> LightStateSnapshot:
        """Return the latest immutable state, or an explicitly requested state."""

        query_time_us = self._latest_observed_time_us if time_us is None else time_us
        return self.state_at(query_time_us)

    def command_records(self) -> tuple[LightCommandRecord, ...]:
        return tuple(self._command_records)

    def stimulus_state_records(self) -> tuple[LightStimulusStateRecord, ...]:
        return tuple(self._state_records)

    def stimulus_segments(self) -> tuple[LightStimulusSegment, ...]:
        return tuple(self._segments)

    def waveform_samples(self) -> tuple[LightWaveformSample, ...]:
        """Derive the fixed 20 ms grid after completion without scheduling events."""

        if not self._completed:
            raise RuntimeError("waveform samples require a completed simulation")
        interval_us = self.config.diagnostic_sample_interval_us
        return tuple(
            self._sample_at(sample_index, sample_index * interval_us)
            for sample_index in range(
                self.config.simulation_end_time_us // interval_us + 1
            )
        )

    def command_digest(self) -> str:
        records = [
            {
                "effective_time_us": record.effective_time_us,
                "source_signal_index": record.source_signal_index,
                "source_signal_time_us": record.source_signal_time_us,
                "source_effective_time_us": record.source_effective_time_us,
                "active": record.active,
                "holder": record.qualification_holder_id,
                "source_b": record.source_b,
                "hue_degree": record.hue_degree,
                "render_hue_degree": record.render_hue_degree,
                "blink_bpm": record.blink_bpm,
                "saturation": record.saturation,
                "value_center": record.value_center,
                "value_amplitude": record.value_amplitude,
                "value_min": record.value_min,
                "value_max": record.value_max,
                "waveform": record.waveform,
                "mapping_version": record.mapping_version,
                "phase_policy_version": record.phase_policy_version,
                "command_hold_policy_version": record.command_hold_policy_version,
                "inactive_output_policy_version": (
                    record.inactive_output_policy_version
                ),
                "schema_version": record.schema_version,
            }
            for record in self._command_records
        ]
        return self._digest(records)

    def stimulus_state_digest(self) -> str:
        return self._digest(
            [
                {
                    "effective_time_us": record.effective_time_us,
                    "source_signal_index": record.source_signal_index,
                    "active": record.active,
                    "holder": record.qualification_holder_id,
                    "source_b": record.source_b,
                    "hue_degree": record.hue_degree,
                    "render_hue_degree": record.render_hue_degree,
                    "saturation": record.saturation,
                    "value_center": record.value_center,
                    "value_amplitude": record.value_amplitude,
                    "value_min": record.value_min,
                    "value_max": record.value_max,
                    "blink_bpm": record.blink_bpm,
                    "waveform": record.waveform,
                    "phase_cycles_at_start": record.phase_cycles_at_start,
                    "value_at_start": record.value_at_start,
                    "phase_reset": record.phase_reset,
                    "physical_parameters_changed": (
                        record.physical_parameters_changed
                    ),
                    "command_equivalent_to_previous": (
                        record.command_equivalent_to_previous
                    ),
                    "schema_version": record.schema_version,
                }
                for record in self._state_records
            ]
        )

    def segment_digest(self) -> str:
        return self._digest(
            [
                {
                    "segment_index": record.segment_index,
                    "start_time_us": record.start_time_us,
                    "end_time_us": record.end_time_us,
                    "duration_us": record.duration_us,
                    "active": record.active,
                    "source_signal_index": record.source_signal_index,
                    "holder": record.qualification_holder_id,
                    "source_b": record.source_b,
                    "hue_degree": record.hue_degree,
                    "render_hue_degree": record.render_hue_degree,
                    "saturation": record.saturation,
                    "value_center": record.value_center,
                    "value_amplitude": record.value_amplitude,
                    "value_min": record.value_min,
                    "value_max": record.value_max,
                    "blink_bpm": record.blink_bpm,
                    "waveform": record.waveform,
                    "phase_cycles_at_start": record.phase_cycles_at_start,
                    "phase_cycles_at_end": record.phase_cycles_at_end,
                    "value_at_start": record.value_at_start,
                    "value_at_end": record.value_at_end,
                    "schema_version": record.schema_version,
                }
                for record in self._segments
            ]
        )

    def waveform_sample_digest(self) -> str:
        return self._digest(
            [
                {
                    "sample_index": record.sample_index,
                    "time_us": record.time_us,
                    "active": record.active,
                    "source_signal_index": record.source_signal_index,
                    "holder": record.holder_id,
                    "hue_degree": record.hue_degree,
                    "render_hue_degree": record.render_hue_degree,
                    "saturation": record.saturation,
                    "blink_bpm": record.blink_bpm,
                    "phase_cycles": record.phase_cycles,
                    "value": record.value,
                }
                for record in self.waveform_samples()
            ]
        )

    def _validate_next_command(self, command: LightCommandInput) -> None:
        if command.command_effective_time_us > self.config.simulation_end_time_us:
            raise ValueError("light command is beyond simulation_end_time_us")
        if command.schema_version != self.config.input_schema_version:
            raise ValueError("light command schema differs from device input schema")
        if command.phase_policy_version != self.config.phase_policy_version:
            raise ValueError("light command phase policy differs from device config")
        if (
            command.command_hold_policy_version
            != self.config.command_hold_policy_version
        ):
            raise ValueError("light command hold policy differs from device config")
        if (
            command.inactive_output_policy_version
            != self.config.inactive_output_policy_version
        ):
            raise ValueError("light command inactive policy differs from device config")
        if self._command_records:
            previous = self._command_records[-1]
            if command.source_signal_index <= previous.source_signal_index:
                raise ValueError("source_signal_index must strictly increase")
            if command.command_effective_time_us <= previous.effective_time_us:
                raise ValueError("command effective time must strictly increase")

    def _command_record(self, command: LightCommandInput) -> LightCommandRecord:
        return LightCommandRecord(
            command_index=len(self._command_records),
            garden_id=command.garden_id,
            source_signal_index=command.source_signal_index,
            source_signal_time_us=command.source_signal_time_us,
            source_effective_time_us=command.source_effective_time_us,
            effective_time_us=command.command_effective_time_us,
            active=command.active,
            qualification_holder_id=command.qualification_holder_id,
            source_b=command.source_b,
            hue_degree=command.hue_degree,
            render_hue_degree=command.render_hue_degree,
            saturation=command.saturation,
            value_center=command.value_center,
            value_amplitude=command.value_amplitude,
            value_min=command.value_min,
            value_max=command.value_max,
            blink_bpm=command.blink_bpm,
            waveform=command.waveform,
            mapping_version=command.mapping_version,
            phase_policy_version=command.phase_policy_version,
            command_hold_policy_version=command.command_hold_policy_version,
            inactive_output_policy_version=command.inactive_output_policy_version,
            schema_version=command.schema_version,
        )

    def _segment_for(
        self,
        command: LightCommandRecord,
        state: LightStimulusStateRecord | None,
        *,
        end_time_us: int,
    ) -> LightStimulusSegment:
        if state is None:
            raise RuntimeError("a command segment requires its stimulus state")
        if end_time_us <= command.effective_time_us:
            raise ValueError("a stored light segment must have positive duration")
        if command.active:
            assert state.phase_cycles_at_start is not None
            assert command.blink_bpm is not None
            phase_at_end = phase_cycles_at(
                end_time_us,
                start_time_us=command.effective_time_us,
                phase_cycles_at_start=state.phase_cycles_at_start,
                blink_bpm=command.blink_bpm,
            )
            value_at_end = sine_value(
                phase_at_end,
                value_center=command.value_center,
                value_amplitude=command.value_amplitude,
            )
        else:
            phase_at_end = None
            value_at_end = 0.0
        return LightStimulusSegment(
            segment_index=len(self._segments),
            start_time_us=command.effective_time_us,
            end_time_us=end_time_us,
            duration_us=end_time_us - command.effective_time_us,
            active=command.active,
            source_signal_index=command.source_signal_index,
            source_signal_time_us=command.source_signal_time_us,
            qualification_holder_id=command.qualification_holder_id,
            source_b=command.source_b,
            hue_degree=command.hue_degree,
            render_hue_degree=command.render_hue_degree,
            saturation=command.saturation,
            value_center=command.value_center,
            value_amplitude=command.value_amplitude,
            value_min=command.value_min,
            value_max=command.value_max,
            blink_bpm=command.blink_bpm,
            waveform=command.waveform,
            phase_cycles_at_start=state.phase_cycles_at_start,
            phase_cycles_at_end=phase_at_end,
            value_at_start=state.value_at_start,
            value_at_end=value_at_end,
            mapping_version=command.mapping_version,
            phase_policy_version=command.phase_policy_version,
            command_hold_policy_version=command.command_hold_policy_version,
            inactive_output_policy_version=command.inactive_output_policy_version,
            schema_version=self.config.segment_schema_version,
        )

    def _sample_at(self, sample_index: int, time_us: int) -> LightWaveformSample:
        state = self.state_at(time_us)
        return LightWaveformSample(
            sample_index=sample_index,
            time_us=time_us,
            time_seconds=time_us / 1_000_000.0,
            active=state.active,
            source_signal_index=state.source_signal_index,
            holder_id=state.current_holder_id,
            hue_degree=state.hue_degree,
            render_hue_degree=state.render_hue_degree,
            saturation=state.saturation,
            blink_bpm=state.blink_bpm,
            phase_cycles=state.phase_cycles,
            value=state.current_value,
        )

    def _validate_segment_history(self) -> None:
        for index, segment in enumerate(self._segments):
            if segment.segment_index != index:
                raise RuntimeError("light segment indices are not contiguous")
            if segment.end_time_us <= segment.start_time_us:
                raise RuntimeError("light segment duration is not positive")
            if index and self._segments[index - 1].end_time_us != segment.start_time_us:
                raise RuntimeError("light segment history has a gap or overlap")
            if segment.end_time_us > self.config.simulation_end_time_us:
                raise RuntimeError("light segment extends beyond simulation end")
            if index:
                previous = self._segments[index - 1]
                if (
                    previous.active
                    and segment.active
                    and previous.phase_cycles_at_end
                    != segment.phase_cycles_at_start
                ):
                    raise RuntimeError("active light segment phase is discontinuous")

    @staticmethod
    def _physical_key(record: LightCommandRecord) -> tuple[object, ...]:
        return (
            record.active,
            record.hue_degree,
            record.saturation,
            record.value_center,
            record.value_amplitude,
            record.value_min,
            record.value_max,
            record.blink_bpm,
            record.waveform,
            record.phase_policy_version,
        )

    @staticmethod
    def _physical_key_for_input(command: LightCommandInput) -> tuple[object, ...]:
        return (
            command.active,
            command.hue_degree,
            command.saturation,
            command.value_center,
            command.value_amplitude,
            command.value_min,
            command.value_max,
            command.blink_bpm,
            command.waveform,
            command.phase_policy_version,
        )

    @staticmethod
    def _digest(records: list[dict[str, object]]) -> str:
        canonical = json.dumps(
            records,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
