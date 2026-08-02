"""GUI-independent Stage 4 Garden input-layer component."""

from __future__ import annotations

import hashlib
import json
import math
from collections import deque

from symbiotic_sim_v2.domain.event_priorities import (
    GARDEN_EVALUATION_FINALIZE_TRIGGER_PRIORITY,
    GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
    GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
    GARDEN_PHASE_EVENT_PRIORITY,
    RRI_MEASUREMENT_EVENT_PRIORITY,
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import (
    GARDEN_INPUT_EVENT_SOURCE,
    POLAR_H10_EVENT_SOURCE,
)
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE,
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE,
    GARDEN_PHASE_CHANGED_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.garden.input_layer.artifact_filter import classify_rri
from symbiotic_sim_v2.garden.input_layer.config import (
    RRI_INPUT_SCHEMA_VERSION,
    GardenInputConfig,
)
from symbiotic_sim_v2.garden.input_layer.normalization import normalize_rmssd_to_n
from symbiotic_sim_v2.garden.input_layer.phases import (
    GardenEvaluationKind,
    GardenEvaluationQuality,
    GardenSessionStatus,
)
from symbiotic_sim_v2.garden.input_layer.records import (
    GardenEvaluationRecord,
    GardenInputSignalRecord,
    GardenInputSnapshot,
    GardenRriRecord,
)
from symbiotic_sim_v2.garden.input_layer.rmssd import calculate_rmssd_ms
from symbiotic_sim_v2.garden.input_layer.timing import (
    GardenEvaluationWindow,
    evaluation_windows,
    phase_at,
)
from symbiotic_sim_v2.simulation.engine import SimulationEngine

GARDEN_INPUT_SCENARIO_SOURCE = "garden_input_scenario"
STANDARD_GARDEN_SESSION_ID = "session-001"

_RRI_PAYLOAD_FIELDS = {
    "device_id",
    "user_id",
    "measurement_index",
    "previous_beat_index",
    "current_beat_index",
    "previous_heartbeat_time_us",
    "current_heartbeat_time_us",
    "rri_us",
    "rri_ms",
    "event_schema_version",
}


class GardenInputComponent:
    """Convert formal raw RRI events into evaluation-window N and one-second S."""

    def __init__(
        self,
        config: GardenInputConfig,
        *,
        session_id: str = STANDARD_GARDEN_SESSION_ID,
    ) -> None:
        if not isinstance(config, GardenInputConfig):
            raise TypeError("config must be a GardenInputConfig")
        if session_id != STANDARD_GARDEN_SESSION_ID:
            raise ValueError(f"session_id must be {STANDARD_GARDEN_SESSION_ID}")
        self.config = config
        self.session_id = session_id
        self._windows = {window.evaluation_id: window for window in evaluation_windows(config)}
        self.reset()

    def reset(self) -> None:
        """Clear every session-derived value while retaining immutable config."""

        descriptor = phase_at(0, self.config)
        self._current_descriptor = descriptor
        self._current_s = 0
        self._session_status = GardenSessionStatus.BASELINE
        self._baseline_finalized = False
        self._baseline_available = False
        self._baseline_id: str | None = None
        self._n_baseline_session: float | None = None
        self._n_current: float | None = None
        self._valid_evaluation_revision = 0
        self._latest_valid_evaluation_id: str | None = None
        self._latest_rmssd_ms: float | None = None
        self._latest_evaluation_quality: str | None = None
        self._latest_evaluation_id: str | None = None
        self._recent_valid_rri_us: deque[int] = deque(
            maxlen=self.config.median_history_max_valid_count
        )
        self._rri_records: list[GardenRriRecord] = []
        self._evaluation_records: list[GardenEvaluationRecord] = []
        self._signal_records: list[GardenInputSignalRecord] = []
        self._evaluation_buffers: dict[str, list[GardenRriRecord]] = {
            evaluation_id: [] for evaluation_id in self._windows
        }
        self._valid_rri_count = 0
        self._artifact_rri_count = 0
        self._seen_input_event_ids: set[str] = set()
        self._seen_measurement_indices: set[int] = set()

    def handle_rri_measurement(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Validate and classify one formal H10 RriMeasurementEvent."""

        values = self._validated_rri_payload(event)
        measurement_index = values["measurement_index"]
        if event.event_id in self._seen_input_event_ids:
            raise ValueError("duplicate RRI input event_id")
        if measurement_index in self._seen_measurement_indices:
            raise ValueError("duplicate RRI measurement_index")

        rri_us = values["rri_us"]
        descriptor = phase_at(event.scheduled_time_us, self.config)
        decision = classify_rri(rri_us, tuple(self._recent_valid_rri_us), self.config)
        included = descriptor.evaluation_id is not None
        record = GardenRriRecord(
            input_measurement_index=measurement_index,
            input_event_id=event.event_id,
            event_time_us=event.scheduled_time_us,
            device_id=values["device_id"],
            user_id=values["user_id"],
            raw_rri_us=rri_us,
            raw_rri_ms=rri_us / 1_000.0,
            phase=descriptor.phase.value,
            bundle_index=descriptor.bundle_index,
            window_role=descriptor.window_role.value,
            evaluation_id=descriptor.evaluation_id,
            artifact=decision.artifact,
            artifact_reason=decision.artifact_reason,
            median_history_count_before=decision.median_history_count_before,
            median_rri_us_before=decision.median_rri_us_before,
            relative_deviation=decision.relative_deviation,
            accepted_into_valid_history=not decision.artifact,
            included_in_evaluation_window=included,
            membership_policy=self.config.rri_window_membership_policy,
        )
        self._seen_input_event_ids.add(event.event_id)
        self._seen_measurement_indices.add(measurement_index)
        self._rri_records.append(record)
        if decision.artifact:
            self._artifact_rri_count += 1
        else:
            self._recent_valid_rri_us.append(rri_us)
            self._valid_rri_count += 1
        if descriptor.evaluation_id is not None:
            self._evaluation_buffers[descriptor.evaluation_id].append(record)

    def handle_phase_change(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Apply one pre-scheduled formal phase boundary event."""

        if event.event_type != GARDEN_PHASE_CHANGED_EVENT_TYPE:
            raise ValueError("phase handler received the wrong event type")
        if event.source != GARDEN_INPUT_EVENT_SOURCE:
            raise ValueError("phase event source must be garden_input")
        if event.priority != GARDEN_PHASE_EVENT_PRIORITY:
            raise ValueError("phase event priority does not match the boundary constant")
        descriptor = phase_at(event.scheduled_time_us, self.config)
        expected_payload = {
            "garden_id": self.config.garden_id,
            "session_id": self.session_id,
            "phase_time_us": event.scheduled_time_us,
            "phase": descriptor.phase.value,
            "bundle_index": descriptor.bundle_index,
            "window_role": descriptor.window_role.value,
            "schema_version": self.config.phase_schema_version,
        }
        if dict(event.payload) != expected_payload:
            raise ValueError("phase payload does not match its deterministic boundary")
        self._current_descriptor = descriptor
        self._refresh_session_state(event.scheduled_time_us)

    def handle_evaluation_finalize_trigger(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Finalize one closed window and schedule its formal result event."""

        if event.event_type != GARDEN_EVALUATION_FINALIZE_TRIGGER_EVENT_TYPE:
            raise ValueError("evaluation trigger handler received the wrong event type")
        if event.source != GARDEN_INPUT_SCENARIO_SOURCE:
            raise ValueError("evaluation trigger source must be garden_input_scenario")
        if event.priority != GARDEN_EVALUATION_FINALIZE_TRIGGER_PRIORITY:
            raise ValueError("evaluation trigger priority does not match the boundary constant")
        if not isinstance(event.payload, dict):
            raise ValueError("evaluation trigger payload must be an object")
        if set(event.payload) != {"evaluation_id"}:
            raise ValueError("evaluation trigger payload must contain only evaluation_id")
        evaluation_id = event.payload["evaluation_id"]
        if not isinstance(evaluation_id, str) or evaluation_id not in self._windows:
            raise ValueError("evaluation trigger has an unknown evaluation_id")
        window = self._windows[evaluation_id]
        if event.scheduled_time_us != window.window_end_us:
            raise ValueError("evaluation trigger time must equal the window end")
        if any(record.evaluation_id == evaluation_id for record in self._evaluation_records):
            raise RuntimeError("evaluation window was finalized more than once")

        record = self._finalize_window(window)
        self._evaluation_records.append(record)
        self._latest_rmssd_ms = record.rmssd_ms
        self._latest_evaluation_quality = record.quality
        self._latest_evaluation_id = record.evaluation_id
        engine.schedule_at(
            event.scheduled_time_us,
            GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
            source=GARDEN_INPUT_EVENT_SOURCE,
            priority=GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
            payload={
                "garden_id": self.config.garden_id,
                "session_id": self.session_id,
                **record.to_dict(),
            },
        )
        self._refresh_session_state(event.scheduled_time_us)

    def handle_signal_trigger(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        """Snapshot state once per second and schedule the formal N/S event."""

        if event.event_type != GARDEN_INPUT_SIGNAL_TRIGGER_EVENT_TYPE:
            raise ValueError("signal trigger handler received the wrong event type")
        if event.source != GARDEN_INPUT_SCENARIO_SOURCE:
            raise ValueError("signal trigger source must be garden_input_scenario")
        if event.priority != GARDEN_INPUT_SIGNAL_EVENT_PRIORITY:
            raise ValueError("signal trigger priority does not match the boundary constant")
        if not isinstance(event.payload, dict) or set(event.payload) != {"signal_index"}:
            raise ValueError("signal trigger payload must contain only signal_index")
        signal_index = event.payload["signal_index"]
        if isinstance(signal_index, bool) or not isinstance(signal_index, int):
            raise TypeError("signal_index must be an integer")
        if signal_index != len(self._signal_records):
            raise RuntimeError("signal_index does not match component state")
        if event.scheduled_time_us != signal_index * self.config.signal_interval_us:
            raise ValueError("signal trigger time does not match signal_index")

        descriptor = phase_at(event.scheduled_time_us, self.config)
        self._current_descriptor = descriptor
        self._refresh_session_state(event.scheduled_time_us)
        record = GardenInputSignalRecord(
            garden_id=self.config.garden_id,
            session_id=self.session_id,
            signal_index=signal_index,
            signal_time_us=event.scheduled_time_us,
            s=self._current_s,
            phase=descriptor.phase.value,
            bundle_index=descriptor.bundle_index,
            window_role=descriptor.window_role.value,
            n_current=self._n_current,
            n_available=self._n_current is not None,
            n_baseline_session=self._n_baseline_session,
            baseline_available=self._baseline_available,
            latest_valid_evaluation_id=self._latest_valid_evaluation_id,
            valid_evaluation_revision=self._valid_evaluation_revision,
            session_status=self._session_status.value,
            schema_version=self.config.signal_schema_version,
        )
        self._signal_records.append(record)
        engine.schedule_at(
            event.scheduled_time_us,
            GARDEN_INPUT_SIGNAL_EVENT_TYPE,
            source=GARDEN_INPUT_EVENT_SOURCE,
            priority=GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
            payload=record.to_dict(),
        )

    def handle_simulation_complete(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Close the diagnostic session after all same-time raw inputs."""

        if event.event_type != SIMULATION_COMPLETE_EVENT_TYPE:
            raise ValueError("completion handler received the wrong event type")
        if event.priority != SIMULATION_COMPLETE_EVENT_PRIORITY:
            raise ValueError("completion event priority does not match the boundary constant")
        self._session_status = GardenSessionStatus.COMPLETED
        self._current_s = 0

    def snapshot(self) -> GardenInputSnapshot:
        """Return a frozen view without exposing mutable history or window buffers."""

        return GardenInputSnapshot(
            garden_id=self.config.garden_id,
            model_version=self.config.model_version,
            session_id=self.session_id,
            session_status=self._session_status.value,
            current_phase=self._current_descriptor.phase.value,
            current_s=self._current_s,
            current_bundle_index=self._current_descriptor.bundle_index,
            current_window_role=self._current_descriptor.window_role.value,
            received_rri_count=len(self._rri_records),
            valid_rri_count=self._valid_rri_count,
            artifact_rri_count=self._artifact_rri_count,
            recent_valid_history_count=len(self._recent_valid_rri_us),
            n_baseline_session=self._n_baseline_session,
            n_current=self._n_current,
            baseline_available=self._baseline_available,
            latest_rmssd_ms=self._latest_rmssd_ms,
            latest_evaluation_quality=self._latest_evaluation_quality,
            latest_evaluation_id=self._latest_evaluation_id,
            valid_evaluation_revision=self._valid_evaluation_revision,
            signal_count=len(self._signal_records),
            evaluation_count=len(self._evaluation_records),
        )

    def rri_records(self) -> tuple[GardenRriRecord, ...]:
        return tuple(self._rri_records)

    def evaluation_records(self) -> tuple[GardenEvaluationRecord, ...]:
        return tuple(self._evaluation_records)

    def signal_records(self) -> tuple[GardenInputSignalRecord, ...]:
        return tuple(self._signal_records)

    def artifact_digest(self) -> str:
        records = [
            {
                "input_measurement_index": record.input_measurement_index,
                "event_time_us": record.event_time_us,
                "raw_rri_us": record.raw_rri_us,
                "phase": record.phase,
                "bundle_index": record.bundle_index,
                "window_role": record.window_role,
                "artifact": record.artifact,
                "artifact_reason": record.artifact_reason,
                "median_rri_us_before": record.median_rri_us_before,
                "accepted_into_valid_history": record.accepted_into_valid_history,
                "included_in_evaluation_window": record.included_in_evaluation_window,
            }
            for record in self._rri_records
        ]
        return self._canonical_digest(records)

    def evaluation_digest(self) -> str:
        records = [
            {
                "evaluation_id": record.evaluation_id,
                "evaluation_kind": record.evaluation_kind,
                "bundle_index": record.bundle_index,
                "window_start_us": record.window_start_us,
                "window_end_us": record.window_end_us,
                "total_rri_count": record.total_rri_count,
                "artifact_rri_count": record.artifact_rri_count,
                "valid_rri_count": record.valid_rri_count,
                "artifact_rate": record.artifact_rate,
                "rmssd_ms": record.rmssd_ms,
                "n": record.n,
                "quality": record.quality,
                "is_valid": record.is_valid,
                "reject_reasons": record.reject_reasons,
                "n_revision": record.n_revision,
            }
            for record in self._evaluation_records
        ]
        return self._canonical_digest(records)

    def signal_digest(self) -> str:
        records = [
            {
                "signal_index": record.signal_index,
                "signal_time_us": record.signal_time_us,
                "s": record.s,
                "phase": record.phase,
                "bundle_index": record.bundle_index,
                "window_role": record.window_role,
                "n_current": record.n_current,
                "n_baseline_session": record.n_baseline_session,
                "valid_evaluation_revision": record.valid_evaluation_revision,
                "session_status": record.session_status,
            }
            for record in self._signal_records
        ]
        return self._canonical_digest(records)

    def _finalize_window(self, window: GardenEvaluationWindow) -> GardenEvaluationRecord:
        records = tuple(self._evaluation_buffers[window.evaluation_id])
        valid_records = tuple(record for record in records if not record.artifact)
        artifact_count = len(records) - len(valid_records)
        artifact_rate = 1.0 if not records else artifact_count / len(records)
        rmssd_ms = calculate_rmssd_ms(
            [
                record.raw_rri_us
                for record in sorted(valid_records, key=lambda item: item.event_time_us)
            ]
        )
        reject_reasons: list[str] = []
        if not records:
            reject_reasons.append("no_rri")
        if artifact_rate > self.config.reject_artifact_rate:
            reject_reasons.append("artifact_rate_exceeded")
        if len(valid_records) < self.config.minimum_valid_rri_count:
            reject_reasons.append("insufficient_valid_rri")
        if window.evaluation_kind is GardenEvaluationKind.BUNDLE and not self._baseline_available:
            reject_reasons.append("skipped_baseline_invalid")

        if reject_reasons:
            quality = GardenEvaluationQuality.REJECTED
        elif artifact_rate > self.config.low_confidence_artifact_rate:
            quality = GardenEvaluationQuality.LOW_CONFIDENCE
        else:
            quality = GardenEvaluationQuality.VALID
        is_valid = quality in {
            GardenEvaluationQuality.VALID,
            GardenEvaluationQuality.LOW_CONFIDENCE,
        }
        n = (
            normalize_rmssd_to_n(
                rmssd_ms,
                self.config.rmssd_min_ms,
                self.config.rmssd_max_ms,
            )
            if is_valid and rmssd_ms is not None
            else None
        )

        if window.evaluation_kind is GardenEvaluationKind.BASELINE:
            self._baseline_finalized = True
            if is_valid:
                if n is None:  # pragma: no cover - valid count guarantees RMSSD
                    raise RuntimeError("valid baseline evaluation must produce N")
                self._n_baseline_session = n
                self._n_current = n
                self._baseline_available = True
                self._baseline_id = window.evaluation_id
                self._valid_evaluation_revision += 1
                self._latest_valid_evaluation_id = window.evaluation_id
        elif is_valid:
            if n is None:  # pragma: no cover - valid count guarantees RMSSD
                raise RuntimeError("valid bundle evaluation must produce N")
            self._n_current = n
            self._valid_evaluation_revision += 1
            self._latest_valid_evaluation_id = window.evaluation_id

        baseline_id = (
            window.evaluation_id
            if window.evaluation_kind is GardenEvaluationKind.BASELINE
            else self._baseline_id
        )
        return GardenEvaluationRecord(
            evaluation_id=window.evaluation_id,
            evaluation_kind=window.evaluation_kind.value,
            bundle_index=window.bundle_index,
            window_start_us=window.window_start_us,
            window_end_us=window.window_end_us,
            total_rri_count=len(records),
            artifact_rri_count=artifact_count,
            valid_rri_count=len(valid_records),
            artifact_rate=artifact_rate,
            rmssd_ms=rmssd_ms,
            n=n,
            quality=quality.value,
            is_valid=is_valid,
            reject_reasons=tuple(reject_reasons),
            n_revision=self._valid_evaluation_revision,
            baseline_id=baseline_id,
            schema_version=self.config.evaluation_schema_version,
        )

    def _refresh_session_state(self, time_us: int) -> None:
        descriptor = phase_at(time_us, self.config)
        self._current_descriptor = descriptor
        if descriptor.phase.value == "outside":
            self._session_status = GardenSessionStatus.COMPLETED
            self._current_s = 0
        elif descriptor.nominal_s == 0:
            self._session_status = GardenSessionStatus.BASELINE
            self._current_s = 0
        elif self._baseline_available:
            self._session_status = GardenSessionStatus.ACTIVE
            self._current_s = 1
        elif self._baseline_finalized:
            self._session_status = GardenSessionStatus.BASELINE_INVALID
            self._current_s = 0
        else:
            self._session_status = GardenSessionStatus.BASELINE
            self._current_s = 0

    def _validated_rri_payload(self, event: SimulationEvent) -> dict[str, object]:
        if event.event_type != RRI_MEASUREMENT_EVENT_TYPE:
            raise ValueError("GardenInputComponent only accepts rri_measurement events")
        if event.source != POLAR_H10_EVENT_SOURCE:
            raise ValueError("RRI event source must be polar_h10")
        if event.priority != RRI_MEASUREMENT_EVENT_PRIORITY:
            raise ValueError("RRI event priority does not match the boundary constant")
        if not isinstance(event.payload, dict) or set(event.payload) != _RRI_PAYLOAD_FIELDS:
            raise ValueError("RRI payload fields do not match rri_measurement_event_v1")
        values = dict(event.payload)
        for name in ("device_id", "user_id"):
            value = values[name]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if values["event_schema_version"] != RRI_INPUT_SCHEMA_VERSION:
            raise ValueError(f"event_schema_version must be {RRI_INPUT_SCHEMA_VERSION}")
        for name in (
            "measurement_index",
            "previous_beat_index",
            "current_beat_index",
            "previous_heartbeat_time_us",
            "current_heartbeat_time_us",
            "rri_us",
        ):
            value = values[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if values["rri_us"] <= 0:
            raise ValueError("rri_us must be positive")
        if values["current_beat_index"] <= values["previous_beat_index"]:
            raise ValueError("current_beat_index must exceed previous_beat_index")
        if values["current_heartbeat_time_us"] <= values["previous_heartbeat_time_us"]:
            raise ValueError("heartbeat times must be strictly increasing")
        if values["rri_us"] != (
            values["current_heartbeat_time_us"] - values["previous_heartbeat_time_us"]
        ):
            raise ValueError("rri_us must equal the heartbeat timestamp difference")
        if event.scheduled_time_us != values["current_heartbeat_time_us"]:
            raise ValueError("RRI event time must equal current_heartbeat_time_us")
        rri_ms = values["rri_ms"]
        if isinstance(rri_ms, bool) or not isinstance(rri_ms, (int, float)):
            raise TypeError("rri_ms must be a number")
        if not math.isfinite(float(rri_ms)) or float(rri_ms) != values["rri_us"] / 1_000.0:
            raise ValueError("rri_ms must equal rri_us / 1000")
        return values

    @staticmethod
    def _canonical_digest(records: list[dict[str, object]]) -> str:
        canonical = json.dumps(
            records,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
