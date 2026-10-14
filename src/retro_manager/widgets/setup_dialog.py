"""Einrichtungsdialog (HDD, RomM-Login)."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.widgets.info_label import InfoLabel
from retro_manager.widgets.path_picker import PathPicker

# Testwerte für den Dev-Button (nur im Entwicklungsbetrieb sichtbar).
DEV_HDD_PATH = "/var/mnt/SATAHDD/RetroManager/"
DEV_USER = "dev"
# RomM verlangt mindestens 6 Zeichen.
DEV_PASSWORD = "devdev"


class SetupDialog(QDialog):
    """Fragt HDD-Ordner und RomM-Zugangsdaten ab.

    Zugänge zu Metadaten-Diensten (IGDB, ScreenScraper usw.) werden nicht hier,
    sondern später in den Einstellungen konfiguriert.
    """

    def __init__(
        self,
        settings: SettingsController,
        dev_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._dev_mode = dev_mode
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.setObjectName("setupDialog")
        self.setWindowTitle(self.tr("Einrichtung"))

        self._hint = QLabel()
        self._hint.setObjectName("setupHint")
        self._hint.setWordWrap(True)
        self._hint.hide()

        self._hdd_path = PathPicker(self.tr("Ordner auf der Archiv-HDD wählen"))
        self._romm_user = QLineEdit()
        self._romm_password = QLineEdit()
        self._romm_password.setEchoMode(QLineEdit.EchoMode.Password)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        self._dev_button = QPushButton(self.tr("Dev"))
        self._dev_button.setObjectName("devFillButton")
        self._dev_button.setToolTip(self.tr("Felder mit Testwerten füllen"))
        self._dev_button.setVisible(self._dev_mode)

        dev_row = QHBoxLayout()
        dev_row.addStretch()
        dev_row.addWidget(self._dev_button)

        layout = QFormLayout(self)
        if self._dev_mode:
            layout.addRow(dev_row)
        layout.addRow(self._hint)
        layout.addRow(
            InfoLabel(
                self.tr("HDD-Ordner:"),
                self.tr(
                    "Ordner auf der externen Archiv-HDD, in dem die Spielesammlung liegt. "
                    "Er wird in RomM als Bibliothek eingebunden. "
                    "Die Platte muss beim Programmstart eingehängt sein."
                ),
            ),
            self._hdd_path,
        )
        layout.addRow(
            InfoLabel(
                self.tr("RomM-Benutzer:"),
                self.tr(
                    "Benutzername deines RomM-Kontos. "
                    "Das Konto legst du beim ersten Start von RomM selbst an."
                ),
            ),
            self._romm_user,
        )
        layout.addRow(
            InfoLabel(
                self.tr("RomM-Passwort:"),
                self.tr(
                    "Passwort deines RomM-Kontos, mindestens 6 Zeichen. Es wird im "
                    "Schlüsselbund des Systems gespeichert, nicht in der Einstellungsdatei."
                ),
            ),
            self._romm_password,
        )
        layout.addRow(self._buttons)

    def _connect_signals(self) -> None:
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._dev_button.clicked.connect(self._fill_dev_values)

    def prompt(self, hint: str) -> None:
        """Zeigt den Dialog mit gespeicherten Werten und optionalem Hinweis an."""
        config = self._settings.config
        self._hdd_path.set_path(config.hdd_path)
        self._romm_user.setText(config.romm_user)
        self._romm_password.clear()
        self._show_hint(hint)
        self.open()

    def accept(self) -> None:
        hdd_path = self._hdd_path.text()
        user = self._romm_user.text().strip()
        password = self._romm_password.text()
        if not (hdd_path and user and password):
            self._show_hint(self.tr("Bitte alle Felder ausfüllen."))
            return
        error = self._settings.save_setup(Path(hdd_path), user, password)
        if error:
            self._show_hint(error)
            return
        super().accept()

    def _fill_dev_values(self) -> None:
        self._hdd_path.set_path(DEV_HDD_PATH)
        self._romm_user.setText(DEV_USER)
        self._romm_password.setText(DEV_PASSWORD)

    def _show_hint(self, text: str) -> None:
        self._hint.setText(text)
        self._hint.setVisible(bool(text))
