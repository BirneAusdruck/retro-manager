"""Arbeitsfläche „Export vorbereiten“: Spiele für ein gewähltes Zielgerät aufbereiten."""

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtGui import QShowEvent, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
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

from retro_manager.controllers.export_controller import ExportController
from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.controllers.transfer_controller import TransferController
from retro_manager.core.devices import PLATFORM_LABELS, DeviceProfile
from retro_manager.widgets.info_label import InfoLabel
from retro_manager.widgets.models.export_table_model import ExportTableModel
from retro_manager.widgets.models.game_table_model import COLUMN_NAME, COLUMN_SELECT, SORT_ROLE

MAX_LOG_LINES = 2000


class ExportPanel(QWidget):
    """Zielgerät wählen, passende Discs aufbereiten (Export-Ordner) oder Export löschen."""

    def __init__(
        self,
        exports: ExportController,
        transfers: TransferController,
        settings: SettingsController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._exports = exports
        self._transfers = transfers
        self._settings = settings
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.setObjectName("exportPanel")

        self._device = QComboBox()
        self._device.setObjectName("exportDevice")
        for profile in self._exports.profiles():
            self._device.addItem(profile.label, profile.id)
        items = self._device.model()
        assert isinstance(items, QStandardItemModel)
        for row, profile in enumerate(self._exports.profiles()):
            if not profile.available:
                item = items.item(row)
                item.setEnabled(False)
                item.setText(self.tr("{0} – kommt später").format(profile.label))
        device_row = QHBoxLayout()
        device_row.addWidget(
            InfoLabel(
                self.tr("Zielgerät:"),
                self.tr(
                    "Für welches Gerät die Spiele aufbereitet werden. Davon hängen ab, welche "
                    "Systeme angeboten werden, in welchem Format und in welchen Ordnern sie im "
                    "Export landen. Die Originale im Archiv bleiben unverändert."
                ),
            )
        )
        device_row.addWidget(self._device)
        device_row.addStretch()

        self._description = QLabel()
        self._description.setObjectName("exportDescription")
        self._description.setWordWrap(True)

        self._export_dir = QLabel()
        self._export_dir.setObjectName("exportDir")
        self._export_dir.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._chdman_missing = QLabel(
            self.tr(
                "chdman wurde nicht gefunden – CHD-Dateien können nicht aufbereitet werden. "
                "Unter Linux z. B. über das Paket „mame-tools“ installieren."
            )
        )
        self._chdman_missing.setObjectName("exportChdmanMissing")
        self._chdman_missing.setWordWrap(True)
        self._chdman_missing.setVisible(not self._exports.chdman_available)

        self._send_connection = QComboBox()
        self._send_connection.setObjectName("exportSendConnection")
        self._send_connection.setMinimumWidth(200)
        self._send_button = QPushButton(self.tr("An Gerät senden"))
        self._send_button.setObjectName("exportSendButton")
        send_row = QHBoxLayout()
        send_row.addWidget(
            InfoLabel(
                self.tr("Senden an:"),
                self.tr(
                    "Gespeicherte Verbindung aus dem Reiter „FTP“. „An Gerät senden“ stellt die "
                    "aufbereiteten Dateien als Auftrag in die Warteschlange des FTP-Reiters; die "
                    "Zielordner auf dem Gerät (z. B. /dev_hdd0/PS2ISO) kommen aus dem Zielgerät."
                ),
            )
        )
        send_row.addWidget(self._send_connection)
        send_row.addWidget(self._send_button)
        send_row.addStretch()

        self._refresh_button = QPushButton(self.tr("Liste aktualisieren"))
        self._select_all_button = QPushButton(self.tr("Alle auswählen"))
        self._select_none_button = QPushButton(self.tr("Keine"))
        self._prepare_button = QPushButton(self.tr("Aufbereiten"))
        self._prepare_button.setObjectName("exportPrepareButton")
        self._delete_button = QPushButton(self.tr("Export löschen"))
        self._delete_button.setObjectName("exportDeleteButton")
        self._cancel_button = QPushButton(self.tr("Abbrechen"))
        self._cancel_button.setEnabled(False)
        buttons = QHBoxLayout()
        for button in (self._refresh_button, self._select_all_button, self._select_none_button):
            buttons.addWidget(button)
        buttons.addStretch()
        for button in (self._prepare_button, self._delete_button, self._cancel_button):
            buttons.addWidget(button)

        self._current = QLabel()
        self._current.setObjectName("exportCurrent")
        self._progress = QProgressBar()
        self._progress.hide()

        self._model = ExportTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)
        self._table = QTableView()
        self._table.setObjectName("exportTable")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(COLUMN_NAME, Qt.SortOrder.AscendingOrder)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COLUMN_NAME, QHeaderView.ResizeMode.Stretch)

        self._log = QPlainTextEdit()
        self._log.setObjectName("exportLog")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(MAX_LOG_LINES)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._table)
        splitter.addWidget(self._log)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(device_row)
        layout.addWidget(self._description)
        layout.addWidget(self._export_dir)
        layout.addWidget(self._chdman_missing)
        layout.addLayout(buttons)
        layout.addLayout(send_row)
        layout.addWidget(self._current)
        layout.addWidget(self._progress)
        layout.addWidget(splitter, stretch=1)

    def _connect_signals(self) -> None:
        self._refresh_button.clicked.connect(self.refresh)
        self._select_all_button.clicked.connect(lambda: self._model.set_all_checked(True))
        self._select_none_button.clicked.connect(lambda: self._model.set_all_checked(False))
        self._prepare_button.clicked.connect(self._prepare)
        self._delete_button.clicked.connect(self._delete)
        self._cancel_button.clicked.connect(self._exports.cancel)
        self._exports.running_changed.connect(self._on_running_changed)
        self._exports.status.connect(self._on_status)
        self._exports.progress.connect(self._on_progress)
        self._exports.game_done.connect(lambda key: self._refresh_statuses())
        self._exports.finished.connect(self._on_finished)
        self._device.currentIndexChanged.connect(self._on_device_changed)
        self._settings.changed.connect(self._load_device)
        self._send_button.clicked.connect(self._send)
        self._send_connection.currentIndexChanged.connect(self._on_send_connection_changed)
        self._transfers.connections_changed.connect(self._reload_connections)
        self._exports.transferred.connect(self._refresh_statuses)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._exports.is_running():
            self.refresh()

    def _reload_connections(self) -> None:
        self._send_connection.blockSignals(True)
        self._send_connection.clear()
        for connection in self._transfers.connections():
            self._send_connection.addItem(connection.name, connection.id)
        index = self._send_connection.findData(self._settings.config.export_connection)
        self._send_connection.setCurrentIndex(index if index >= 0 else 0)
        self._send_connection.blockSignals(False)
        self._send_button.setEnabled(self._send_connection.count() > 0)

    def _on_send_connection_changed(self) -> None:
        connection_id = self._send_connection.currentData()
        if connection_id:
            self._settings.save_export_connection(connection_id)

    def _send(self) -> None:
        games = self._model.checked_games()
        hdd = self._settings.config.hdd_path
        connection_id = self._send_connection.currentData()
        if not games or hdd is None:
            self._on_status(self.tr("Bitte zuerst Spiele auswählen."))
            return
        if not connection_id:
            self._on_status(self.tr("Bitte im Reiter „FTP“ zuerst eine Verbindung anlegen."))
            return
        self._exports.send(games, hdd, self._profile(), connection_id)

    def _profile(self) -> DeviceProfile:
        return self._exports.profile(self._device.currentData() or "")

    def _load_device(self) -> None:
        """Übernimmt das gespeicherte Zielgerät (nur, wenn es verfügbar ist)."""
        index = self._device.findData(self._exports.profile(self._settings.config.export_device).id)
        if index >= 0 and index != self._device.currentIndex():
            self._device.blockSignals(True)
            self._device.setCurrentIndex(index)
            self._device.blockSignals(False)

    def _on_device_changed(self) -> None:
        self._settings.save_export_device(self._profile().id)
        self.refresh()

    def refresh(self) -> None:
        """Liest die Bibliothek für das gewählte Zielgerät neu ein."""
        self._load_device()
        self._reload_connections()
        profile = self._profile()
        systems = ", ".join(sorted(PLATFORM_LABELS.get(slug, slug) for slug in profile.platforms))
        self._description.setText(
            self.tr("Angeboten werden: {0}. Ordner im Export: {1}.").format(
                systems, ", ".join(profile.platforms.values())
            )
        )
        hdd = self._settings.config.hdd_path
        if hdd is None:
            self._export_dir.setText(self.tr("Es ist noch kein HDD-Ordner eingerichtet."))
            return
        self._export_dir.setText(
            self.tr("Export-Ordner: {0}").format(self._exports.export_dir(hdd, profile))
        )
        self._model.set_games(
            self._exports.library(hdd, profile),
            self._exports.statuses(hdd, profile),
            self._exports.chdman_available,
        )
        self._table.resizeColumnToContents(COLUMN_SELECT)

    def _refresh_statuses(self) -> None:
        hdd = self._settings.config.hdd_path
        if hdd is not None:
            self._model.set_statuses(self._exports.statuses(hdd, self._profile()))

    def _prepare(self) -> None:
        games = self._model.checked_games()
        hdd = self._settings.config.hdd_path
        if not games or hdd is None:
            self._on_status(self.tr("Bitte zuerst Spiele auswählen."))
            return
        self._log.clear()
        self._exports.prepare(games, hdd, self._profile())

    def _delete(self) -> None:
        games = self._model.checked_games()
        hdd = self._settings.config.hdd_path
        if not games or hdd is None:
            self._on_status(self.tr("Bitte zuerst Spiele auswählen."))
            return
        answer = QMessageBox.question(
            self,
            self.tr("Export löschen"),
            self.tr(
                "Die aufbereiteten Dateien von {0} Spielen löschen? Die Originale im Archiv "
                "bleiben erhalten."
            ).format(len(games)),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._exports.delete([game.key for game in games], hdd, self._profile())
            self._refresh_statuses()

    def _on_running_changed(self, running: bool) -> None:
        for button in (
            self._refresh_button,
            self._select_all_button,
            self._select_none_button,
            self._prepare_button,
            self._delete_button,
            self._device,
            self._send_button,
        ):
            button.setEnabled(not running)
        self._cancel_button.setEnabled(running)
        self._progress.setVisible(running)
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
            self.tr("Fertig: {0} aufbereitet, {1} fehlgeschlagen.").format(ok, failed)
        )
        self._log.appendPlainText(self._current.text())
        self._refresh_statuses()
