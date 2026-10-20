"""Arbeitsfläche für chdman: Discs der Bibliothek in CHD umwandeln, zurückwandeln, prüfen."""

from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from retro_manager.controllers.chdman_controller import ChdmanController
from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.core.library import LibraryGame
from retro_manager.widgets.info_label import InfoLabel
from retro_manager.widgets.models.chd_table_model import ChdTableModel
from retro_manager.widgets.models.game_table_model import COLUMN_NAME, COLUMN_SELECT, SORT_ROLE

MAX_LOG_LINES = 5000


class ChdmanPanel(QWidget):
    """Liste der Disc-Spiele aus `roms/`, Aktionen für die ausgewählten, Protokoll."""

    def __init__(
        self,
        chdman: ChdmanController,
        settings: SettingsController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._chdman = chdman
        self._settings = settings
        self._library: list[LibraryGame] = []
        self._build_ui()
        self._connect_signals()
        self._on_running_changed(False)

    def _build_ui(self) -> None:
        self.setObjectName("chdmanPanel")

        intro = QLabel(
            self.tr(
                "CHD fasst die Dateien einer Disc verlustfrei in einer komprimierten Datei "
                "zusammen; RomM und Emulatoren wie DuckStation, PCSX2, Flycast oder PPSSPP "
                "lesen sie direkt. Echte Hardware (z. B. webMAN, OPL, XStation) braucht "
                "dagegen BIN/CUE bzw. ISO – dafür wandelt „Export vorbereiten“ automatisch "
                "zurück."
            )
        )
        intro.setObjectName("chdmanIntro")
        intro.setWordWrap(True)

        self._missing = QLabel(
            self.tr(
                "chdman wurde nicht gefunden. Unter Linux z. B. über das Paket „mame-tools“ "
                "installieren oder die Programmdatei nach tools/chdman/ legen."
            )
        )
        self._missing.setObjectName("chdmanMissing")
        self._missing.setWordWrap(True)
        self._missing.setVisible(not self._chdman.chdman_available)

        self._system = QComboBox()
        self._system.setObjectName("chdmanSystem")
        self._delete_originals = QCheckBox(self.tr("Originale nach erfolgreicher Prüfung löschen"))
        self._delete_originals.setObjectName("chdmanDeleteOriginals")
        options = QHBoxLayout()
        options.addWidget(
            InfoLabel(
                self.tr("System:"),
                self.tr(
                    "Angezeigt werden Disc-Spiele aus roms/<plattform>/ der Systeme, für die CHD "
                    "in Frage kommt. GameCube/Wii (RVZ), Switch (NSZ) und PS3 gehören nicht dazu."
                ),
            )
        )
        options.addWidget(self._system)
        options.addSpacing(24)
        options.addWidget(
            InfoLabel(
                "",
                self.tr(
                    "Die neue CHD wird zuerst im Arbeitsordner auf der HDD erzeugt und mit "
                    "„chdman verify“ geprüft. Erst danach kommt sie neben das Original in die "
                    "Bibliothek, und – wenn angehakt – das Original (Archiv bzw. CUE/GDI mit "
                    "allen Tracks oder ISO) wird gelöscht."
                ),
            )
        )
        options.addWidget(self._delete_originals)
        options.addStretch()

        self._refresh_button = QPushButton(self.tr("Liste aktualisieren"))
        self._select_all_button = QPushButton(self.tr("Alle auswählen"))
        self._select_none_button = QPushButton(self.tr("Keine"))
        self._convert_button = QPushButton(self.tr("In CHD umwandeln"))
        self._convert_button.setObjectName("chdmanConvertButton")
        self._extract_button = QPushButton(self.tr("Zurückwandeln …"))
        self._verify_button = QPushButton(self.tr("Prüfen"))
        self._info_button = QPushButton(self.tr("Infos"))
        self._cancel_button = QPushButton(self.tr("Abbrechen"))
        self._cancel_button.setEnabled(False)
        buttons = QHBoxLayout()
        for button in (self._refresh_button, self._select_all_button, self._select_none_button):
            buttons.addWidget(button)
        buttons.addStretch()
        for button in (
            self._convert_button,
            self._extract_button,
            self._verify_button,
            self._info_button,
            self._cancel_button,
        ):
            buttons.addWidget(button)
        self._convert_button.setToolTip(
            self.tr("Ausgewählte BIN/CUE-, GDI-, ISO-Dateien und Archive (7z/ZIP) umwandeln.")
        )
        self._extract_button.setToolTip(
            self.tr(
                "Ausgewählte CHDs in einen wählbaren Ordner zurückwandeln: CDs als BIN/CUE "
                "(ein BIN je Track), Dreamcast als GDI, DVDs als ISO."
            )
        )
        self._verify_button.setToolTip(self.tr("Prüfsummen der ausgewählten CHDs nachrechnen."))
        self._info_button.setToolTip(self.tr("Tracks, Kompression und SHA1 der CHDs anzeigen."))

        self._current = QLabel()
        self._current.setObjectName("chdmanCurrent")
        self._phase = QLabel()
        self._phase.setObjectName("chdmanPhase")
        self._progress = QProgressBar()
        self._progress.hide()

        self._model = ChdTableModel(self._chdman.platform_labels(), self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)
        self._table = QTableView()
        self._table.setObjectName("chdmanTable")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(COLUMN_NAME, Qt.SortOrder.AscendingOrder)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COLUMN_NAME, QHeaderView.ResizeMode.Stretch)

        self._log = QPlainTextEdit()
        self._log.setObjectName("chdmanLog")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(MAX_LOG_LINES)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._table)
        splitter.addWidget(self._log)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._missing)
        layout.addLayout(options)
        layout.addLayout(buttons)
        layout.addWidget(self._current)
        layout.addWidget(self._phase)
        layout.addWidget(self._progress)
        layout.addWidget(splitter, stretch=1)

    def _connect_signals(self) -> None:
        self._refresh_button.clicked.connect(self.refresh)
        self._select_all_button.clicked.connect(lambda: self._model.set_all_checked(True))
        self._select_none_button.clicked.connect(lambda: self._model.set_all_checked(False))
        self._convert_button.clicked.connect(self._convert)
        self._extract_button.clicked.connect(self._extract)
        self._verify_button.clicked.connect(
            lambda: self._run_on_chds(self._chdman.verify, self.tr("Prüfen"))
        )
        self._info_button.clicked.connect(
            lambda: self._run_on_chds(self._chdman.info, self.tr("Infos"))
        )
        self._cancel_button.clicked.connect(self._chdman.cancel)
        self._system.currentIndexChanged.connect(self._apply_filter)
        self._delete_originals.toggled.connect(self._settings.save_chd_delete_originals)
        self._settings.changed.connect(self._load_settings)
        self._chdman.running_changed.connect(self._on_running_changed)
        self._chdman.status.connect(self._on_status)
        self._chdman.phase.connect(self._phase.setText)
        self._chdman.progress.connect(self._on_progress)
        self._chdman.result_changed.connect(
            lambda key, result: self._model.set_statuses(self._chdman.results())
        )
        self._chdman.finished.connect(self._on_finished)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._chdman.is_running():
            self.refresh()

    def _load_settings(self) -> None:
        self._delete_originals.blockSignals(True)
        self._delete_originals.setChecked(self._settings.config.chd_delete_originals)
        self._delete_originals.blockSignals(False)

    # --- Liste ---------------------------------------------------------------------------

    def refresh(self) -> None:
        """Liest die Disc-Spiele der Bibliothek neu ein."""
        self._load_settings()
        hdd = self._settings.config.hdd_path
        if hdd is None:
            self._current.setText(self.tr("Es ist noch kein HDD-Ordner eingerichtet."))
            self._library = []
        else:
            self._library = self._chdman.library(hdd)
        self._reload_systems()
        self._apply_filter()
        self._table.resizeColumnToContents(COLUMN_SELECT)

    def _reload_systems(self) -> None:
        """Auswahl „Alle Systeme“ plus die Systeme, die in der Bibliothek vorkommen."""
        current = self._system.currentData()
        labels = self._chdman.platform_labels()
        present = sorted({game.slug for game in self._library}, key=lambda s: labels.get(s, s))
        self._system.blockSignals(True)
        self._system.clear()
        self._system.addItem(self.tr("Alle Systeme"), "")
        for slug in present:
            self._system.addItem(labels.get(slug, slug), slug)
        index = self._system.findData(current)
        self._system.setCurrentIndex(index if index >= 0 else 0)
        self._system.blockSignals(False)

    def _apply_filter(self) -> None:
        slug = self._system.currentData()
        games = [game for game in self._library if not slug or game.slug == slug]
        self._model.set_games(games, self._chdman.results())

    # --- Aktionen ------------------------------------------------------------------------

    def _selected(self) -> list[LibraryGame]:
        games = self._model.checked_games()
        if not games:
            self._on_status(self.tr("Bitte zuerst Spiele auswählen."))
        return games

    def _convert(self) -> None:
        games = self._selected()
        hdd = self._settings.config.hdd_path
        if not games or hdd is None:
            return
        convertible = [game for game in games if game.kind != "chd"]
        if not convertible:
            self._on_status(self.tr("Die ausgewählten Spiele liegen bereits als CHD vor."))
            return
        delete = self._delete_originals.isChecked()
        if delete:
            answer = QMessageBox.question(
                self,
                self.tr("In CHD umwandeln"),
                self.tr(
                    "{0} Discs in CHD umwandeln? Die Originale werden gelöscht, sobald die "
                    "jeweilige CHD erfolgreich geprüft ist."
                ).format(len(convertible)),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._log.clear()
        self._report_skipped(len(games) - len(convertible), self.tr("liegen bereits als CHD vor"))
        self._chdman.convert(convertible, hdd, delete)

    def _extract(self) -> None:
        games = self._selected()
        if not games:
            return
        chds = [game for game in games if game.kind == "chd"]
        if not chds:
            self._on_status(self.tr("Unter den ausgewählten Spielen ist keine CHD."))
            return
        start = str(self._settings.config.hdd_path or Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Zielordner für die zurückgewandelten Discs"), start
        )
        if not folder:
            return
        delete = self._delete_originals.isChecked()
        if delete:
            answer = QMessageBox.question(
                self,
                self.tr("Zurückwandeln"),
                self.tr(
                    "{0} CHDs zurückwandeln? Die CHDs werden gelöscht, sobald die jeweilige "
                    "Disc erfolgreich zurückgewandelt ist."
                ).format(len(chds)),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._log.clear()
        self._report_skipped(len(games) - len(chds), self.tr("sind keine CHD"))
        self._chdman.extract(chds, Path(folder), delete)

    def _run_on_chds(self, action, title: str) -> None:
        games = self._selected()
        if not games:
            return
        chds = [game for game in games if game.kind == "chd"]
        if not chds:
            self._on_status(self.tr("Unter den ausgewählten Spielen ist keine CHD."))
            return
        self._log.clear()
        self._report_skipped(len(games) - len(chds), self.tr("sind keine CHD"))
        action(chds)

    def _report_skipped(self, count: int, reason: str) -> None:
        if count:
            self._on_status(
                self.tr("{0} ausgewählte Spiele {1} und werden übersprungen.").format(count, reason)
            )

    # --- Rückmeldungen -------------------------------------------------------------------

    def _on_running_changed(self, running: bool) -> None:
        for widget in (
            self._refresh_button,
            self._select_all_button,
            self._select_none_button,
            self._convert_button,
            self._extract_button,
            self._verify_button,
            self._info_button,
            self._system,
            self._delete_originals,
        ):
            widget.setEnabled(not running and self._chdman.chdman_available)
        self._refresh_button.setEnabled(not running)
        self._cancel_button.setEnabled(running)
        self._progress.setVisible(running)
        self._phase.setVisible(running)
        self._table.setEnabled(not running)

    def _on_status(self, text: str) -> None:
        self._log.appendPlainText(text)
        if text.startswith("["):
            self._current.setText(text)

    def _on_progress(self, done: int, total: int) -> None:
        # Bytes können 2^31 überschreiten; die Anzeige rechnet daher in Promille.
        self._progress.setRange(0, 1000 if total else 0)
        if total:
            self._progress.setValue(int(done * 1000 / total))

    def _on_finished(self, ok: int, failed: int) -> None:
        self._current.setText(
            self.tr("Fertig: {0} erfolgreich, {1} fehlgeschlagen.").format(ok, failed)
        )
        self._log.appendPlainText(self._current.text())
        self.refresh()
