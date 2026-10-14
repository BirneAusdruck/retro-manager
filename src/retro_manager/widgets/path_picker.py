"""Ordnerauswahl: Eingabezeile mit „Durchsuchen…“-Knopf."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


class PathPicker(QWidget):
    """Wiederverwendbare Auswahl eines Ordners."""

    path_changed = Signal(str)

    def __init__(self, dialog_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dialog_title = dialog_title
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.setObjectName("pathPicker")
        self._edit = QLineEdit()
        self._browse = QPushButton(self.tr("Durchsuchen …"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit, stretch=1)
        layout.addWidget(self._browse)

    def _connect_signals(self) -> None:
        self._browse.clicked.connect(self._choose)
        self._edit.textChanged.connect(self.path_changed)

    def text(self) -> str:
        return self._edit.text().strip()

    def path(self) -> Path | None:
        """Gewählter Ordner oder None, wenn das Feld leer ist."""
        text = self.text()
        return Path(text) if text else None

    def set_path(self, path: Path | str | None) -> None:
        self._edit.setText(str(path) if path else "")

    def _choose(self) -> None:
        start = self.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, self._dialog_title, start)
        if chosen:
            self._edit.setText(chosen)
