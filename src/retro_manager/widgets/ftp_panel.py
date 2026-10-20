"""Arbeitsfläche „FTP“: Dateimanager lokal ↔ Gerät (FTP/FTPS/SFTP) mit Warteschlange."""

from pathlib import Path, PurePosixPath

from PySide6.QtCore import QDir, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileSystemModel,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QStyleOptionViewItem,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from retro_manager.controllers.settings_controller import SettingsController
from retro_manager.controllers.transfer_controller import TransferController
from retro_manager.widgets.connection_dialog import ConnectionDialog
from retro_manager.widgets.models.game_table_model import SORT_ROLE
from retro_manager.widgets.models.remote_model import COLUMN_NAME, RemoteModel
from retro_manager.widgets.models.transfer_model import (
    COLUMN_LABEL,
    COLUMN_PROGRESS,
    PROGRESS_ROLE,
    TransferModel,
)


class _ProgressDelegate(QStyledItemDelegate):
    """Zeichnet in der Fortschrittsspalte einen Balken mit Text."""

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        bar = QStyleOptionProgressBar()
        bar.rect = option.rect.adjusted(2, 3, -2, -3)
        bar.minimum, bar.maximum = 0, 1000
        bar.progress = int(index.data(PROGRESS_ROLE) or 0)
        bar.text = str(index.data() or "")
        bar.textVisible = True
        QApplication.style().drawControl(QStyle.ControlElement.CE_ProgressBar, bar, painter)


