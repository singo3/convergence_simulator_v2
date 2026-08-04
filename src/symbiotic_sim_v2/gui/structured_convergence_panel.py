"""Independent Stage 8A.1 convergence-structure diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import first_record_value

STRUCTURED_HISTORY_TABLE_MIN_HEIGHT = 320
STRUCTURE_EXAMPLES = (
    ("A. 生命優勢収束", "8有効session中6以上が同じlife。1回outlierと復帰を許容。Hue一致は不要。"),
    ("B. BPM共通収束", "life/Hueを横断し、8有効session中6以上が20 BPM帯に集中。"),
    ("C. 生命別多峰収束", "lifeごとに再現するBPM attractorを別々に保持。単一clusterへ潰さない。"),
    ("D. 単一生命・単一パターン", "life dominanceとBPM commonが同時に安定。"),
    ("E. 混合型収束", "異なる構造flagが同時に成立。各flagは独立保存。"),
    ("F. 未収束・拡散", "必要supportを満たす構造なし。一時outlierだけで直ちにここへ落とさない。"),
)

HISTORY_COLUMNS = (
    ("session", ("evaluated_at_session_index", "session_index")),
    ("early 3-of-4", ("early_single_life_pattern_signal",)),
    ("life dominant", ("life_dominant_converged",)),
    ("dominant life", ("dominant_life_id",)),
    ("life share", ("dominant_life_share", "life_dominant_share")),
    ("strict run", ("strict_consecutive_run",)),
    ("latest outlier", ("latest_session_outlier",)),
    ("BPM common", ("bpm_common_converged",)),
    ("BPM support", ("bpm_common_support",)),
    ("BPM range", ("bpm_common_range", "bpm_range")),
    ("multi-attractor", ("multi_attractor_converged",)),
    ("attractors", ("attractor_count",)),
    ("summary", ("summary_classification",)),
)
_INVALID_INDEX = QModelIndex()


class StructuredConvergenceHistoryTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._records: tuple[object, ...] = ()

    def rowCount(self, parent=_INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent=_INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(HISTORY_COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role not in {
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        }:
            return None
        value = first_record_value(
            self._records[index.row()],
            HISTORY_COLUMNS[index.column()][1],
        )
        if value is None:
            return "—"
        if isinstance(value, bool):
            return "yes" if value else "no"
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
        return (
            HISTORY_COLUMNS[section][0]
            if orientation == Qt.Orientation.Horizontal
            else str(section + 1)
        )

    def set_records(self, records: Sequence[object]) -> None:
        self.beginResetModel()
        self._records = tuple(records)
        self.endResetModel()


class StructuredConvergencePanel(QWidget):
    """Show each diagnostic independently and one summary classification."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("stage8a1StructuredConvergencePanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("stage8a1StructuredConvergenceContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(5, 5, 5, 5)
        content.setSpacing(8)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        notice = QLabel(
            "収束評価は観測専用です。Digital Life、holder、candidate、E、sigma、"
            "p_explore、停止条件は変更しません。",
            self.diagnostics_content,
        )
        notice.setObjectName("stage8a1DiagnosticOnlyNotice")
        notice.setWordWrap(True)
        content.addWidget(notice)
        self.cards_frame = self._build_cards()
        content.addWidget(self.cards_frame)

        examples_heading = QLabel(
            "構造の定義 / 合成診断例（実run結果ではありません）", self.diagnostics_content
        )
        examples_heading.setObjectName("sectionTitle")
        content.addWidget(examples_heading)
        self.example_frames: list[QFrame] = []
        examples = QGridLayout()
        for index, (title, description) in enumerate(STRUCTURE_EXAMPLES):
            frame = QFrame(self.diagnostics_content)
            frame.setObjectName("stage8a1StructureExampleCard")
            layout = QVBoxLayout(frame)
            title_label = QLabel(title, frame)
            title_label.setObjectName("stage8a1StructureExampleTitle")
            description_label = QLabel(description, frame)
            description_label.setWordWrap(True)
            layout.addWidget(title_label)
            layout.addWidget(description_label)
            examples.addWidget(frame, index // 2, index % 2)
            self.example_frames.append(frame)
        content.addLayout(examples)

        self.history_model = StructuredConvergenceHistoryTableModel(self)
        self.history_table = QTableView(self.diagnostics_content)
        self.history_table.setObjectName("stage8a1StructuredConvergenceHistoryTable")
        self.history_table.setModel(self.history_model)
        self.history_table.setMinimumHeight(STRUCTURED_HISTORY_TABLE_MIN_HEIGHT)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.history_table.horizontalHeader().setStretchLastSection(True)
        content.addWidget(self.history_table)
        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        root.addWidget(self.diagnostics_scroll)
        self.setStyleSheet(
            """
            QLabel#stage8a1DiagnosticOnlyNotice {
                background: #E8F1FF; border: 1px solid #B9D2F5;
                border-radius: 6px; color: #234A75; padding: 8px 10px;
            }
            QFrame#stage8a1StructuredCards, QFrame#stage8a1StructureExampleCard {
                background: #F8FAFC; border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
            QLabel#stage8a1StructureCardCaption { color: #64748B; font-size: 10px; }
            QLabel#stage8a1StructureCardValue,
            QLabel#stage8a1StructureExampleTitle { color: #172033; font-weight: 700; }
            """
        )
        self.reset_views()

    def _build_cards(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("stage8a1StructuredCards")
        layout = QGridLayout(frame)
        fields = (
            ("life", "生命優勢: life / share / tolerant run / return"),
            ("bpm", "BPM共通: support / medoid / range / lives"),
            ("multi", "多峰: count / medoids / support / separation"),
            ("summary", "observed summary classification"),
            ("truth", "simulation-only truth classification"),
            ("early", "早期の単一生命・近接パターン兆候"),
            ("mechanical", "mechanical rotation warning"),
            ("w_ceiling", "W ceiling classification"),
        )
        self.card_labels: dict[str, QLabel] = {}
        for index, (key, caption) in enumerate(fields):
            column = index % 2
            row = (index // 2) * 2
            caption_label = QLabel(caption, frame)
            caption_label.setObjectName("stage8a1StructureCardCaption")
            value_label = QLabel("—", frame)
            value_label.setObjectName("stage8a1StructureCardValue")
            value_label.setWordWrap(True)
            layout.addWidget(caption_label, row, column)
            layout.addWidget(value_label, row + 1, column)
            self.card_labels[key] = value_label
        return frame

    def set_records(
        self,
        history: Sequence[object],
        *,
        truth_record: object | None = None,
        mechanical_record: object | None = None,
        w_ceiling_record: object | None = None,
    ) -> None:
        selected = tuple(history)
        self.history_model.set_records(selected)
        latest = selected[-1] if selected else None
        if latest is None:
            self.reset_cards()
            return
        self.card_labels["life"].setText(
            f"{first_record_value(latest, ('dominant_life_id',), '—')} / "
            "share="
            f"{first_record_value(latest, ('dominant_life_share', 'life_dominant_share'), '—')} / "
            f"strict={first_record_value(latest, ('strict_consecutive_run',), '—')} / "
            f"tolerant={first_record_value(latest, ('one_outlier_tolerant_longest_run',), '—')} / "
            "latest-outlier="
            f"{_yes_no(first_record_value(latest, ('latest_session_outlier',), None))} / "
            f"return1={first_record_value(latest, ('return_within_1_rate',), '—')}"
        )
        self.card_labels["bpm"].setText(
            f"support={first_record_value(latest, ('bpm_common_support',), '—')} / "
            f"medoid={first_record_value(latest, ('bpm_common_medoid_bpm', 'bpm_medoid'), '—')} / "
            f"range={first_record_value(latest, ('bpm_common_range', 'bpm_range'), '—')} / "
            f"lives={first_record_value(latest, ('bpm_common_participating_life_ids',), '—')}"
        )
        self.card_labels["multi"].setText(
            f"count={first_record_value(latest, ('attractor_count',), '—')} / "
            f"medoids={first_record_value(latest, ('attractor_medoid_bpm_by_life',), '—')} / "
            f"support={first_record_value(latest, ('attractor_support_by_life',), '—')} / "
            f"separation={first_record_value(latest, ('attractor_separation',), '—')}"
        )
        self.card_labels["summary"].setText(
            str(first_record_value(latest, ("summary_classification",), "—"))
        )
        self.card_labels["early"].setText(
            _yes_no(first_record_value(latest, ("early_single_life_pattern_signal",), None))
        )
        self.card_labels["truth"].setText(
            str(first_record_value(truth_record, ("truth_classification", "classification"), "—"))
        )
        self.card_labels["mechanical"].setText(
            str(first_record_value(mechanical_record, ("classification", "warning"), "—"))
        )
        self.card_labels["w_ceiling"].setText(
            str(first_record_value(w_ceiling_record, ("classification",), "—"))
        )

    def reset_cards(self) -> None:
        for label in self.card_labels.values():
            label.setText("—")

    def reset_views(self) -> None:
        self.history_model.set_records(())
        self.reset_cards()


def _yes_no(value: object) -> str:
    if value is None:
        return "—"
    return "yes" if bool(value) else "no"


__all__ = [
    "STRUCTURE_EXAMPLES",
    "STRUCTURED_HISTORY_TABLE_MIN_HEIGHT",
    "StructuredConvergenceHistoryTableModel",
    "StructuredConvergencePanel",
]
