"""Qt table model for immutable Stage 5A first-round signal records."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.digital_life.records import DigitalLifeFirstRoundRecord
from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class DigitalLifeSignalTableModel(QAbstractTableModel):
    """Incrementally display first-round values without recalculating them."""

    HEADERS = (
        "signal index",
        "time",
        "phase",
        "bundle",
        "S",
        "N",
        "baseline N",
        "revision",
        "new evaluation",
        "Nd",
        "W",
        "P",
        "E",
        "q",
        "V",
        "B F",
        "B T",
        "tau",
        "G",
        "touch dispatched",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[DigitalLifeFirstRoundRecord] = []

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._records):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        record = self._records[index.row()]
        values = (
            record.signal_index,
            format_time_us(record.signal_time_us),
            record.phase,
            "—" if record.bundle_index is None else f"Bundle {record.bundle_index}",
            record.s,
            self._format_number(record.n_current),
            self._format_number(record.n_baseline_session),
            record.valid_evaluation_revision,
            self._format_bool(record.is_new_valid_evaluation),
            self._format_number(record.nd),
            self._format_number(record.w),
            self._format_number(record.p),
            self._format_number(record.e),
            self._format_number(record.q),
            self._format_number(record.v),
            self._format_number(record.b_f),
            self._format_number(record.b_t),
            self._format_number(record.tau),
            self._format_g_status(record.g_status),
            "実行" if record.touch_dispatched else "未実行",
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
        if orientation is Qt.Orientation.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        if orientation is Qt.Orientation.Vertical:
            return section + 1
        return None

    def set_records(self, records: tuple[DigitalLifeFirstRoundRecord, ...]) -> None:
        """Append a shared prefix, or reset after scenario replacement."""

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
        if not self._records:
            return
        self.beginResetModel()
        self._records.clear()
        self.endResetModel()

    def record_at(self, row: int) -> DigitalLifeFirstRoundRecord:
        return self._records[row]

    @staticmethod
    def _format_number(value: float | None) -> str:
        return "—" if value is None else f"{value:.6f}"

    @staticmethod
    def _format_bool(value: bool) -> str:
        return "はい" if value else "いいえ"

    @staticmethod
    def _format_g_status(value: str) -> str:
        return "未接続" if value == "not_connected" else value
