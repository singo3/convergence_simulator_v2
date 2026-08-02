"""Read-only Qt table model for Stage 5B Garden touch arrival records."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class TouchTableModel(QAbstractTableModel):
    """Expose immutable touch records without deriving qualification decisions."""

    HEADERS = (
        "signal index",
        "arrival order",
        "arrival time",
        "life ID",
        "role",
        "B_F",
        "B_A",
        "B_T",
        "B_D",
        "holder before",
        "holder after",
        "assigned",
        "exact tie",
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
            if index.column() in {0, 1, 2, 5, 6, 7, 8, 11, 12}:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        record = self._records[index.row()]
        values = (
            record.signal_index,
            record.arrival_order,
            format_time_us(record.arrival_time_us),
            record.digital_life_id,
            record.role,
            self._b_value(record, 0),
            self._b_value(record, 1),
            self._b_value(record, 2),
            self._b_value(record, 3),
            record.holder_before or "—",
            record.holder_after or "—",
            self._yes_no(
                getattr(
                    record,
                    "assigned_holder_on_this_touch",
                    getattr(record, "assigned", False),
                )
            ),
            self._yes_no(record.exact_time_tie),
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
        attribute = ("b_f", "b_a", "b_t", "b_d")[index]
        value = getattr(record, attribute, None)
        if value is None and hasattr(record, "b"):
            value = record.b[index]
        return "—" if value is None else f"{value:.6f}"

    @staticmethod
    def _yes_no(value: object) -> str:
        return "yes" if value else "no"


GardenTouchTableModel = TouchTableModel
