"""GUI-independent Stage 6 Garden Light Mapper component."""

from __future__ import annotations

import hashlib
import json

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.output_layer.events import (
    parse_garden_qualified_b_event,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine

from .config import GardenLightMapperConfig
from .events import (
    LIGHT_COMMAND_EVENT_PRIORITY,
    LIGHT_COMMAND_EVENT_SOURCE,
    LIGHT_COMMAND_EVENT_TYPE,
    light_command_payload,
)
from .mapping import map_b_to_i
from .records import GardenLightMapperSnapshot, LightCommandRecord

MAX_STANDARD_SIGNAL_INDEX = 240


class GardenLightMapperComponent:
    """Translate only formal qualified-B events into one formal I command each."""

    def __init__(self, config: GardenLightMapperConfig) -> None:
        if not isinstance(config, GardenLightMapperConfig):
            raise TypeError("config must be a GardenLightMapperConfig")
        self.config = config
        self.reset()

    def reset(self) -> None:
        """Restore a fresh deterministic Stage 6 mapper session."""

        self._command_records: list[LightCommandRecord] = []
        self._last_source_signal_index: int | None = None
        self._last_source_effective_time_us: int | None = None
        self._active_command_count = 0
        self._inactive_command_count = 0

    def handle_garden_qualified_b(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Validate one qB v2 input and schedule exactly one p66 LightCommand."""

        qualified = parse_garden_qualified_b_event(event)
        if qualified.garden_id != self.config.garden_id:
            raise ValueError("qualified B garden_id does not match the mapper")
        self._validate_next_input(
            signal_index=qualified.signal_index,
            effective_time_us=qualified.effective_time_us,
        )
        mapped = map_b_to_i(
            active=qualified.active,
            b=qualified.b,
            config=self.config,
        )
        if qualified.active != mapped.active:
            raise RuntimeError("B-to-I mapping changed the active state")
        record = LightCommandRecord(
            command_index=len(self._command_records),
            garden_id=self.config.garden_id,
            source_signal_index=qualified.signal_index,
            source_signal_time_us=qualified.signal_time_us,
            source_effective_time_us=qualified.effective_time_us,
            command_effective_time_us=qualified.effective_time_us,
            active=mapped.active,
            qualification_holder_id=qualified.qualification_holder_id,
            source_b=mapped.source_b,
            hue_degree=mapped.hue_degree,
            render_hue_degree=mapped.render_hue_degree,
            saturation=mapped.saturation,
            value_center=mapped.value_center,
            value_amplitude=mapped.value_amplitude,
            value_min=mapped.value_min,
            value_max=mapped.value_max,
            blink_bpm=mapped.blink_bpm,
            waveform=mapped.waveform,
            mapping_version=self.config.mapping_version,
            phase_policy_version=self.config.phase_policy_version,
            command_hold_policy_version=self.config.command_hold_policy_version,
            inactive_output_policy_version=self.config.inactive_output_policy_version,
            schema_version=self.config.output_schema_version,
        )
        engine.schedule_at(
            record.command_effective_time_us,
            LIGHT_COMMAND_EVENT_TYPE,
            source=LIGHT_COMMAND_EVENT_SOURCE,
            priority=LIGHT_COMMAND_EVENT_PRIORITY,
            payload=light_command_payload(record),
        )
        self._command_records.append(record)
        self._last_source_signal_index = record.source_signal_index
        self._last_source_effective_time_us = record.source_effective_time_us
        if record.active:
            self._active_command_count += 1
        else:
            self._inactive_command_count += 1

    handle_qualified_b = handle_garden_qualified_b

    def command_records(self) -> tuple[LightCommandRecord, ...]:
        return tuple(self._command_records)

    def snapshot(self) -> GardenLightMapperSnapshot:
        return GardenLightMapperSnapshot(
            garden_id=self.config.garden_id,
            model_version=self.config.model_version,
            mapping_version=self.config.mapping_version,
            input_schema_version=self.config.input_schema_version,
            output_schema_version=self.config.output_schema_version,
            command_count=len(self._command_records),
            active_command_count=self._active_command_count,
            inactive_command_count=self._inactive_command_count,
            last_source_signal_index=self._last_source_signal_index,
            last_source_effective_time_us=self._last_source_effective_time_us,
            current_command=(
                self._command_records[-1] if self._command_records else None
            ),
        )

    def command_digest(self) -> str:
        records = [
            {
                "effective_time_us": record.command_effective_time_us,
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
        canonical = json.dumps(
            records,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _validate_next_input(self, *, signal_index: int, effective_time_us: int) -> None:
        if signal_index > MAX_STANDARD_SIGNAL_INDEX:
            raise ValueError("qualified B signal_index must be between 0 and 240")
        expected_index = (
            0
            if self._last_source_signal_index is None
            else self._last_source_signal_index + 1
        )
        if signal_index != expected_index:
            raise ValueError("qualified B signal_index must increase from 0 by exactly one")
        if (
            self._last_source_effective_time_us is not None
            and effective_time_us <= self._last_source_effective_time_us
        ):
            raise ValueError("qualified B effective time must strictly increase")
