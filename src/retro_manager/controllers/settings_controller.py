"""Laden/Speichern über core.config und core.credentials."""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from retro_manager.core import config, credentials, dat_update, docker_compose, romm_api
from retro_manager.core.config import AppConfig
from retro_manager.core.credentials import CredentialsError

logger = logging.getLogger(__name__)


class SettingsController(QObject):
    """Hält die aktuelle Konfiguration und verwaltet die Geheimnisse im Schlüsselbund."""

    changed = Signal()

    def __init__(self, ini_path: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ini_path = ini_path
        self.config = AppConfig()

    def load(self) -> None:
        """Lädt die Konfiguration aus der INI-Datei."""
        self.config = config.load_config(self._ini_path)
        logger.info("Konfiguration geladen aus %s", self._ini_path)
        self.changed.emit()

    def romm_password(self) -> str:
        """RomM-Passwort aus dem Schlüsselbund; leer, wenn keines gespeichert ist.

        Wirft CredentialsError, wenn der Schlüsselbund nicht erreichbar ist.
        """
        return credentials.get_secret(credentials.ROMM_PASSWORD) or ""

    def save_setup(self, hdd_path: Path, user: str, password: str) -> str | None:
        """Speichert die Angaben aus dem Einrichtungsdialog; gibt eine Fehlermeldung zurück."""
        if len(password) < romm_api.MIN_PASSWORD_LENGTH:
            return self.tr("Das Passwort muss mindestens {0} Zeichen lang sein.").format(
                romm_api.MIN_PASSWORD_LENGTH
            )
        try:
            credentials.set_secret(credentials.ROMM_PASSWORD, password)
        except CredentialsError as error:
            logger.error("Passwort konnte nicht gespeichert werden: %s", error)
            return self.tr("Der Schlüsselbund des Systems ist nicht erreichbar: {0}").format(error)
        self.config.hdd_path = hdd_path
        self.config.romm_user = user
        config.save_config(self._ini_path, self.config)
        self.changed.emit()
        return None

    def dats_dir(self) -> Path | None:
        """Ordner für DATs auf der Archiv-HDD oder None, solange kein HDD-Ordner gesetzt ist."""
        hdd = self.config.hdd_path
        return config.dats_dir(hdd) if hdd else None

    def cues_dir(self) -> Path | None:
        """Ordner mit den korrekten Redump-CUEs (von „DATs aktualisieren“ angelegt)."""
        dats = self.dats_dir()
        return dats / dat_update.CUES_DIRNAME if dats else None

    def save_igir_paths(self, input_dir: Path, dat_dir: Path) -> None:
        """Merkt sich die zuletzt verwendeten Ordner für Igir."""
        self.config.igir_input_dir = input_dir
        self.config.igir_dat_dir = dat_dir
        config.save_config(self._ini_path, self.config)
        self.changed.emit()

    def compose_secrets(self) -> tuple[str, str, str]:
        """DB-Passwort, DB-Root-Passwort und Auth-Schlüssel; fehlende werden einmalig erzeugt.

        Wirft CredentialsError, wenn der Schlüsselbund nicht erreichbar ist.
        """
        keys = (credentials.DB_PASSWORD, credentials.DB_ROOT_PASSWORD, credentials.AUTH_SECRET_KEY)
        values = []
        for key in keys:
            value = credentials.get_secret(key)
            if not value:
                value = docker_compose.generate_secret()
                credentials.set_secret(key, value)
                logger.info("Neues Geheimnis %s erzeugt", key)
            values.append(value)
        return values[0], values[1], values[2]
