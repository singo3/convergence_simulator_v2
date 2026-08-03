"""Strict single-session persistent-state JSON boundary for Stage 5C."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .persistent_state import RelationMemoryPersistentState


def _expected_ids(values: object) -> tuple[str, str, str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("expected_digital_life_ids must be a three-element sequence")
    normalized = tuple(values)
    if len(normalized) != 3:
        raise ValueError("Stage 5C requires exactly three Digital Life IDs")
    if any(not isinstance(value, str) or not value.strip() for value in normalized):
        raise ValueError("Digital Life IDs must be non-empty strings")
    if len(set(normalized)) != 3:
        raise ValueError("Digital Life IDs must be unique")
    return normalized  # type: ignore[return-value]


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate relation-state field: {key}")
        result[key] = value
    return result


def relation_memory_state_map_from_dict(
    values: Mapping[str, Any],
    *,
    expected_digital_life_ids: Sequence[str],
) -> Mapping[str, RelationMemoryPersistentState]:
    """Validate an exact three-life mapping without silent defaults or clipping."""

    if not isinstance(values, Mapping):
        raise TypeError("relation state values must be a mapping")
    life_ids = _expected_ids(expected_digital_life_ids)
    actual_ids = set(values)
    expected_id_set = set(life_ids)
    if missing := expected_id_set - actual_ids:
        raise ValueError(f"missing relation state IDs: {', '.join(sorted(missing))}")
    if unknown := actual_ids - expected_id_set:
        raise ValueError(f"unknown relation state IDs: {', '.join(sorted(unknown))}")
    states = {
        life_id: RelationMemoryPersistentState.from_dict(
            values[life_id],
            expected_digital_life_id=life_id,
        )
        for life_id in life_ids
    }
    return MappingProxyType(states)


def relation_memory_state_map_from_json(
    encoded: str,
    *,
    expected_digital_life_ids: Sequence[str],
) -> Mapping[str, RelationMemoryPersistentState]:
    """Parse canonical-compatible JSON while rejecting duplicate object keys."""

    if not isinstance(encoded, str):
        raise TypeError("encoded relation state must be a string")
    values = json.loads(encoded, object_pairs_hook=_strict_object_pairs)
    if not isinstance(values, dict):
        raise ValueError("relation state JSON must contain an object")
    return relation_memory_state_map_from_dict(
        values,
        expected_digital_life_ids=expected_digital_life_ids,
    )


def relation_memory_state_map_to_dict(
    states: Mapping[str, RelationMemoryPersistentState],
    *,
    expected_digital_life_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Return an insertion-stable exact-roster state document."""

    life_ids = _expected_ids(expected_digital_life_ids)
    if not isinstance(states, Mapping):
        raise TypeError("relation states must be a mapping")
    if set(states) != set(life_ids):
        raise ValueError("relation state IDs must exactly match the expected roster")
    result: dict[str, dict[str, Any]] = {}
    for life_id in life_ids:
        state = states[life_id]
        if not isinstance(state, RelationMemoryPersistentState):
            raise TypeError("relation states must contain persistent-state values")
        if state.digital_life_id != life_id:
            raise ValueError("persistent state digital_life_id does not match its key")
        result[life_id] = state.to_dict()
    return result


def relation_memory_state_map_to_json(
    states: Mapping[str, RelationMemoryPersistentState],
    *,
    expected_digital_life_ids: Sequence[str],
) -> str:
    """Encode the strict import/export document as canonical compact JSON."""

    return json.dumps(
        relation_memory_state_map_to_dict(
            states,
            expected_digital_life_ids=expected_digital_life_ids,
        ),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def load_relation_memory_state_file(
    path: Path,
    *,
    expected_digital_life_ids: Sequence[str],
) -> Mapping[str, RelationMemoryPersistentState]:
    """Load one strict state handoff document for the single-session factory."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    return relation_memory_state_map_from_json(
        path.read_text(encoding="utf-8"),
        expected_digital_life_ids=expected_digital_life_ids,
    )


def export_relation_memory_state_file(
    path: Path,
    states: Mapping[str, RelationMemoryPersistentState],
    *,
    expected_digital_life_ids: Sequence[str],
) -> Path:
    """Write one importable final-state document after normal session closing."""

    if not isinstance(path, Path):
        raise TypeError("path must be a pathlib.Path")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = relation_memory_state_map_to_json(
        states,
        expected_digital_life_ids=expected_digital_life_ids,
    )
    path.write_text(encoded + "\n", encoding="utf-8")
    return path


__all__ = [
    "export_relation_memory_state_file",
    "load_relation_memory_state_file",
    "relation_memory_state_map_from_dict",
    "relation_memory_state_map_from_json",
    "relation_memory_state_map_to_dict",
    "relation_memory_state_map_to_json",
]
