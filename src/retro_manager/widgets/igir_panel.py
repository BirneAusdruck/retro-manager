"""Arbeitsfläche für Igir: ROMs gegen DATs prüfen und Report anzeigen."""

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from retro_manager.controllers.dat_controller import DatController
from retro_manager.controllers.igir_controller import IgirController
from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.widgets.info_label import InfoLabel
from retro_manager.widgets.models.report_table_model import ReportTableModel
from retro_manager.widgets.path_picker import PathPicker

if TYPE_CHECKING:
    from retro_manager.core.dat_update import DatUpdateResult

MAX_LOG_LINES = 5000


class IgirPanel(QWidget):
    """Formular, Live-Ausgabe und Report für `igir test report`; DATs aktualisieren."""

    def __init__(
        self,
        igir: IgirController,
        dats: DatController,
        settings: SettingsController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._igir = igir
        self._dats = dats
        self._settings = settings
        self._build_ui()
        self._connect_signals()
        self._update_availability()

    def _build_ui(self) -> None:
        self.setObjectName("igirPanel")

        self._missing = QLabel()
        self._missing.setObjectName("igirMissing")
        self._missing.setWordWrap(True)
        self._missing.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        description = QLabel(
            self.tr(
                "Prüft deine ROMs gegen DAT-Dateien (z. B. No-Intro, Redump) und erstellt "
                "einen Report. Es werden keine Dateien verändert."
            )
        )
        description.setObjectName("igirDescription")
        description.setWordWrap(True)

        self._input_dir = PathPicker(self.tr("ROM-Ordner wählen"))
        self._dat_dir = PathPicker(self.tr("DAT-Ordner wählen"))
        form = QFormLayout()
        form.addRow(
            InfoLabel(
                self.tr("ROM-Ordner:"),
                self.tr(
                    "Ordner mit den Dumps, die geprüft werden sollen. Unterordner und "
                    "Archive (ZIP, 7z …) werden mit durchsucht."
                ),
            ),
            self._input_dir,
        )
        form.addRow(
            InfoLabel(
                self.tr("DAT-Ordner:"),
                self.tr(
                    "Ordner mit DAT-Dateien (.dat, .xml oder als ZIP), z. B. von "
                    "datomatic.no-intro.org oder redump.org. Igir erkennt anhand der "
                    "Prüfsummen, welche Spiele du hast."
                ),
            ),
            self._dat_dir,
        )

        self._dat_button = QPushButton(self.tr("DATs aktualisieren"))
        self._dat_button.setObjectName("datUpdateButton")
        self._dat_button.setToolTip(
            self.tr(
                "Lädt die aktuellen DATs von No-Intro und Redump, behält die zu RomM passenden "
                "und schreibt sie nach <HDD>/dats. Eine Übersicht, welche Systeme abgedeckt "
                "sind, steht danach in dats/ABGLEICH.md. Selbst abgelegte DATs bleiben erhalten."
            )
        )
        self._verify_button = QPushButton(self.tr("Prüfen"))
        self._verify_button.setObjectName("igirVerifyButton")
        self._cancel_button = QPushButton(self.tr("Abbrechen"))
        self._cancel_button.setEnabled(False)
        buttons = QHBoxLayout()
        buttons.addWidget(self._dat_button)
        buttons.addStretch()
        buttons.addWidget(self._verify_button)
        buttons.addWidget(self._cancel_button)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()

        self._status = QLabel()
        self._status.setObjectName("igirStatus")
        self._status.setWordWrap(True)
        self._status.hide()

        self._info = QLabel()
        self._info.setObjectName("igirInfo")
        self._info.setWordWrap(True)
        self._info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._info.hide()

        self._log = QPlainTextEdit()
        self._log.setObjectName("igirLog")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(MAX_LOG_LINES)
        self._log.setPlaceholderText(self.tr("Hier erscheint die Ausgabe von Igir."))

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._log)
        self._splitter.addWidget(self._build_report_area())
        self._splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._missing)
        layout.addWidget(description)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self._progress)
        layout.addWidget(self._status)
        layout.addWidget(self._info)
        layout.addWidget(self._splitter, stretch=1)

    def _build_report_area(self) -> QWidget:
        self._summary = QLabel(self.tr("Noch kein Report."))
        self._summary.setObjectName("igirSummary")

        self._filter = QComboBox()
        self._filter.addItem(self.tr("Alle"), "")
        self._filter.setEnabled(False)
        self._filter.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        header = QHBoxLayout()
        header.addWidget(self._summary, stretch=1)
        header.addWidget(QLabel(self.tr("Status:")))
        header.addWidget(self._filter)

        self._model = ReportTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._table = QTableView()
        self._table.setObjectName("igirReportTable")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)

        area = QWidget()
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self._table, stretch=1)
        return area

    def _connect_signals(self) -> None:
        self._verify_button.clicked.connect(self._start_verify)
        self._cancel_button.clicked.connect(self._igir.cancel)
        self._cancel_button.clicked.connect(self._dats.cancel)
        self._dat_button.clicked.connect(self._start_dat_update)
        self._filter.currentIndexChanged.connect(self._apply_filter)
        self._igir.running_changed.connect(self._on_running_changed)
        self._igir.output_line.connect(self._log.appendPlainText)
        self._igir.report_ready.connect(self._show_report)
        self._igir.failed.connect(self._show_error)
        self._dats.running_changed.connect(self._on_dat_running_changed)
        self._dats.status.connect(self._log.appendPlainText)
        self._dats.progress.connect(self._on_dat_progress)
        self._dats.finished.connect(self._on_dats_updated)
        self._dats.failed.connect(self._show_error)
        self._settings.changed.connect(self._load_saved_paths)

    def _load_saved_paths(self) -> None:
        """Übernimmt gespeicherte Ordner, ohne eigene Eingaben zu überschreiben."""
        config = self._settings.config
        if not self._input_dir.text():
            self._input_dir.set_path(config.igir_input_dir)
        if not self._dat_dir.text():
            self._dat_dir.set_path(config.igir_dat_dir)

    def _update_availability(self) -> None:
        available = self._igir.is_available()
        self._missing.setVisible(not available)
        self._missing.setText(
            self.tr(
                "Igir wurde nicht gefunden. Erwartet unter:\n{0}\n\nLade Igir von "
                "github.com/emmercm/igir/releases herunter und entpacke es dorthin."
            ).format(self._igir.igir_path)
        )
        self._verify_button.setEnabled(available)

    def _start_verify(self) -> None:
        input_dir = self._input_dir.path()
        dat_dir = self._dat_dir.path()
        if input_dir is None or dat_dir is None:
            self._show_error(self.tr("Bitte ROM-Ordner und DAT-Ordner angeben."))
            return
        self._settings.save_igir_paths(input_dir, dat_dir)
        self._igir.verify(input_dir, dat_dir, self._settings.cues_dir())

    def _refresh_state(self) -> None:
        busy = self._igir.is_running() or self._dats.is_running()
        self._verify_button.setEnabled(not busy and self._igir.is_available())
        self._dat_button.setEnabled(not busy)
        self._cancel_button.setEnabled(busy)
        self._input_dir.setEnabled(not busy)
        self._dat_dir.setEnabled(not busy)
        self._progress.setVisible(busy)

    def _start_new_run(self) -> None:
        self._log.clear()
        self._status.hide()
        self._info.hide()
        self._progress.setRange(0, 0)

    def _on_running_changed(self, running: bool) -> None:
        if running:
            self._start_new_run()
            self._summary.setText(self.tr("Prüfung läuft …"))
        self._refresh_state()

    def _start_dat_update(self) -> None:
        dats_dir = self._settings.dats_dir()
        if dats_dir is None:
            self._show_error(self.tr("Es ist noch kein HDD-Ordner eingerichtet."))
            return
        self._dats.update(dats_dir)

    def _on_dat_running_changed(self, running: bool) -> None:
        if running:
            self._start_new_run()
        self._refresh_state()

    def _on_dat_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_dats_updated(self, result: DatUpdateResult) -> None:
        written = len(result.written)
        self._info.setText(
            self.tr(
                "{0} DATs für {1} RomM-Plattformen aktualisiert, dazu {5} korrekte CUE-Dateien "
                "und {6} Disc-Keys von Redump. Ohne DAT: {2} RomM-Plattformen; {3} DATs passen "
                "zu keiner RomM-Plattform. Details: {4}"
            ).format(
                written,
                result.covered_platforms,
                result.missing_platforms,
                result.unmapped_dats,
                result.report_path,
                result.cue_files,
                result.key_files,
            )
        )
        self._info.show()
        if not self._dat_dir.text():
            self._dat_dir.set_path(result.report_path.parent)

    def _show_report(self, report: object) -> None:
        self._model.set_report(report)
        counts = self._model.status_counts()
        labels = {
            "FOUND": self.tr("Gefunden"),
            "MISSING": self.tr("Fehlend"),
            "DUPLICATE": self.tr("Doppelt"),
            "UNUSED": self.tr("Unbekannt"),
            "DELETED": self.tr("Gelöscht"),
        }
        parts = [f"{labels.get(status, status)}: {count}" for status, count in counts.items()]
        self._summary.setText(" · ".join(parts) if parts else self.tr("Der Report ist leer."))

        self._filter.blockSignals(True)
        self._filter.clear()
        self._filter.addItem(self.tr("Alle"), "")
        for status in counts:
            self._filter.addItem(labels.get(status, status), status)
        self._filter.blockSignals(False)
        self._filter.setEnabled(self._model.status_column is not None)
        self._apply_filter()
        self._table.resizeColumnsToContents()

    def _apply_filter(self) -> None:
        status = self._filter.currentData() or ""
        column = self._model.status_column
        self._proxy.setFilterKeyColumn(column if column is not None else 0)
        self._proxy.setFilterRegularExpression(f"^{re.escape(status)}$" if status else "")

    def _show_error(self, message: str) -> None:
        self._status.setText(message)
        self._status.show()
        if self._model.rowCount() == 0:
            self._summary.setText(self.tr("Noch kein Report."))
