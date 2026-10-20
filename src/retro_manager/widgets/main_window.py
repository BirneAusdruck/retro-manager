"""Hauptfenster (erbt QMainWindow)."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from retro_manager.controllers.activity_controller import (
    TAB_ARCHIVE,
    TAB_CHDMAN,
    TAB_EXPORT,
    TAB_FTP,
    TAB_IGIR,
    ActivityController,
)
from retro_manager.controllers.archive_controller import ArchiveController
from retro_manager.controllers.chdman_controller import ChdmanController
from retro_manager.controllers.dat_controller import DatController
from retro_manager.controllers.export_controller import ExportController
from retro_manager.controllers.igir_controller import IgirController
from retro_manager.controllers.job_controller import JobController
from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.controllers.transfer_controller import TransferController
from retro_manager.widgets import images
from retro_manager.widgets.activity_indicator import (
    ActivityIndicator,
    ActivityPanel,
    ActivityPopup,
)
from retro_manager.widgets.archive_panel import ArchivePanel
from retro_manager.widgets.chdman_panel import ChdmanPanel
from retro_manager.widgets.export_panel import ExportPanel
from retro_manager.widgets.ftp_panel import FtpPanel
from retro_manager.widgets.igir_panel import IgirPanel
from retro_manager.widgets.romm_view import RommView
from retro_manager.widgets.settings_panel import SettingsPanel

LOGO_HEIGHT = 96


class MainWindow(QMainWindow):
    """Hauptfenster der Anwendung."""

    closed_by_user = Signal()

    def __init__(
        self,
        job_controller: JobController,
        igir: IgirController,
        dats: DatController,
        chdman: ChdmanController,
        archives: ArchiveController,
        exports: ExportController,
        transfers: TransferController,
        activities: ActivityController,
        settings: SettingsController,
        webdata_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._jobs = job_controller
        self._igir = igir
        self._dats = dats
        self._chdman = chdman
        self._archives = archives
        self._exports = exports
        self._transfers = transfers
        self._activities = activities
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
        archive_tab = self._tabs.addTab(self.tr("Archive"))
        igir_tab = self._tabs.addTab(self.tr("Igir"))
        chdman_tab = self._tabs.addTab(self.tr("chdman"))
        export_tab = self._tabs.addTab(self.tr("Export vorbereiten"))
        self._ftp_tab = self._tabs.addTab(self.tr("FTP"))
        self._tabs.addTab(self.tr("Einstellungen"))
        self._tab_index = {
            TAB_IGIR: igir_tab,
            TAB_CHDMAN: chdman_tab,
            TAB_ARCHIVE: archive_tab,
            TAB_EXPORT: export_tab,
            TAB_FTP: self._ftp_tab,
        }

        header = QWidget()
        header.setObjectName("appHeader")
        header_layout = QHBoxLayout(header)
        header_layout.addWidget(logo)
        header_layout.addWidget(self._tabs, stretch=1, alignment=Qt.AlignmentFlag.AlignBottom)
        self._activity_indicator = ActivityIndicator()
        header_layout.addWidget(self._activity_indicator, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._romm_view = RommView(self._webdata_dir)
        self._igir_panel = IgirPanel(self._igir, self._dats, self._settings)
        self._chdman_panel = ChdmanPanel(self._chdman, self._settings)
        self._archive_panel = ArchivePanel(self._archives, self._settings)
        self._export_panel = ExportPanel(self._exports, self._transfers, self._settings)
        self._ftp_panel = FtpPanel(self._transfers, self._settings)
        self._settings_panel = SettingsPanel()
        self._stack = QStackedWidget()
        self._stack.setObjectName("workspace")
        self._stack.addWidget(self._romm_view)
        self._stack.addWidget(self._archive_panel)
        self._stack.addWidget(self._igir_panel)
        self._stack.addWidget(self._chdman_panel)
        self._stack.addWidget(self._export_panel)
        self._stack.addWidget(self._ftp_panel)
        self._stack.addWidget(self._settings_panel)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._stack, stretch=1)
        self.setCentralWidget(central)

        # Schwebt über der Arbeitsfläche, gehört daher nicht ins Layout.
        self._activity_panel = ActivityPanel(central)
        self._activity_popup = ActivityPopup(
            self._activities, self._activity_indicator, self._activity_panel, header, self
        )

    def _connect_signals(self) -> None:
        self._tabs.currentChanged.connect(self._stack.setCurrentIndex)
        self._activity_popup.activity_clicked.connect(
            lambda tab: self._tabs.setCurrentIndex(
                self._tab_index.get(tab, self._tabs.currentIndex())
            )
        )
        # „An Gerät senden“: zur Warteschlange im FTP-Reiter wechseln.
        self._exports.sent.connect(lambda job: self._tabs.setCurrentIndex(self._ftp_tab))

    def show_romm(self, url: str, login_script: str) -> None:
        """Lädt die RomM-Oberfläche."""
        self._romm_view.open(url, login_script)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._activity_popup.relayout()

    def closeEvent(self, event: QCloseEvent) -> None:
        # Nur Schließen durch den Nutzer melden, nicht programmatisches close().
        if event.spontaneous():
            self.closed_by_user.emit()
        super().closeEvent(event)
