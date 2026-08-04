"""GUI-facing protocols for the Stage 8A.1 laboratory.

The concrete experiment runner is deliberately kept behind these protocols so
the Qt surface never owns fatigue, sigma, convergence, or truth calculations.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable


def record_value(record: object, name: str, default: Any = None) -> Any:
    """Read one immutable record field without requiring a concrete core type."""

    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def first_record_value(
    record: object,
    names: tuple[str, ...],
    default: Any = None,
) -> Any:
    """Read the first available alias from a mapping or record object."""

    missing = object()
    for name in names:
        value = record_value(record, name, missing)
        if value is not missing:
            return value
    return default


@runtime_checkable
class LabExecutionControl(Protocol):
    """Thread-safe boundary checks supplied to GUI-launched core operations."""

    @property
    def cancel_requested(self) -> bool: ...

    @property
    def pause_requested(self) -> bool: ...


type LabProgressCallback = Callable[[object], None]


@runtime_checkable
class LabOperation(Protocol):
    """One core-owned operation executed away from the GUI thread."""

    def __call__(
        self,
        progress: LabProgressCallback,
        control: LabExecutionControl,
    ) -> object: ...


@runtime_checkable
class FatigueSigmaLabBackend(Protocol):
    """Adapter boundary between the Qt window and Stage 8A.1 runners."""

    def create_single_operation(
        self,
        action: str,
        settings: Mapping[str, object],
    ) -> LabOperation: ...

    def create_grid_operation(
        self,
        settings: Mapping[str, object],
    ) -> LabOperation: ...

    def reset_single(self, settings: Mapping[str, object]) -> object: ...

    def save_single_state(self, path: object) -> None: ...

    def load_single_state(self, path: object) -> object: ...

    def export_csv(self, path: object) -> None: ...

    def current_simulation(self) -> object | None: ...


__all__ = [
    "FatigueSigmaLabBackend",
    "LabExecutionControl",
    "LabOperation",
    "LabProgressCallback",
    "first_record_value",
    "record_value",
]
