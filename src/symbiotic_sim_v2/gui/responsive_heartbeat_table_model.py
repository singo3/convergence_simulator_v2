"""Qt model for Stage 7 light-responsive heartbeat diagnostics."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class ResponsiveHeartbeatTableModel(QAbstractTableModel):
    """Display immutable internal truth without becoming a formal signal source."""

    HEADERS = (
        "beat index",
        "heartbeat time",
        "true RRI",
        "instantaneous HR",
        "response level",
        "preference match",
        "effective respiratory amplitude",
        "effective mean RRI",
        "respiratory component",
        "slow wave",
        "correlated component",
        "jitter",
        "clamp",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: list[Any] = []

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
            record.beat_index,
            format_time_us(record.heartbeat_time_us),
            _number(record.true_rri_ms, 3, " ms"),
            _number(record.instantaneous_hr_bpm, 2, " bpm"),
            _number(record.response_level, 6),
            _number(record.preference_match, 6),
            _number(record.effective_respiratory_amplitude_ms, 3, " ms"),
            _number(record.effective_mean_rri_ms, 3, " ms"),
            _number(record.respiratory_component_ms, 3, " ms"),
            _number(record.slow_wave_component_ms, 3, " ms"),
            _number(record.correlated_component_ms, 3, " ms"),
            _number(record.beat_jitter_component_ms, 3, " ms"),
            "—" if record.clamped is None else ("yes" if record.clamped else "no"),
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

    def set_records(self, records: tuple[Any, ...]) -> None:
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

    def record_at(self, row: int) -> Any:
        return self._records[row]


LightResponsiveHeartbeatTableModel = ResponsiveHeartbeatTableModel


def _number(value: float | None, decimals: int, suffix: str = "") -> str:
    return "—" if value is None else f"{value:.{decimals}f}{suffix}"
