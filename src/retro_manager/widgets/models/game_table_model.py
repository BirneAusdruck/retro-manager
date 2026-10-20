"""Tabellenmodell für Spiele der Bibliothek mit Auswahl (Basis für Export, chdman, Archive)."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt

from retro_manager.core.library import LibraryGame

ModelIndex = QModelIndex | QPersistentModelIndex

# Spalten in der Standardreihenfolge; Unterklassen können über `columns()` Spalten ergänzen.
COLUMN_SELECT, COLUMN_SYSTEM, COLUMN_NAME, COLUMN_FORMAT, COLUMN_SIZE, COLUMN_STATUS = range(6)
SELECT, SYSTEM, NAME, FORMAT, SIZE, STATUS = "select", "system", "name", "format", "size", "status"
DEFAULT_COLUMNS = (SELECT, SYSTEM, NAME, FORMAT, SIZE, STATUS)

# Für die Sortierung nach Größe: Rohwert statt Text.
SORT_ROLE = Qt.ItemDataRole.UserRole + 1

_FORMATS = {"chd": "CHD", "iso": "ISO", "cue": "BIN/CUE", "gdi": "GDI"}


def format_size(size: int) -> str:
    for unit, factor in (("GB", 1_000_000_000), ("MB", 1_000_000)):
        if size >= factor:
            return f"{size / factor:.1f} {unit}"
    return f"{size // 1000} KB"


class GameTableModel(QAbstractTableModel):
    """Spiele mit Spalten Auswahl, System, Spiel, Format, Größe und einer Statusspalte.

    Unterklassen legen Überschrift und Text der Statusspalte fest, können Spiele sperren und
    eigene Spalten ergänzen (`columns`, `extra_header`, `extra_text`).
    """

    def __init__(self, platform_labels: dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self._platform_labels = platform_labels
        self._games: list[LibraryGame] = []
        self._statuses: dict[str, str] = {}
        self._checked: set[str] = set()
        self._columns = self.columns()

    # --- Anpassung durch Unterklassen ----------------------------------------------------

    def columns(self) -> tuple[str, ...]:
        return DEFAULT_COLUMNS

    def extra_header(self, column: str) -> str:
        return column

    def extra_text(self, game: LibraryGame, column: str) -> str:
        return ""

    def column_index(self, column: str) -> int:
        return self._columns.index(column)

    def status_header(self) -> str:
        return self.tr("Status")

    def status_text(self, game: LibraryGame, status: str) -> str:
        return status

    def format_text(self, game: LibraryGame) -> str:
        return _FORMATS.get(game.kind, game.path.suffix.lstrip(".").upper())

    def disabled_reason(self, game: LibraryGame) -> str | None:
        """Text für den Tooltip, wenn die Disc nicht ausgewählt werden kann."""
        return None

    # --- Daten ---------------------------------------------------------------------------

    def set_games(self, games: list[LibraryGame], statuses: dict[str, str]) -> None:
        self.beginResetModel()
        self._games = games
        self._statuses = statuses
        self._checked &= {game.key for game in games if self._selectable(game)}
        self.endResetModel()

    def set_statuses(self, statuses: dict[str, str]) -> None:
        self._statuses = statuses
        if self._games:
            column = self.column_index(STATUS)
            self.dataChanged.emit(self.index(0, column), self.index(len(self._games) - 1, column))

    def games(self) -> list[LibraryGame]:
        return list(self._games)

    def checked_games(self) -> list[LibraryGame]:
        return [game for game in self._games if game.key in self._checked]

    def set_all_checked(self, checked: bool) -> None:
        self.beginResetModel()
        self._checked = {g.key for g in self._games if self._selectable(g)} if checked else set()
        self.endResetModel()

    def _selectable(self, game: LibraryGame) -> bool:
        return self.disabled_reason(game) is None

    # --- Qt-Schnittstelle ----------------------------------------------------------------

    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._games)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._columns)

    def flags(self, index: ModelIndex) -> Qt.ItemFlag:
        game = self._games[index.row()]
        if not self._selectable(game):
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._columns[index.column()] == SELECT:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        game = self._games[index.row()]
        column = self._columns[index.column()]
        if column == SELECT and role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if game.key in self._checked else Qt.CheckState.Unchecked
        if role == SORT_ROLE:
            return game.size if column == SIZE else self.data(index)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self.disabled_reason(game) or str(game.path)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if column == SYSTEM:
            return self._platform_labels.get(game.slug, game.slug)
        if column == NAME:
            return f"{game.game_dir} / {game.name}" if game.game_dir else game.name
        if column == FORMAT:
            return self.format_text(game)
        if column == SIZE:
            return format_size(game.size)
        if column == STATUS:
            return self.status_text(game, self._statuses.get(game.key, ""))
        if column == SELECT:
            return None
        return self.extra_text(game, column)

    def setData(
        self, index: ModelIndex, value: object, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if self._columns[index.column()] != SELECT or role != Qt.ItemDataRole.CheckStateRole:
            return False
        key = self._games[index.row()].key
        if Qt.CheckState(value) == Qt.CheckState.Checked:
            self._checked.add(key)
        else:
            self._checked.discard(key)
        self.dataChanged.emit(index, index, [role])
        return True

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        column = self._columns[section]
        headers = {
            SELECT: "",
            SYSTEM: self.tr("System"),
            NAME: self.tr("Spiel"),
            FORMAT: self.tr("Format"),
            SIZE: self.tr("Größe"),
            STATUS: self.status_header(),
        }
        return headers.get(column) if column in headers else self.extra_header(column)
