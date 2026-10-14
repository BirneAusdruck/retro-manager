"""QProcess für Docker-Prüfung und compose up/stop."""

import logging
from collections.abc import Callable
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, QProcess, Signal

from retro_manager.core import docker_compose

logger = logging.getLogger(__name__)


class DockerController(QObject):
    """Prüft Docker und startet bzw. stoppt den RomM-Stack asynchron."""

    available = Signal()
    started = Signal()
    failed = Signal(str)

    def __init__(self, compose_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._compose_dir = compose_dir

    def check(self) -> None:
        """Prüft, ob Docker installiert ist und der Dienst erreichbar ist."""
        self._run(
            docker_compose.docker_info_args(),
            self.available.emit,
            self.tr(
                "Docker läuft nicht oder dein Benutzer darf ihn nicht verwenden "
                "(Benutzer muss in der Gruppe „docker“ sein)."
            ),
        )

    def start(self) -> None:
        """Führt `docker compose up -d` aus (lädt beim ersten Mal die Images herunter)."""
        self._run(
            docker_compose.up_args(self._compose_dir),
            self.started.emit,
            self.tr("RomM konnte nicht gestartet werden."),
        )

    def stop(self) -> None:
        """Führt `docker compose stop` losgelöst aus, damit es das Beenden der App überdauert."""
        docker = docker_compose.docker_executable()
        if docker is None:
            return
        logger.info("Stoppe RomM")
        QProcess.startDetached(docker, docker_compose.stop_args(self._compose_dir))

    def _run(self, args: list[str], on_success: Callable[[], None], error_text: str) -> None:
        docker = docker_compose.docker_executable()
        if docker is None:
            self.failed.emit(self.tr("Docker ist nicht installiert."))
            return

        process = QProcess(self)
        process.setProgram(docker)
        process.setArguments(args)
        process.finished.connect(
            lambda code, status: self._on_finished(process, code, status, on_success, error_text)
        )
        process.errorOccurred.connect(lambda error: self._on_error(process, error, error_text))
        logger.info("Starte: docker %s", " ".join(args))
        process.start()

    def _on_finished(
        self,
        process: QProcess,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
        on_success: Callable[[], None],
        error_text: str,
    ) -> None:
        if not shiboken6.isValid(process):  # App wird gerade beendet
            return
        process.deleteLater()
        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
            on_success()
            return
        stderr = bytes(process.readAllStandardError().data()).decode(errors="replace").strip()
        logger.error("Docker-Befehl fehlgeschlagen (%s): %s", exit_code, stderr)
        self.failed.emit(f"{error_text}\n\n{stderr}" if stderr else error_text)

    def _on_error(self, process: QProcess, error: QProcess.ProcessError, error_text: str) -> None:
        # Bei allen anderen Fehlern folgt noch `finished`.
        if not shiboken6.isValid(process):
            return
        if error == QProcess.ProcessError.FailedToStart:
            process.deleteLater()
            logger.error("Docker konnte nicht gestartet werden: %s", process.errorString())
            self.failed.emit(f"{error_text}\n\n{process.errorString()}")
