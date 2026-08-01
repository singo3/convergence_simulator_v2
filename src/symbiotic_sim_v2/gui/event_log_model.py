"""Append-only Qt table model for executed simulation events."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.domain.events import SimulationEvent, thaw_json
from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class EventLogModel(QAbstractTableModel):
    """Display only executed events, never pending scheduler internals."""

    HEADERS = (
        "実行順",
        "仮想時刻",
        "event type",
        "source",
        "priority",
        "event ID",
        "payload要約",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._events: list[SimulationEvent] = []

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        """Return the number of executed events."""

        return 0 if parent.isValid() else len(self._events)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        """Return the fixed column count."""

        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return display/alignment data for one event cell."""

        if not index.isValid() or not (0 <= index.row() < len(self._events)):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() in {0, 1, 4}:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        event = self._events[index.row()]
        values = (
            index.row() + 1,
            format_time_us(event.scheduled_time_us),
            event.event_type,
            event.source,
            event.priority,
            event.event_id,
            json.dumps(
                thaw_json(event.payload),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
        return values[index.column()]

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return Japanese horizontal headers and one-based row numbers."""

        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def append_events(self, events: tuple[SimulationEvent, ...]) -> None:
        """Append a delta without rebuilding prior model rows."""

        if not events:
            return
        first = len(self._events)
        last = first + len(events) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._events.extend(events)
        self.endInsertRows()

    def reset_events(self) -> None:
        """Clear the execution log after a scenario reset."""

        self.beginResetModel()
        self._events.clear()
        self.endResetModel()

    def event_at(self, row: int) -> SimulationEvent:
        """Return a logged event for tests and diagnostics."""

        return self._events[row]
