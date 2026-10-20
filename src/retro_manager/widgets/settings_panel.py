"""Reiter „Einstellungen“: später zentrales Prüfen und Reparieren der Bibliothek (Platzhalter)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SettingsPanel(QWidget):
    """Platzhalter: Hier sollen später alle Werkzeuge gebündelt die Bibliothek prüfen und
    in Ordnung bringen, wobei die nötigen Aufgaben automatisch ausgewählt werden."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("settingsPanel")

        title = QLabel(self.tr("Bibliothek prüfen und reparieren"))
        title.setObjectName("settingsTitle")

        text = QLabel(
            self.tr(
                "Dieser Reiter ist noch in Arbeit. Hier wird die Bibliothek künftig mit einem "
                "Klick geprüft und in Ordnung gebracht: Die App erkennt, was zu tun ist, und "
                "wählt die nötigen Aufgaben der einzelnen Werkzeuge automatisch aus – etwa DATs "
                "aktualisieren, Dateien mit Igir prüfen und nach DAT benennen, Disc-Spiele mit "
                "chdman in CHD umwandeln und über RomM hochgeladene Dateien einsortieren."
            )
        )
        text.setObjectName("settingsPlaceholder")
        text.setWordWrap(True)

        hint = QLabel(
            self.tr("Bis dahin stehen die Werkzeuge einzeln in ihren Reitern zur Verfügung.")
        )
        hint.setObjectName("settingsHint")
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addWidget(title)
        layout.addWidget(text)
        layout.addWidget(hint)
        layout.addStretch()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
