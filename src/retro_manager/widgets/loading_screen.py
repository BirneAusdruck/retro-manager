"""Anzeige während des Docker-Starts."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class LoadingScreen(QWidget):
    """Fortschrittsanzeige, solange RomM startet."""

    closed_by_user = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.setObjectName("loadingScreen")
        self.setWindowTitle(self.tr("Retro Manager"))
        self.setMinimumWidth(420)

        self._label = QLabel(self.tr("RomM wird gestartet …"))
        self._label.setObjectName("loadingLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)

        progress = QProgressBar()
        progress.setObjectName("loadingProgress")
        progress.setRange(0, 0)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(progress)

    def _connect_signals(self) -> None:
        pass

    def set_status(self, text: str) -> None:
        """Zeigt den aktuellen Startschritt an."""
        self._label.setText(text)

    def closeEvent(self, event: QCloseEvent) -> None:
        # Nur Schließen durch den Nutzer melden, nicht programmatisches close().
        if event.spontaneous():
            self.closed_by_user.emit()
        super().closeEvent(event)
