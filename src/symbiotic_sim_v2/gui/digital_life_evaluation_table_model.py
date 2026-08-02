"""Qt table model for immutable Stage 5A evaluation-update records."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.digital_life.records import DigitalLifeEvaluationUpdateRecord

_INVALID_INDEX = QModelIndex()


class DigitalLifeEvaluationTableModel(QAbstractTableModel):
    """Display evaluation application metadata without deriving Nd or W."""

    HEADERS = (
        "evaluation ID",
        "kind",
        "bundle",
        "quality",
        "revision",
        "N",
        "baseline N",
        "previous Nd",
        "new Nd",
        "previous W",
        "new W",
        "applied",
        "skip reason",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[DigitalLifeEvaluationUpdateRecord] = []

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
            record.evaluation_id,
            record.evaluation_kind,
            "—" if record.bundle_index is None else f"Bundle {record.bundle_index}",
            record.quality,
            record.n_revision,
            self._format_number(record.n),
            self._format_number(record.n_baseline_session),
            self._format_number(record.previous_nd),
            self._format_number(record.new_nd),
            self._format_number(record.previous_w),
            self._format_number(record.new_w),
            "はい" if record.applied else "いいえ",
            record.skip_reason or "—",
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

    def set_records(
        self,
        records: tuple[DigitalLifeEvaluationUpdateRecord, ...],
    ) -> None:
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

    def record_at(self, row: int) -> DigitalLifeEvaluationUpdateRecord:
        return self._records[row]

    @staticmethod
    def _format_number(value: float | None) -> str:
        return "—" if value is None else f"{value:.6f}"
