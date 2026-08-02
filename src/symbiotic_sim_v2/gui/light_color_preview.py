"""GUI-only HSV preview for the Stage 6 virtual light device."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class LightColorPreview(QWidget):
    """Paint one optional live HSV frame without storing RGB in the core."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lightColorPreview")
        self.setMinimumSize(320, 250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._active = False
        self._live_preview_enabled = False
        self._render_hue_degree: float | None = None
        self._saturation = 0.0
        self._value = 0.0
        self._display_color = QColor("#000000")

    @property
    def live_preview_enabled(self) -> bool:
        return self._live_preview_enabled

    @property
    def display_color(self) -> QColor:
        """Return a defensive GUI-only QColor copy for widget tests."""

        return QColor(self._display_color)

    def set_light_state(self, state: Any, *, live_preview_enabled: bool) -> None:
        """Render a supplied formal state; never calculate phase or B-to-I here."""

        self._active = bool(getattr(state, "active", False))
        self._live_preview_enabled = bool(live_preview_enabled and self._active)
        self._render_hue_degree = getattr(state, "render_hue_degree", None)
        self._saturation = float(getattr(state, "saturation", 0.0) or 0.0)
        self._value = float(getattr(state, "current_value", 0.0) or 0.0)

        if self._live_preview_enabled and self._render_hue_degree is not None:
            hue_turn = (float(self._render_hue_degree) % 360.0) / 360.0
            self._display_color = QColor.fromHsvF(
                hue_turn,
                min(1.0, max(0.0, self._saturation)),
                min(1.0, max(0.0, self._value)),
            )
        else:
            self._display_color = QColor("#000000")
        self.update()

    def clear(self) -> None:
        self._active = False
        self._live_preview_enabled = False
        self._render_hue_degree = None
        self._saturation = 0.0
        self._value = 0.0
        self._display_color = QColor("#000000")
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(4.0, 4.0, -4.0, -4.0)
        painter.setPen(QPen(QColor("#64748B"), 2.0))
        painter.setBrush(self._display_color)
        painter.drawRoundedRect(rect, 12.0, 12.0)

        painter.setPen(QColor("#FFFFFF"))
        font = QFont(painter.font())
        font.setBold(True)
        font.setPointSize(max(11, font.pointSize()))
        painter.setFont(font)
        if self._live_preview_enabled:
            label = "実光プレビュー ON"
        elif self._active:
            label = "実光プレビュー OFF"
        else:
            label = "LIGHT OFF"
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignCenter),
            label,
        )
        painter.end()
        event.accept()
