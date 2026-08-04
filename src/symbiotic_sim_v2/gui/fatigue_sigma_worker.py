"""QThread worker seam for long Stage 8A.1 single and grid operations."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal, Slot

from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import LabOperation


class FatigueSigmaExecutionControl:
    """Thread-safe cancel/pause flags checked only by the core at safe boundaries."""

    def __init__(self) -> None:
        self._cancel = threading.Event()
        self._pause = threading.Event()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    @property
    def pause_requested(self) -> bool:
        return self._pause.is_set()

    def request_cancel(self) -> None:
        self._cancel.set()

    def request_pause(self, selected: bool = True) -> None:
        if selected:
            self._pause.set()
        else:
            self._pause.clear()


class FatigueSigmaOperationWorker(QObject):
    """Execute a core operation without importing any concrete runner type."""

    progress = Signal(object)
    succeeded = Signal(object)
    cancelled = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        operation: LabOperation,
        control: FatigueSigmaExecutionControl,
    ) -> None:
        super().__init__()
        if not callable(operation):
            raise TypeError("operation must be callable")
        self._operation = operation
        self._control = control

    @Slot()
    def run(self) -> None:
        result: object | None = None
        try:
            result = self._operation(self.progress.emit, self._control)
            if self._control.cancel_requested:
                self.cancelled.emit(result)
            else:
                self.succeeded.emit(result)
        except Exception as exc:  # pragma: no cover - exercised through the signal
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.finished.emit()


__all__ = [
    "FatigueSigmaExecutionControl",
    "FatigueSigmaOperationWorker",
]
