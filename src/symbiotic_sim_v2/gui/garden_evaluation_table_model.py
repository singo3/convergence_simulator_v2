"""Qt table model for the four immutable Garden evaluation results."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.garden.input_layer.records import GardenEvaluationRecord
from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class GardenEvaluationTableModel(QAbstractTableModel):
    """Display finalized windows without recalculating RMSSD, N, or quality."""

    HEADERS = (
        "evaluation ID",
        "window",
        "total RRI",
        "artifact数",
        "artifact率",
        "valid RRI数",
        "RMSSD",
        "N",
        "quality",
        "reject reason",
        "N revision",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[GardenEvaluationRecord] = []

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
            f"{format_time_us(record.window_start_us)}–{format_time_us(record.window_end_us)}",
            record.total_rri_count,
            record.artifact_rri_count,
            f"{record.artifact_rate * 100:.3f}%",
            record.valid_rri_count,
            "—" if record.rmssd_ms is None else f"{record.rmssd_ms:.3f} ms",
            "—" if record.n is None else f"{record.n:.6f}",
            record.quality,
            "—" if not record.reject_reasons else ", ".join(record.reject_reasons),
            record.n_revision,
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

    def set_records(self, records: tuple[GardenEvaluationRecord, ...]) -> None:
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

    def record_at(self, row: int) -> GardenEvaluationRecord:
        return self._records[row]
