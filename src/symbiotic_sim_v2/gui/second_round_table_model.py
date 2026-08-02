"""Read-only Qt table model for Stage 5B Digital Life second rounds."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

_INVALID_INDEX = QModelIndex()


class SecondRoundTableModel(QAbstractTableModel):
    """Display the specified second-round audit projection without recomputation."""

    HEADERS = (
        "signal index",
        "life ID",
        "S",
        "holder ID",
        "G",
        "W",
        "E before",
        "E after",
        "q before",
        "q after",
        "q applied",
        "q skip reason",
        "B match",
        "k update status",
        "closing attribution",
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
            if index.column() in {0, 2, 4, 5, 6, 7, 8, 9, 10, 12, 14}:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        record = self._records[index.row()]
        values = (
            record.signal_index,
            record.digital_life_id,
            record.s,
            record.qualification_holder_id or "—",
            record.g,
            f"{record.w:.6f}",
            f"{record.e_before:.6f}",
            f"{record.e_after:.6f}",
            f"{record.q_before:.6f}",
            f"{record.q_after:.6f}",
            self._yes_no(record.q_update_applied),
            record.q_skip_reason,
            self._yes_no(record.b_match),
            record.k_update_status,
            self._yes_no(record.closing_evaluation_attribution),
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
    def _yes_no(value: object) -> str:
        return "yes" if value else "no"


DigitalLifeSecondRoundTableModel = SecondRoundTableModel
