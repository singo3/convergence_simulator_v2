"""Read-only projections for Stage 8A completed-session history."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


def record_value(record: Any, field: str, default: Any = None) -> Any:
    """Read one field from an immutable record or its dictionary projection."""

    if record is None:
        return default
    if isinstance(record, Mapping):
        return record.get(field, default)
    return getattr(record, field, default)


def first_record_value(
    record: Any,
    fields: Sequence[str],
    default: Any = None,
) -> Any:
    """Read the first available alias without changing the source record."""

    for field in fields:
        value = record_value(record, field, None)
        if value is not None:
            return value
    return default


def truth_value(record: Any, field: str, default: Any = None) -> Any:
    """Read a truth diagnostic whether it is flat or nested on a record."""

    direct = record_value(record, field, None)
    if direct is not None:
        return direct
    truth = first_record_value(
        record,
        ("truth_alignment", "truth_alignment_record", "truth"),
        None,
    )
    return record_value(truth, field, default)


def convergence_record_index(record: Any) -> int | None:
    value = first_record_value(
        record,
        (
            "evaluated_at_session_index",
            "evaluation_session_index",
            "session_index",
        ),
        None,
    )
    return int(value) if value is not None else None


class ImmutableProjectionTableModel(QAbstractTableModel):
    """Small reusable model that never mutates or re-evaluates source records."""

    FIELDS: tuple[str, ...] = ()
    HEADERS: tuple[str, ...] = ()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[Mapping[str, Any]] = []

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        field = self.FIELDS[index.column()]
        return format_table_value(field, self._rows[index.row()].get(field))

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

    def set_projected_rows(self, rows: Sequence[Mapping[str, Any]]) -> None:
        values = tuple(dict(row) for row in rows)
        self.beginResetModel()
        self._rows = list(values)
        self.endResetModel()

    def clear(self) -> None:
        self.set_projected_rows(())

    def row_at(self, row: int) -> Mapping[str, Any]:
        return self._rows[row]


class SessionHistoryTableModel(ImmutableProjectionTableModel):
    """Join each outcome to its already-computed convergence/truth record."""

    FIELDS = (
        "session_index",
        "valid",
        "root_seed",
        "holder",
        "initial_hue_bpm",
        "final_hue_bpm",
        "exploration",
        "adoption",
        "w_anchor",
        "w_trial_1",
        "w_trial_2",
        "cluster_member",
        "outlier",
        "convergence_state",
        "truth_classification",
    )
    HEADERS = (
        "session",
        "valid",
        "root seed",
        "holder",
        "initial Hue / BPM",
        "final Hue / BPM",
        "exploration",
        "adoption",
        "W anchor",
        "W trial 1",
        "W trial 2",
        "cluster member",
        "outlier",
        "convergence after session",
        "truth classification",
    )

    def set_records(
        self,
        session_outcomes: Sequence[Any],
        convergence_records: Sequence[Any] = (),
        truth_alignment_records: Sequence[Any] = (),
    ) -> None:
        by_session = {
            index: record
            for record in convergence_records
            if (index := convergence_record_index(record)) is not None
        }
        truth_by_session = {
            index: record
            for record in truth_alignment_records
            if (index := convergence_record_index(record)) is not None
        }
        rows: list[dict[str, Any]] = []
        for outcome in session_outcomes:
            session_index = int(record_value(outcome, "session_index", 0))
            convergence = by_session.get(session_index)
            truth = truth_by_session.get(session_index, convergence)
            members = tuple(record_value(convergence, "member_session_indices", ()) or ())
            outliers = tuple(record_value(convergence, "outlier_session_indices", ()) or ())
            initial_hue = first_record_value(
                outcome,
                ("holder_initial_hue_degree", "initial_hue_degree"),
                None,
            )
            initial_bpm = first_record_value(
                outcome,
                ("holder_initial_blink_bpm", "initial_blink_bpm"),
                None,
            )
            final_hue = first_record_value(
                outcome,
                ("holder_final_hue_degree", "final_hue_degree"),
                None,
            )
            final_bpm = first_record_value(
                outcome,
                ("holder_final_blink_bpm", "final_blink_bpm"),
                None,
            )
            rows.append(
                {
                    "session_index": session_index,
                    "valid": record_value(outcome, "valid_for_convergence", False),
                    "root_seed": record_value(outcome, "physiology_root_seed"),
                    "holder": record_value(outcome, "holder_id"),
                    "initial_hue_bpm": _pattern_pair(initial_hue, initial_bpm),
                    "final_hue_bpm": _pattern_pair(final_hue, final_bpm),
                    "exploration": record_value(outcome, "exploration_decision"),
                    "adoption": record_value(outcome, "adoption_result"),
                    "w_anchor": record_value(outcome, "holder_W_anchor_session"),
                    "w_trial_1": record_value(outcome, "holder_W_trial_1"),
                    "w_trial_2": record_value(outcome, "holder_W_trial_2"),
                    "cluster_member": session_index in members,
                    "outlier": session_index in outliers,
                    "convergence_state": first_record_value(
                        convergence,
                        ("convergence_state", "state"),
                    ),
                    "truth_classification": truth_value(
                        truth,
                        "truth_classification",
                        truth_value(truth, "classification"),
                    ),
                }
            )
        self.set_projected_rows(rows)


def _pattern_pair(hue: Any, bpm: Any) -> tuple[Any, Any] | None:
    return None if hue is None or bpm is None else (hue, bpm)


def format_table_value(field: str, value: Any) -> Any:
    if value is None:
        return "—"
    if field.endswith("_time_us") and isinstance(value, int):
        return format_time_us(value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, tuple) and len(value) == 2 and field.endswith("hue_bpm"):
        return f"{float(value[0]):.3f}° / {float(value[1]):.3f} BPM"
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return value


__all__ = [
    "ImmutableProjectionTableModel",
    "SessionHistoryTableModel",
    "convergence_record_index",
    "first_record_value",
    "format_table_value",
    "record_value",
    "truth_value",
]
