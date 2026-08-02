"""Qt table model for Stage 3 raw-RRI measurement diagnostics."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.devices.polar_h10.diagnostics import RriMeasurementDiagnostic
from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class RriMeasurementTableModel(QAbstractTableModel):
    """Incrementally display immutable H10 measurements joined to diagnostic truth."""

    HEADERS = (
        "measurement index",
        "RRI event時刻",
        "previous beat index",
        "current beat index",
        "previous heartbeat時刻",
        "current heartbeat時刻",
        "H10測定RRI",
        "診断用true RRI",
        "絶対誤差",
        "match",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[RriMeasurementDiagnostic] = []

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        """Return the number of displayed diagnostic rows."""

        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        """Return the fixed Stage 3 measurement column count."""

        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return one formatted raw or explicitly diagnostic value."""

        if not index.isValid() or not 0 <= index.row() < len(self._records):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        record = self._records[index.row()]
        values = (
            record.measurement_index,
            format_time_us(record.event_time_us),
            record.previous_beat_index,
            record.current_beat_index,
            format_time_us(record.previous_heartbeat_time_us),
            format_time_us(record.current_heartbeat_time_us),
            f"{record.rri_ms:.3f} ms",
            f"{record.diagnostic_true_rri_ms:.3f} ms",
            f"{record.absolute_error_us} µs",
            "一致" if record.match else "不一致",
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

    def set_records(self, records: tuple[RriMeasurementDiagnostic, ...]) -> None:
        """Append a shared prefix as a delta, resetting only when the source changed."""

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
        """Remove all displayed rows while retaining the model instance."""

        if not self._records:
            return
        self.beginResetModel()
        self._records.clear()
        self.endResetModel()

    def record_at(self, row: int) -> RriMeasurementDiagnostic:
        """Return one immutable diagnostic record for inspection and tests."""

        return self._records[row]
