"""Read-only stimulus-segment history model for the Stage 6 GUI."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class LightSegmentTableModel(QAbstractTableModel):
    """Expose immutable half-open segment records without deriving them in Qt."""

    HEADERS = (
        "segment index",
        "start",
        "end",
        "duration",
        "active",
        "signal",
        "holder",
        "Hue",
        "BPM",
        "phase start",
        "phase end",
        "Value start",
        "Value end",
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
            if index.column() != 6:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        record = self._records[index.row()]
        values = (
            record.segment_index,
            format_time_us(record.start_time_us),
            format_time_us(record.end_time_us),
            f"{record.duration_us / 1_000_000:.6f} s",
            _yes_no(record.active),
            record.source_signal_index,
            record.qualification_holder_id or "—",
            _number(record.hue_degree, 3),
            _number(record.blink_bpm, 3),
            _number(record.phase_cycles_at_start, 6),
            _number(record.phase_cycles_at_end, 6),
            _number(record.value_at_start, 6),
            _number(record.value_at_end, 6),
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


def _number(value: Any, places: int) -> str:
    return "—" if value is None else f"{float(value):.{places}f}"


def _yes_no(value: Any) -> str:
    return "yes" if value else "no"
