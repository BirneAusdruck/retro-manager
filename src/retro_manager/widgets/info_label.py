"""Feldbeschriftung mit vorangestelltem Info-Symbol, das beim Überfahren eine Erklärung zeigt."""

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStyle, QWidget


class InfoLabel(QWidget):
    """Info-Symbol mit Tooltip, rechts daneben der Feldname."""

    def __init__(self, text: str, info: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui(text, info)

    def _build_ui(self, text: str, info: str) -> None:
        size = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)

        info_icon = QLabel()
        info_icon.setObjectName("infoIcon")
        info_icon.setPixmap(icon.pixmap(size))
        # Als Rich Text, damit Qt lange Erklärungen automatisch umbricht.
        info_icon.setToolTip(f"<p>{escape(info)}</p>")
        info_icon.setCursor(Qt.CursorShape.WhatsThisCursor)

        label = QLabel(text)
        label.setObjectName("infoLabelText")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(info_icon)
        layout.addWidget(label)
