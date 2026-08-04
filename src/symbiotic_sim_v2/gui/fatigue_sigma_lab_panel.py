"""Four-subtab Stage 8A.1 fatigue/sigma/convergence laboratory."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QLayout,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.fatigue_sigma_grid_panel import FatigueSigmaGridPanel
from symbiotic_sim_v2.gui.fatigue_sigma_lab_models import first_record_value
from symbiotic_sim_v2.gui.fatigue_sigma_single_run_panel import (
    DEFAULT_V2_USER_TYPES,
    FatigueSigmaSingleRunPanel,
)
from symbiotic_sim_v2.gui.structured_convergence_panel import (
    StructuredConvergencePanel,
)

LAB_SUBTAB_TITLES = (
    "単一条件",
    "条件比較",
    "収束構造",
    "実験manifest・回帰",
)


class ExperimentManifestPanel(QWidget):
    """Read-only separation of the formal reference and experimental arm."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("stage8a1ManifestContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(5, 5, 5, 5)
        content.setSpacing(8)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.formal_notice = QLabel(
            "formal_spec_adoption=false — v2.0 reference coefficientsの正式変更ではありません。",
            self.diagnostics_content,
        )
        self.formal_notice.setObjectName("stage8a1FormalAdoptionNotice")
        self.formal_notice.setWordWrap(True)
        content.addWidget(self.formal_notice)

        flags_frame = QFrame(self.diagnostics_content)
        flags_frame.setObjectName("stage8a1ManifestFlagsFrame")
        flags_layout = QGridLayout(flags_frame)
        flags = (
            ("stationary_preference", "true"),
            ("moving_preference", "false"),
            ("unselected_full_recovery", "true"),
            ("convergence_is_diagnostic_only", "true"),
            ("exploration_continues_after_convergence", "true"),
            ("p_explore_modified", "false"),
            ("epsilon_accept_modified", "false"),
            ("q_coefficients_modified", "false"),
            ("v2_reference_arm_available", "true"),
            ("Monte_Carlo", "false"),
        )
        self.flag_labels: dict[str, QLabel] = {}
        for index, (name, value) in enumerate(flags):
            caption = QLabel(name, flags_frame)
            selected = QLabel(value, flags_frame)
            selected.setObjectName("stage8a1ManifestFlagValue")
            flags_layout.addWidget(caption, index // 2, (index % 2) * 2)
            flags_layout.addWidget(selected, index // 2, (index % 2) * 2 + 1)
            self.flag_labels[name] = selected
        content.addWidget(flags_frame)

        self.regression_label = QLabel(
            "Stage 1〜8A public factory / CLI / JSON / digest / CSV / GUI / "
            "screenshotを別回帰で監査します。",
            self.diagnostics_content,
        )
        self.regression_label.setWordWrap(True)
        content.addWidget(self.regression_label)
        self.manifest_view = QPlainTextEdit(self.diagnostics_content)
        self.manifest_view.setObjectName("stage8a1ExperimentManifestView")
        self.manifest_view.setReadOnly(True)
        self.manifest_view.setMinimumHeight(520)
        content.addWidget(self.manifest_view)
        self.digest_label = QLabel("—", self.diagnostics_content)
        self.digest_label.setObjectName("stage8a1ManifestDigestLabel")
        self.digest_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.digest_label.setWordWrap(True)
        content.addWidget(self.digest_label)
        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        root.addWidget(self.diagnostics_scroll)
        self.setStyleSheet(
            """
            QLabel#stage8a1FormalAdoptionNotice {
                background: #FFF7E6; border: 1px solid #F5D28A;
                border-radius: 6px; color: #6B4B16; padding: 8px 10px;
            }
            QFrame#stage8a1ManifestFlagsFrame {
                background: #F8FAFC; border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
            QLabel#stage8a1ManifestFlagValue { font-weight: 700; color: #172033; }
            """
        )
        self.set_manifest(_default_manifest())

    def set_manifest(self, manifest: object) -> None:
        values = _serializable(manifest)
        if isinstance(values, Mapping):
            for name, label in self.flag_labels.items():
                if name in values:
                    label.setText(_flag_text(values[name]))
        self.manifest_view.setPlainText(
            json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        )
        digest = first_record_value(
            manifest,
            ("experiment_manifest_digest", "manifest_digest"),
            None,
        )
        self.digest_label.setText(
            "experiment_manifest_digest: —"
            if digest is None
            else f"experiment_manifest_digest: {digest}"
        )


class FatigueSigmaLabPanel(QWidget):
    """Compose all Stage 8A.1 views and relay operation requests."""

    single_next_requested = Signal(object)
    single_run_all_requested = Signal(object)
    single_pause_changed = Signal(bool)
    single_cancel_requested = Signal()
    single_reset_requested = Signal()
    reference_compare_requested = Signal(object)
    save_state_requested = Signal(object)
    load_state_requested = Signal(object)
    export_csv_requested = Signal(object)
    grid_run_requested = Signal(object)
    grid_cancel_requested = Signal()

    def __init__(
        self,
        user_types: Mapping[str, object] | Sequence[str] = DEFAULT_V2_USER_TYPES,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stage8a1FatigueSigmaLabPanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.subtabs = QTabWidget(self)
        self.subtabs.setObjectName("stage8a1LabSubtabs")
        self.single_panel = FatigueSigmaSingleRunPanel(user_types, self.subtabs)
        self.grid_panel = FatigueSigmaGridPanel(user_types, self.subtabs)
        self.structured_panel = StructuredConvergencePanel(self.subtabs)
        self.manifest_panel = ExperimentManifestPanel(self.subtabs)
        for widget, title in zip(
            (
                self.single_panel,
                self.grid_panel,
                self.structured_panel,
                self.manifest_panel,
            ),
            LAB_SUBTAB_TITLES,
            strict=True,
        ):
            self.subtabs.addTab(widget, title)
        root.addWidget(self.subtabs)
        self._relay_signals()

    def _relay_signals(self) -> None:
        self.single_panel.run_next_requested.connect(self.single_next_requested)
        self.single_panel.run_all_requested.connect(self.single_run_all_requested)
        self.single_panel.pause_after_session_changed.connect(self.single_pause_changed)
        self.single_panel.cancel_requested.connect(self.single_cancel_requested)
        self.single_panel.reset_requested.connect(self.single_reset_requested)
        self.single_panel.reference_compare_requested.connect(self.reference_compare_requested)
        self.single_panel.save_state_requested.connect(self.save_state_requested)
        self.single_panel.load_state_requested.connect(self.load_state_requested)
        self.single_panel.export_csv_requested.connect(self.export_csv_requested)
        self.grid_panel.run_requested.connect(self.grid_run_requested)
        self.grid_panel.cancel_requested.connect(self.grid_cancel_requested)

    def set_backend_available(self, available: bool) -> None:
        self.single_panel.set_backend_available(available)
        self.grid_panel.set_backend_available(available)

    def set_single_result(self, result: object) -> None:
        self.single_panel.set_result(result)
        history = (
            first_record_value(
                result,
                ("structured_convergence_history", "structured_convergence_records"),
                (),
            )
            or ()
        )
        truth = first_record_value(
            result,
            ("truth_alignment", "latest_truth_alignment"),
            None,
        )
        mechanical = first_record_value(
            result,
            ("mechanical_rotation_diagnostics",),
            None,
        )
        w_ceiling = first_record_value(result, ("w_ceiling_diagnostics",), None)
        self.structured_panel.set_records(
            tuple(history),
            truth_record=truth,
            mechanical_record=mechanical,
            w_ceiling_record=w_ceiling,
        )
        manifest = first_record_value(result, ("experiment_manifest", "manifest"), None)
        if manifest is not None:
            self.manifest_panel.set_manifest(manifest)

    def set_grid_result(self, result: object) -> None:
        self.grid_panel.set_result(result)
        manifest = first_record_value(result, ("experiment_manifest", "manifest"), None)
        if manifest is not None:
            self.manifest_panel.set_manifest(manifest)

    def reset_views(self) -> None:
        self.single_panel.reset_views()
        self.grid_panel.reset_views()
        self.structured_panel.reset_views()
        self.manifest_panel.set_manifest(_default_manifest())


def _default_manifest() -> dict[str, object]:
    return {
        "formal_spec_adoption": False,
        "base_profile_version": "symbiotic_signal_loop_reference_v1_0",
        "experiment_profile_version": "stage_08a1_fatigue_sigma_experiment_v0_1",
        "stationary_preference": True,
        "moving_preference": False,
        "unselected_full_recovery": True,
        "convergence_is_diagnostic_only": True,
        "exploration_continues_after_convergence": True,
        "p_explore_modified": False,
        "epsilon_accept_modified": False,
        "q_coefficients_modified": False,
        "v2_reference_arm_available": True,
        "Monte_Carlo": False,
    }


def _serializable(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _serializable(to_dict())
    return value


def _flag_text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


__all__ = [
    "LAB_SUBTAB_TITLES",
    "ExperimentManifestPanel",
    "FatigueSigmaLabPanel",
]
