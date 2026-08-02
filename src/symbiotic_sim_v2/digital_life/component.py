"""GUI-independent Stage 5A single-Digital-Life first-round component."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from symbiotic_sim_v2.digital_life.config import (
    DIGITAL_LIFE_MODEL_VERSION,
    DigitalLifeConfig,
)
from symbiotic_sim_v2.digital_life.intrinsic import IntrinsicProfile, derive_intrinsic_profile
from symbiotic_sim_v2.digital_life.math import (
    calculate_nd,
    calculate_p,
    calculate_tau,
    calculate_v,
    evaluate_w,
    intrinsic_b_mapping,
)
from symbiotic_sim_v2.digital_life.records import (
    DigitalLifeEvaluationUpdateRecord,
    DigitalLifeFirstRoundRecord,
    DigitalLifeSnapshot,
)
from symbiotic_sim_v2.digital_life.state import DigitalLifeState
from symbiotic_sim_v2.domain.event_priorities import (
    GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY,
    GARDEN_INPUT_SIGNAL_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import GARDEN_INPUT_EVENT_SOURCE
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.simulation.engine import SimulationEngine

GARDEN_INPUT_SIGNAL_SCHEMA_VERSION = "garden_input_signal_event_v1"
GARDEN_EVALUATION_SCHEMA_VERSION = "garden_evaluation_finalized_event_v1"
G_STATUS_NOT_CONNECTED = "not_connected"

_KNOWN_PHASES = {
    "baseline_discard",
    "baseline_evaluation",
    "bundle_0_discard",
    "bundle_0_evaluation",
    "bundle_1_discard",
    "bundle_1_evaluation",
    "bundle_2_discard",
    "bundle_2_evaluation",
    "outside",
}
_KNOWN_WINDOW_ROLES = {"discard", "evaluation", "outside"}
_KNOWN_SESSION_STATUSES = {"baseline", "active", "baseline_invalid", "completed"}
_KNOWN_EVALUATION_KINDS = {"baseline", "bundle"}
_KNOWN_EVALUATION_QUALITIES = {"valid", "low_confidence", "rejected"}

_SIGNAL_REQUIRED_FIELDS = {
    "signal_index",
    "signal_time_us",
    "s",
    "phase",
    "bundle_index",
    "window_role",
    "n_current",
    "n_available",
    "n_baseline_session",
    "baseline_available",
    "latest_valid_evaluation_id",
    "valid_evaluation_revision",
    "session_status",
    "schema_version",
}
_EVALUATION_REQUIRED_FIELDS = {
    "evaluation_id",
    "evaluation_kind",
    "bundle_index",
    "quality",
    "is_valid",
    "n",
    "n_revision",
    "baseline_id",
    "schema_version",
}


@dataclass(frozen=True, slots=True)
class GardenInputSignalInput:
    signal_index: int
    signal_time_us: int
    s: int
    phase: str
    bundle_index: int | None
    window_role: str
    n_current: float | None
    n_available: bool
    n_baseline_session: float | None
    baseline_available: bool
    latest_valid_evaluation_id: str | None
    valid_evaluation_revision: int
    session_status: str


@dataclass(frozen=True, slots=True)
class GardenEvaluationMetadata:
    evaluation_id: str
    evaluation_kind: str
    bundle_index: int | None
    event_time_us: int
    quality: str
    is_valid: bool
    n: float | None
    n_revision: int
    baseline_id: str | None


def _finite_unit_or_none(name: str, value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number or null")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _optional_bundle_index(value: object) -> int | None:
    if value is None:
        return None
    bundle_index = _non_negative_int("bundle_index", value)
    if bundle_index > 2:
        raise ValueError("bundle_index must be null or between 0 and 2")
    return bundle_index


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_string(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _required_string(name, value)


def parse_garden_input_signal_event(event: SimulationEvent) -> GardenInputSignalInput:
    """Validate and project only the formal Stage 5A signal input fields."""

    if event.event_type != GARDEN_INPUT_SIGNAL_EVENT_TYPE:
        raise ValueError("signal handler received the wrong event type")
    if event.source != GARDEN_INPUT_EVENT_SOURCE:
        raise ValueError("signal source must be garden_input")
    if event.priority != GARDEN_INPUT_SIGNAL_EVENT_PRIORITY:
        raise ValueError("signal priority does not match the formal boundary")
    if not isinstance(event.payload, dict):
        raise ValueError("signal payload must be an object")
    if missing := _SIGNAL_REQUIRED_FIELDS - set(event.payload):
        raise ValueError(f"signal payload is missing fields: {', '.join(sorted(missing))}")
    values = event.payload
    if values["schema_version"] != GARDEN_INPUT_SIGNAL_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {GARDEN_INPUT_SIGNAL_SCHEMA_VERSION}"
        )

    signal_index = _non_negative_int("signal_index", values["signal_index"])
    signal_time_us = _non_negative_int("signal_time_us", values["signal_time_us"])
    if signal_time_us != event.scheduled_time_us:
        raise ValueError("signal_time_us must equal the event scheduled time")
    s = values["s"]
    if isinstance(s, bool) or not isinstance(s, int):
        raise TypeError("s must be an integer")
    if s not in (0, 1):
        raise ValueError("s must be 0 or 1")
    phase = _required_string("phase", values["phase"])
    if phase not in _KNOWN_PHASES:
        raise ValueError("phase is not part of the formal Garden vocabulary")
    window_role = _required_string("window_role", values["window_role"])
    if window_role not in _KNOWN_WINDOW_ROLES:
        raise ValueError("window_role is not part of the formal Garden vocabulary")
    session_status = _required_string("session_status", values["session_status"])
    if session_status not in _KNOWN_SESSION_STATUSES:
        raise ValueError("session_status is not part of the formal Garden vocabulary")
    bundle_index = _optional_bundle_index(values["bundle_index"])

    n_available = values["n_available"]
    if not isinstance(n_available, bool):
        raise TypeError("n_available must be boolean")
    n_current = _finite_unit_or_none("n_current", values["n_current"])
    if n_available != (n_current is not None):
        raise ValueError("n_available and n_current are inconsistent")
    baseline_available = values["baseline_available"]
    if not isinstance(baseline_available, bool):
        raise TypeError("baseline_available must be boolean")
    n_baseline_session = _finite_unit_or_none(
        "n_baseline_session", values["n_baseline_session"]
    )
    if baseline_available != (n_baseline_session is not None):
        raise ValueError("baseline_available and n_baseline_session are inconsistent")
    if baseline_available and not n_available:
        raise ValueError("baseline availability requires current N availability")
    revision = _non_negative_int(
        "valid_evaluation_revision", values["valid_evaluation_revision"]
    )
    latest_valid_evaluation_id = _optional_string(
        "latest_valid_evaluation_id", values["latest_valid_evaluation_id"]
    )
    if revision == 0 and latest_valid_evaluation_id is not None:
        raise ValueError("revision zero cannot identify a valid evaluation")
    if revision > 0 and latest_valid_evaluation_id is None:
        raise ValueError("a positive revision requires latest_valid_evaluation_id")
    return GardenInputSignalInput(
        signal_index=signal_index,
        signal_time_us=signal_time_us,
        s=s,
        phase=phase,
        bundle_index=bundle_index,
        window_role=window_role,
        n_current=n_current,
        n_available=n_available,
        n_baseline_session=n_baseline_session,
        baseline_available=baseline_available,
        latest_valid_evaluation_id=latest_valid_evaluation_id,
        valid_evaluation_revision=revision,
        session_status=session_status,
    )


def parse_garden_evaluation_finalized_event(
    event: SimulationEvent,
) -> GardenEvaluationMetadata:
    """Validate and project only allowed evaluation metadata, ignoring diagnostics."""

    if event.event_type != GARDEN_EVALUATION_FINALIZED_EVENT_TYPE:
        raise ValueError("evaluation handler received the wrong event type")
    if event.source != GARDEN_INPUT_EVENT_SOURCE:
        raise ValueError("evaluation source must be garden_input")
    if event.priority != GARDEN_EVALUATION_FINALIZED_EVENT_PRIORITY:
        raise ValueError("evaluation priority does not match the formal boundary")
    if not isinstance(event.payload, dict):
        raise ValueError("evaluation payload must be an object")
    if missing := _EVALUATION_REQUIRED_FIELDS - set(event.payload):
        raise ValueError(f"evaluation payload is missing fields: {', '.join(sorted(missing))}")
    values = event.payload
    if values["schema_version"] != GARDEN_EVALUATION_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {GARDEN_EVALUATION_SCHEMA_VERSION}"
        )
    evaluation_id = _required_string("evaluation_id", values["evaluation_id"])
    evaluation_kind = _required_string("evaluation_kind", values["evaluation_kind"])
    if evaluation_kind not in _KNOWN_EVALUATION_KINDS:
        raise ValueError("evaluation_kind must be baseline or bundle")
    bundle_index = _optional_bundle_index(values["bundle_index"])
    if evaluation_kind == "baseline" and bundle_index is not None:
        raise ValueError("baseline evaluation cannot have a bundle_index")
    if evaluation_kind == "bundle" and bundle_index is None:
        raise ValueError("bundle evaluation requires a bundle_index")
    quality = _required_string("quality", values["quality"])
    if quality not in _KNOWN_EVALUATION_QUALITIES:
        raise ValueError("quality is not part of the formal evaluation vocabulary")
    is_valid = values["is_valid"]
    if not isinstance(is_valid, bool):
        raise TypeError("is_valid must be boolean")
    if is_valid != (quality != "rejected"):
        raise ValueError("quality and is_valid are inconsistent")
    n = _finite_unit_or_none("n", values["n"])
    if is_valid and n is None:
        raise ValueError("valid evaluation requires N")
    revision = _non_negative_int("n_revision", values["n_revision"])
    if is_valid and revision == 0:
        raise ValueError("valid evaluation requires a positive revision")
    baseline_id = _optional_string("baseline_id", values["baseline_id"])
    return GardenEvaluationMetadata(
        evaluation_id=evaluation_id,
        evaluation_kind=evaluation_kind,
        bundle_index=bundle_index,
        event_time_us=event.scheduled_time_us,
        quality=quality,
        is_valid=is_valid,
        n=n,
        n_revision=revision,
        baseline_id=baseline_id,
    )


class SingleDigitalLifeComponent:
    """Consume only formal Garden N/S events and record one deterministic first round."""

    def __init__(self, config: DigitalLifeConfig) -> None:
        if not isinstance(config, DigitalLifeConfig):
            raise TypeError("config must be a DigitalLifeConfig")
        self.config = config
        self.intrinsic_profile: IntrinsicProfile = derive_intrinsic_profile(config)
        self.reset()

    def reset(self) -> None:
        """Restore exact Stage 5A initial state and clear all diagnostics."""

        k_anchor = self.config.initial_k_anchor
        self._state = DigitalLifeState(
            e=self.config.initial_e,
            q=self.config.initial_q,
            k_anchor=k_anchor,
            k_current=k_anchor,
            n_baseline_session=None,
            n_current=None,
            nd=0.5,
            w=0.5,
            p=1.0,
            v=None,
            b=self.intrinsic_profile.initial_b,
            tau=None,
            g_status=G_STATUS_NOT_CONNECTED,
            last_processed_signal_index=None,
            last_processed_evaluation_revision=0,
            baseline_initialized=False,
            new_valid_evaluation_count=0,
            second_round_connected=False,
            touch_dispatched_count=0,
        )
        self._first_round_records: list[DigitalLifeFirstRoundRecord] = []
        self._evaluation_update_records: list[DigitalLifeEvaluationUpdateRecord] = []
        self._pending_valid_evaluations: dict[int, GardenEvaluationMetadata] = {}
        self._seen_evaluation_ids: set[str] = set()
        self._last_evaluation_event_time_us: int | None = None
        self._last_signal_time_us: int | None = None
        self._last_seen_signal_revision = 0
        self._latest_applied_evaluation: GardenEvaluationMetadata | None = None
        self._latest_evaluation_id: str | None = None

    def handle_evaluation_finalized(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Cache valid metadata; record rejected evaluation without changing state."""

        metadata = parse_garden_evaluation_finalized_event(event)
        if metadata.evaluation_id in self._seen_evaluation_ids:
            raise ValueError("duplicate evaluation_id")
        if (
            self._last_evaluation_event_time_us is not None
            and metadata.event_time_us < self._last_evaluation_event_time_us
        ):
            raise ValueError("evaluation event time moved backwards")
        if metadata.is_valid:
            if metadata.n_revision <= self._state.last_processed_evaluation_revision:
                raise ValueError("valid evaluation revision was already processed")
            if metadata.n_revision in self._pending_valid_evaluations:
                raise ValueError("duplicate pending valid evaluation revision")
        rejected_record = None
        if not metadata.is_valid:
            rejected_record = DigitalLifeEvaluationUpdateRecord(
                evaluation_id=metadata.evaluation_id,
                evaluation_kind=metadata.evaluation_kind,
                bundle_index=metadata.bundle_index,
                event_time_us=metadata.event_time_us,
                quality=metadata.quality,
                is_valid=False,
                n_revision=metadata.n_revision,
                n=metadata.n,
                n_baseline_session=self._state.n_baseline_session,
                previous_nd=self._state.nd,
                new_nd=self._state.nd,
                previous_w=self._state.w,
                new_w=self._state.w,
                applied=False,
                skip_reason="evaluation_rejected",
            )

        self._seen_evaluation_ids.add(metadata.evaluation_id)
        self._last_evaluation_event_time_us = metadata.event_time_us
        self._latest_evaluation_id = metadata.evaluation_id
        if metadata.is_valid:
            self._pending_valid_evaluations[metadata.n_revision] = metadata
        else:
            assert rejected_record is not None
            self._evaluation_update_records.append(rejected_record)

    def handle_garden_input_signal(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Apply a new valid revision first, then calculate all per-signal activities."""

        signal = parse_garden_input_signal_event(event)
        previous_index = self._state.last_processed_signal_index
        if previous_index is not None and signal.signal_index <= previous_index:
            raise ValueError("signal_index must be strictly increasing")
        if (
            self._last_signal_time_us is not None
            and signal.signal_time_us <= self._last_signal_time_us
        ):
            raise ValueError("signal time must be strictly increasing")
        if signal.valid_evaluation_revision < self._last_seen_signal_revision:
            raise ValueError("valid evaluation revision moved backwards")

        is_new_evaluation = (
            signal.valid_evaluation_revision
            > self._state.last_processed_evaluation_revision
        )
        metadata = self._latest_applied_evaluation
        previous_nd = self._state.nd
        previous_w = self._state.w
        next_n = self._state.n_current
        next_baseline = self._state.n_baseline_session
        next_nd = self._state.nd
        next_w = self._state.w
        next_revision = self._state.last_processed_evaluation_revision
        next_baseline_initialized = self._state.baseline_initialized
        next_evaluation_count = self._state.new_valid_evaluation_count
        update_record: DigitalLifeEvaluationUpdateRecord | None = None

        if is_new_evaluation:
            try:
                metadata = self._pending_valid_evaluations[signal.valid_evaluation_revision]
            except KeyError as exc:
                raise ValueError(
                    "signal revision has no pending valid evaluation metadata"
                ) from exc
            if signal.latest_valid_evaluation_id != metadata.evaluation_id:
                raise ValueError("signal latest evaluation does not match pending metadata")
            if not signal.n_available or signal.n_current is None:
                raise ValueError("new valid evaluation requires current N")
            if metadata.n != signal.n_current:
                raise ValueError("signal N does not match pending evaluation metadata")
            if not signal.baseline_available or signal.n_baseline_session is None:
                raise ValueError("new valid evaluation requires session baseline N")
            if not self._state.baseline_initialized:
                if signal.valid_evaluation_revision != 1:
                    raise ValueError("the first valid evaluation revision must be 1")
                if metadata.evaluation_kind != "baseline":
                    raise ValueError("the first valid evaluation must be baseline")
                if signal.n_baseline_session != signal.n_current:
                    raise ValueError("baseline evaluation must initialize N from itself")
                next_baseline = signal.n_baseline_session
                next_n = signal.n_current
                next_nd = 0.5
                next_w = 0.5
                next_baseline_initialized = True
            else:
                if metadata.evaluation_kind != "bundle":
                    raise ValueError("post-baseline valid evaluation must be a bundle")
                if signal.n_baseline_session != self._state.n_baseline_session:
                    raise ValueError("session baseline N changed after initialization")
                next_n = signal.n_current
                next_nd = calculate_nd(
                    signal.n_current,
                    signal.n_baseline_session,
                    self.config.delta_n,
                )
                next_w = evaluate_w(next_nd)
            next_revision = signal.valid_evaluation_revision
            next_evaluation_count += 1
            update_record = DigitalLifeEvaluationUpdateRecord(
                evaluation_id=metadata.evaluation_id,
                evaluation_kind=metadata.evaluation_kind,
                bundle_index=metadata.bundle_index,
                event_time_us=metadata.event_time_us,
                quality=metadata.quality,
                is_valid=True,
                n_revision=metadata.n_revision,
                n=metadata.n,
                n_baseline_session=next_baseline,
                previous_nd=previous_nd,
                new_nd=next_nd,
                previous_w=previous_w,
                new_w=next_w,
                applied=True,
                skip_reason=None,
            )
        else:
            if signal.valid_evaluation_revision != self._state.last_processed_evaluation_revision:
                raise ValueError("signal revision is inconsistent with component state")
            if signal.n_current != self._state.n_current:
                raise ValueError("N changed without a new valid evaluation revision")
            if signal.n_baseline_session != self._state.n_baseline_session:
                raise ValueError("baseline N changed without a new valid evaluation revision")
            expected_id = (
                None
                if self._latest_applied_evaluation is None
                else self._latest_applied_evaluation.evaluation_id
            )
            if signal.latest_valid_evaluation_id != expected_id:
                raise ValueError("latest valid evaluation ID changed without a new revision")

        next_p = calculate_p(signal.s, self.intrinsic_profile.p_intrinsic)
        next_v = calculate_v(next_n, self._state.q, self._state.e)
        next_b = intrinsic_b_mapping(
            self._state.k_current,
            f_min=self.config.f_min,
            f_max=self.config.f_max,
            a_fixed=self.config.a_fixed,
            t_min=self.config.t_min,
            t_max=self.config.t_max,
            d_fixed=self.config.d_fixed,
        )
        next_tau = calculate_tau(
            signal.s,
            next_p,
            next_v,
            self.config.epsilon_tau,
            self.intrinsic_profile.birth_phase,
        )
        record = DigitalLifeFirstRoundRecord(
            signal_index=signal.signal_index,
            signal_time_us=signal.signal_time_us,
            digital_life_id=self.config.digital_life_id,
            role=self.config.role,
            phase=signal.phase,
            bundle_index=signal.bundle_index,
            window_role=signal.window_role,
            session_status=signal.session_status,
            s=signal.s,
            n_current=next_n,
            n_available=next_n is not None,
            n_baseline_session=next_baseline,
            baseline_available=next_baseline is not None,
            valid_evaluation_revision=signal.valid_evaluation_revision,
            is_new_valid_evaluation=is_new_evaluation,
            source_evaluation_id=None if metadata is None else metadata.evaluation_id,
            source_evaluation_kind=None if metadata is None else metadata.evaluation_kind,
            source_evaluation_quality=None if metadata is None else metadata.quality,
            nd=next_nd,
            w=next_w,
            p=next_p,
            p_intrinsic=self.intrinsic_profile.p_intrinsic,
            e=self._state.e,
            q=self._state.q,
            v=next_v,
            k_anchor=self._state.k_anchor,
            k_current=self._state.k_current,
            b_f=next_b[0],
            b_a=next_b[1],
            b_t=next_b[2],
            b_d=next_b[3],
            tau=next_tau,
            birth_phase=self.intrinsic_profile.birth_phase,
            touch_enabled=signal.s == 1 and next_tau is not None,
            touch_dispatched=False,
            second_round_connected=False,
            g_status=G_STATUS_NOT_CONNECTED,
        )

        self._state.n_current = next_n
        self._state.n_baseline_session = next_baseline
        self._state.nd = next_nd
        self._state.w = next_w
        self._state.p = next_p
        self._state.v = next_v
        self._state.b = next_b
        self._state.tau = next_tau
        self._state.last_processed_signal_index = signal.signal_index
        self._state.last_processed_evaluation_revision = next_revision
        self._state.baseline_initialized = next_baseline_initialized
        self._state.new_valid_evaluation_count = next_evaluation_count
        self._last_signal_time_us = signal.signal_time_us
        self._last_seen_signal_revision = signal.valid_evaluation_revision
        if is_new_evaluation:
            assert metadata is not None
            self._latest_applied_evaluation = metadata
            del self._pending_valid_evaluations[metadata.n_revision]
            assert update_record is not None
            self._evaluation_update_records.append(update_record)
        self._first_round_records.append(record)

    def snapshot(self) -> DigitalLifeSnapshot:
        """Return an immutable view without exposing pending metadata or mutable state."""

        latest_s = None if not self._first_round_records else self._first_round_records[-1].s
        return DigitalLifeSnapshot(
            digital_life_id=self.config.digital_life_id,
            role=self.config.role,
            model_version=DIGITAL_LIFE_MODEL_VERSION,
            n_current=self._state.n_current,
            n_baseline_session=self._state.n_baseline_session,
            baseline_initialized=self._state.baseline_initialized,
            nd=self._state.nd,
            w=self._state.w,
            p=self._state.p,
            p_intrinsic=self.intrinsic_profile.p_intrinsic,
            e=self._state.e,
            q=self._state.q,
            v=self._state.v,
            k_anchor=self._state.k_anchor,
            k_current=self._state.k_current,
            b=self._state.b,
            tau=self._state.tau,
            birth_phase=self.intrinsic_profile.birth_phase,
            last_signal_index=self._state.last_processed_signal_index,
            last_revision=self._state.last_processed_evaluation_revision,
            latest_s=latest_s,
            latest_evaluation_id=self._latest_evaluation_id,
            first_round_count=len(self._first_round_records),
            evaluation_update_count=len(self._evaluation_update_records),
            new_valid_evaluation_count=self._state.new_valid_evaluation_count,
            g_status=self._state.g_status,
            second_round_connected=self._state.second_round_connected,
            touch_dispatched_count=self._state.touch_dispatched_count,
        )

    def first_round_records(self) -> tuple[DigitalLifeFirstRoundRecord, ...]:
        return tuple(self._first_round_records)

    def evaluation_update_records(self) -> tuple[DigitalLifeEvaluationUpdateRecord, ...]:
        return tuple(self._evaluation_update_records)

    def first_round_digest(self) -> str:
        records = [
            {
                "signal_index": record.signal_index,
                "signal_time_us": record.signal_time_us,
                "digital_life_id": record.digital_life_id,
                "role": record.role,
                "phase": record.phase,
                "bundle_index": record.bundle_index,
                "s": record.s,
                "n_current": record.n_current,
                "n_baseline_session": record.n_baseline_session,
                "valid_evaluation_revision": record.valid_evaluation_revision,
                "is_new_valid_evaluation": record.is_new_valid_evaluation,
                "nd": record.nd,
                "w": record.w,
                "p": record.p,
                "e": record.e,
                "q": record.q,
                "v": record.v,
                "k_current": record.k_current,
                "b": (record.b_f, record.b_a, record.b_t, record.b_d),
                "tau": record.tau,
                "g_status": record.g_status,
                "touch_dispatched": record.touch_dispatched,
            }
            for record in self._first_round_records
        ]
        return self._canonical_digest(records)

    def evaluation_update_digest(self) -> str:
        records = [
            {
                "evaluation_id": record.evaluation_id,
                "evaluation_kind": record.evaluation_kind,
                "bundle_index": record.bundle_index,
                "event_time_us": record.event_time_us,
                "quality": record.quality,
                "is_valid": record.is_valid,
                "n_revision": record.n_revision,
                "n": record.n,
                "n_baseline_session": record.n_baseline_session,
                "previous_nd": record.previous_nd,
                "new_nd": record.new_nd,
                "previous_w": record.previous_w,
                "new_w": record.new_w,
                "applied": record.applied,
                "skip_reason": record.skip_reason,
            }
            for record in self._evaluation_update_records
        ]
        return self._canonical_digest(records)

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
