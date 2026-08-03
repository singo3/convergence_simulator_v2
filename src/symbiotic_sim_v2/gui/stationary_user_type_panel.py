"""Stage 8A fixed-user-type inspector and simulation-only landscape heatmap."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from symbiotic_sim_v2.gui.session_history_table_model import (
    ImmutableProjectionTableModel,
    first_record_value,
    record_value,
)

STATIONARY_USER_HEATMAP_MIN_HEIGHT = 720
STATIONARY_USER_PANEL_CONTENT_MIN_HEIGHT = 1_180
STATIONARY_USER_TABLE_MIN_HEIGHT = 300

ROLE_HUE_BANDS = {
    "red": (0.0, 10.0),
    "green": (120.0, 130.0),
    "blue": (245.0, 255.0),
}
ROLE_COLORS = {
    "red": (251, 113, 133, 45),
    "green": (52, 211, 153, 45),
    "blue": (96, 165, 250, 45),
}


class StationaryPeakTableModel(ImmutableProjectionTableModel):
    """Display every immutable peak parameter of the selected profile."""

    FIELDS = (
        "peak_id",
        "preferred_hue_degree",
        "preferred_blink_bpm",
        "hue_sigma_degree",
        "blink_sigma_bpm",
        "peak_weight",
    )
    HEADERS = (
        "peak ID",
        "preferred Hue",
        "preferred BPM",
        "Hue sigma",
        "BPM sigma",
        "weight",
    )

    def set_records(self, peaks: Sequence[Any]) -> None:
        self.set_projected_rows(
            tuple(
                {field: record_value(peak, field) for field in self.FIELDS}
                for peak in peaks
            )
        )


class StationaryUserTypePanel(QWidget):
    """Render hidden stationary landscapes while exposing no algorithm input seam."""

    user_type_selected = Signal(str)

    def __init__(
        self,
        profiles: Mapping[str, Any] | Sequence[Any],
        parent: QWidget | None = None,
        *,
        selected_user_type_id: str | None = None,
        landscape_evaluator: Callable[..., Any] | None = None,
        role_hue_bands: Mapping[str, tuple[float, float]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._profiles = _profile_mapping(profiles)
        self._landscape_evaluator = landscape_evaluator
        self._role_hue_bands = dict(role_hue_bands or ROLE_HUE_BANDS)
        self._heatmap_cache: dict[str, np.ndarray] = {}
        self._settings_editable = True
        self._build_ui()
        self.set_profiles(
            self._profiles,
            selected_user_type_id=selected_user_type_id,
        )

    @property
    def selected_user_type_id(self) -> str | None:
        value = self.user_type_combo.currentData()
        return None if value is None else str(value)

    @property
    def selected_profile(self) -> Any | None:
        selected = self.selected_user_type_id
        return None if selected is None else self._profiles.get(selected)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("stationaryUserTypeDiagnosticsScroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("stationaryUserTypeDiagnosticsContent")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(4, 4, 4, 4)
        content.setSpacing(8)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.description_notice = _notice(
            "固定presetの好み地形はmulti-session run中に変化しません。",
            "stationaryUserTypeDescription",
            self.diagnostics_content,
        )
        self.hidden_truth_notice = _notice(
            "この地図はシミュレーターだけが知る隠れた正解で、"
            "Digital Lifeの探索計算には入力されません。",
            "stationaryUserTypeHiddenTruthNotice",
            self.diagnostics_content,
        )
        self.preset_only_notice = _notice(
            "Stage 8Aではpreset選択だけを行い、peakの自由編集は行いません。",
            "stationaryUserTypePresetOnlyNotice",
            self.diagnostics_content,
        )
        for notice in (
            self.description_notice,
            self.hidden_truth_notice,
            self.preset_only_notice,
        ):
            content.addWidget(notice)

        self.profile_frame = QFrame(self.diagnostics_content)
        self.profile_frame.setObjectName("stationaryUserTypeProfileFrame")
        profile_layout = QHBoxLayout(self.profile_frame)
        profile_layout.setContentsMargins(10, 9, 10, 9)
        profile_layout.setSpacing(12)
        selector_form = QFormLayout()
        self.user_type_combo = QComboBox(self.profile_frame)
        self.user_type_combo.setObjectName("stationaryUserTypeCombo")
        selector_form.addRow("user type", self.user_type_combo)
        profile_layout.addLayout(selector_form, stretch=1)

        values_form = QFormLayout()
        self.profile_labels: dict[str, QLabel] = {}
        fields = (
            ("user_type_id", "ID"),
            ("display_name_ja", "表示名"),
            ("description_ja", "説明"),
            ("peak_count", "peak数"),
            ("rsa_gain", "RSA gain"),
            ("mean_rri_gain", "mean RRI gain"),
            ("onset", "onset"),
            ("recovery", "recovery"),
            ("versions", "model versions"),
        )
        for key, caption in fields:
            label = QLabel("—", self.profile_frame)
            label.setObjectName("stationaryUserTypeValue")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            values_form.addRow(caption, label)
            self.profile_labels[key] = label
        profile_layout.addLayout(values_form, stretch=3)
        content.addWidget(self.profile_frame)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("stationaryUserTypeChartTableSplitter")
        self.chart_table_splitter.setMinimumHeight(
            STATIONARY_USER_PANEL_CONTENT_MIN_HEIGHT
        )
        self.heatmap_widget = pg.GraphicsLayoutWidget(self.chart_table_splitter)
        self.heatmap_widget.setObjectName("stationaryUserTypeLandscapeHeatmap")
        self.heatmap_widget.setMinimumHeight(STATIONARY_USER_HEATMAP_MIN_HEIGHT)
        self.heatmap_widget.setBackground("#111827")
        self.heatmap_plot = self.heatmap_widget.addPlot(row=0, col=0)
        self.heatmap_plot.setTitle(
            "stationary preference match — simulation-only hidden truth",
            color="#E5E7EB",
            size="12pt",
        )
        self.heatmap_plot.setLabel("bottom", "Hue", units="degree")
        self.heatmap_plot.setLabel("left", "blink BPM")
        self.heatmap_plot.setXRange(0.0, 360.0, padding=0)
        self.heatmap_plot.setYRange(10.0, 165.0, padding=0)
        self.heatmap_plot.showGrid(x=True, y=True, alpha=0.12)
        self.heatmap_image = pg.ImageItem(axisOrder="row-major")
        self.heatmap_plot.addItem(self.heatmap_image)
        color_map = pg.colormap.get("viridis")
        self.heatmap_image.setLookupTable(color_map.getLookupTable(0.0, 1.0, 256))
        self.heatmap_image.setLevels((0.0, 1.0))
        self.role_band_items: dict[str, pg.LinearRegionItem] = {}
        for role, limits in self._role_hue_bands.items():
            color = ROLE_COLORS.get(role, (255, 255, 255, 35))
            region = pg.LinearRegionItem(
                values=limits,
                orientation="vertical",
                movable=False,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color[:3], width=1),
            )
            region.setZValue(5)
            self.heatmap_plot.addItem(region)
            self.role_band_items[role] = region
        self.peak_item = self.heatmap_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=18,
            symbolPen=pg.mkPen("#FFFFFF", width=3),
            name="preference peaks",
        )

        table_group = QGroupBox("固定preference peaks", self.chart_table_splitter)
        table_layout = QVBoxLayout(table_group)
        self.peak_model = StationaryPeakTableModel(self)
        self.peak_table = QTableView(table_group)
        self.peak_table.setObjectName("stationaryUserTypePeakTable")
        self.peak_table.setModel(self.peak_model)
        self.peak_table.setMinimumHeight(STATIONARY_USER_TABLE_MIN_HEIGHT)
        self.peak_table.setAlternatingRowColors(True)
        self.peak_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.peak_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self.peak_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table_layout.addWidget(self.peak_table)

        self.chart_table_splitter.addWidget(self.heatmap_widget)
        self.chart_table_splitter.addWidget(table_group)
        self.chart_table_splitter.setCollapsible(0, False)
        self.chart_table_splitter.setCollapsible(1, False)
        self.chart_table_splitter.setStretchFactor(0, 1)
        self.chart_table_splitter.setStretchFactor(1, 0)
        self.chart_table_splitter.setSizes([820, 360])
        content.addWidget(self.chart_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self.heatmap_widget.viewport().installEventFilter(self)
        root.addWidget(self.diagnostics_scroll, stretch=1)

        self.user_type_combo.currentIndexChanged.connect(self._selection_changed)
        self.setStyleSheet(
            """
                QLabel#stationaryUserTypeDescription {
                    background: #E8F1FF; border: 1px solid #B9D2F5;
                    border-radius: 6px; color: #234A75; padding: 7px 10px;
                }
                QLabel#stationaryUserTypeHiddenTruthNotice,
                QLabel#stationaryUserTypePresetOnlyNotice {
                    background: #FFF7E6; border: 1px solid #F5D28A;
                    border-radius: 6px; color: #6B4B16; padding: 7px 10px;
                }
                QFrame#stationaryUserTypeProfileFrame {
                    background: #F8FAFC; border: 1px solid #CBD5E1;
                    border-radius: 8px;
                }
                QLabel#stationaryUserTypeValue { color: #172033; font-weight: 700; }
            """
        )

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.heatmap_widget.viewport() and event.type() is QEvent.Type.Wheel:
            delta = event.pixelDelta().y() or event.angleDelta().y()
            if delta:
                bar = self.diagnostics_scroll.verticalScrollBar()
                bar.setValue(bar.value() - delta)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def set_profiles(
        self,
        profiles: Mapping[str, Any] | Sequence[Any],
        *,
        selected_user_type_id: str | None = None,
    ) -> None:
        selected_before = selected_user_type_id or self.selected_user_type_id
        self._heatmap_cache.clear()
        self._profiles = _profile_mapping(profiles)
        self.user_type_combo.blockSignals(True)
        self.user_type_combo.clear()
        for user_type_id, profile in self._profiles.items():
            display = first_record_value(
                profile,
                ("display_name_ja", "display_name"),
                user_type_id,
            )
            self.user_type_combo.addItem(f"{display}  ({user_type_id})", user_type_id)
        if selected_before in self._profiles:
            self.user_type_combo.setCurrentIndex(
                self.user_type_combo.findData(selected_before)
            )
        self.user_type_combo.blockSignals(False)
        self._refresh_selected_profile()

    def set_selected_user_type(self, user_type_id: str) -> None:
        if user_type_id not in self._profiles:
            raise ValueError(f"unknown stationary user type: {user_type_id}")
        index = self.user_type_combo.findData(user_type_id)
        self.user_type_combo.setCurrentIndex(index)
        self._refresh_selected_profile()

    def set_settings_editable(self, editable: bool) -> None:
        if not isinstance(editable, bool):
            raise TypeError("editable must be boolean")
        self._settings_editable = editable
        self.user_type_combo.setEnabled(editable)

    def _selection_changed(self, _index: int) -> None:
        self._refresh_selected_profile()
        selected = self.selected_user_type_id
        if selected is not None:
            self.user_type_selected.emit(selected)

    def _refresh_selected_profile(self) -> None:
        profile = self.selected_profile
        if profile is None:
            self.peak_model.clear()
            self.heatmap_image.clear()
            for label in self.profile_labels.values():
                label.setText("—")
            self.heatmap_shape = (0, 0)
            return
        peaks = tuple(record_value(profile, "peaks", ()) or ())
        self.profile_labels["user_type_id"].setText(
            str(record_value(profile, "user_type_id", self.selected_user_type_id))
        )
        self.profile_labels["display_name_ja"].setText(
            str(first_record_value(profile, ("display_name_ja", "display_name"), "—"))
        )
        self.profile_labels["description_ja"].setText(
            str(first_record_value(profile, ("description_ja", "description"), "—"))
        )
        self.profile_labels["peak_count"].setText(str(len(peaks)))
        self.profile_labels["rsa_gain"].setText(
            _number(
                record_value(profile, "maximum_respiratory_amplitude_gain_ms"),
                " ms",
            )
        )
        self.profile_labels["mean_rri_gain"].setText(
            _number(record_value(profile, "maximum_mean_rri_increase_ms"), " ms")
        )
        self.profile_labels["onset"].setText(
            _number(
                first_record_value(
                    profile,
                    (
                        "onset_time_constant_seconds",
                        "response_onset_time_constant_seconds",
                    ),
                ),
                " s",
            )
        )
        self.profile_labels["recovery"].setText(
            _number(
                first_record_value(
                    profile,
                    (
                        "recovery_time_constant_seconds",
                        "response_recovery_time_constant_seconds",
                    ),
                ),
                " s",
            )
        )
        versions = first_record_value(
            profile,
            ("model_versions", "versions", "profile_version"),
            None,
        )
        if versions is None:
            version_fields = (
                "landscape_version",
                "peak_model_version",
                "multi_peak_combination_version",
                "schema_version",
            )
            version_values = tuple(
                (name, record_value(profile, name, None)) for name in version_fields
            )
            versions = "; ".join(
                f"{name}={value}"
                for name, value in version_values
                if value is not None
            ) or "—"
        self.profile_labels["versions"].setText(str(versions))
        self.peak_model.set_records(peaks)
        self.peak_item.setData(
            [record_value(peak, "preferred_hue_degree") for peak in peaks],
            [record_value(peak, "preferred_blink_bpm") for peak in peaks],
        )
        self._update_heatmap(profile)

    def _update_heatmap(self, profile: Any) -> None:
        # One-degree sampling includes every preset peak while remaining cheap enough
        # to rebuild synchronously when the stopped/reset-only selector changes.
        profile_id = str(record_value(profile, "user_type_id"))
        values = self._heatmap_cache.get(profile_id)
        if values is None:
            hue_values = np.linspace(0.0, 360.0, 361)
            bpm_values = np.linspace(10.0, 165.0, 63)
            values = np.empty((len(bpm_values), len(hue_values)), dtype=float)
            for bpm_index, bpm in enumerate(bpm_values):
                for hue_index, hue in enumerate(hue_values):
                    values[bpm_index, hue_index] = min(
                        1.0,
                        max(0.0, self._evaluate(profile, float(hue), float(bpm))),
                    )
            self._heatmap_cache[profile_id] = values
        self.heatmap_image.setImage(values, autoLevels=False, levels=(0.0, 1.0))
        self.heatmap_image.setRect(QRectF(0.0, 10.0, 360.0, 155.0))
        self.heatmap_shape = values.shape
        self.heatmap_minimum = float(values.min())
        self.heatmap_maximum = float(values.max())

    def _evaluate(self, profile: Any, hue: float, bpm: float) -> float:
        if self._landscape_evaluator is not None:
            try:
                result = self._landscape_evaluator(
                    profile,
                    active=True,
                    hue_degree=hue,
                    blink_bpm=bpm,
                )
            except TypeError:
                result = self._landscape_evaluator(profile, hue, bpm)
            return float(
                first_record_value(result, ("preference_match", "match"), result)
            )
        evaluator = getattr(profile, "evaluate", None)
        if not callable(evaluator):
            landscape = record_value(profile, "landscape", None)
            evaluator = getattr(landscape, "evaluate", None)
        if not callable(evaluator):
            return 0.0
        try:
            result = evaluator(hue_degree=hue, blink_bpm=bpm, active=True)
        except TypeError:
            result = evaluator(hue, bpm)
        return float(
            first_record_value(result, ("preference_match", "match"), result)
        )


def _profile_mapping(profiles: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
    if isinstance(profiles, Mapping):
        selected = dict(profiles)
    elif isinstance(profiles, Sequence) and not isinstance(profiles, (str, bytes)):
        selected = {
            str(record_value(profile, "user_type_id")): profile for profile in profiles
        }
    else:
        raise TypeError("profiles must be a mapping or sequence")
    for user_type_id, profile in selected.items():
        if not isinstance(user_type_id, str) or not user_type_id:
            raise ValueError("stationary user type IDs must be non-empty strings")
        if record_value(profile, "user_type_id", user_type_id) != user_type_id:
            raise ValueError("profile ID does not match its mapping key")
    return selected


def _notice(text: str, name: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _number(value: Any, suffix: str = "") -> str:
    return "—" if value is None else f"{float(value):.3f}{suffix}"


__all__ = [
    "ROLE_HUE_BANDS",
    "STATIONARY_USER_HEATMAP_MIN_HEIGHT",
    "STATIONARY_USER_PANEL_CONTENT_MIN_HEIGHT",
    "STATIONARY_USER_TABLE_MIN_HEIGHT",
    "StationaryPeakTableModel",
    "StationaryUserTypePanel",
]
