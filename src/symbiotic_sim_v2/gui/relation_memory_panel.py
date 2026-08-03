"""Scrollable, read-only Stage 5C relation-memory diagnostics panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.relation_memory_chart import RelationMemoryChart
from symbiotic_sim_v2.gui.relation_memory_signal_table_model import (
    RelationMemorySignalTableModel,
)
from symbiotic_sim_v2.gui.relation_memory_transition_table_model import (
    RelationMemoryPersistentStateTableModel,
    RelationMemoryTransitionTableModel,
)
from symbiotic_sim_v2.simulation.engine import EngineSnapshot

DESCRIPTION = (
    "Bundle 0で現在のanchorを評価し、holdまたはtrialを決めます。"
    "trialはBundle 1で仮評価し、Bundle 2で同じcandidateを確認した場合だけ"
    "正式採用します。"
)
BASELINE_NOTICE = "baseline終了時のW=0.5はanchor評価ではありません。"
OWNERSHIP_NOTICE = (
    "候補生成と採否は資格生命自身の関係記憶C_iが行います。"
    "RuntimeやGardenは候補を選びません。"
)
OPTIMUM_NON_INPUT_NOTICE = (
    "最適点はシミュレーター診断専用で、Digital Lifeの探索計算には"
    "渡されません。"
)

RELATION_MEMORY_TABLE_TABS_MIN_HEIGHT = 360
RELATION_MEMORY_TABLE_MIN_HEIGHT = 300
RELATION_MEMORY_CHART_TABLE_SPLITTER_MIN_HEIGHT = 2_520
RELATION_MEMORY_CHART_TABLE_INITIAL_SIZES = (2_130, 390)

_ROLE_ORDER = {"red": 0, "green": 1, "blue": 2}


@dataclass(frozen=True, slots=True)
class _PersistentStateProjection:
    state_position: str
    digital_life_id: str
    k_anchor: tuple[float, float, float, float]
    q: float
    e: float
    trial_count: int
    session_count: int
    profile_version: str
    algorithm_version: str
    state_schema_version: str


class RelationMemoryPanel(QWidget):
    """Observe the three independent C_i state machines without recomputation."""

    def __init__(
        self,
        digital_life_components: Mapping[str, Any],
        parent: QWidget | None = None,
        *,
        preset_name: str = "off_center_green",
        diagnostic_optimum_ft: tuple[float, float] | None = None,
        garden_output_component: Any | None = None,
        garden_light_mapper_component: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self._components = _validated_components(digital_life_components)
        self._garden_output_component = _optional_record_source(
            garden_output_component,
            "qualified_b_records",
        )
        self._garden_light_mapper_component = _optional_record_source(
            garden_light_mapper_component,
            "command_records",
        )
        self._preset_name = preset_name
        self._diagnostic_optimum_ft = _visible_optimum(
            preset_name,
            diagnostic_optimum_ft,
        )
        self._record_revision: tuple[Any, ...] | None = None
        self._build_ui()
        self.reset_views()

    @property
    def preset_name(self) -> str:
        return self._preset_name

    @property
    def diagnostic_optimum_ft(self) -> tuple[float, float] | None:
        return self._diagnostic_optimum_ft

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("relationMemoryDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("relationMemoryDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(4, 4, 4, 4)
        content.setSpacing(7)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.description_label = _notice(
            DESCRIPTION,
            "relationMemoryDescription",
            self.diagnostics_content,
        )
        self.baseline_notice = _notice(
            BASELINE_NOTICE,
            "relationMemoryBaselineNotice",
            self.diagnostics_content,
        )
        self.ownership_notice = _notice(
            OWNERSHIP_NOTICE,
            "relationMemoryOwnershipNotice",
            self.diagnostics_content,
        )
        for notice in (
            self.description_label,
            self.baseline_notice,
            self.ownership_notice,
        ):
            content.addWidget(notice)
        content.addWidget(self._build_flow())

        self.cards_frame = QFrame(self.diagnostics_content)
        self.cards_frame.setObjectName("relationMemoryCardsFrame")
        cards_layout = QHBoxLayout(self.cards_frame)
        cards_layout.setContentsMargins(4, 4, 4, 4)
        cards_layout.setSpacing(7)
        self.life_cards: dict[str, QGroupBox] = {}
        self.life_value_labels: dict[str, dict[str, QLabel]] = {}
        for life_id, component in self._ordered_components():
            role = str(getattr(component.snapshot(), "role", life_id.removeprefix("life-")))
            card, labels = self._build_life_card(life_id, role)
            self.life_cards[life_id] = card
            self.life_value_labels[life_id] = labels
            cards_layout.addWidget(card, stretch=1)
        content.addWidget(self.cards_frame)

        self.parameter_group = self._build_parameter_group()
        content.addWidget(self.parameter_group)

        self.optimum_notice = _notice(
            OPTIMUM_NON_INPUT_NOTICE,
            "relationMemoryOptimumNotice",
            self.diagnostics_content,
        )
        self.optimum_notice.setVisible(self._diagnostic_optimum_ft is not None)
        content.addWidget(self.optimum_notice)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("relationMemoryChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(
            RELATION_MEMORY_CHART_TABLE_SPLITTER_MIN_HEIGHT
        )
        self.chart = RelationMemoryChart(self.chart_table_splitter)
        self.relation_memory_chart = self.chart
        self.chart_table_splitter.addWidget(self.chart)
        self.table_tabs = self._build_table_tabs()
        self.chart_table_splitter.addWidget(self.table_tabs)
        self.chart_table_splitter.setCollapsible(0, False)
        self.chart_table_splitter.setCollapsible(1, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 0)
        self.chart_table_splitter.setSizes(
            list(RELATION_MEMORY_CHART_TABLE_INITIAL_SIZES)
        )
        content.addWidget(self.chart_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self._diagnostic_scroll_wheel_targets = (self.chart.graphics.viewport(),)
        for target in self._diagnostic_scroll_wheel_targets:
            target.installEventFilter(self)
        root.addWidget(self.diagnostics_scroll, stretch=1)

        self.setStyleSheet(
            """
                QLabel#relationMemoryDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5;
                    border-radius: 6px; color: #234A75; padding: 7px 10px;
                }
                QLabel#relationMemoryBaselineNotice,
                QLabel#relationMemoryOwnershipNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A;
                    border-radius: 6px; color: #6B4B16; padding: 7px 10px;
                }
                QLabel#relationMemoryOptimumNotice {
                    background: #ECFDF5; border: 1px solid #6EE7B7;
                    border-radius: 6px; color: #065F46; padding: 7px 10px;
                }
                QFrame#relationMemoryFlowFrame {
                    background: #F5F3FF; border: 1px solid #C4B5FD;
                    border-radius: 7px;
                }
                QLabel#relationMemoryFlowNode {
                    background: white; border: 1px solid #A78BFA;
                    border-radius: 5px; color: #4C1D95; font-weight: 700;
                    padding: 5px 6px;
                }
                QLabel#relationMemoryFlowArrow {
                    color: #7C3AED; font-size: 18px; font-weight: 700;
                }
                QLabel#relationMemoryCardValue,
                QLabel#relationMemoryParameterValue {
                    color: #172033; font-weight: 700;
                }
            """
        )

    def _build_flow(self) -> QFrame:
        frame = QFrame(self.diagnostics_content)
        frame.setObjectName("relationMemoryFlowFrame")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(5)
        nodes = (
            "保存済みk_anchor",
            "Bundle 0 anchor評価",
            "C_i hold / explore",
            "Bundle 1 trial仮評価",
            "Bundle 2同候補確認",
            "adopt / rollback",
            "次signalから反映",
        )
        for index, text in enumerate(nodes):
            if index:
                arrow = QLabel("→", frame)
                arrow.setObjectName("relationMemoryFlowArrow")
                layout.addWidget(arrow)
            node = QLabel(text, frame)
            node.setObjectName("relationMemoryFlowNode")
            node.setAlignment(Qt.AlignmentFlag.AlignCenter)
            node.setWordWrap(True)
            layout.addWidget(node, stretch=1)
        return frame

    def _build_life_card(
        self,
        life_id: str,
        role: str,
    ) -> tuple[QGroupBox, dict[str, QLabel]]:
        card = QGroupBox(role, self.cards_frame)
        card.setObjectName(f"relationMemory{role.title()}LifeCard")
        form = QFormLayout(card)
        form.setContentsMargins(7, 7, 7, 7)
        form.setHorizontalSpacing(7)
        form.setVerticalSpacing(2)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        fields = (
            ("digital_life_id", "ID", life_id),
            ("role", "role", role),
            ("g", "G", "0"),
            ("holder", "holder", "no"),
            ("curiosity", "curiosity", "—"),
            ("sigma_range", "sigma min / max", "—"),
            ("epsilon_accept", "epsilon accept", "—"),
            ("p_explore_min", "p explore min", "—"),
            ("k_anchor", "persistent k anchor", "—"),
            ("k_current", "current k", "—"),
            ("trial_count", "trial count", "—"),
            ("session_count", "session count", "—"),
            ("adaptation_phase", "adaptation phase", "anchor_evaluation"),
            ("exploration_decision", "exploration decision", "—"),
            ("w_anchor_session", "W anchor session", "—"),
            ("k_trial", "k trial", "—"),
            ("w_trial_1", "W trial 1", "—"),
            ("w_trial_2", "W trial 2", "—"),
            ("adoption_result", "adoption result", "pending"),
        )
        labels: dict[str, QLabel] = {}
        for key, caption, initial in fields:
            label = QLabel(initial, card)
            label.setObjectName("relationMemoryCardValue")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(caption, label)
            labels[key] = label
        return card, labels

    def _build_parameter_group(self) -> QGroupBox:
        group = QGroupBox(
            "探索parameter（component recordの読み取り専用表示）",
            self.diagnostics_content,
        )
        layout = QGridLayout(group)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(7)
        self.parameter_value_labels: dict[str, dict[str, QLabel]] = {}
        fields = (
            ("curiosity", "c"),
            ("sigma", "sigma"),
            ("p_explore", "p explore"),
            ("u_explore", "u explore"),
            ("direction_u_f", "direction u F"),
            ("direction_u_t", "direction u T"),
            ("direction_xi", "normalized xi"),
            ("direction_trial_index", "trial index"),
            ("session_count_used", "session count used"),
        )
        for column, (life_id, component) in enumerate(self._ordered_components()):
            role = str(getattr(component.snapshot(), "role", life_id.removeprefix("life-")))
            box = QGroupBox(role, group)
            form = QFormLayout(box)
            form.setContentsMargins(7, 7, 7, 7)
            labels: dict[str, QLabel] = {}
            for key, caption in fields:
                label = QLabel("—", box)
                label.setObjectName("relationMemoryParameterValue")
                label.setWordWrap(True)
                label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                form.addRow(caption, label)
                labels[key] = label
            self.parameter_value_labels[life_id] = labels
            layout.addWidget(box, 0, column)
        return group

    def _build_table_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self.chart_table_splitter)
        tabs.setObjectName("relationMemoryTableTabs")
        tabs.setMinimumHeight(RELATION_MEMORY_TABLE_TABS_MIN_HEIGHT)

        transition_page = QWidget(tabs)
        transition_layout = QVBoxLayout(transition_page)
        transition_layout.setContentsMargins(4, 4, 4, 4)
        self.transition_model = RelationMemoryTransitionTableModel(self)
        self.transition_table_model = self.transition_model
        self.transition_table = QTableView(transition_page)
        self.transition_table.setObjectName("relationMemoryTransitionTable")
        _configure_table(self.transition_table, self.transition_model)
        transition_layout.addWidget(self.transition_table)
        tabs.addTab(transition_page, "relation transition")

        signal_page = QWidget(tabs)
        signal_layout = QVBoxLayout(signal_page)
        signal_layout.setContentsMargins(4, 4, 4, 4)
        self.signal_model = RelationMemorySignalTableModel(self)
        self.signal_table_model = self.signal_model
        self.signal_table = QTableView(signal_page)
        self.signal_table.setObjectName("relationMemorySignalTable")
        _configure_table(self.signal_table, self.signal_model)
        signal_layout.addWidget(self.signal_table)
        tabs.addTab(signal_page, "adaptive signal")

        persistent_page = QWidget(tabs)
        persistent_layout = QVBoxLayout(persistent_page)
        persistent_layout.setContentsMargins(4, 4, 4, 4)
        self.persistent_model = RelationMemoryPersistentStateTableModel(self)
        self.persistent_table_model = self.persistent_model
        self.persistent_table = QTableView(persistent_page)
        self.persistent_table.setObjectName("relationMemoryPersistentStateTable")
        _configure_table(self.persistent_table, self.persistent_model)
        persistent_layout.addWidget(self.persistent_table)
        tabs.addTab(persistent_page, "persistent before / after")
        return tabs

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (
            watched in self._diagnostic_scroll_wheel_targets
            and event.type() is QEvent.Type.Wheel
        ):
            scroll_delta = event.pixelDelta().y()
            angle_delta = event.angleDelta().y()
            if scroll_delta == 0 and angle_delta:
                scroll_delta = round(
                    (angle_delta / 120.0)
                    * 3
                    * self.diagnostics_scroll.verticalScrollBar().singleStep()
                )
            if scroll_delta:
                bar = self.diagnostics_scroll.verticalScrollBar()
                bar.setValue(bar.value() - scroll_delta)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def set_components(self, digital_life_components: Mapping[str, Any]) -> None:
        selected = _validated_components(digital_life_components)
        if set(selected) != set(self.life_cards):
            raise ValueError("Stage 5C GUI requires the same three Digital Life IDs")
        self._components = selected
        self.reset_views()

    def set_formal_output_components(
        self,
        garden_output_component: Any,
        garden_light_mapper_component: Any,
    ) -> None:
        """Rebind read-only formal output audits after a scenario rebuild."""

        self._garden_output_component = _optional_record_source(
            garden_output_component,
            "qualified_b_records",
        )
        self._garden_light_mapper_component = _optional_record_source(
            garden_light_mapper_component,
            "command_records",
        )
        self.reset_views()

    def set_diagnostic_optimum(
        self,
        preset_name: str,
        diagnostic_optimum_ft: tuple[float, float] | None,
    ) -> None:
        self._preset_name = preset_name
        self._diagnostic_optimum_ft = _visible_optimum(
            preset_name,
            diagnostic_optimum_ft,
        )
        self.optimum_notice.setVisible(self._diagnostic_optimum_ft is not None)
        if self._diagnostic_optimum_ft is None:
            self.chart.optimum_item.setData([], [])
            self.chart.optimum_visible = False
        else:
            self.chart.optimum_item.setData(
                [self._diagnostic_optimum_ft[0]],
                [self._diagnostic_optimum_ft[1]],
            )
            self.chart.optimum_visible = True
        self._record_revision = None

    def update_diagnostics(self, engine_snapshot: EngineSnapshot) -> None:
        transitions_by_id = {
            life_id: tuple(component.relation_memory_transition_records())
            for life_id, component in self._components.items()
        }
        signals_by_id = {
            life_id: tuple(component.adaptive_signal_records())
            for life_id, component in self._components.items()
        }
        initial_by_id = {
            life_id: component.initial_persistent_state()
            for life_id, component in self._components.items()
        }
        final_by_id = {
            life_id: component.final_persistent_state()
            for life_id, component in self._components.items()
        }
        session_by_id = {
            life_id: component.relation_memory_session_state()
            for life_id, component in self._components.items()
        }
        qualified_b_records = self._formal_records(
            self._garden_output_component,
            "qualified_b_records",
        )
        light_command_records = self._formal_records(
            self._garden_light_mapper_component,
            "command_records",
        )

        for life_id, component in self._components.items():
            self._update_life_card(
                life_id,
                component,
                initial_by_id[life_id],
                final_by_id[life_id],
                session_by_id[life_id],
                transitions_by_id[life_id],
                signals_by_id[life_id],
            )
            self._update_parameter_card(
                life_id,
                component,
                session_by_id[life_id],
                transitions_by_id[life_id],
            )

        revision = tuple(
            (life_id, len(transitions_by_id[life_id]), len(signals_by_id[life_id]))
            for life_id in sorted(self._components)
        ) + tuple(
            (life_id, final_by_id[life_id]) for life_id in sorted(self._components)
        ) + (
            len(qualified_b_records),
            len(light_command_records),
            self._diagnostic_optimum_ft,
        )
        if revision != self._record_revision:
            transitions = _combined_records(transitions_by_id, "transition_index")
            signals = _combined_records(signals_by_id, "signal_index")
            previous_transition_rows = self.transition_model.rowCount()
            previous_signal_rows = self.signal_model.rowCount()
            self.transition_model.set_records(transitions)
            self.signal_model.set_records(signals)
            self.persistent_model.set_records(
                _persistent_projections(initial_by_id, final_by_id)
            )
            self.chart.set_records(
                transitions_by_id,
                signals_by_id,
                initial_by_id,
                final_by_id,
                engine_snapshot.current_time_us,
                diagnostic_optimum_ft=self._diagnostic_optimum_ft,
                qualified_b_records=qualified_b_records,
                light_command_records=light_command_records,
            )
            if self.transition_model.rowCount() > previous_transition_rows:
                self.transition_table.scrollToBottom()
            if self.signal_model.rowCount() > previous_signal_rows:
                self.signal_table.scrollToBottom()
            self._record_revision = revision
        else:
            self.chart.set_current_time_us(engine_snapshot.current_time_us)

    def reset_views(self) -> None:
        self.transition_model.clear()
        self.signal_model.clear()
        self.persistent_model.clear()
        self.chart.clear()
        self._record_revision = None
        initial_by_id = {
            life_id: component.initial_persistent_state()
            for life_id, component in self._components.items()
        }
        final_by_id = {
            life_id: component.final_persistent_state()
            for life_id, component in self._components.items()
        }
        for life_id, component in self._components.items():
            initial = initial_by_id[life_id]
            final = final_by_id[life_id]
            session = component.relation_memory_session_state()
            transitions = tuple(component.relation_memory_transition_records())
            signals = tuple(component.adaptive_signal_records())
            self._update_life_card(
                life_id,
                component,
                initial,
                final,
                session,
                transitions,
                signals,
            )
            self._update_parameter_card(life_id, component, session, transitions)
        self.persistent_model.set_records(
            _persistent_projections(initial_by_id, final_by_id)
        )
        self.chart.set_records(
            {life_id: () for life_id in self._components},
            {life_id: () for life_id in self._components},
            initial_by_id,
            final_by_id,
            0,
            diagnostic_optimum_ft=self._diagnostic_optimum_ft,
            qualified_b_records=(),
            light_command_records=(),
        )
        self.diagnostics_scroll.verticalScrollBar().setValue(0)

    @staticmethod
    def _formal_records(source: Any | None, method_name: str) -> tuple[Any, ...]:
        if source is None:
            return ()
        return tuple(getattr(source, method_name)())

    def _update_life_card(
        self,
        life_id: str,
        component: Any,
        initial: Any,
        final: Any | None,
        session: Any,
        transitions: tuple[Any, ...],
        signals: tuple[Any, ...],
    ) -> None:
        labels = self.life_value_labels[life_id]
        profile = component.relation_memory_intrinsic_profile()
        snapshot = component.snapshot()
        current_state_reader = getattr(component, "current_persistent_state", None)
        persistent = (
            current_state_reader()
            if callable(current_state_reader)
            else (final if final is not None else initial)
        )
        latest_signal = signals[-1] if signals else None
        current_k = _first_present(
            latest_signal,
            ("k_current_after", "k_presented"),
            default=getattr(persistent, "k_anchor", None),
        )
        current_anchor = _first_present(
            latest_signal,
            ("k_anchor_after",),
            default=getattr(persistent, "k_anchor", None),
        )
        g_value = _first_present(
            snapshot,
            ("current_g", "g"),
            default=getattr(latest_signal, "g", 0),
        )
        holder = _first_present(
            snapshot,
            ("holder_matches", "holder_match", "is_holder"),
            default=False,
        )
        holder_id = getattr(snapshot, "qualification_holder_id", None)
        labels["digital_life_id"].setText(str(getattr(snapshot, "digital_life_id", life_id)))
        labels["role"].setText(str(getattr(snapshot, "role", life_id.removeprefix("life-"))))
        labels["g"].setText(str(g_value))
        labels["holder"].setText(
            str(holder_id) if holder_id is not None else ("self" if holder else "—")
        )
        labels["curiosity"].setText(_format_number(profile.curiosity))
        labels["sigma_range"].setText(
            f"{profile.sigma_min:.6f} / {profile.sigma_max:.6f}"
        )
        labels["epsilon_accept"].setText(_format_number(profile.epsilon_accept))
        labels["p_explore_min"].setText(_format_number(profile.p_explore_min))
        labels["k_anchor"].setText(_format_vector(current_anchor))
        labels["k_current"].setText(_format_vector(current_k))
        labels["trial_count"].setText(str(getattr(persistent, "trial_count", "—")))
        labels["session_count"].setText(str(getattr(persistent, "session_count", "—")))
        labels["adaptation_phase"].setText(str(session.adaptation_phase))
        labels["exploration_decision"].setText(_format_text(session.exploration_decision))
        labels["w_anchor_session"].setText(_format_number(session.w_anchor_session))
        labels["k_trial"].setText(_format_vector(session.k_trial))
        labels["w_trial_1"].setText(_format_number(session.w_trial_1))
        labels["w_trial_2"].setText(_format_number(session.w_trial_2))
        labels["adoption_result"].setText(str(session.adoption_result))

    def _update_parameter_card(
        self,
        life_id: str,
        component: Any,
        session: Any,
        transitions: tuple[Any, ...],
    ) -> None:
        labels = self.parameter_value_labels[life_id]
        profile = component.relation_memory_intrinsic_profile()
        direction_record = next(
            (
                record
                for record in reversed(transitions)
                if getattr(record, "direction_trial_index", None) is not None
            ),
            None,
        )
        labels["curiosity"].setText(_format_number(profile.curiosity))
        labels["sigma"].setText(_format_number(session.sigma))
        labels["p_explore"].setText(_format_number(session.p_explore))
        labels["u_explore"].setText(_format_number(session.u_explore))
        labels["direction_u_f"].setText(
            _format_number(getattr(direction_record, "direction_u_f", None))
        )
        labels["direction_u_t"].setText(
            _format_number(getattr(direction_record, "direction_u_t", None))
        )
        labels["direction_xi"].setText(_format_vector(session.direction_xi))
        labels["direction_trial_index"].setText(
            _format_text(getattr(direction_record, "direction_trial_index", None))
        )
        labels["session_count_used"].setText(str(session.session_count_used))

    def _ordered_components(self) -> tuple[tuple[str, Any], ...]:
        return tuple(
            sorted(
                self._components.items(),
                key=lambda item: _ROLE_ORDER.get(
                    str(getattr(item[1].snapshot(), "role", "")),
                    99,
                ),
            )
        )


ConfirmedRelationMemoryPanel = RelationMemoryPanel


def _notice(text: str, name: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _configure_table(table: QTableView, model: Any) -> None:
    table.setModel(model)
    table.setMinimumHeight(RELATION_MEMORY_TABLE_MIN_HEIGHT)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)


def _validated_components(values: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        raise TypeError("digital_life_components must be a mapping")
    selected = dict(values)
    if len(selected) != 3:
        raise ValueError("Stage 5C GUI requires exactly three Digital Lives")
    required_methods = (
        "relation_memory_intrinsic_profile",
        "relation_memory_session_state",
        "relation_memory_transition_records",
        "adaptive_signal_records",
        "initial_persistent_state",
        "final_persistent_state",
        "snapshot",
    )
    for life_id, component in selected.items():
        if not isinstance(life_id, str) or not life_id:
            raise ValueError("Digital Life IDs must be non-empty strings")
        missing = [
            name
            for name in required_methods
            if not callable(getattr(component, name, None))
        ]
        if missing:
            raise TypeError(
                f"{life_id} is missing relation-memory GUI API: {', '.join(missing)}"
            )
    return selected


def _optional_record_source(value: Any | None, method_name: str) -> Any | None:
    if value is not None and not callable(getattr(value, method_name, None)):
        raise TypeError(f"formal output source must provide {method_name}()")
    return value


def _visible_optimum(
    preset_name: str,
    value: tuple[float, float] | None,
) -> tuple[float, float] | None:
    if preset_name != "off_center_green" or value is None:
        return None
    if len(value) != 2 or any(not 0.0 <= float(item) <= 1.0 for item in value):
        raise ValueError("diagnostic_optimum_ft must contain two unit values")
    return float(value[0]), float(value[1])


def _combined_records(
    records_by_id: Mapping[str, Sequence[Any]],
    index_field: str,
) -> tuple[Any, ...]:
    return tuple(
        sorted(
            (record for records in records_by_id.values() for record in records),
            key=lambda record: (
                getattr(record, "signal_index", 0),
                getattr(record, index_field, 0),
                getattr(record, "digital_life_id", ""),
            ),
        )
    )


def _persistent_projections(
    initial_by_id: Mapping[str, Any],
    final_by_id: Mapping[str, Any | None],
) -> tuple[_PersistentStateProjection, ...]:
    records: list[_PersistentStateProjection] = []
    for life_id in sorted(initial_by_id):
        records.append(_state_projection("before", initial_by_id[life_id]))
        if (final := final_by_id.get(life_id)) is not None:
            records.append(_state_projection("after", final))
    return tuple(records)


def _state_projection(position: str, state: Any) -> _PersistentStateProjection:
    return _PersistentStateProjection(
        state_position=position,
        digital_life_id=state.digital_life_id,
        k_anchor=tuple(state.k_anchor),
        q=state.q,
        e=state.e,
        trial_count=state.trial_count,
        session_count=state.session_count,
        profile_version=state.profile_version,
        algorithm_version=state.algorithm_version,
        state_schema_version=state.state_schema_version,
    )


def _first_present(record: Any, fields: tuple[str, ...], *, default: Any) -> Any:
    if record is not None:
        for field in fields:
            if hasattr(record, field):
                return getattr(record, field)
    return default


def _format_number(value: Any | None) -> str:
    return "—" if value is None else f"{float(value):.6f}"


def _format_vector(value: Any | None) -> str:
    if value is None:
        return "—"
    return "[" + ", ".join(f"{float(item):.6f}" for item in value) + "]"


def _format_text(value: Any | None) -> str:
    return "—" if value is None else str(value)


__all__ = [
    "BASELINE_NOTICE",
    "ConfirmedRelationMemoryPanel",
    "DESCRIPTION",
    "OPTIMUM_NON_INPUT_NOTICE",
    "OWNERSHIP_NOTICE",
    "RELATION_MEMORY_CHART_TABLE_SPLITTER_MIN_HEIGHT",
    "RELATION_MEMORY_TABLE_MIN_HEIGHT",
    "RELATION_MEMORY_TABLE_TABS_MIN_HEIGHT",
    "RelationMemoryPanel",
]
