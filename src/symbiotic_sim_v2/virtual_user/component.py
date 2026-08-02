"""GUI-independent virtual user that formally emits heartbeat events only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from symbiotic_sim_v2.domain.event_priorities import HEARTBEAT_EVENT_PRIORITY
from symbiotic_sim_v2.domain.event_sources import VIRTUAL_USER_EVENT_SOURCE
from symbiotic_sim_v2.domain.event_types import HEARTBEAT_EVENT_TYPE
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.diagnostics import (
    HeartbeatRecord,
    instantaneous_hr_bpm,
)
from symbiotic_sim_v2.virtual_user.physiology import RriComputation, calculate_next_rri

HEARTBEAT_EVENT_SOURCE = VIRTUAL_USER_EVENT_SOURCE


@dataclass(frozen=True, slots=True)
class VirtualUserSnapshot:
    """Immutable current state without exposing mutable physiology internals."""

    user_id: str
    model_version: str
    heartbeat_count: int
    current_heartbeat_time_us: int | None
    latest_true_rri_ms: float | None
    latest_instantaneous_hr_bpm: float | None
    latest_respiratory_component_ms: float | None
    latest_slow_wave_component_ms: float | None
    latest_correlated_component_ms: float | None
    latest_beat_jitter_component_ms: float | None
    clamped_beat_count: int


class VirtualUserComponent:
    """Generate causal heartbeat events from an external-input-free internal model."""

    def __init__(self, config: VirtualUserConfig) -> None:
        self.config = config
        self._records: list[HeartbeatRecord] = []
        self._previous_heartbeat_time_us: int | None = None
        self._correlated_state = 0.0
        self._pending_computation: RriComputation | None = None
        self._clamped_beat_count = 0

    def reset(self) -> None:
        """Restore initial physiology, beat index, timestamp, and diagnostic records."""

        self._records.clear()
        self._previous_heartbeat_time_us = None
        self._correlated_state = 0.0
        self._pending_computation = None
        self._clamped_beat_count = 0

    def schedule_initial(self, scheduler: EventScheduler) -> SimulationEvent:
        """Schedule the first heartbeat at scenario time zero with the formal payload."""

        return scheduler.schedule_at(
            0,
            HEARTBEAT_EVENT_TYPE,
            source=HEARTBEAT_EVENT_SOURCE,
            priority=HEARTBEAT_EVENT_PRIORITY,
            payload={"user_id": self.config.user_id, "beat_index": 0},
        )

    def handle_heartbeat(self, event: SimulationEvent, engine: SimulationEngine) -> None:
        """Record one heartbeat and causally schedule at most one future heartbeat."""

        self._validate_event(event)
        beat_index = len(self._records)
        if event.payload["beat_index"] != beat_index:
            raise RuntimeError("heartbeat beat_index does not match component state")
        if self._previous_heartbeat_time_us is not None:
            if event.scheduled_time_us <= self._previous_heartbeat_time_us:
                raise RuntimeError("heartbeat times must be strictly increasing")
            if self._pending_computation is None:
                raise RuntimeError("missing causal RRI computation for heartbeat")
            true_interval_us = event.scheduled_time_us - self._previous_heartbeat_time_us
            if true_interval_us != self._pending_computation.rri_us:
                raise RuntimeError("heartbeat timestamp differs from scheduled physiology interval")
            true_interval_ms = true_interval_us / 1_000.0
            calculation = self._pending_computation
            record = HeartbeatRecord(
                beat_index=beat_index,
                heartbeat_time_us=event.scheduled_time_us,
                previous_heartbeat_time_us=self._previous_heartbeat_time_us,
                true_rri_us=true_interval_us,
                true_rri_ms=true_interval_ms,
                instantaneous_hr_bpm=instantaneous_hr_bpm(true_interval_ms),
                respiratory_component_ms=calculation.respiratory_component_ms,
                slow_wave_component_ms=calculation.slow_wave_component_ms,
                correlated_component_ms=calculation.correlated_component_ms,
                beat_jitter_component_ms=calculation.beat_jitter_component_ms,
                unclamped_rri_ms=calculation.unclamped_rri_ms,
                final_rri_ms=calculation.final_rri_ms,
                clamped=calculation.clamped,
            )
            if calculation.clamped:
                self._clamped_beat_count += 1
        else:
            if beat_index != 0:
                raise RuntimeError("only beat zero may omit a previous heartbeat")
            record = HeartbeatRecord(
                beat_index=0,
                heartbeat_time_us=event.scheduled_time_us,
                previous_heartbeat_time_us=None,
                true_rri_us=None,
                true_rri_ms=None,
                instantaneous_hr_bpm=None,
                respiratory_component_ms=None,
                slow_wave_component_ms=None,
                correlated_component_ms=None,
                beat_jitter_component_ms=None,
                unclamped_rri_ms=None,
                final_rri_ms=None,
                clamped=None,
            )

        self._records.append(record)
        self._previous_heartbeat_time_us = event.scheduled_time_us
        self._pending_computation = None
        self._schedule_next_if_in_bounds(event, engine)

    def snapshot(self) -> VirtualUserSnapshot:
        """Return a frozen snapshot suitable for GUI diagnostic reads."""

        latest = self._records[-1] if self._records else None
        return VirtualUserSnapshot(
            user_id=self.config.user_id,
            model_version=self.config.model_version,
            heartbeat_count=len(self._records),
            current_heartbeat_time_us=latest.heartbeat_time_us if latest else None,
            latest_true_rri_ms=latest.true_rri_ms if latest else None,
            latest_instantaneous_hr_bpm=latest.instantaneous_hr_bpm if latest else None,
            latest_respiratory_component_ms=(
                latest.respiratory_component_ms if latest else None
            ),
            latest_slow_wave_component_ms=latest.slow_wave_component_ms if latest else None,
            latest_correlated_component_ms=(latest.correlated_component_ms if latest else None),
            latest_beat_jitter_component_ms=(
                latest.beat_jitter_component_ms if latest else None
            ),
            clamped_beat_count=self._clamped_beat_count,
        )

    def heartbeat_records(self) -> tuple[HeartbeatRecord, ...]:
        """Return immutable diagnostic records; these are not formal output events."""

        return tuple(self._records)

    def heartbeat_digest(self) -> str:
        """Hash only formal heartbeat identity and virtual timestamp fields."""

        records = [
            {"beat_index": record.beat_index, "heartbeat_time_us": record.heartbeat_time_us}
            for record in self._records
        ]
        return self._canonical_digest(records)

    def diagnostic_digest(self) -> str:
        """Hash internal true-RRI/component records separately from formal output."""

        return self._canonical_digest([record.to_dict() for record in self._records])

    def _schedule_next_if_in_bounds(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        if event.scheduled_time_us >= engine.clock.end_time_us:
            return
        calculation = calculate_next_rri(
            self.config,
            event.scheduled_time_us,
            len(self._records) - 1,
            self._correlated_state,
        )
        next_time_us = event.scheduled_time_us + calculation.rri_us
        if next_time_us > engine.clock.end_time_us:
            return
        self._correlated_state = calculation.next_correlated_state
        self._pending_computation = calculation
        engine.schedule_at(
            next_time_us,
            HEARTBEAT_EVENT_TYPE,
            source=HEARTBEAT_EVENT_SOURCE,
            priority=HEARTBEAT_EVENT_PRIORITY,
            payload={
                "user_id": self.config.user_id,
                "beat_index": len(self._records),
            },
        )

    def _validate_event(self, event: SimulationEvent) -> None:
        if event.event_type != HEARTBEAT_EVENT_TYPE:
            raise ValueError("VirtualUserComponent only handles heartbeat events")
        if event.source != HEARTBEAT_EVENT_SOURCE:
            raise ValueError("heartbeat event source must be virtual_user")
        if event.priority != HEARTBEAT_EVENT_PRIORITY:
            raise ValueError("heartbeat event priority does not match the boundary constant")
        if set(event.payload) != {"user_id", "beat_index"}:
            raise ValueError("heartbeat payload must contain only user_id and beat_index")
        if event.payload["user_id"] != self.config.user_id:
            raise ValueError("heartbeat user_id does not match component config")

    @staticmethod
    def _canonical_digest(records: list[dict[str, object]]) -> str:
        encoded = json.dumps(
            records,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
