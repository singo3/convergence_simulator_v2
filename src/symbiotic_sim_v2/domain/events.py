"""Immutable simulation event values and JSON payload helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Never

type JsonPrimitive = None | bool | int | float | str
type JsonValue = JsonPrimitive | tuple["JsonValue", ...] | "FrozenJsonDict"


class FrozenJsonDict(dict[str, JsonValue]):
    """A ``dict`` compatible with ``json`` that rejects every mutation."""

    def _immutable(self, *_args: object, **_kwargs: object) -> Never:
        raise TypeError("event payload is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _freeze_json(value: Any) -> JsonValue:
    if isinstance(value, dict):
        return FrozenJsonDict({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def thaw_json(value: JsonValue) -> Any:
    """Return ordinary JSON containers for serialization and display."""

    if isinstance(value, dict):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def normalize_json_payload(value: Any) -> JsonValue:
    """Validate, detach, and freeze a JSON-serializable payload value."""

    try:
        canonical = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be a finite JSON-serializable value") from exc
    return _freeze_json(json.loads(canonical))


def _require_int(name: str, value: object, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    """An immutable event ordered by time, priority, and registration sequence."""

    event_id: str
    event_type: str
    source: str
    scheduled_time_us: int
    priority: int
    sequence: int
    payload: JsonValue = field(default_factory=FrozenJsonDict)

    def __post_init__(self) -> None:
        for name in ("event_id", "event_type", "source"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        _require_int("scheduled_time_us", self.scheduled_time_us, minimum=0)
        _require_int("priority", self.priority)
        _require_int("sequence", self.sequence, minimum=0)
        object.__setattr__(self, "payload", normalize_json_payload(self.payload))

    @property
    def ordering_key(self) -> tuple[int, int, int]:
        """Return the complete deterministic queue ordering key."""

        return (self.scheduled_time_us, self.priority, self.sequence)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable event record."""

        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "scheduled_time_us": self.scheduled_time_us,
            "priority": self.priority,
            "sequence": self.sequence,
            "payload": thaw_json(self.payload),
        }