class FtpPanel(QWidget):
    """Lokale Dateien links, Gerät rechts; Aufträge laufen in der Warteschlange unten."""

    def __init__(
        self,
        transfers: TransferController,
        settings: SettingsController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._transfers = transfers
        self._settings = settings
        self._remote_path = "/"
        self._build_ui()
        self._connect_signals()
        self._reload_connections()

    # --- Aufbau --------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setObjectName("ftpPanel")

        self._connection = QComboBox()
        self._connection.setObjectName("ftpConnection")
        self._connection.setMinimumWidth(220)
        self._connect_button = QPushButton(self.tr("Verbinden"))
        self._connect_button.setObjectName("ftpConnectButton")
        self._manage_button = QPushButton(self.tr("Verwalten …"))
        self._state = QLabel(self.tr("Nicht verbunden."))
        self._state.setObjectName("ftpState")
        top = QHBoxLayout()
        top.addWidget(QLabel(self.tr("Verbindung:")))
        top.addWidget(self._connection)
        top.addWidget(self._connect_button)
        top.addWidget(self._manage_button)
        top.addWidget(self._state, stretch=1)

        # Links: lokale Dateien
        self._local_model = QFileSystemModel(self)
        self._local_model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        self._local_model.setRootPath("")
        self._local_view = QTreeView()
        self._local_view.setObjectName("ftpLocalView")
        self._local_view.setModel(self._local_model)
        self._local_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._local_view.setSortingEnabled(True)
        self._local_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._local_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._local_path = QLineEdit()
        self._local_up = QPushButton(self.tr("↑ Hoch"))
        local_box = self._pane(self.tr("Lokal"), self._local_path, self._local_up, self._local_view)

        # Rechts: Gerät
        self._remote_model = RemoteModel(self)
        self._remote_proxy = QSortFilterProxyModel(self)
        self._remote_proxy.setSourceModel(self._remote_model)
        self._remote_proxy.setSortRole(SORT_ROLE)
        self._remote_view = QTableView()
        self._remote_view.setObjectName("ftpRemoteView")
        self._remote_view.setModel(self._remote_proxy)
        self._remote_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._remote_view.setSortingEnabled(True)
        self._remote_view.sortByColumn(COLUMN_NAME, Qt.SortOrder.AscendingOrder)
        self._remote_view.verticalHeader().hide()
        self._remote_view.setShowGrid(False)
        self._remote_view.horizontalHeader().setSectionResizeMode(
            COLUMN_NAME, QHeaderView.ResizeMode.Stretch
        )
        self._remote_path_edit = QLineEdit("/")
        self._remote_up = QPushButton(self.tr("↑ Hoch"))
        remote_box = self._pane(
            self.tr("Gerät"), self._remote_path_edit, self._remote_up, self._remote_view
        )

        panes = QSplitter(Qt.Orientation.Horizontal)
        panes.addWidget(local_box)
        panes.addWidget(remote_box)

        self._upload_button = QPushButton(self.tr("Hochladen →"))
        self._upload_button.setObjectName("ftpUploadButton")
        self._download_button = QPushButton(self.tr("← Herunterladen"))
        self._download_button.setObjectName("ftpDownloadButton")
        self._mkdir_button = QPushButton(self.tr("Neuer Ordner"))
        self._rename_button = QPushButton(self.tr("Umbenennen"))
        self._delete_button = QPushButton(self.tr("Löschen"))
        self._refresh_button = QPushButton(self.tr("Aktualisieren"))
        actions = QHBoxLayout()
        actions.addWidget(self._upload_button)
        actions.addWidget(self._download_button)
        actions.addStretch()
        for button in (
            self._mkdir_button,
            self._rename_button,
            self._delete_button,
            self._refresh_button,
        ):
            actions.addWidget(button)

        # Unten: Warteschlange
        self._queue_model = TransferModel(self)
        self._queue_view = QTableView()
        self._queue_view.setObjectName("ftpQueue")
        self._queue_view.setModel(self._queue_model)
        self._queue_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._queue_view.verticalHeader().hide()
        self._queue_view.setItemDelegateForColumn(COLUMN_PROGRESS, _ProgressDelegate(self))
        header = self._queue_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COLUMN_LABEL, QHeaderView.ResizeMode.Stretch)
        header.setMinimumSectionSize(140)
        self._cancel_job_button = QPushButton(self.tr("Auftrag abbrechen"))
        self._clear_button = QPushButton(self.tr("Erledigte entfernen"))
        queue_buttons = QHBoxLayout()
        queue_buttons.addWidget(QLabel(self.tr("Warteschlange")))
        queue_buttons.addStretch()
        queue_buttons.addWidget(self._cancel_job_button)
        queue_buttons.addWidget(self._clear_button)
        queue_box = QWidget()
        queue_layout = QVBoxLayout(queue_box)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        queue_layout.addLayout(queue_buttons)
        queue_layout.addWidget(self._queue_view)

        upper = QWidget()
        upper_layout = QVBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.addWidget(panes, stretch=1)
        upper_layout.addLayout(actions)
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(upper)
        vertical.addWidget(queue_box)
        vertical.setStretchFactor(0, 3)
        vertical.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(vertical, stretch=1)
        self._update_buttons()

    def _pane(self, title: str, path: QLineEdit, up: QPushButton, view: QWidget) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("ftpPaneTitle")
        row.addWidget(label)
        row.addWidget(path, stretch=1)
        row.addWidget(up)
        layout.addLayout(row)
        layout.addWidget(view, stretch=1)
        return box

    def _connect_signals(self) -> None:
        self._manage_button.clicked.connect(self._manage)
        self._connect_button.clicked.connect(self._toggle_connection)
        self._local_view.doubleClicked.connect(self._on_local_double_click)
        self._local_path.returnPressed.connect(
            lambda: self.set_local_dir(Path(self._local_path.text()))
        )
        self._local_up.clicked.connect(lambda: self.set_local_dir(self._local_dir().parent))
        self._remote_view.doubleClicked.connect(self._on_remote_double_click)
        self._remote_path_edit.returnPressed.connect(
            lambda: self._transfers.list_dir(self._remote_path_edit.text() or "/")
        )
        self._remote_up.clicked.connect(
            lambda: self._transfers.list_dir(str(PurePosixPath(self._remote_path).parent))
        )
        self._upload_button.clicked.connect(self._upload)
        self._download_button.clicked.connect(self._download)
        self._mkdir_button.clicked.connect(self._mkdir)
        self._rename_button.clicked.connect(self._rename)
        self._delete_button.clicked.connect(self._delete)
        self._refresh_button.clicked.connect(lambda: self._transfers.list_dir(self._remote_path))
        self._cancel_job_button.clicked.connect(self._cancel_job)
        self._clear_button.clicked.connect(self._clear_finished)
        self._transfers.connections_changed.connect(self._reload_connections)
        self._transfers.browse_connected.connect(self._on_connected)
        self._transfers.browse_disconnected.connect(self._on_disconnected)
        self._transfers.listing.connect(self._on_listing)
        self._transfers.browse_error.connect(self._on_error)
        self._transfers.job_added.connect(self._queue_model.add)
        self._transfers.job_changed.connect(self._queue_model.update)
        self._transfers.job_finished.connect(self._on_job_finished)
        self._remote_view.selectionModel().selectionChanged.connect(self._update_buttons)
        self._local_view.selectionModel().selectionChanged.connect(self._update_buttons)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._local_path.text():
            hdd = self._settings.config.hdd_path
            exports = hdd / "exports" if hdd else None
            self.set_local_dir(exports if exports and exports.is_dir() else Path.home())

    # --- Lokal ---------------------------------------------------------------------------

    def set_local_dir(self, path: Path) -> None:
        if not path.is_dir():
            return
        self._local_view.setRootIndex(self._local_model.index(str(path)))
        self._local_path.setText(str(path))

    def _local_dir(self) -> Path:
        return Path(self._local_path.text() or Path.home())

    def _on_local_double_click(self, index: QModelIndex) -> None:
        path = Path(self._local_model.filePath(index))
        if path.is_dir():
            self.set_local_dir(path)

    def _selected_local(self) -> list[Path]:
        rows = self._local_view.selectionModel().selectedRows()
        return [Path(self._local_model.filePath(index)) for index in rows]

    # --- Gerät ---------------------------------------------------------------------------

    def _reload_connections(self) -> None:
        current = self._connection.currentData()
        self._connection.blockSignals(True)
        self._connection.clear()
        for connection in self._transfers.connections():
            self._connection.addItem(
                f"{connection.name} ({connection.protocol.upper()})", connection.id
            )
        index = self._connection.findData(current)
        self._connection.setCurrentIndex(index if index >= 0 else 0)
        self._connection.blockSignals(False)
        self._update_buttons()

    def _manage(self) -> None:
        ConnectionDialog(self._transfers, self).exec()

    def _toggle_connection(self) -> None:
        if self._transfers.is_browsing():
            self._transfers.disconnect_browse()
            return
        connection_id = self._connection.currentData()
        if not connection_id:
            self._manage()
            return
        self._state.setText(self.tr("Verbinde …"))
        self._connect_button.setEnabled(False)
        self._transfers.connect_browse(connection_id)

    def _on_connected(self, connection_id: str) -> None:
        connection = self._transfers.connection(connection_id)
        self._state.setText(
            self.tr("Verbunden mit {0}.").format(connection.name if connection else connection_id)
        )
        self._connect_button.setText(self.tr("Trennen"))
        self._connect_button.setEnabled(True)
        self._update_buttons()

    def _on_disconnected(self) -> None:
        self._state.setText(self.tr("Nicht verbunden."))
        self._connect_button.setText(self.tr("Verbinden"))
        self._remote_model.set_entries([])
        self._update_buttons()

    def _on_listing(self, path: str, entries: list) -> None:
        self._remote_path = path
        self._remote_path_edit.setText(path)
        self._remote_model.set_entries(entries)
        self._update_buttons()

    def _on_error(self, message: str) -> None:
        self._connect_button.setEnabled(True)
        if not self._transfers.is_browsing():
            self._state.setText(self.tr("Nicht verbunden."))
        QMessageBox.warning(self, self.tr("FTP"), message)

    def _on_remote_double_click(self, index: QModelIndex) -> None:
        entry = self._remote_model.entry(self._remote_proxy.mapToSource(index).row())
        if entry.is_dir:
            self._transfers.list_dir(str(PurePosixPath(self._remote_path) / entry.name))

    def _selected_remote(self) -> list:
        rows = self._remote_view.selectionModel().selectedRows()
        return [
            self._remote_model.entry(self._remote_proxy.mapToSource(index).row()) for index in rows
        ]

    # --- Aktionen ------------------------------------------------------------------------

    def _upload(self) -> None:
        sources = self._selected_local()
        if not sources:
            return
        label = (
            sources[0].name if len(sources) == 1 else self.tr("{0} Einträge").format(len(sources))
        )
        self._transfers.enqueue_upload(
            self._transfers.browse_connection_id(),
            label,
            local_sources=sources,
            remote_dir=self._remote_path,
            tag=("ftp-panel", self._remote_path),
        )

    def _download(self) -> None:
        entries = self._selected_remote()
        if not entries:
            return
        base = PurePosixPath(self._remote_path)
        label = (
            entries[0].name if len(entries) == 1 else self.tr("{0} Einträge").format(len(entries))
        )
        self._transfers.enqueue_download(
            self._transfers.browse_connection_id(),
            label,
            [(str(base / entry.name), entry.is_dir) for entry in entries],
            self._local_dir(),
        )

    def _mkdir(self) -> None:
        name, ok = QInputDialog.getText(self, self.tr("Neuer Ordner"), self.tr("Name:"))
        if ok and name.strip():
            self._transfers.mkdir(self._remote_path, name.strip())

    def _rename(self) -> None:
        entries = self._selected_remote()
        if len(entries) != 1:
            return
        name, ok = QInputDialog.getText(
            self, self.tr("Umbenennen"), self.tr("Neuer Name:"), text=entries[0].name
        )
        if ok and name.strip() and name.strip() != entries[0].name:
            self._transfers.rename(self._remote_path, entries[0].name, name.strip())

    def _delete(self) -> None:
        entries = self._selected_remote()
        if not entries:
            return
        folders = sum(1 for e in entries if e.is_dir)
        text = self.tr("{0} Einträge auf dem Gerät löschen?").format(len(entries))
        if folders:
            text += " " + self.tr(
                "{0} davon sind Ordner – deren gesamter Inhalt wird gelöscht."
            ).format(folders)
        answer = QMessageBox.question(self, self.tr("Löschen"), text)
        if answer == QMessageBox.StandardButton.Yes:
            self._transfers.delete(self._remote_path, [(e.name, e.is_dir) for e in entries])

    def _cancel_job(self) -> None:
        for index in self._queue_view.selectionModel().selectedRows():
            self._transfers.cancel_job(self._queue_model.job(index.row()).id)

    def _clear_finished(self) -> None:
        self._transfers.clear_finished()
        self._queue_model.set_jobs(self._transfers.jobs())

    def _on_job_finished(self, job) -> None:
        self._queue_model.update(job)
        # Nach dem Hochladen in den angezeigten Ordner diesen neu laden.
        if job.direction == "upload" and self._transfers.is_browsing():
            if job.connection_id == self._transfers.browse_connection_id():
                self._transfers.list_dir(self._remote_path)

    def _update_buttons(self) -> None:
        connected = self._transfers.is_browsing()
        remote_selected = (
            bool(self._remote_view.selectionModel().selectedRows())
            if self._remote_view.selectionModel()
            else False
        )
        local_selected = (
            bool(self._local_view.selectionModel().selectedRows())
            if self._local_view.selectionModel()
            else False
        )
        self._upload_button.setEnabled(connected and local_selected)
        self._download_button.setEnabled(connected and remote_selected)
        self._mkdir_button.setEnabled(connected)
        self._refresh_button.setEnabled(connected)
        self._rename_button.setEnabled(connected and remote_selected)
        self._delete_button.setEnabled(connected and remote_selected)
        self._remote_up.setEnabled(connected)
        self._remote_path_edit.setEnabled(connected)
        self._connect_button.setEnabled(self._connection.count() > 0 or not connected)
