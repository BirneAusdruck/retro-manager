"""Fehlermeldung, wenn der Start nicht abgeschlossen werden kann."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMessageBox, QWidget


class StartupErrorDialog(QMessageBox):
    """Zeigt einen Startfehler mit den Möglichkeiten „Erneut versuchen“ und „Beenden“."""

    retry_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.setObjectName("startupErrorDialog")
        self.setWindowTitle(self.tr("Retro Manager – Start fehlgeschlagen"))
        self.setIcon(QMessageBox.Icon.Critical)
        self._retry_button = self.addButton(
            self.tr("Erneut versuchen"), QMessageBox.ButtonRole.AcceptRole
        )
        self._quit_button = self.addButton(self.tr("Beenden"), QMessageBox.ButtonRole.RejectRole)
        self.setDefaultButton(self._retry_button)
        self.setEscapeButton(self._quit_button)

    def _connect_signals(self) -> None:
        self.buttonClicked.connect(self._on_button_clicked)

    def show_error(self, message: str) -> None:
        """Zeigt die Meldung nicht blockierend und holt das Fenster in den Vordergrund."""
        self.setText(message)
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_button_clicked(self, button: object) -> None:
        if button is self._retry_button:
            self.retry_requested.emit()
        else:
            self.quit_requested.emit()
