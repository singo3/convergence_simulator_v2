"""Read-only Qt table model for Stage 5B Garden qualification records."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class QualificationTableModel(QAbstractTableModel):
    """Display immutable per-signal holder/output decisions from the Garden core."""

    HEADERS = (
        "signal index",
        "signal time",
        "S",
        "holder before",
        "holder after",
        "assigned",
        "assignment time",
        "assignment ID",
        "held",
        "released",
        "touch order",
        "active",
        "B_F",
        "B_A",
        "B_T",
        "B_D",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: tuple[Any, ...] = ()

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() in {0, 1, 2, 5, 6, 8, 9, 11, 12, 13, 14, 15}:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        record = self._records[index.row()]
        assignment_time = getattr(record, "assignment_touch_time_us", None)
        touch_order = getattr(record, "touch_order", ())
        values = (
            record.signal_index,
            format_time_us(record.signal_time_us),
            record.s,
            record.holder_before or "—",
            record.holder_after or "—",
            self._yes_no(record.assigned_this_signal),
            "—" if assignment_time is None else format_time_us(assignment_time),
            getattr(record, "assignment_touch_id", None) or "—",
            self._yes_no(record.held_from_previous_signal),
            self._yes_no(record.released_after_second_round),
            " → ".join(touch_order) if touch_order else "—",
            self._yes_no(record.active_output),
            self._b_value(record, 0),
            self._b_value(record, 1),
            self._b_value(record, 2),
            self._b_value(record, 3),
        )
        return values[index.column()]

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def set_records(self, records: Sequence[Any]) -> None:
        self.beginResetModel()
        self._records = tuple(records)
        self.endResetModel()

    def clear(self) -> None:
        self.set_records(())

    def record_at(self, row: int) -> Any:
        return self._records[row]

    @staticmethod
    def _b_value(record: Any, index: int) -> str:
        attribute = ("qualified_b_f", "qualified_b_a", "qualified_b_t", "qualified_b_d")[
            index
        ]
        value = getattr(record, attribute, None)
        if value is None and getattr(record, "qualified_b", None) is not None:
            value = record.qualified_b[index]
        return "—" if value is None else f"{value:.6f}"

    @staticmethod
    def _yes_no(value: object) -> str:
        return "yes" if value else "no"


GardenQualificationTableModel = QualificationTableModel
