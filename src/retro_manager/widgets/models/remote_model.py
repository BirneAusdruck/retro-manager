"""Tabellenmodell für den Inhalt eines Ordners auf dem Gerät."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import QApplication, QStyle

from retro_manager.core.remote import RemoteEntry
from retro_manager.widgets.models.game_table_model import SORT_ROLE, format_size

ModelIndex = QModelIndex | QPersistentModelIndex

COLUMN_NAME, COLUMN_SIZE, COLUMN_MODIFIED = range(3)


class RemoteModel(QAbstractTableModel):
    """Einträge eines entfernten Ordners; Ordner stehen vor Dateien."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[RemoteEntry] = []

    def set_entries(self, entries: list[RemoteEntry]) -> None:
        self.beginResetModel()
        self._entries = sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))
        self.endResetModel()

    def entry(self, row: int) -> RemoteEntry:
        return self._entries[row]

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else 3

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DecorationRole and column == COLUMN_NAME:
            icon = (
                QStyle.StandardPixmap.SP_DirIcon
                if entry.is_dir
                else QStyle.StandardPixmap.SP_FileIcon
            )
            return QApplication.style().standardIcon(icon)
        if role == SORT_ROLE:
            if column == COLUMN_SIZE:
                return -1 if entry.is_dir else entry.size
            if column == COLUMN_MODIFIED:
                return entry.modified.timestamp() if entry.modified else 0
            return (not entry.is_dir, entry.name.lower())
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if column == COLUMN_NAME:
            return entry.name
        if column == COLUMN_SIZE:
            return "" if entry.is_dir else format_size(entry.size)
        if column == COLUMN_MODIFIED:
            return entry.modified.strftime("%d.%m.%Y %H:%M") if entry.modified else ""
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        return [self.tr("Name"), self.tr("Größe"), self.tr("Geändert")][section]
