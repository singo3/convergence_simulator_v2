"""Stage 5B read-only diagnostics for three independent Digital Lives."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.multi_life_chart import MultiLifeChart
from symbiotic_sim_v2.gui.second_round_table_model import SecondRoundTableModel
from symbiotic_sim_v2.gui.touch_table_model import TouchTableModel
from symbiotic_sim_v2.simulation.engine import EngineSnapshot
from symbiotic_sim_v2.simulation.time_utils import format_time_us

THREE_LIFE_DESCRIPTION = (
    "3体のデジタル生命は同じN、Sを受けますが、互いのP、V、B、tau、"
    "内部状態を参照せず、それぞれ独立に演算します。"
)
RUNTIME_NOTICE = (
    "RuntimeはP/Vを比較せず、各生命のtauを個別touch時刻へ変換して"
    "配送するだけです。"
)
GARDEN_NOTICE = (
    "Gardenは実際に到着したID、Bだけから資格生命を決めます。"
)
K_NOTICE = "Stage 5Bでk_anchor / k_currentは全3生命とも固定です。"

MULTI_LIFE_TABLE_TABS_MIN_HEIGHT = 350
MULTI_LIFE_CHART_TABLE_SPLITTER_MIN_HEIGHT = 1_500
MULTI_LIFE_CHART_TABLE_INITIAL_SIZES = (1_140, 360)
SECOND_ROUND_CSV_FILENAME = "stage_05b_digital_life_second_round.csv"

_ROLE_ORDER = {"red": 0, "green": 1, "blue": 2}


class MultiLifePanel(QWidget):
    """Observe immutable first/second-round and Garden touch records."""

    def __init__(
        self,
        digital_life_components: Mapping[str, Any],
        garden_output_component: Any,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._components = dict(digital_life_components)
        self._garden_output_component = garden_output_component
        self._build_ui()
        self.reset_views()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        description = QLabel(THREE_LIFE_DESCRIPTION, self)
        description.setObjectName("multiLifeDescription")
        description.setWordWrap(True)
        root.addWidget(description)
        runtime_notice = QLabel(RUNTIME_NOTICE, self)
        runtime_notice.setObjectName("multiLifeRuntimeNotice")
        runtime_notice.setWordWrap(True)
        root.addWidget(runtime_notice)
        garden_notice = QLabel(GARDEN_NOTICE, self)
        garden_notice.setObjectName("multiLifeGardenNotice")
        garden_notice.setWordWrap(True)
        root.addWidget(garden_notice)
        root.addWidget(self._build_flow())

        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("multiLifeDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("multiLifeDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content_layout = QVBoxLayout(self.diagnostics_content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(7)
        content_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.cards_frame = QFrame(self.diagnostics_content)
        self.cards_frame.setObjectName("multiLifeCardsFrame")
        cards_layout = QHBoxLayout(self.cards_frame)
        cards_layout.setContentsMargins(4, 4, 4, 4)
        cards_layout.setSpacing(7)
        self.life_cards: dict[str, QGroupBox] = {}
        self.life_value_labels: dict[str, dict[str, QLabel]] = {}
        for life_id, component in self._ordered_components():
            snapshot = component.snapshot()
            card, labels = self._build_life_card(life_id, snapshot.role)
            self.life_cards[life_id] = card
            self.life_value_labels[life_id] = labels
            cards_layout.addWidget(card, stretch=1)
        content_layout.addWidget(self.cards_frame)

        k_notice = QLabel(K_NOTICE, self.diagnostics_content)
        k_notice.setObjectName("multiLifeKNotice")
        k_notice.setWordWrap(True)
        content_layout.addWidget(k_notice)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("multiLifeChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(
            MULTI_LIFE_CHART_TABLE_SPLITTER_MIN_HEIGHT
        )
        self.chart = MultiLifeChart(self.chart_table_splitter)
        self.chart_table_splitter.addWidget(self.chart)

        self.table_tabs = QTabWidget(self.chart_table_splitter)
        self.table_tabs.setObjectName("multiLifeTableTabs")
        self.table_tabs.setMinimumHeight(MULTI_LIFE_TABLE_TABS_MIN_HEIGHT)
        self._build_touch_table_tab()
        self._build_second_round_table_tab()
        self.chart_table_splitter.addWidget(self.table_tabs)
        self.chart_table_splitter.setCollapsible(0, False)
        self.chart_table_splitter.setCollapsible(1, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 0)
        self.chart_table_splitter.setSizes(list(MULTI_LIFE_CHART_TABLE_INITIAL_SIZES))
        content_layout.addWidget(self.chart_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self._diagnostic_scroll_wheel_targets = (self.chart.graphics.viewport(),)
        for target in self._diagnostic_scroll_wheel_targets:
            target.installEventFilter(self)
        root.addWidget(self.diagnostics_scroll, stretch=1)

        self.setStyleSheet(
            """
                QLabel#multiLifeDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5; border-radius: 6px;
                    color: #234A75; padding: 6px 10px;
                }
                QLabel#multiLifeRuntimeNotice, QLabel#multiLifeGardenNotice,
                QLabel#multiLifeKNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A; border-radius: 6px;
                    color: #6B4B16; padding: 6px 10px;
                }
                QFrame#multiLifeFlowFrame {
                    background: #F5F3FF; border: 1px solid #C4B5FD; border-radius: 7px;
                }
                QLabel#multiLifeFlowNode {
                    background: white; border: 1px solid #A78BFA; border-radius: 5px;
                    color: #4C1D95; font-weight: 700; padding: 5px 6px;
                }
                QLabel#multiLifeFlowArrow {
                    color: #7C3AED; font-size: 18px; font-weight: 700;
                }
                QLabel#multiLifeCardValue { color: #172033; font-weight: 700; }
            """
        )

    def _build_flow(self) -> QFrame:
        frame = QFrame(self)
        frame.setObjectName("multiLifeFlowFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(2)
        rows = (
            (
                "Garden入力層",
                "red / green / blue独立第1周",
                "各tauでID,B touch",
                "Garden出力資格層",
            ),
            (
                "資格ID返送",
                "各生命G",
                "E/q第2周",
                "次signal",
            ),
        )
        for row_index, nodes in enumerate(rows):
            row = QWidget(frame)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            for index, text in enumerate(nodes):
                if index:
                    arrow = QLabel("→", row)
                    arrow.setObjectName("multiLifeFlowArrow")
                    row_layout.addWidget(arrow)
                node = QLabel(text, row)
                node.setObjectName("multiLifeFlowNode")
                node.setAlignment(Qt.AlignmentFlag.AlignCenter)
                node.setWordWrap(True)
                row_layout.addWidget(node, stretch=1)
            layout.addWidget(row)
            if row_index == 0:
                down = QLabel("↓", frame)
                down.setObjectName("multiLifeFlowArrow")
                down.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(down)
        return frame

    def _build_life_card(
        self,
        life_id: str,
        role: str,
    ) -> tuple[QGroupBox, dict[str, QLabel]]:
        card = QGroupBox(role, self.cards_frame)
        card.setObjectName(f"{role}LifeCard")
        form = QFormLayout(card)
        form.setContentsMargins(7, 7, 7, 7)
        form.setHorizontalSpacing(7)
        form.setVerticalSpacing(2)
        labels: dict[str, QLabel] = {}
        fields = (
            ("digital_life_id", "ID", life_id),
            ("role", "role", role),
            ("n", "N", "—"),
            ("baseline_n", "baseline N", "—"),
            ("nd", "Nd", "0.500000"),
            ("w", "W", "0.500000"),
            ("p", "P", "1.000000"),
            ("e", "E", "0.000000"),
            ("q", "q", "0.500000"),
            ("v", "V", "—"),
            ("b", "B=[F,A,T,D]", "—"),
            ("tau", "tau", "—"),
            ("latest_touch", "latest touch time", "—"),
            ("g", "G", "0"),
            ("holder_match", "holder一致", "no"),
            ("first_completed", "first-round completed", "no"),
            ("second_completed", "second-round completed", "no"),
        )
        for key, caption, initial in fields:
            label = QLabel(initial, card)
            label.setObjectName("multiLifeCardValue")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setWordWrap(True)
            form.addRow(caption, label)
            labels[key] = label
        return card, labels

    def _build_touch_table_tab(self) -> None:
        page = QWidget(self.table_tabs)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        notice = QLabel(
            "Gardenのタッチ表は実到着のID/Bだけを表示し、P、V、tauを表示しません。",
            page,
        )
        notice.setObjectName("touchBoundaryNotice")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.touch_model = TouchTableModel(self)
        self.touch_table = QTableView(page)
        self.touch_table.setObjectName("multiLifeTouchTable")
        self._configure_table(self.touch_table, self.touch_model)
        layout.addWidget(self.touch_table)
        self.table_tabs.addTab(page, "touch到着")

    def _build_second_round_table_tab(self) -> None:
        page = QWidget(self.table_tabs)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        self.second_round_model = SecondRoundTableModel(self)
        self.second_round_table = QTableView(page)
        self.second_round_table.setObjectName("multiLifeSecondRoundTable")
        self._configure_table(self.second_round_table, self.second_round_model)
        layout.addWidget(self.second_round_table)
        self.export_second_round_button = QPushButton("第2周CSVを保存", page)
        self.export_second_round_button.setObjectName("exportSecondRoundCsvButton")
        self.export_second_round_button.clicked.connect(self._export_second_round_clicked)
        layout.addWidget(self.export_second_round_button)
        self.table_tabs.addTab(page, "第2周")

    @staticmethod
    def _configure_table(table: QTableView, model: Any) -> None:
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            watched in self._diagnostic_scroll_wheel_targets
            and event.type() is QEvent.Type.Wheel
        ):
            pixel_delta = event.pixelDelta().y()
            angle_delta = event.angleDelta().y()
            scroll_delta = pixel_delta
            if scroll_delta == 0 and angle_delta:
                steps = angle_delta / 120.0
                scroll_delta = round(
                    steps
                    * 3
                    * self.diagnostics_scroll.verticalScrollBar().singleStep()
                )
            if scroll_delta:
                bar = self.diagnostics_scroll.verticalScrollBar()
                bar.setValue(bar.value() - scroll_delta)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def set_components(
        self,
        digital_life_components: Mapping[str, Any],
        garden_output_component: Any,
    ) -> None:
        selected = dict(digital_life_components)
        if set(selected) != set(self.life_cards):
            raise ValueError("Stage 5B GUI requires the same red/green/blue life IDs")
        self._components = selected
        self._garden_output_component = garden_output_component

    def update_diagnostics(self, engine_snapshot: EngineSnapshot) -> None:
        first_round_by_id = {
            life_id: component.first_round_records()
            for life_id, component in self._components.items()
        }
        second_round_by_id = {
            life_id: component.second_round_records()
            for life_id, component in self._components.items()
        }
        touch_records = self._garden_output_component.touch_records()
        qualification_records = self._garden_output_component.qualification_records()

        for life_id, component in self._components.items():
            self._update_life_card(life_id, component.snapshot())

        previous_touch_rows = self.touch_model.rowCount()
        previous_second_rows = self.second_round_model.rowCount()
        combined_second = tuple(
            sorted(
                (
                    record
                    for records in second_round_by_id.values()
                    for record in records
                ),
                key=lambda record: (record.signal_index, record.digital_life_id),
            )
        )
        self.touch_model.set_records(touch_records)
        self.second_round_model.set_records(combined_second)
        self.chart.set_records(
            first_round_by_id,
            second_round_by_id,
            touch_records,
            qualification_records,
            engine_snapshot.current_time_us,
        )
        if self.touch_model.rowCount() > previous_touch_rows:
            self.touch_table.scrollToBottom()
        if self.second_round_model.rowCount() > previous_second_rows:
            self.second_round_table.scrollToBottom()
        self.export_second_round_button.setEnabled(bool(combined_second))

    def reset_views(self) -> None:
        self.touch_model.clear()
        self.second_round_model.clear()
        self.chart.clear()
        for life_id, component in self._components.items():
            self._update_life_card(life_id, component.snapshot())
        self.export_second_round_button.setEnabled(False)
        self.diagnostics_scroll.verticalScrollBar().setValue(0)

    def _update_life_card(self, life_id: str, snapshot: Any) -> None:
        labels = self.life_value_labels[life_id]
        labels["digital_life_id"].setText(snapshot.digital_life_id)
        labels["role"].setText(snapshot.role)
        labels["n"].setText(self._optional(snapshot.n_current))
        labels["baseline_n"].setText(self._optional(snapshot.n_baseline_session))
        labels["nd"].setText(f"{snapshot.nd:.6f}")
        labels["w"].setText(f"{snapshot.w:.6f}")
        labels["p"].setText(f"{snapshot.p:.6f}")
        labels["e"].setText(f"{snapshot.e:.6f}")
        labels["q"].setText(f"{snapshot.q:.6f}")
        labels["v"].setText(self._optional(snapshot.v))
        labels["b"].setText("[" + ", ".join(f"{value:.6f}" for value in snapshot.b) + "]")
        labels["tau"].setText(self._optional(snapshot.tau))
        labels["latest_touch"].setText(
            "—"
            if snapshot.latest_touch_time_us is None
            else format_time_us(snapshot.latest_touch_time_us)
        )
        labels["g"].setText(str(snapshot.current_g))
        labels["holder_match"].setText("yes" if snapshot.holder_matches else "no")
        labels["first_completed"].setText(
            "yes" if snapshot.first_round_completed else "no"
        )
        labels["second_completed"].setText(
            "yes" if snapshot.second_round_completed else "no"
        )

    def _export_second_round_clicked(self) -> None:
        records = tuple(
            sorted(
                (
                    record
                    for component in self._components.values()
                    for record in component.second_round_records()
                ),
                key=lambda record: (record.signal_index, record.digital_life_id),
            )
        )
        if not records:
            return
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Stage 5B第2周CSVを保存",
            SECOND_ROUND_CSV_FILENAME,
            "CSV (*.csv)",
        )
        if destination:
            from symbiotic_sim_v2.digital_life.second_round_diagnostics import (
                export_second_round_diagnostics_csv,
            )

            export_second_round_diagnostics_csv(destination, records)

    def _ordered_components(self) -> tuple[tuple[str, Any], ...]:
        return tuple(
            sorted(
                self._components.items(),
                key=lambda item: _ROLE_ORDER[item[1].snapshot().role],
            )
        )

    @staticmethod
    def _optional(value: float | None) -> str:
        return "—" if value is None else f"{value:.6f}"


ThreeDigitalLifePanel = MultiLifePanel
ThreeLifeCompetitionPanel = MultiLifePanel
MultiDigitalLifePanel = MultiLifePanel
