"""Read-only Qt table model for Stage 5C adaptive signal records."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class RelationMemorySignalTableModel(QAbstractTableModel):
    """Project immutable adaptive records without regenerating B or candidates."""

    FIELDS = (
        "signal_index",
        "signal_time_us",
        "digital_life_id",
        "role",
        "s",
        "bundle_index",
        "phase",
        "evaluation_id",
        "evaluation_quality",
        "is_new_valid_evaluation",
        "g",
        "w",
        "k_anchor_before",
        "k_current_before",
        "k_presented",
        "b_presented",
        "relation_phase_before",
        "relation_phase_after",
        "k_current_after",
        "k_anchor_after",
        "candidate_effective_next_signal",
        "q_before",
        "q_after",
        "e_before",
        "e_after",
        "schema_version",
    )
    HEADERS = (
        "signal",
        "time",
        "life ID",
        "role",
        "S",
        "bundle",
        "phase",
        "evaluation ID",
        "quality",
        "new valid evaluation",
        "G",
        "W",
        "k anchor before",
        "k current before",
        "k presented",
        "B presented",
        "relation phase before",
        "relation phase after",
        "k current after",
        "k anchor after",
        "candidate next signal",
        "q before",
        "q after",
        "E before",
        "E after",
        "schema",
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
        field = self.FIELDS[index.column()]
        return _format_field(field, getattr(record, field, None))

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

    def set_records(self, records: Sequence[Any]) -> None:
        values = tuple(records)
        old_count = len(self._records)
        if old_count <= len(values) and tuple(self._records) == values[:old_count]:
            additions = values[old_count:]
            if additions:
                self.beginInsertRows(
                    _INVALID_INDEX,
                    old_count,
                    old_count + len(additions) - 1,
                )
                self._records.extend(additions)
                self.endInsertRows()
            return
        self.beginResetModel()
        self._records = list(values)
        self.endResetModel()

    def clear(self) -> None:
        self.set_records(())

    def record_at(self, row: int) -> Any:
        return self._records[row]


AdaptiveRelationMemorySignalTableModel = RelationMemorySignalTableModel


def _format_field(field: str, value: Any) -> Any:
    if value is None:
        return "—"
    if field == "signal_time_us":
        return format_time_us(value)
    if field == "bundle_index":
        return f"Bundle {value}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, (tuple, list)):
        return "[" + ", ".join(
            f"{item:.6f}" if isinstance(item, float) else str(item)
            for item in value
        ) + "]"
    return value


__all__ = [
    "AdaptiveRelationMemorySignalTableModel",
    "RelationMemorySignalTableModel",
]
