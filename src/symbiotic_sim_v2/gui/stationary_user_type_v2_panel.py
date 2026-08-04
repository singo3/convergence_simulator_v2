"""Record-backed Stage 8A.1 fixed-user profile and hidden-truth map."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
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

STAGE8A1_USER_TYPE_CONTENT_MIN_HEIGHT = 1_260
STAGE8A1_USER_TYPE_HEATMAP_MIN_HEIGHT = 720
STAGE8A1_USER_TYPE_TABLE_MIN_HEIGHT = 300

LIFE_BAND_COLORS = {
    "life-red": (251, 113, 133, 42),
    "life-green": (52, 211, 153, 42),
    "life-blue": (96, 165, 250, 42),
}


class StationaryPeakV2TableModel(ImmutableProjectionTableModel):
    """Immutable neutral/Gaussian axis parameters for every fixed peak."""

    FIELDS = (
        "peak_id",
        "hue_axis_mode",
        "preferred_hue_degree",
        "hue_sigma_degree",
        "bpm_axis_mode",
        "preferred_blink_bpm",
        "blink_sigma_bpm",
        "peak_weight",
    )
    HEADERS = (
        "peak ID",
        "Hue axis",
        "preferred Hue",
        "Hue sigma",
        "BPM axis",
        "preferred BPM",
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


class StationaryUserTypeV2Panel(QWidget):
    """Display only core-projected hidden truth; no preference formula lives here."""

    user_type_selected = Signal(str)

    def __init__(
        self,
        profiles: Mapping[str, Any] | Sequence[Any],
        heatmap_projections: Mapping[str, Any],
        parent: QWidget | None = None,
        *,
        selected_user_type_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stage8a1StationaryUserTypeV2Panel")
        self._profiles = _profile_mapping(profiles)
        self._heatmap_projections = _projection_mapping(heatmap_projections)
        if set(self._profiles) != set(self._heatmap_projections):
            raise ValueError("every user type v2 requires one matching heatmap projection")
        self._band_items: list[pg.LinearRegionItem] = []
        self._band_labels: list[pg.TextItem] = []
        self._attractor_lines: list[pg.InfiniteLine] = []
        self._build_ui()
        self.set_profiles(
            self._profiles,
            self._heatmap_projections,
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
        self.diagnostics_scroll = QScrollArea(self)
        self.diagnostics_scroll.setObjectName("stage8a1StationaryV2Scroll")
        self.diagnostics_scroll.setWidgetResizable(True)
        self.diagnostics_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.diagnostics_content = QWidget(self.diagnostics_scroll)
        self.diagnostics_content.setObjectName("stage8a1StationaryV2Content")
        self.diagnostics_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        content = QVBoxLayout(self.diagnostics_content)
        content.setContentsMargins(5, 5, 5, 5)
        content.setSpacing(8)
        content.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

        self.stationary_notice = _notice(
            "Stage 8A.1 stationary user type v2: 固定presetはrun中に変化しません。"
            "moving preferenceとpeak自由編集は実装していません。",
            "stage8a1StationaryV2Notice",
            self.diagnostics_content,
        )
        self.hidden_truth_notice = _notice(
            "この地図はシミュレーターだけが知る固定された隠れた反応傾向で、"
            "Digital Life、Runtime、Gardenの探索計算には入力されません。",
            "stage8a1StationaryV2HiddenTruthNotice",
            self.diagnostics_content,
        )
        content.addWidget(self.stationary_notice)
        content.addWidget(self.hidden_truth_notice)

        self.profile_frame = QFrame(self.diagnostics_content)
        self.profile_frame.setObjectName("stage8a1StationaryV2ProfileFrame")
        profile_form = QFormLayout(self.profile_frame)
        profile_form.setContentsMargins(10, 9, 10, 9)
        self.user_type_combo = QComboBox(self.profile_frame)
        self.user_type_combo.setObjectName("stage8a1StationaryV2Combo")
        profile_form.addRow("固定仮想ユーザータイプ", self.user_type_combo)
        self.profile_labels: dict[str, QLabel] = {}
        fields = (
            ("user_type_id", "profile ID"),
            ("expected_structure", "expected structure"),
            ("expected_dominant_life_id", "expected dominant life"),
            ("expected_attractor_count", "expected attractor count"),
            ("peak_count", "peak count"),
            ("physiology", "physiology gains"),
            ("dynamics", "onset / recovery"),
            ("versions", "profile / landscape versions"),
        )
        for name, caption in fields:
            label = QLabel("—", self.profile_frame)
            label.setObjectName("stage8a1StationaryV2Value")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            profile_form.addRow(caption, label)
            self.profile_labels[name] = label
        content.addWidget(self.profile_frame)

        self.chart_table_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.diagnostics_content,
        )
        self.chart_table_splitter.setObjectName("stage8a1StationaryV2Splitter")
        self.chart_table_splitter.setMinimumHeight(
            STAGE8A1_USER_TYPE_CONTENT_MIN_HEIGHT
        )
        self.heatmap_widget = pg.GraphicsLayoutWidget(self.chart_table_splitter)
        self.heatmap_widget.setObjectName("stage8a1StationaryV2Heatmap")
        self.heatmap_widget.setMinimumHeight(STAGE8A1_USER_TYPE_HEATMAP_MIN_HEIGHT)
        self.heatmap_widget.setBackground("#111827")
        self.heatmap_plot = self.heatmap_widget.addPlot(row=0, col=0)
        self.heatmap_plot.setTitle(
            "fixed preference match / output Hue bands / expected attractors",
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
        self.heatmap_image.setLookupTable(
            color_map.getLookupTable(0.0, 1.0, 256)
        )
        self.heatmap_image.setLevels((0.0, 1.0))
        self.expected_attractor_points = self.heatmap_plot.plot(
            pen=None,
            symbol="x",
            symbolSize=19,
            symbolPen=pg.mkPen("#FFFFFF", width=3),
        )

        peak_group = QGroupBox(
            "固定peak（neutral軸はpreferred value / sigma = null）",
            self.chart_table_splitter,
        )
        peak_layout = QVBoxLayout(peak_group)
        self.attractor_summary = QLabel("—", peak_group)
        self.attractor_summary.setObjectName("stage8a1ExpectedAttractorSummary")
        self.attractor_summary.setWordWrap(True)
        peak_layout.addWidget(self.attractor_summary)
        self.peak_model = StationaryPeakV2TableModel(self)
        self.peak_table = QTableView(peak_group)
        self.peak_table.setObjectName("stage8a1StationaryV2PeakTable")
        self.peak_table.setModel(self.peak_model)
        self.peak_table.setMinimumHeight(STAGE8A1_USER_TYPE_TABLE_MIN_HEIGHT)
        self.peak_table.setAlternatingRowColors(True)
        self.peak_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.peak_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self.peak_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        peak_layout.addWidget(self.peak_table)
        self.chart_table_splitter.addWidget(self.heatmap_widget)
        self.chart_table_splitter.addWidget(peak_group)
        self.chart_table_splitter.setCollapsible(0, False)
        self.chart_table_splitter.setCollapsible(1, False)
        self.chart_table_splitter.setSizes([860, 400])
        content.addWidget(self.chart_table_splitter)

        self.diagnostics_scroll.setWidget(self.diagnostics_content)
        self.heatmap_widget.viewport().installEventFilter(self)
        root.addWidget(self.diagnostics_scroll)
        self.user_type_combo.currentIndexChanged.connect(self._selection_changed)
        self.setStyleSheet(
            """
            QLabel#stage8a1StationaryV2Notice {
                background: #E8F1FF; border: 1px solid #B9D2F5;
                border-radius: 6px; color: #234A75; padding: 7px 10px;
            }
            QLabel#stage8a1StationaryV2HiddenTruthNotice {
                background: #FFF7E6; border: 1px solid #F5D28A;
                border-radius: 6px; color: #6B4B16; padding: 7px 10px;
            }
            QFrame#stage8a1StationaryV2ProfileFrame {
                background: #F8FAFC; border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
            QLabel#stage8a1StationaryV2Value {
                color: #172033; font-weight: 700;
            }
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
        heatmap_projections: Mapping[str, Any],
        *,
        selected_user_type_id: str | None = None,
    ) -> None:
        selected_before = selected_user_type_id or self.selected_user_type_id
        selected_profiles = _profile_mapping(profiles)
        selected_projections = _projection_mapping(heatmap_projections)
        if set(selected_profiles) != set(selected_projections):
            raise ValueError("every user type v2 requires one matching heatmap projection")
        self._profiles = selected_profiles
        self._heatmap_projections = selected_projections
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
            raise ValueError(f"unknown stationary user type v2: {user_type_id}")
        index = self.user_type_combo.findData(user_type_id)
        if index != self.user_type_combo.currentIndex():
            self.user_type_combo.setCurrentIndex(index)
        else:
            self._refresh_selected_profile()

    def set_settings_editable(self, editable: bool) -> None:
        if not isinstance(editable, bool):
            raise TypeError("editable must be boolean")
        self.user_type_combo.setEnabled(editable)

    def _selection_changed(self, _index: int) -> None:
        self._refresh_selected_profile()
        if self.selected_user_type_id is not None:
            self.user_type_selected.emit(self.selected_user_type_id)

    def _refresh_selected_profile(self) -> None:
        profile = self.selected_profile
        selected = self.selected_user_type_id
        if profile is None or selected is None:
            self.peak_model.clear()
            self.heatmap_image.clear()
            return
        peaks = tuple(record_value(profile, "peaks", ()) or ())
        self.profile_labels["user_type_id"].setText(selected)
        self.profile_labels["expected_structure"].setText(
            str(record_value(profile, "expected_structure", "—"))
        )
        self.profile_labels["expected_dominant_life_id"].setText(
            str(record_value(profile, "expected_dominant_life_id", None) or "—")
        )
        self.profile_labels["expected_attractor_count"].setText(
            str(record_value(profile, "expected_attractor_count", None) or "—")
        )
        self.profile_labels["peak_count"].setText(str(len(peaks)))
        rsa = record_value(profile, "maximum_respiratory_amplitude_gain_ms", None)
        mean = record_value(profile, "maximum_mean_rri_increase_ms", None)
        self.profile_labels["physiology"].setText(
            f"maximum RSA gain={_number(rsa)} ms / "
            f"maximum mean RRI increase={_number(mean)} ms"
        )
        onset = record_value(profile, "onset_time_constant_seconds", None)
        recovery = record_value(profile, "recovery_time_constant_seconds", None)
        self.profile_labels["dynamics"].setText(
            f"onset={_number(onset)} s / recovery={_number(recovery)} s"
        )
        versions = tuple(
            (name, record_value(profile, name, None))
            for name in (
                "landscape_version",
                "peak_model_version",
                "multi_peak_combination_version",
                "schema_version",
            )
        )
        self.profile_labels["versions"].setText(
            "; ".join(f"{name}={value}" for name, value in versions if value is not None)
            or "—"
        )
        self.peak_model.set_records(peaks)
        self._set_expected_attractors(peaks)
        self._set_heatmap(self._heatmap_projections[selected])

    def _set_heatmap(self, projection: Any) -> None:
        rows = record_value(projection, "preference_match_rows", ())
        hue_values = tuple(record_value(projection, "hue_values_degree", ()) or ())
        bpm_values = tuple(record_value(projection, "blink_bpm_values", ()) or ())
        values = np.asarray(rows, dtype=float)
        if values.shape != (len(bpm_values), len(hue_values)) or values.size == 0:
            raise ValueError("invalid Stage 8A.1 heatmap projection shape")
        self.heatmap_image.setImage(values, autoLevels=False, levels=(0.0, 1.0))
        self.heatmap_image.setRect(
            QRectF(
                float(hue_values[0]),
                float(bpm_values[0]),
                float(hue_values[-1] - hue_values[0]),
                float(bpm_values[-1] - bpm_values[0]),
            )
        )
        self.heatmap_shape = values.shape
        self.heatmap_minimum = float(values.min())
        self.heatmap_maximum = float(values.max())
        self._replace_life_bands(
            tuple(record_value(projection, "life_hue_bands", ()) or ())
        )

    def _replace_life_bands(self, bands: tuple[Any, ...]) -> None:
        for item in (*self._band_items, *self._band_labels):
            self.heatmap_plot.removeItem(item)
        self._band_items.clear()
        self._band_labels.clear()
        for raw_band in bands:
            life_id, lower, upper = raw_band
            color = LIFE_BAND_COLORS.get(str(life_id), (255, 255, 255, 35))
            region = pg.LinearRegionItem(
                values=(float(lower), float(upper)),
                orientation="vertical",
                movable=False,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color[:3], width=1),
            )
            region.setZValue(5)
            label = pg.TextItem(str(life_id), color=color[:3], anchor=(0.5, 0.0))
            label.setPos((float(lower) + float(upper)) / 2.0, 162.0)
            label.setZValue(8)
            self.heatmap_plot.addItem(region)
            self.heatmap_plot.addItem(label)
            self._band_items.append(region)
            self._band_labels.append(label)

    def _set_expected_attractors(self, peaks: tuple[Any, ...]) -> None:
        for line in self._attractor_lines:
            self.heatmap_plot.removeItem(line)
        self._attractor_lines.clear()
        points_x: list[float] = []
        points_y: list[float] = []
        summaries: list[str] = []
        for peak in peaks:
            peak_id = str(record_value(peak, "peak_id"))
            hue_mode = str(record_value(peak, "hue_axis_mode"))
            bpm_mode = str(record_value(peak, "bpm_axis_mode"))
            hue = record_value(peak, "preferred_hue_degree", None)
            bpm = record_value(peak, "preferred_blink_bpm", None)
            if hue_mode == "gaussian" and bpm_mode == "gaussian":
                points_x.append(float(hue))
                points_y.append(float(bpm))
                summaries.append(f"{peak_id}: Hue {hue}° / BPM {bpm}")
            elif hue_mode == "gaussian":
                line = pg.InfiniteLine(
                    pos=float(hue),
                    angle=90,
                    movable=False,
                    pen=pg.mkPen("#FFFFFF", width=2, style=Qt.PenStyle.DashLine),
                )
                self.heatmap_plot.addItem(line)
                self._attractor_lines.append(line)
                summaries.append(f"{peak_id}: Hue {hue}° / BPM neutral")
            elif bpm_mode == "gaussian":
                line = pg.InfiniteLine(
                    pos=float(bpm),
                    angle=0,
                    movable=False,
                    pen=pg.mkPen("#FFFFFF", width=2, style=Qt.PenStyle.DashLine),
                )
                self.heatmap_plot.addItem(line)
                self._attractor_lines.append(line)
                summaries.append(f"{peak_id}: Hue neutral / BPM {bpm}")
        self.expected_attractor_points.setData(points_x, points_y)
        self.attractor_summary.setText(
            "expected attractor: " + ("; ".join(summaries) if summaries else "none")
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
            raise ValueError("stationary user type v2 IDs must be non-empty strings")
        if record_value(profile, "user_type_id", user_type_id) != user_type_id:
            raise ValueError("profile ID does not match its mapping key")
    return selected


def _projection_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        raise TypeError("heatmap projections must be a mapping")
    selected = dict(values)
    for user_type_id, projection in selected.items():
        if record_value(projection, "user_type_id", None) != user_type_id:
            raise ValueError("heatmap projection ID does not match its mapping key")
    return selected


def _notice(text: str, name: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _number(value: Any) -> str:
    return "—" if value is None else f"{float(value):.3f}"


__all__ = [
    "STAGE8A1_USER_TYPE_CONTENT_MIN_HEIGHT",
    "STAGE8A1_USER_TYPE_HEATMAP_MIN_HEIGHT",
    "STAGE8A1_USER_TYPE_TABLE_MIN_HEIGHT",
    "StationaryPeakV2TableModel",
    "StationaryUserTypeV2Panel",
]
