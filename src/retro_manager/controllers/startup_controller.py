"""Steuert den gesamten Startablauf."""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from retro_manager.controllers.docker_controller import DockerController
from retro_manager.controllers.romm_controller import RommController
from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.core import docker_compose, mount_check, romm_api
from retro_manager.core.credentials import CredentialsError
from retro_manager.core.romm_api import Heartbeat

logger = logging.getLogger(__name__)

# Der erste Start kann wegen Datenbank-Migrationen 15–20 Minuten dauern.
READY_TIMEOUT_MS = 30 * 60 * 1000


class StartupController(QObject):
    """Führt die Startschritte nacheinander aus und meldet den Stand per Signal."""

    setup_required = Signal(str)  # Hinweistext, leer beim ersten Mal
    status = Signal(str)
    docker_starting = Signal()
    romm_ready = Signal(str, str)  # URL, Login-Skript für die Web-Oberfläche
    finished = Signal()
    failed = Signal(str)

    def __init__(
        self,
        settings: SettingsController,
        docker: DockerController,
        romm: RommController,
        compose_dir: Path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._docker = docker
        self._romm = romm
        self._compose_dir = compose_dir
        self._password = ""

        docker.available.connect(self._on_docker_available)
        docker.started.connect(self._on_docker_started)
        docker.failed.connect(self.failed)
        romm.ready.connect(self._on_romm_ready)
        romm.admin_created.connect(self._login)
        romm.logged_in.connect(self._on_logged_in)
        romm.login_failed.connect(self.setup_required)
        romm.admin_rejected.connect(self.setup_required)
        romm.failed.connect(self.failed)
        self.failed.connect(self._log_failure)

    def _log_failure(self, message: str) -> None:
        logger.error("Start fehlgeschlagen: %s", message)

    @property
    def _base_url(self) -> str:
        return romm_api.base_url(self._settings.config.romm_port)

    def start(self) -> None:
        """Beginnt (oder wiederholt nach dem Einrichtungsdialog) den Startablauf."""
        try:
            self._settings.load()
            self._password = self._settings.romm_password()
        except CredentialsError as error:
            self.failed.emit(self.tr("Der Schlüsselbund ist nicht erreichbar: {0}").format(error))
            return
        if not self._settings.config.is_complete or not self._password:
            self.setup_required.emit("")
            return
        self.status.emit(self.tr("Docker wird geprüft …"))
        self._docker.check()

    def _on_docker_available(self) -> None:
        config = self._settings.config
        assert config.hdd_path is not None
        if not mount_check.is_on_mounted_drive(config.hdd_path):
            self.failed.emit(
                self.tr("Die Archiv-HDD ist nicht eingehängt oder der Ordner fehlt:\n{0}").format(
                    config.hdd_path
                )
            )
            return
        try:
            db_password, db_root_password, auth_key = self._settings.compose_secrets()
            docker_compose.write_env(
                self._compose_dir / docker_compose.ENV_FILENAME,
                docker_compose.env_values(
                    config.hdd_path, config.romm_port, db_password, db_root_password, auth_key
                ),
            )
        except (CredentialsError, OSError) as error:
            self.failed.emit(
                self.tr("RomM-Konfiguration konnte nicht geschrieben werden: {0}").format(error)
            )
            return
        self.docker_starting.emit()
        self.status.emit(self.tr("RomM wird gestartet …"))
        self._docker.start()

    def _on_docker_started(self) -> None:
        self.status.emit(self.tr("Warte auf RomM … Der erste Start kann bis zu 20 Minuten dauern."))
        self._romm.wait_until_ready(self._base_url, READY_TIMEOUT_MS)

    def _on_romm_ready(self, heartbeat: Heartbeat) -> None:
        if heartbeat.show_setup_wizard:
            self.status.emit(self.tr("RomM-Admin wird angelegt …"))
            self._romm.create_admin(self._settings.config.romm_user, self._password)
            return
        self._login()

    def _login(self) -> None:
        self.status.emit(self.tr("Anmeldung bei RomM …"))
        self._romm.login(self._settings.config.romm_user, self._password)

    def _on_logged_in(self) -> None:
        auth_header = romm_api.basic_auth_header(self._settings.config.romm_user, self._password)
        self.romm_ready.emit(self._base_url, romm_api.web_login_script(auth_header))
        self.finished.emit()
