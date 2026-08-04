"""Qt table projection for Stage 8A.1 condition summaries."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import first_record_value


@dataclass(frozen=True, slots=True)
class _Column:
    title: str
    aliases: tuple[str, ...]


COLUMNS = (
    _Column("condition", ("condition_id",)),
    _Column("fatigue target", ("selected_session_fatigue_target", "fatigue_target")),
    _Column("sigma multiplier", ("sigma_multiplier",)),
    _Column("completed / replicates", ("completed_replicate_count",)),
    _Column("failed", ("failed_replicate_count",)),
    _Column("life dominant", ("life_dominant_convergence_rate",)),
    _Column("BPM common", ("bpm_common_convergence_rate",)),
    _Column("multi-attractor", ("multi_attractor_convergence_rate",)),
    _Column("single pattern", ("single_life_pattern_convergence_rate",)),
    _Column("correct structure", ("correct_structure_rate",)),
    _Column("diffuse", ("diffuse_rate",)),
    _Column(
        "median convergence",
        ("median_first_convergence_session", "median_first_life_convergence_session"),
    ),
    _Column("holder switch", ("holder_switch_rate",)),
    _Column("mechanical rotation", ("mechanical_rotation_rate", "three_distinct_life_window_rate")),
    _Column("accepted", ("accepted_candidate_count", "accepted_count")),
    _Column("W blocked", ("w_ceiling_blocked_rate",)),
)
_INVALID_INDEX = QModelIndex()


class ConditionResultTableModel(QAbstractTableModel):
    """Display aggregate fields without calculating or ranking conditions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: tuple[object, ...] = ()

    def rowCount(self, parent=_INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent=_INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role not in {
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        }:
            return None
        value = first_record_value(
            self._records[index.row()],
            COLUMNS[index.column()].aliases,
        )
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section].title
        return str(section + 1)

    def set_records(self, records: Sequence[object]) -> None:
        self.beginResetModel()
        self._records = tuple(records)
        self.endResetModel()

    def row_at(self, index: int) -> object:
        return self._records[index]


__all__ = ["COLUMNS", "ConditionResultTableModel"]
