"""Qt table models for Stage 7.1 light-response audit diagnostics."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from symbiotic_sim_v2.simulation.time_utils import format_time_us

_INVALID_INDEX = QModelIndex()


class _ImmutableRecordTableModel(QAbstractTableModel):
    """Append immutable diagnostic records without recalculating model values."""

    HEADERS: tuple[str, ...] = ()

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
        return self._values(self._records[index.row()])[index.column()]

    def _values(self, record: Any) -> tuple[Any, ...]:
        raise NotImplementedError

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


class LightResponseReceiptTableModel(_ImmutableRecordTableModel):
    """Display receipts and both independent Stage 7.1 split decisions."""

    HEADERS = (
        "receipt index",
        "time",
        "active",
        "physical Hue",
        "physical BPM",
        "Hue match",
        "BPM match",
        "total match",
        "target",
        "response before",
        "physical changed",
        "target changed",
        "audit segment",
        "response epoch",
        "audit split reason",
        "provenance used by physiology",
    )

    def _values(self, record: Any) -> tuple[Any, ...]:
        physical = record.physical_stimulus
        return (
            record.receipt_index,
            format_time_us(record.event_time_us),
            _yes_no(record.active),
            _number(_nested_field(record, physical, "render_hue_degree"), 3, "°"),
            _number(_nested_field(record, physical, "blink_bpm"), 3, " BPM"),
            _number(record.hue_match, 6),
            _number(record.bpm_match, 6),
            _number(record.preference_match, 6),
            _number(record.response_target, 6),
            _number(record.response_before, 6),
            _yes_no(_field(record, "physical_parameters_changed", default=False)),
            _yes_no(record.target_changed),
            _integer(
                _field(
                    record,
                    "audit_segment_index",
                    "physical_audit_segment_index",
                )
            ),
            _integer(
                _field(
                    record,
                    "response_dynamics_epoch_index",
                    "response_epoch_index",
                )
            ),
            _text(
                _field(
                    record,
                    "audit_split_reason",
                    "split_reason",
                )
            ),
            _yes_no(record.provenance_used_by_physiology),
        )


class LightResponseAuditSegmentTableModel(_ImmutableRecordTableModel):
    """Display physical-light audit segments and their epoch linkage."""

    HEADERS = (
        "audit segment",
        "start",
        "end",
        "duration",
        "active",
        "Hue",
        "saturation",
        "value center",
        "value amplitude",
        "value min",
        "value max",
        "BPM",
        "waveform",
        "Hue match",
        "BPM match",
        "total match",
        "target",
        "response epoch",
        "physical changed at start",
        "target changed at start",
        "split reason",
        "schema",
    )

    def _values(self, record: Any) -> tuple[Any, ...]:
        return (
            _field(record, "segment_index", "audit_segment_index"),
            format_time_us(record.start_time_us),
            format_time_us(record.end_time_us),
            format_time_us(record.duration_us),
            _yes_no(record.light_active),
            _number(record.render_hue_degree, 3, "°"),
            _number(_field(record, "saturation"), 6),
            _number(_field(record, "value_center"), 6),
            _number(_field(record, "value_amplitude"), 6),
            _number(_field(record, "value_min"), 6),
            _number(_field(record, "value_max"), 6),
            _number(record.blink_bpm, 3, " BPM"),
            _text(_field(record, "waveform")),
            _number(record.hue_match, 6),
            _number(record.bpm_match, 6),
            _number(record.preference_match, 6),
            _number(record.response_target, 6),
            _integer(
                _field(
                    record,
                    "response_dynamics_epoch_index",
                    "response_epoch_index",
                )
            ),
            _yes_no(
                _field(record, "physical_parameters_changed_at_start", default=False)
            ),
            _yes_no(_field(record, "target_changed_at_start", default=False)),
            _text(_field(record, "split_reason", "audit_split_reason")),
            _text(_field(record, "schema_version")),
        )


class LightResponseDynamicsEpochTableModel(_ImmutableRecordTableModel):
    """Display pure target/response dynamics epochs without physical provenance."""

    HEADERS = (
        "response epoch",
        "start",
        "end",
        "duration",
        "target",
        "response at start",
        "response at end",
        "time constant",
        "target changed at start",
        "dynamics version",
        "schema",
    )

    def _values(self, record: Any) -> tuple[Any, ...]:
        return (
            record.epoch_index,
            format_time_us(record.start_time_us),
            format_time_us(record.end_time_us),
            format_time_us(record.duration_us),
            _number(record.response_target, 6),
            _number(record.response_at_start, 6),
            _number(record.response_at_end, 6),
            _number(record.time_constant_seconds, 6, " s"),
            _yes_no(record.target_changed_at_start),
            record.response_dynamics_version,
            record.schema_version,
        )


LightReceiptTableModel = LightResponseReceiptTableModel
LightAuditSegmentTableModel = LightResponseAuditSegmentTableModel
LightResponseEpochTableModel = LightResponseDynamicsEpochTableModel


def _nested_field(record: Any, nested: Any, name: str) -> Any:
    direct_name = f"physical_{name}"
    if hasattr(record, direct_name):
        return getattr(record, direct_name)
    if nested is not None and hasattr(nested, name):
        return getattr(nested, name)
    return None


def _field(record: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default


def _number(value: float | None, decimals: int, suffix: str = "") -> str:
    return "—" if value is None else f"{value:.{decimals}f}{suffix}"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _integer(value: int | None) -> str:
    return "—" if value is None else str(value)


def _text(value: object | None) -> str:
    return "—" if value is None else str(value)
