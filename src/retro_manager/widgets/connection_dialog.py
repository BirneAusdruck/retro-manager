"""Dialog zum Anlegen, Bearbeiten, Testen und Löschen gespeicherter Verbindungen."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from retro_manager.controllers.transfer_controller import TransferController, updated
from retro_manager.widgets.info_label import InfoLabel

PROTOCOL_LABELS = {"ftp": "FTP", "ftps": "FTPS (FTP über TLS)", "sftp": "SFTP (über SSH)"}


class ConnectionDialog(QDialog):
    """Links die gespeicherten Verbindungen, rechts die Daten der gewählten."""

    def __init__(self, transfers: TransferController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._transfers = transfers
        self._current_id = ""
        self._build_ui()
        self._connect_signals()
        self._reload()

    def _build_ui(self) -> None:
        self.setObjectName("connectionDialog")
        self.setWindowTitle(self.tr("Verbindungen verwalten"))
        self.resize(720, 380)

        self._list = QListWidget()
        self._new_button = QPushButton(self.tr("Neu"))
        self._delete_button = QPushButton(self.tr("Löschen"))
        left = QVBoxLayout()
        left.addWidget(self._list, stretch=1)
        row = QHBoxLayout()
        row.addWidget(self._new_button)
        row.addWidget(self._delete_button)
        left.addLayout(row)

        self._name = QLineEdit()
        self._protocol = QComboBox()
        for protocol in self._transfers.protocols():
            self._protocol.addItem(PROTOCOL_LABELS.get(protocol, protocol), protocol)
        self._host = QLineEdit()
        self._host.setPlaceholderText(self.tr("z. B. 192.168.1.50 oder nas.local"))
        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._user = QLineEdit()
        self._user.setPlaceholderText(self.tr("leer = anonym (nur FTP/FTPS)"))
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._start_dir = QLineEdit()
        self._start_dir.setPlaceholderText("/")
        self._status = QLabel()
        self._status.setObjectName("connectionStatus")
        self._status.setWordWrap(True)

        form = QFormLayout()
        form.addRow(self.tr("Name:"), self._name)
        form.addRow(
            InfoLabel(
                self.tr("Protokoll:"),
                self.tr(
                    "FTP: unverschlüsselt, z. B. PS3 mit webMAN, PS2 (wLaunchELF), Xbox 360 "
                    "(Aurora/FSD). FTPS: FTP mit TLS-Verschlüsselung, z. B. NAS. SFTP: über SSH, "
                    "z. B. Linux-Rechner, Steam Deck, viele NAS. Beim ersten SFTP-Verbinden merkt "
                    "sich die App den Schlüssel des Geräts und warnt, falls er sich ändert."
                ),
            ),
            self._protocol,
        )
        form.addRow(self.tr("Adresse:"), self._host)
        form.addRow(self.tr("Port:"), self._port)
        form.addRow(self.tr("Benutzer:"), self._user)
        form.addRow(
            InfoLabel(
                self.tr("Passwort:"),
                self.tr(
                    "Wird im Schlüsselbund des Systems gespeichert, nicht in der Einstellungsdatei."
                ),
            ),
            self._password,
        )
        form.addRow(self.tr("Startordner:"), self._start_dir)

        self._test_button = QPushButton(self.tr("Testen"))
        self._save_button = QPushButton(self.tr("Speichern"))
        self._save_button.setDefault(True)
        actions = QHBoxLayout()
        actions.addWidget(self._test_button)
        actions.addStretch()
        actions.addWidget(self._save_button)

        right = QVBoxLayout()
        right.addLayout(form)
        right.addWidget(self._status)
        right.addStretch()
        right.addLayout(actions)
        self._editor = QWidget()
        self._editor.setLayout(right)

        body = QHBoxLayout()
        body.addLayout(left, stretch=1)
        body.addWidget(self._editor, stretch=2)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        layout = QVBoxLayout(self)
        layout.addLayout(body)
        layout.addWidget(self._buttons)

    def _connect_signals(self) -> None:
        self._list.currentItemChanged.connect(self._on_selected)
        self._new_button.clicked.connect(self._new)
        self._delete_button.clicked.connect(self._delete)
        self._protocol.currentIndexChanged.connect(self._on_protocol_changed)
        self._test_button.clicked.connect(self._test)
        self._save_button.clicked.connect(self._save)
        self._buttons.rejected.connect(self.reject)
        self._transfers.connection_tested.connect(self._on_tested)

    def _reload(self, select_id: str = "") -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for connection in self._transfers.connections():
            item = QListWidgetItem(connection.name)
            item.setData(Qt.ItemDataRole.UserRole, connection.id)
            self._list.addItem(item)
            if connection.id == (select_id or self._current_id):
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        if self._list.currentItem() is None and self._list.count():
            self._list.setCurrentRow(0)
        self._on_selected(self._list.currentItem())

    def _on_selected(self, item: QListWidgetItem | None) -> None:
        connection = (
            self._transfers.connection(item.data(Qt.ItemDataRole.UserRole)) if item else None
        )
        self._editor.setEnabled(connection is not None)
        self._delete_button.setEnabled(connection is not None)
        self._status.clear()
        if connection is None:
            self._current_id = ""
            return
        self._current_id = connection.id
        self._name.setText(connection.name)
        self._protocol.blockSignals(True)
        self._protocol.setCurrentIndex(max(0, self._protocol.findData(connection.protocol)))
        self._protocol.blockSignals(False)
        self._host.setText(connection.host)
        self._port.setValue(connection.port)
        self._user.setText(connection.user)
        self._password.clear()
        self._password.setPlaceholderText(
            self.tr("unverändert") if self._transfers.password(connection) else ""
        )
        self._start_dir.setText(connection.start_dir)

    def _on_protocol_changed(self) -> None:
        self._port.setValue(self._transfers.default_port(self._protocol.currentData()))

    def _edited(self):
        connection = self._transfers.connection(self._current_id)
        if connection is None:
            return None
        return updated(
            connection,
            name=self._name.text().strip() or self._host.text().strip(),
            protocol=self._protocol.currentData(),
            host=self._host.text().strip(),
            port=self._port.value(),
            user=self._user.text().strip(),
            start_dir=self._start_dir.text().strip() or "/",
        )

    def _password_value(self, connection) -> str:
        return self._password.text() or self._transfers.password(connection)

    def _new(self) -> None:
        connection = self._transfers.new_connection(self.tr("Neue Verbindung"))
        self._transfers.save_connection(connection, None)
        self._reload(connection.id)
        self._name.setFocus()
        self._name.selectAll()

    def _delete(self) -> None:
        connection = self._transfers.connection(self._current_id)
        if connection is None:
            return
        answer = QMessageBox.question(
            self, self.tr("Verbindung löschen"), self.tr("„{0}“ löschen?").format(connection.name)
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._transfers.delete_connection(connection.id)
            self._current_id = ""
            self._reload()

    def _save(self) -> None:
        connection = self._edited()
        if connection is None:
            return
        if not connection.host:
            self._status.setText(self.tr("Bitte eine Adresse eintragen."))
            return
        error = self._transfers.save_connection(connection, self._password.text() or None)
        self._status.setText(error or self.tr("Gespeichert."))
        self._reload(connection.id)

    def _test(self) -> None:
        connection = self._edited()
        if connection is None or not connection.host:
            self._status.setText(self.tr("Bitte eine Adresse eintragen."))
            return
        self._status.setText(self.tr("Verbinde …"))
        self._test_button.setEnabled(False)
        self._transfers.test(connection, self._password_value(connection))

    def _on_tested(self, ok: bool, message: str) -> None:
        self._test_button.setEnabled(True)
        if self.isVisible():
            self._status.setText(
                (self.tr("✓ Verbindung klappt: {0}") if ok else self.tr("✗ {0}")).format(message)
            )
