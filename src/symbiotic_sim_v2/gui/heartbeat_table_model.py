"""Qt table model for developer-only true heartbeat diagnostics."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us
from symbiotic_sim_v2.virtual_user.diagnostics import HeartbeatRecord

_INVALID_INDEX = QModelIndex()


class HeartbeatTableModel(QAbstractTableModel):
    """Incrementally display immutable heartbeat records without becoming a signal API."""

    HEADERS = (
        "beat index",
        "心拍時刻",
        "真のRRI (ms)",
        "瞬時HR (bpm)",
        "呼吸性成分",
        "低周波成分",
        "連続変動",
        "微小変動",
        "clamp",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[HeartbeatRecord] = []

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        """Return the number of diagnostic heartbeat rows."""

        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        """Return the fixed diagnostic column count."""

        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return formatted development diagnostics for one cell."""

        if not index.isValid() or not 0 <= index.row() < len(self._records):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        record = self._records[index.row()]
        values = (
            record.beat_index,
            format_time_us(record.heartbeat_time_us),
            self._format_number(record.true_rri_ms, 3),
            self._format_number(record.instantaneous_hr_bpm, 2),
            self._format_number(record.respiratory_component_ms, 2),
            self._format_number(record.slow_wave_component_ms, 2),
            self._format_number(record.correlated_component_ms, 2),
            self._format_number(record.beat_jitter_component_ms, 2),
            "—" if record.clamped is None else ("はい" if record.clamped else "いいえ"),
        )
        return values[index.column()]

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return horizontal labels and one-based vertical row numbers."""

        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation is Qt.Orientation.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        if orientation is Qt.Orientation.Vertical:
            return section + 1
        return None

    def set_records(self, records: tuple[HeartbeatRecord, ...]) -> None:
        """Append a shared prefix as a delta, or reset when the series was replaced."""

        current_count = len(self._records)
        if current_count <= len(records) and tuple(self._records) == records[:current_count]:
            additions = records[current_count:]
            if additions:
                self.beginInsertRows(
                    QModelIndex(),
                    current_count,
                    current_count + len(additions) - 1,
                )
                self._records.extend(additions)
                self.endInsertRows()
            return
        self.beginResetModel()
        self._records = list(records)
        self.endResetModel()

    def clear(self) -> None:
        """Clear every diagnostic row after scenario reset or config replacement."""

        if not self._records:
            return
        self.beginResetModel()
        self._records.clear()
        self.endResetModel()

    def record_at(self, row: int) -> HeartbeatRecord:
        """Return an immutable record for tests and developer inspection."""

        return self._records[row]

    @staticmethod
    def _format_number(value: float | None, decimals: int) -> str:
        return "—" if value is None else f"{value:.{decimals}f}"
