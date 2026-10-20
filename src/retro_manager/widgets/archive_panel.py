"""Arbeitsfläche „Archive“: Einträge der Bibliothek entpacken, packen und prüfen (7-Zip)."""

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
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from retro_manager.controllers.archive_controller import ArchiveController
from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.core.library import LibraryGame
from retro_manager.widgets.info_label import InfoLabel
from retro_manager.widgets.models.archive_table_model import ArchiveTableModel
from retro_manager.widgets.models.game_table_model import NAME, SELECT, SORT_ROLE

MAX_LOG_LINES = 5000
MAX_PARALLEL_LIMIT = 8

_SHOW_ALL, _SHOW_ARCHIVES, _SHOW_UNPACKED = "all", "archives", "unpacked"


class ArchivePanel(QWidget):
    """Liste aller Einträge aus `roms/`, Optionen fürs Packen, Aktionen, Protokoll."""

    def __init__(
        self,
        archives: ArchiveController,
        settings: SettingsController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._archives = archives
        self._settings = settings
        self._library: list[LibraryGame] = []
        self._build_ui()
        self._connect_signals()
        self._on_running_changed(False)

    def _build_ui(self) -> None:
        self.setObjectName("archivePanel")

        intro = QLabel(
            self.tr(
                "Entpacken, Packen und Prüfen mit 7-Zip: entpackt 7z, ZIP, RAR (auch "
                "mehrteilig), TAR, TAR.GZ/XZ/BZ2 und GZ/XZ/BZ2; packt als ZIP oder 7z – ein "
                "Archiv je Spiel. CHD-Dateien erzeugt der Reiter „chdman“."
            )
        )
        intro.setObjectName("archiveIntro")
        intro.setWordWrap(True)

        self._missing = QLabel(
            self.tr(
                "7-Zip wurde nicht gefunden. Den offiziellen Build „7zz“ von 7-zip.org nach "
                "tools/7zip/ legen oder 7-Zip über die Paketverwaltung installieren."
            )
        )
        self._missing.setObjectName("archiveMissing")
        self._missing.setWordWrap(True)
        self._missing.setVisible(not self._archives.sevenzip_available)

        self._system = QComboBox()
        self._system.setObjectName("archiveSystem")
        self._show = QComboBox()
        self._show.setObjectName("archiveShow")
        self._show.addItem(self.tr("Alle Einträge"), _SHOW_ALL)
        self._show.addItem(self.tr("Nur Archive"), _SHOW_ARCHIVES)
        self._show.addItem(self.tr("Nur ungepackte"), _SHOW_UNPACKED)
        self._parallel = QSpinBox()
        self._parallel.setObjectName("archiveParallel")
        self._parallel.setRange(1, MAX_PARALLEL_LIMIT)
        self._parallel.setValue(self._archives.max_parallel)
        filters = QHBoxLayout()
        filters.addWidget(
            InfoLabel(
                self.tr("System:"),
                self.tr("Plattformordner unter roms/. Gezeigt werden alle Spiele der Bibliothek."),
            )
        )
        filters.addWidget(self._system)
        filters.addSpacing(16)
        filters.addWidget(
            InfoLabel(
                self.tr("Anzeigen:"),
                self.tr(
                    "„Nur Archive“ zeigt Einträge zum Entpacken und Prüfen, „Nur ungepackte“ "
                    "lose Dateien (ROMs, BIN/CUE, GDI, ISO) zum Packen."
                ),
            )
        )
        filters.addWidget(self._show)
        filters.addStretch()
        filters.addWidget(
            InfoLabel(
                self.tr("Gleichzeitig:"),
                self.tr(
                    "Wie viele Archive gleichzeitig bearbeitet werden. Auf einer Festplatte "
                    "(HDD) ist mehr nicht immer schneller, weil der Lesekopf zwischen den "
                    "Dateien springen muss; 1–2 ist meist ein guter Wert. Gilt sofort."
                ),
            )
        )
        filters.addWidget(self._parallel)

        self._format = QComboBox()
        self._format.setObjectName("archiveFormat")
        self._format.addItem("ZIP", "zip")
        self._format.addItem("7z", "7z")
        self._level = QComboBox()
        self._level.setObjectName("archiveLevel")
        self._level.addItem(self.tr("Schnell"), "fast")
        self._level.addItem(self.tr("Normal"), "normal")
        self._level.addItem(self.tr("Maximal"), "max")
        self._delete_originals = QCheckBox(self.tr("Originale nach Erfolg löschen"))
        self._delete_originals.setObjectName("archiveDeleteOriginals")
        options = QHBoxLayout()
        options.addWidget(
            InfoLabel(
                self.tr("Packformat:"),
                self.tr(
                    "ZIP ist das Zielformat für Cartridge-Systeme (Game Boy bis N64) und wird "
                    "von RomM, Igir und fast allen Emulatoren gelesen. 7z packt kleiner, wird "
                    "aber nicht überall direkt unterstützt. Ausgewählte Archive werden in das "
                    "gewählte Format umgepackt."
                ),
            )
        )
        options.addWidget(self._format)
        options.addSpacing(16)
        options.addWidget(
            InfoLabel(
                self.tr("Stufe:"),
                self.tr("Kompressionsstufe: Schnell (-mx=1), Normal (-mx=5), Maximal (-mx=9)."),
            )
        )
        options.addWidget(self._level)
        options.addSpacing(16)
        options.addWidget(
            InfoLabel(
                "",
                self.tr(
                    "Packen: Das neue Archiv entsteht im Arbeitsordner auf der HDD, wird mit "
                    "7-Zip geprüft und erst dann neben das Original gelegt. Entpacken: 7-Zip "
                    "prüft beim Entpacken alle Prüfsummen; erst danach wird einsortiert. Nur "
                    "wenn das geklappt hat und der Haken gesetzt ist, wird das Original "
                    "gelöscht (bei mehrteiligen Archiven alle Teile)."
                ),
            )
        )
        options.addWidget(self._delete_originals)
        options.addStretch()

        self._refresh_button = QPushButton(self.tr("Liste aktualisieren"))
        self._select_all_button = QPushButton(self.tr("Alle auswählen"))
        self._select_none_button = QPushButton(self.tr("Keine"))
        self._extract_button = QPushButton(self.tr("Entpacken"))
        self._extract_button.setObjectName("archiveExtractButton")
        self._extract_button.setToolTip(
            self.tr(
                "Neben das Archiv entpacken: eine einzelne Datei landet direkt daneben, "
                "mehrere Dateien in einem Spielordner mit dem Namen des Archivs."
            )
        )
        self._extract_to_button = QPushButton(self.tr("Entpacken nach …"))
        self._extract_to_button.setToolTip(self.tr("In einen wählbaren Ordner entpacken."))
        self._pack_button = QPushButton(self.tr("Packen"))
        self._pack_button.setToolTip(
            self.tr("Je Spiel ein Archiv im gewählten Format; Archive werden umgepackt.")
        )
        self._test_button = QPushButton(self.tr("Prüfen"))
        self._test_button.setToolTip(self.tr("Alle Dateien der Archive gegen ihre CRCs prüfen."))
        self._cancel_button = QPushButton(self.tr("Abbrechen"))
        buttons = QHBoxLayout()
        for button in (self._refresh_button, self._select_all_button, self._select_none_button):
            buttons.addWidget(button)
        buttons.addStretch()
        for button in (
            self._extract_button,
            self._extract_to_button,
            self._pack_button,
            self._test_button,
            self._cancel_button,
        ):
            buttons.addWidget(button)

        self._current = QLabel()
        self._current.setObjectName("archiveCurrent")
        self._progress = QProgressBar()
        self._progress.setFormat(self.tr("%v von %m erledigt"))

        self._model = ArchiveTableModel(self._archives.platform_labels(), self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)
        self._table = QTableView()
        self._table.setObjectName("archiveTable")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(self._model.column_index(NAME), Qt.SortOrder.AscendingOrder)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self._model.column_index(NAME), QHeaderView.ResizeMode.Stretch)

        self._log = QPlainTextEdit()
        self._log.setObjectName("archiveLog")
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
        layout.addLayout(filters)
        layout.addLayout(options)
        layout.addLayout(buttons)
        layout.addWidget(self._current)
        layout.addWidget(self._progress)
        layout.addWidget(splitter, stretch=1)

    def _connect_signals(self) -> None:
        self._refresh_button.clicked.connect(self.refresh)
        self._select_all_button.clicked.connect(lambda: self._model.set_all_checked(True))
        self._select_none_button.clicked.connect(lambda: self._model.set_all_checked(False))
        self._extract_button.clicked.connect(lambda: self._extract(ask_folder=False))
        self._extract_to_button.clicked.connect(lambda: self._extract(ask_folder=True))
        self._pack_button.clicked.connect(self._pack)
        self._test_button.clicked.connect(self._test)
        self._cancel_button.clicked.connect(self._archives.cancel)
        self._system.currentIndexChanged.connect(self._apply_filter)
        self._show.currentIndexChanged.connect(self._apply_filter)
        self._parallel.valueChanged.connect(self._on_parallel_changed)
        for combo in (self._format, self._level):
            combo.currentIndexChanged.connect(self._save_options)
        self._delete_originals.toggled.connect(self._save_options)
        self._settings.changed.connect(self._load_settings)
        self._archives.running_changed.connect(self._on_running_changed)
        self._archives.status.connect(self._log.appendPlainText)
        self._archives.overall.connect(self._on_overall)
        self._archives.result_changed.connect(
            lambda key, result: self._model.set_statuses(self._archives.results())
        )
        self._archives.finished.connect(self._on_finished)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._archives.is_running():
            self.refresh()

    # --- Einstellungen -------------------------------------------------------------------

    def _load_settings(self) -> None:
        cfg = self._settings.config
        widgets = (self._format, self._level, self._delete_originals, self._parallel)
        for widget in widgets:
            widget.blockSignals(True)
        self._format.setCurrentIndex(max(0, self._format.findData(cfg.archive_format)))
        self._level.setCurrentIndex(max(0, self._level.findData(cfg.archive_level)))
        self._delete_originals.setChecked(cfg.archive_delete_originals)
        self._parallel.setValue(cfg.max_parallel_jobs)
        for widget in widgets:
            widget.blockSignals(False)

    def _save_options(self) -> None:
        self._settings.save_archive_options(
            self._format.currentData(),
            self._level.currentData(),
            self._delete_originals.isChecked(),
        )

    def _on_parallel_changed(self, count: int) -> None:
        self._archives.set_max_parallel(count)
        self._settings.save_max_parallel_jobs(count)

    # --- Liste ---------------------------------------------------------------------------

    def refresh(self) -> None:
        """Liest alle Einträge der Bibliothek neu ein."""
        self._load_settings()
        hdd = self._settings.config.hdd_path
        if hdd is None:
            self._current.setText(self.tr("Es ist noch kein HDD-Ordner eingerichtet."))
            self._library = []
        else:
            self._library = self._archives.library(hdd)
        self._reload_systems()
        self._apply_filter()
        self._table.resizeColumnToContents(self._model.column_index(SELECT))

    def _reload_systems(self) -> None:
        current = self._system.currentData()
        labels = self._archives.platform_labels()
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
        show = self._show.currentData()
        games = [
            game
            for game in self._library
            if (not slug or game.slug == slug)
            and (
                show == _SHOW_ALL
                or (show == _SHOW_ARCHIVES and game.kind == "archive")
                or (show == _SHOW_UNPACKED and game.kind != "archive")
            )
        ]
        self._model.set_games(games, self._archives.results())

    # --- Aktionen ------------------------------------------------------------------------

    def _selected(self) -> list[LibraryGame]:
        games = self._model.checked_games()
        if not games:
            self._log.appendPlainText(self.tr("Bitte zuerst Spiele auswählen."))
        return games

    def _confirm_delete(self, title: str, count: int) -> bool:
        if not self._delete_originals.isChecked():
            return True
        answer = QMessageBox.question(
            self,
            title,
            self.tr(
                "{0} Einträge bearbeiten? Die Originale werden gelöscht, sobald der jeweilige "
                "Eintrag erfolgreich fertig ist."
            ).format(count),
        )
        return answer == QMessageBox.StandardButton.Yes

    def _extract(self, ask_folder: bool) -> None:
        games = self._selected()
        hdd = self._settings.config.hdd_path
        if not games or hdd is None:
            return
        selected = [game for game in games if game.kind == "archive"]
        if not selected:
            self._log.appendPlainText(self.tr("Unter den ausgewählten Einträgen ist kein Archiv."))
            return
        destination = None
        if ask_folder:
            folder = QFileDialog.getExistingDirectory(
                self, self.tr("Zielordner zum Entpacken"), str(hdd or Path.home())
            )
            if not folder:
                return
            destination = Path(folder)
        if not self._confirm_delete(self.tr("Entpacken"), len(selected)):
            return
        self._begin_log(len(games) - len(selected), self.tr("sind keine Archive"))
        self._archives.extract(selected, hdd, destination, self._delete_originals.isChecked())

    def _pack(self) -> None:
        games = self._selected()
        hdd = self._settings.config.hdd_path
        if not games or hdd is None:
            return
        archive_format = self._format.currentData()
        mismatched = self._archives.format_mismatches(games, archive_format)
        if mismatched:
            answer = QMessageBox.question(
                self,
                self.tr("Packen"),
                self.tr(
                    "Für diese Systeme sieht die Bibliothek ein anderes Format vor:\n{0}\n\n"
                    "CHD erzeugt der Reiter „chdman“. Trotzdem als {1} packen?"
                ).format("\n".join(mismatched), self._format.currentText()),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if not self._confirm_delete(self.tr("Packen"), len(games)):
            return
        self._begin_log(0, "")
        self._archives.pack(
            games,
            hdd,
            archive_format,
            self._level.currentData(),
            self._delete_originals.isChecked(),
        )

    def _test(self) -> None:
        games = self._selected()
        if not games:
            return
        selected = [game for game in games if game.kind == "archive"]
        if not selected:
            self._log.appendPlainText(self.tr("Unter den ausgewählten Einträgen ist kein Archiv."))
            return
        self._begin_log(len(games) - len(selected), self.tr("sind keine Archive"))
        self._archives.test(selected)

    def _begin_log(self, skipped: int, reason: str) -> None:
        self._log.clear()
        if skipped:
            self._log.appendPlainText(
                self.tr("{0} ausgewählte Einträge {1} und werden übersprungen.").format(
                    skipped, reason
                )
            )

    # --- Rückmeldungen -------------------------------------------------------------------

    def _on_running_changed(self, running: bool) -> None:
        available = self._archives.sevenzip_available
        for widget in (
            self._extract_button,
            self._extract_to_button,
            self._pack_button,
            self._test_button,
        ):
            widget.setEnabled(not running and available)
        for widget in (
            self._refresh_button,
            self._select_all_button,
            self._select_none_button,
            self._system,
            self._show,
            self._format,
            self._level,
            self._delete_originals,
        ):
            widget.setEnabled(not running)
        self._cancel_button.setEnabled(running)
        self._progress.setVisible(running)
        self._table.setEnabled(not running)

    def _on_overall(self, done: int, total: int) -> None:
        self._progress.setRange(0, max(1, total))
        self._progress.setValue(done)
        self._current.setText(self.tr("{0} von {1} erledigt").format(done, total))

    def _on_finished(self, ok: int, failed: int) -> None:
        self._current.setText(
            self.tr("Fertig: {0} erfolgreich, {1} fehlgeschlagen.").format(ok, failed)
        )
        self._log.appendPlainText(self._current.text())
        self.refresh()
