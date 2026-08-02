"""GUI-independent ideal Polar H10 that measures heartbeat event timestamps."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.polar_h10.records import RriMeasurementRecord
from symbiotic_sim_v2.domain.event_priorities import (
    HEARTBEAT_EVENT_PRIORITY,
    RRI_MEASUREMENT_EVENT_PRIORITY,
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import (
    POLAR_H10_EVENT_SOURCE,
    VIRTUAL_USER_EVENT_SOURCE,
)
from symbiotic_sim_v2.domain.event_types import (
    HEARTBEAT_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.simulation.engine import SimulationEngine

RRI_MEASUREMENT_EVENT_SOURCE = POLAR_H10_EVENT_SOURCE


class PolarH10State(StrEnum):
    """Small deterministic lifecycle for the ideal device."""

    READY = "ready"
    MEASURING = "measuring"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class PolarH10Snapshot:
    """Immutable device state exposed to diagnostics and GUI consumers."""

    device_id: str
    model_version: str
    state: PolarH10State
    observed_heartbeat_count: int
    rri_measurement_count: int
    latest_rri_us: int | None
    latest_rri_ms: float | None
    latest_measurement_time_us: int | None
    previous_heartbeat_time_us: int | None
    previous_beat_index: int | None


class PolarH10Component:
    """Convert adjacent formal heartbeat timestamps into raw RRI events."""

    def __init__(self, config: PolarH10Config) -> None:
        if not isinstance(config, PolarH10Config):
            raise TypeError("config must be a PolarH10Config")
        self.config = config
        self._state = PolarH10State.READY
        self._observed_heartbeat_count = 0
        self._previous_heartbeat_time_us: int | None = None
        self._previous_beat_index: int | None = None
        self._records: list[RriMeasurementRecord] = []

    def reset(self) -> None:
        """Restore the ideal device to its pre-observation state."""

        self._state = PolarH10State.READY
        self._observed_heartbeat_count = 0
        self._previous_heartbeat_time_us = None
        self._previous_beat_index = None
        self._records.clear()

    def handle_heartbeat(self, event: SimulationEvent, engine: SimulationEngine) -> None:
        """Validate one heartbeat and schedule its raw interval when available."""

        beat_index = self._validated_beat_index(event)
        current_time_us = event.scheduled_time_us
        if self._state is PolarH10State.COMPLETED:
            raise RuntimeError("completed device cannot accept heartbeat events")

        previous_time_us = self._previous_heartbeat_time_us
        previous_beat_index = self._previous_beat_index
        if previous_time_us is None:
            if previous_beat_index is not None:
                raise RuntimeError("previous heartbeat state is inconsistent")
            self._previous_heartbeat_time_us = current_time_us
            self._previous_beat_index = beat_index
            self._observed_heartbeat_count = 1
            self._state = PolarH10State.MEASURING
            return

        if previous_beat_index is None:
            raise RuntimeError("previous beat index is missing")
        if current_time_us <= previous_time_us:
            raise ValueError("heartbeat times must be strictly increasing")
        if beat_index <= previous_beat_index:
            raise ValueError("beat_index must be strictly increasing")

        rri_us = current_time_us - previous_time_us
        measurement_index = len(self._records)
        payload = {
            "device_id": self.config.device_id,
            "user_id": self.config.expected_user_id,
            "measurement_index": measurement_index,
            "previous_beat_index": previous_beat_index,
            "current_beat_index": beat_index,
            "previous_heartbeat_time_us": previous_time_us,
            "current_heartbeat_time_us": current_time_us,
            "rri_us": rri_us,
            "rri_ms": rri_us / 1_000.0,
            "event_schema_version": self.config.event_schema_version,
        }
        output_event = engine.schedule_at(
            current_time_us,
            RRI_MEASUREMENT_EVENT_TYPE,
            source=RRI_MEASUREMENT_EVENT_SOURCE,
            priority=RRI_MEASUREMENT_EVENT_PRIORITY,
            payload=payload,
        )
        self._records.append(
            RriMeasurementRecord(
                measurement_index=measurement_index,
                event_id=output_event.event_id,
                device_id=self.config.device_id,
                user_id=self.config.expected_user_id,
                previous_beat_index=previous_beat_index,
                current_beat_index=beat_index,
                previous_heartbeat_time_us=previous_time_us,
                current_heartbeat_time_us=current_time_us,
                rri_us=rri_us,
                rri_ms=rri_us / 1_000.0,
                event_schema_version=self.config.event_schema_version,
            )
        )
        self._previous_heartbeat_time_us = current_time_us
        self._previous_beat_index = beat_index
        self._observed_heartbeat_count += 1
        self._state = PolarH10State.MEASURING

    def handle_simulation_complete(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Mark the device completed after all same-time measurements execute."""

        if event.event_type != SIMULATION_COMPLETE_EVENT_TYPE:
            raise ValueError("completion handler received the wrong event type")
        if event.priority != SIMULATION_COMPLETE_EVENT_PRIORITY:
            raise ValueError("completion event priority does not match the boundary constant")
        self._state = PolarH10State.COMPLETED

    def snapshot(self) -> PolarH10Snapshot:
        """Return a frozen view without exposing mutable record storage."""

        latest = self._records[-1] if self._records else None
        return PolarH10Snapshot(
            device_id=self.config.device_id,
            model_version=self.config.model_version,
            state=self._state,
            observed_heartbeat_count=self._observed_heartbeat_count,
            rri_measurement_count=len(self._records),
            latest_rri_us=latest.rri_us if latest else None,
            latest_rri_ms=latest.rri_ms if latest else None,
            latest_measurement_time_us=latest.event_time_us if latest else None,
            previous_heartbeat_time_us=self._previous_heartbeat_time_us,
            previous_beat_index=self._previous_beat_index,
        )

    def measurement_records(self) -> tuple[RriMeasurementRecord, ...]:
        """Return the immutable sequence of raw device measurements."""

        return tuple(self._records)

    def measurement_digest(self) -> str:
        """Hash the fixed canonical raw-measurement fields (excluding derived ms)."""

        digest_records = [
            {
                "measurement_index": record.measurement_index,
                "scheduled_time_us": record.event_time_us,
                "device_id": record.device_id,
                "user_id": record.user_id,
                "previous_beat_index": record.previous_beat_index,
                "current_beat_index": record.current_beat_index,
                "previous_heartbeat_time_us": record.previous_heartbeat_time_us,
                "current_heartbeat_time_us": record.current_heartbeat_time_us,
                "rri_us": record.rri_us,
                "event_schema_version": record.event_schema_version,
            }
            for record in self._records
        ]
        canonical = json.dumps(
            digest_records,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _validated_beat_index(self, event: SimulationEvent) -> int:
        if event.event_type != HEARTBEAT_EVENT_TYPE:
            raise ValueError("PolarH10Component only accepts heartbeat events")
        if event.source != VIRTUAL_USER_EVENT_SOURCE:
            raise ValueError("heartbeat event source must be virtual_user")
        if event.priority != HEARTBEAT_EVENT_PRIORITY:
            raise ValueError("heartbeat event priority does not match the boundary constant")
        if event.scheduled_time_us < 0:
            raise ValueError("heartbeat event time must be non-negative")
        if set(event.payload) != {"user_id", "beat_index"}:
            raise ValueError("heartbeat payload must contain only user_id and beat_index")
        if event.payload["user_id"] != self.config.expected_user_id:
            raise ValueError("heartbeat user_id does not match expected_user_id")
        beat_index = event.payload["beat_index"]
        if isinstance(beat_index, bool) or not isinstance(beat_index, int):
            raise TypeError("beat_index must be an integer")
        if beat_index < 0:
            raise ValueError("beat_index must be non-negative")
        return beat_index
