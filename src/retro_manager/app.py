"""QApplication erzeugen, Objekte verdrahten, main()."""

import logging
import sys
from importlib import resources

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from retro_manager.controllers.dat_controller import DatController
from retro_manager.controllers.docker_controller import DockerController
from retro_manager.controllers.igir_controller import IgirController
from retro_manager.controllers.job_controller import JobController
from retro_manager.controllers.romm_controller import RommController
from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.controllers.startup_controller import StartupController
from retro_manager.core import config, tools
from retro_manager.widgets import images
from retro_manager.widgets.error_dialog import StartupErrorDialog
from retro_manager.widgets.loading_screen import LoadingScreen
from retro_manager.widgets.main_window import MainWindow
from retro_manager.widgets.setup_dialog import SetupDialog
from retro_manager.widgets.splash_screen import SplashScreen

APP_NAME = "retro-manager"
# Mindestanzeigedauer des Startbilds, bevor der Startablauf beginnt.
SPLASH_MIN_DURATION_MS = 1500

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Richtet das Logging für die gesamte Anwendung ein."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def load_stylesheet(app: QApplication) -> None:
    """Lädt style.qss aus dem Ressourcen-Paket (funktioniert auch im PyInstaller-Build)."""
    stylesheet = resources.files("retro_manager.resources").joinpath("style.qss")
    app.setStyleSheet(stylesheet.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Startet die Anwendung und gibt den Exit-Code zurück."""
    configure_logging()

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_NAME)
    # Zwischen den Startfenstern ist kurz keines sichtbar; Beenden erfolgt ausdrücklich.
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(images.app_icon())
    load_stylesheet(app)

    splash = SplashScreen()
    splash.show()
    app.processEvents()

    base = config.app_dir()
    logger.info("Basisordner: %s", base)

    # Controller
    settings = SettingsController(config.ini_path(base))
    docker = DockerController(config.compose_dir(base))
    romm = RommController()
    jobs = JobController(max_parallel_jobs=settings.config.max_parallel_jobs)
    igir = IgirController(tools.igir_executable(config.tools_dir(base)), config.reports_dir(base))
    dats = DatController(romm, tools.IGIR_VERSION)
    startup = StartupController(settings, docker, romm, config.compose_dir(base))

    # Views
    window = MainWindow(jobs, igir, dats, settings, config.webdata_dir(base))
    loading = LoadingScreen()
    setup_dialog = SetupDialog(settings, dev_mode=config.is_dev_build())
    error_dialog = StartupErrorDialog()

    # Verdrahtung
    startup.setup_required.connect(setup_dialog.prompt)
    startup.status.connect(splash.showMessage)
    startup.status.connect(loading.set_status)
    startup.romm_ready.connect(window.show_romm)
    setup_dialog.accepted.connect(startup.start)
    setup_dialog.rejected.connect(app.quit)
    loading.closed_by_user.connect(app.quit)
    window.closed_by_user.connect(app.quit)
    startup.docker_starting.connect(loading.show)
    startup.finished.connect(loading.close)
    startup.finished.connect(window.show)
    startup.failed.connect(loading.close)
    startup.failed.connect(splash.close)
    # Verzögert anzeigen, damit die Meldung nicht innerhalb eines anderen Dialogs aufgeht.
    startup.failed.connect(
        lambda message: QTimer.singleShot(0, lambda: error_dialog.show_error(message))
    )
    error_dialog.retry_requested.connect(startup.start)
    error_dialog.quit_requested.connect(app.quit)
    app.aboutToQuit.connect(docker.stop)
    app.aboutToQuit.connect(igir.shutdown)
    # Startbild erst schließen, wenn das Folgefenster schon sichtbar ist.
    startup.setup_required.connect(splash.close)
    startup.docker_starting.connect(splash.close)
    startup.finished.connect(lambda: splash.finish(window))

    # Startablauf erst nach Beginn der Event-Loop, damit Signale verarbeitet werden.
    QTimer.singleShot(SPLASH_MIN_DURATION_MS, startup.start)
    return app.exec()
