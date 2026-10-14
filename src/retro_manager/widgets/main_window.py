"""Hauptfenster (erbt QMainWindow)."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from retro_manager.controllers.dat_controller import DatController
from retro_manager.controllers.igir_controller import IgirController
from retro_manager.controllers.job_controller import JobController
from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.widgets import images
from retro_manager.widgets.igir_panel import IgirPanel
from retro_manager.widgets.romm_view import RommView

LOGO_HEIGHT = 96


class MainWindow(QMainWindow):
    """Hauptfenster der Anwendung."""

    closed_by_user = Signal()

    def __init__(
        self,
        job_controller: JobController,
        igir: IgirController,
        dats: DatController,
        settings: SettingsController,
        webdata_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._jobs = job_controller
        self._igir = igir
        self._dats = dats
        self._settings = settings
        self._webdata_dir = webdata_dir
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.setObjectName("mainWindow")
        self.setWindowTitle(self.tr("Retro Manager"))
        self.resize(1280, 800)

        logo = QLabel()
        logo.setObjectName("logo")
        logo.setPixmap(images.svg_pixmap(images.LOGO, LOGO_HEIGHT))

        # Reihenfolge der Reiter = Reihenfolge der Seiten im Stapel.
        self._tabs = QTabBar()
        self._tabs.setObjectName("toolTabs")
        self._tabs.setExpanding(False)
        self._tabs.setDrawBase(False)
        self._tabs.addTab(self.tr("RomM"))
        self._tabs.addTab(self.tr("Igir"))

        header = QWidget()
        header.setObjectName("appHeader")
        header_layout = QHBoxLayout(header)
        header_layout.addWidget(logo)
        header_layout.addWidget(self._tabs, stretch=1, alignment=Qt.AlignmentFlag.AlignBottom)

        self._romm_view = RommView(self._webdata_dir)
        self._igir_panel = IgirPanel(self._igir, self._dats, self._settings)
        self._stack = QStackedWidget()
        self._stack.setObjectName("workspace")
        self._stack.addWidget(self._romm_view)
        self._stack.addWidget(self._igir_panel)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._stack, stretch=1)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self._tabs.currentChanged.connect(self._stack.setCurrentIndex)

    def show_romm(self, url: str, login_script: str) -> None:
        """Lädt die RomM-Oberfläche."""
        self._romm_view.open(url, login_script)

    def closeEvent(self, event: QCloseEvent) -> None:
        # Nur Schließen durch den Nutzer melden, nicht programmatisches close().
        if event.spontaneous():
            self.closed_by_user.emit()
        super().closeEvent(event)
