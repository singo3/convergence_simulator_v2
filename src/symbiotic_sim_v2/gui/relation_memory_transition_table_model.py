"""Read-only Qt projections of Stage 5C transition and persistent records."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class _ImmutableRecordTableModel(QAbstractTableModel):
    """Incrementally expose immutable records without deriving decisions."""

    HEADERS: tuple[str, ...] = ()
    FIELDS: tuple[str, ...] = ()

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


class RelationMemoryTransitionTableModel(_ImmutableRecordTableModel):
    """Display every audit field supplied by RelationMemoryTransitionRecord."""

    FIELDS = (
        "transition_index",
        "signal_index",
        "signal_time_us",
        "digital_life_id",
        "g",
        "bundle_index",
        "evaluation_id",
        "evaluation_quality",
        "evaluation_is_valid",
        "w",
        "phase_before",
        "phase_after",
        "exploration_decision",
        "curiosity",
        "sigma_min",
        "sigma_max",
        "sigma",
        "epsilon_accept",
        "p_explore_min",
        "p_explore",
        "u_explore",
        "direction_trial_index",
        "direction_u_f",
        "direction_u_t",
        "direction_norm",
        "direction_xi",
        "k_anchor_before",
        "k_current_before",
        "k_trial",
        "k_current_after",
        "k_anchor_after",
        "w_anchor_session_before",
        "w_anchor_session_after",
        "w_trial_1_before",
        "w_trial_1_after",
        "w_trial_2_before",
        "w_trial_2_after",
        "provisional_condition",
        "confirmation_condition_1",
        "confirmation_condition_2",
        "candidate_mean_w",
        "trial_count_before",
        "trial_count_after",
        "session_count_used",
        "session_count_after",
        "adoption_result",
        "rollback_reason",
        "candidate_effective_signal_index",
        "relation_update_effective_policy_version",
        "algorithm_version",
        "state_schema_version",
        "schema_version",
    )
    HEADERS = (
        "transition",
        "signal",
        "time",
        "life ID",
        "G",
        "bundle",
        "evaluation ID",
        "quality",
        "valid",
        "W",
        "phase before",
        "phase after",
        "decision",
        "curiosity",
        "sigma min",
        "sigma max",
        "sigma",
        "epsilon accept",
        "p explore min",
        "p explore",
        "u explore",
        "trial index",
        "direction u F",
        "direction u T",
        "direction norm",
        "direction xi",
        "k anchor before",
        "k current before",
        "k trial",
        "k current after",
        "k anchor after",
        "W anchor before",
        "W anchor after",
        "W trial 1 before",
        "W trial 1 after",
        "W trial 2 before",
        "W trial 2 after",
        "provisional",
        "confirmation 1",
        "confirmation 2",
        "trial mean W",
        "trial count before",
        "trial count after",
        "session used",
        "session after",
        "adoption",
        "rollback reason",
        "candidate effective signal",
        "effective policy",
        "algorithm",
        "state schema",
        "record schema",
    )


class RelationMemoryPersistentStateTableModel(_ImmutableRecordTableModel):
    """Show the injected before state and normally finalized after state."""

    FIELDS = (
        "state_position",
        "digital_life_id",
        "k_anchor",
        "q",
        "e",
        "trial_count",
        "session_count",
        "profile_version",
        "algorithm_version",
        "state_schema_version",
    )
    HEADERS = (
        "position",
        "life ID",
        "k anchor",
        "q",
        "E",
        "trial count",
        "session count",
        "profile",
        "algorithm",
        "state schema",
    )


def _format_field(field: str, value: Any) -> Any:
    if value is None:
        return "—"
    if field.endswith("_time_us"):
        return format_time_us(value)
    if field == "bundle_index":
        return f"Bundle {value}"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, (tuple, list)):
        return "[" + ", ".join(_format_vector_value(item) for item in value) + "]"
    return value


def _format_vector_value(value: Any) -> str:
    return f"{value:.6f}" if isinstance(value, float) else str(value)


__all__ = [
    "RelationMemoryPersistentStateTableModel",
    "RelationMemoryTransitionTableModel",
]
