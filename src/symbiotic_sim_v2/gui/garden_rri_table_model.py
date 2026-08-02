"""Qt table model for immutable Garden RRI classification records."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.garden.input_layer.records import GardenRriRecord
from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class GardenRriTableModel(QAbstractTableModel):
    """Append Garden classification rows without reproducing artifact logic."""

    HEADERS = (
        "measurement index",
        "event時刻",
        "raw RRI",
        "phase",
        "bundle",
        "window",
        "artifact",
        "artifact reason",
        "median",
        "relative deviation",
        "evaluationへ使用",
        "membership policy",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[GardenRriRecord] = []

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._records):
            return None
        record = self._records[index.row()]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        median_ms = (
            None
            if record.median_rri_us_before is None
            else record.median_rri_us_before / 1_000.0
        )
        values = (
            record.input_measurement_index,
            format_time_us(record.event_time_us),
            f"{record.raw_rri_ms:.3f} ms",
            record.phase,
            "—" if record.bundle_index is None else f"Bundle {record.bundle_index}",
            record.window_role,
            "はい" if record.artifact else "いいえ",
            record.artifact_reason or "—",
            "—" if median_ms is None else f"{median_ms:.3f} ms",
            (
                "—"
                if record.relative_deviation is None
                else f"{record.relative_deviation * 100:.3f}%"
            ),
            "はい" if record.included_in_evaluation_window else "いいえ",
            record.membership_policy,
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

    def set_records(self, records: tuple[GardenRriRecord, ...]) -> None:
        """Append a shared prefix, or reset when a scenario was replaced."""

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

    def record_at(self, row: int) -> GardenRriRecord:
        return self._records[row]
