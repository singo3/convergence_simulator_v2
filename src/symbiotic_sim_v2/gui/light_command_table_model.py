"""Read-only B-to-I command history model for the Stage 6 GUI."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class LightCommandTableModel(QAbstractTableModel):
    """Join immutable command/state records without recomputing light output."""

    HEADERS = (
        "signal index",
        "effective time",
        "active",
        "holder",
        "B_F",
        "B_A",
        "B_T",
        "B_D",
        "Hue",
        "BPM",
        "Saturation",
        "Value range",
        "waveform",
        "equivalent",
        "phase reset",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: tuple[tuple[Any, Any | None], ...] = ()

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() in {0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 13, 14}:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        command, state = self._rows[index.row()]
        effective_time_us = _field(command, "effective_time_us", "command_effective_time_us")
        values = (
            _field(command, "source_signal_index", "signal_index", default="—"),
            "—" if effective_time_us is None else format_time_us(effective_time_us),
            _yes_no(_field(command, "active", default=False)),
            _field(
                command,
                "qualification_holder_id",
                "holder_id",
                default=None,
            )
            or "—",
            _b_value(command, 0),
            _b_value(command, 1),
            _b_value(command, 2),
            _b_value(command, 3),
            _number(_field(command, "hue_degree", default=None), 3),
            _number(_field(command, "blink_bpm", default=None), 3),
            _number(_field(command, "saturation", default=None), 3),
            _value_range(command),
            _field(command, "waveform", default="—"),
            _flag_from_state(state, "command_equivalent_to_previous"),
            _flag_from_state(state, "phase_reset"),
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
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def set_records(
        self,
        commands: Sequence[Any],
        states: Sequence[Any] = (),
    ) -> None:
        state_by_key = {
            (
                _field(state, "source_signal_index", "signal_index", default=None),
                _field(state, "effective_time_us", default=None),
            ): state
            for state in states
        }
        rows = tuple(
            (
                command,
                state_by_key.get(
                    (
                        _field(
                            command,
                            "source_signal_index",
                            "signal_index",
                            default=None,
                        ),
                        _field(
                            command,
                            "effective_time_us",
                            "command_effective_time_us",
                            default=None,
                        ),
                    )
                ),
            )
            for command in commands
        )
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def clear(self) -> None:
        self.set_records(())

    def record_at(self, row: int) -> Any:
        return self._rows[row][0]


def _field(record: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default


def _b_value(record: Any, index: int) -> str:
    direct = ("source_b_f", "source_b_a", "source_b_t", "source_b_d")[index]
    value = _field(record, direct, default=None)
    source_b = _field(record, "source_b", "b", default=None)
    if value is None and source_b is not None:
        value = source_b[index]
    return _number(value, 6)


def _value_range(record: Any) -> str:
    minimum = _field(record, "value_min", default=None)
    maximum = _field(record, "value_max", default=None)
    if minimum is None or maximum is None:
        return "—"
    return f"{float(minimum):.3f}–{float(maximum):.3f}"


def _number(value: Any, places: int) -> str:
    return "—" if value is None else f"{float(value):.{places}f}"


def _yes_no(value: Any) -> str:
    return "yes" if value else "no"


def _flag_from_state(state: Any | None, name: str) -> str:
    if state is None or not hasattr(state, name):
        return "—"
    return _yes_no(getattr(state, name))
