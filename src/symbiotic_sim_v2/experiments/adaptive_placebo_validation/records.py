"""Immutable bundle/session and replay records for Stage 8A.3."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from typing import Any

from symbiotic_sim_v2.runtime.multi_session.session_seed import UINT32_MAX

from .config import (
    ARM_IDS,
    BUNDLE_OUTCOME_SCHEMA_VERSION,
    RANDOM_ARM,
    SESSION_OUTCOME_SCHEMA_VERSION,
    YOKED_ARM,
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_text(name: str, value: object | None) -> str | None:
    return None if value is None else _text(name, value)


def _index(name: str, value: object, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0 or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside its allowed range")
    return value


def _number(name: str, value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric or null")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _exact(values: Mapping[str, Any], cls: type[Any], label: str) -> None:
    expected = {field.name for field in fields(cls)}
    actual = set(values)
    if expected != actual:
        raise ValueError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


@dataclass(frozen=True, slots=True)
class ReplayLightState:
    session_index: int
    source_participant_id: str
    source_bundle_index: int | None
    scheduled_time_us: int
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_index", _index("session_index", self.session_index))
        _text("source_participant_id", self.source_participant_id)
        bundle = self.source_bundle_index
        if bundle is not None:
            bundle = _index("source_bundle_index", bundle, 2)
        object.__setattr__(self, "source_bundle_index", bundle)
        object.__setattr__(
            self,
            "scheduled_time_us",
            _index("scheduled_time_us", self.scheduled_time_us),
        )
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        object.__setattr__(self, "payload", dict(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_index": self.session_index,
            "source_participant_id": self.source_participant_id,
            "source_bundle_index": self.source_bundle_index,
            "scheduled_time_us": self.scheduled_time_us,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> ReplayLightState:
        _exact(values, cls, "replay light state")
        return cls(**dict(values))


@dataclass(frozen=True, slots=True)
class BundleOutcome:
    participant_id: str
    user_type_id: str
    response_strength_scale: float
    condition_id: str
    arm: str
    session_index: int
    bundle_index: int
    bundle_role: str
    evaluation_quality: str
    valid_for_analysis: bool
    baseline_rmssd_ms: float | None
    bundle_rmssd_ms: float | None
    delta_rmssd_ms: float | None
    baseline_n: float | None
    bundle_n: float | None
    w: float | None
    w_anchor_session: float | None
    displayed_life_id: str | None
    displayed_hue_degree: float | None
    displayed_blink_bpm: float | None
    displayed_b: tuple[float, float, float, float] | None
    anchor_or_trial: str | None
    adoption_result: str | None
    source_participant_id: str | None
    source_session_index: int | None
    source_bundle_index: int | None
    target_rmssd_used_for_future_output: bool
    physiology_seed: int
    output_seed: int | None
    event_digest: str
    data_digest: str
    schema_version: str = BUNDLE_OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("participant_id", "user_type_id", "condition_id", "bundle_role"):
            _text(name, getattr(self, name))
        if self.arm not in ARM_IDS:
            raise ValueError(f"unknown arm: {self.arm!r}")
        object.__setattr__(self, "session_index", _index("session_index", self.session_index))
        object.__setattr__(self, "bundle_index", _index("bundle_index", self.bundle_index, 2))
        if not isinstance(self.valid_for_analysis, bool):
            raise TypeError("valid_for_analysis must be boolean")
        if not isinstance(self.target_rmssd_used_for_future_output, bool):
            raise TypeError("target_rmssd_used_for_future_output must be boolean")
        if self.target_rmssd_used_for_future_output != (
            self.arm == "autonomous_closed_loop"
        ):
            raise ValueError("future-output RMSSD-use flag differs from the arm contract")
        scale = _number("response_strength_scale", self.response_strength_scale)
        assert scale is not None
        if not 0.0 <= scale <= 1.0:
            raise ValueError("response_strength_scale must be within [0,1]")
        for name in (
            "baseline_rmssd_ms",
            "bundle_rmssd_ms",
            "delta_rmssd_ms",
            "baseline_n",
            "bundle_n",
            "w",
            "w_anchor_session",
            "displayed_hue_degree",
            "displayed_blink_bpm",
        ):
            object.__setattr__(self, name, _number(name, getattr(self, name)))
        if self.delta_rmssd_ms is not None:
            if self.baseline_rmssd_ms is None or self.bundle_rmssd_ms is None:
                raise ValueError("delta_rmssd_ms requires baseline and bundle RMSSD")
            expected_delta = self.bundle_rmssd_ms - self.baseline_rmssd_ms
            if not math.isclose(
                self.delta_rmssd_ms,
                expected_delta,
                abs_tol=1e-12,
                rel_tol=0.0,
            ):
                raise ValueError("delta_rmssd_ms differs from bundle minus baseline")
        if self.valid_for_analysis != (self.delta_rmssd_ms is not None):
            raise ValueError("valid_for_analysis must reflect an available RMSSD delta")
        displayed_b = self.displayed_b
        if displayed_b is not None:
            if len(displayed_b) != 4:
                raise ValueError("displayed_b must have four axes")
            converted = tuple(float(value) for value in displayed_b)
            if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in converted):
                raise ValueError("displayed_b axes must be finite within [0,1]")
            object.__setattr__(self, "displayed_b", converted)
        for name in (
            "displayed_life_id",
            "anchor_or_trial",
            "adoption_result",
            "source_participant_id",
        ):
            object.__setattr__(self, name, _optional_text(name, getattr(self, name)))
        for name, maximum in (
            ("source_session_index", None),
            ("source_bundle_index", 2),
            ("output_seed", UINT32_MAX),
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _index(name, value, maximum))
        object.__setattr__(
            self,
            "physiology_seed",
            _index("physiology_seed", self.physiology_seed, UINT32_MAX),
        )
        for name in ("event_digest", "data_digest"):
            digest = _text(name, getattr(self, name))
            if len(digest) != 64:
                raise ValueError(f"{name} must be a SHA-256 hex digest")
            int(digest, 16)
        if self.arm in (YOKED_ARM, RANDOM_ARM) and self.w_anchor_session is not None:
            raise ValueError("open-loop arms cannot publish a committed W anchor")
        if self.schema_version != BUNDLE_OUTCOME_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {BUNDLE_OUTCOME_SCHEMA_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "displayed_b": self.displayed_b}

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> BundleOutcome:
        _exact(values, cls, "bundle outcome")
        normalized = dict(values)
        if normalized["displayed_b"] is not None:
            normalized["displayed_b"] = tuple(normalized["displayed_b"])
        return cls(**normalized)


@dataclass(frozen=True, slots=True)
class SessionOutcome:
    participant_id: str
    user_type_id: str
    response_strength_scale: float
    condition_id: str
    arm: str
    session_index: int
    physiology_seed: int
    baseline_rmssd_ms: float | None
    bundle_rmssd_ms: tuple[float | None, float | None, float | None]
    bundle_delta_rmssd_ms: tuple[float | None, float | None, float | None]
    mean_valid_bundle_delta_rmssd_ms: float | None
    median_valid_bundle_delta_rmssd_ms: float | None
    holder_id: str | None
    bundle_life_ids: tuple[str | None, str | None, str | None]
    bundle_hue_degrees: tuple[float | None, float | None, float | None]
    bundle_blink_bpms: tuple[float | None, float | None, float | None]
    representative_life_id: str | None
    representative_hue_degree: float | None
    representative_blink_bpm: float | None
    actual_bundle2_evaluation_output: Mapping[str, Any] | None
    final_committed_anchor: tuple[float, float, float, float] | None
    exploration_decision: str | None
    candidate_generated: bool
    adoption_result: str | None
    valid_bundle_count: int
    session_valid: bool
    invalid_reason: str | None
    source_participant_id: str | None
    output_sequence_digest: str
    schema_version: str = SESSION_OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("participant_id", "user_type_id", "condition_id"):
            _text(name, getattr(self, name))
        if self.arm not in ARM_IDS:
            raise ValueError(f"unknown arm: {self.arm!r}")
        object.__setattr__(self, "session_index", _index("session_index", self.session_index))
        object.__setattr__(
            self,
            "physiology_seed",
            _index("physiology_seed", self.physiology_seed, UINT32_MAX),
        )
        object.__setattr__(
            self,
            "baseline_rmssd_ms",
            _number("baseline_rmssd_ms", self.baseline_rmssd_ms),
        )
        for name in (
            "bundle_rmssd_ms",
            "bundle_delta_rmssd_ms",
            "bundle_hue_degrees",
            "bundle_blink_bpms",
        ):
            value = tuple(getattr(self, name))
            if len(value) != 3:
                raise ValueError(f"{name} must contain Bundle 0/1/2 values")
            object.__setattr__(self, name, tuple(_number(name, item) for item in value))
        life_ids = tuple(self.bundle_life_ids)
        if len(life_ids) != 3:
            raise ValueError("bundle_life_ids must contain three values")
        object.__setattr__(
            self,
            "bundle_life_ids",
            tuple(_optional_text("bundle_life_id", item) for item in life_ids),
        )
        for name in (
            "mean_valid_bundle_delta_rmssd_ms",
            "median_valid_bundle_delta_rmssd_ms",
            "representative_hue_degree",
            "representative_blink_bpm",
        ):
            object.__setattr__(self, name, _number(name, getattr(self, name)))
        for name in (
            "holder_id",
            "representative_life_id",
            "exploration_decision",
            "adoption_result",
            "invalid_reason",
            "source_participant_id",
        ):
            object.__setattr__(self, name, _optional_text(name, getattr(self, name)))
        if not isinstance(self.candidate_generated, bool) or not isinstance(
            self.session_valid, bool
        ):
            raise TypeError("candidate_generated and session_valid must be boolean")
        valid_count = _index("valid_bundle_count", self.valid_bundle_count, 3)
        object.__setattr__(self, "valid_bundle_count", valid_count)
        if self.session_valid != (valid_count > 0 and self.invalid_reason is None):
            raise ValueError("session_valid differs from valid bundle count/invalid reason")
        if self.arm in (YOKED_ARM, RANDOM_ARM):
            if self.final_committed_anchor is not None:
                raise ValueError("open-loop arms cannot publish a committed anchor")
            if self.candidate_generated or self.exploration_decision is not None:
                raise ValueError("open-loop arms cannot adapt k/q")
        anchor = self.final_committed_anchor
        if anchor is not None:
            if len(anchor) != 4:
                raise ValueError("final_committed_anchor must contain four values")
            object.__setattr__(self, "final_committed_anchor", tuple(float(v) for v in anchor))
        output = self.actual_bundle2_evaluation_output
        if output is not None and not isinstance(output, Mapping):
            raise TypeError("actual_bundle2_evaluation_output must be a mapping or null")
        object.__setattr__(
            self,
            "actual_bundle2_evaluation_output",
            None if output is None else dict(output),
        )
        if len(self.output_sequence_digest) != 64:
            raise ValueError("output_sequence_digest must be a SHA-256 hex digest")
        int(self.output_sequence_digest, 16)
        if self.schema_version != SESSION_OUTCOME_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SESSION_OUTCOME_SCHEMA_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> SessionOutcome:
        _exact(values, cls, "session outcome")
        normalized = dict(values)
        for name in (
            "bundle_rmssd_ms",
            "bundle_delta_rmssd_ms",
            "bundle_life_ids",
            "bundle_hue_degrees",
            "bundle_blink_bpms",
        ):
            normalized[name] = tuple(normalized[name])
        if normalized["final_committed_anchor"] is not None:
            normalized["final_committed_anchor"] = tuple(
                normalized["final_committed_anchor"]
            )
        return cls(**normalized)


def bundle_outcomes_from_dicts(
    values: Sequence[Mapping[str, Any]],
) -> tuple[BundleOutcome, ...]:
    return tuple(BundleOutcome.from_dict(value) for value in values)


def session_outcomes_from_dicts(
    values: Sequence[Mapping[str, Any]],
) -> tuple[SessionOutcome, ...]:
    return tuple(SessionOutcome.from_dict(value) for value in values)


__all__ = [
    "BundleOutcome",
    "ReplayLightState",
    "SessionOutcome",
    "bundle_outcomes_from_dicts",
    "session_outcomes_from_dicts",
]
