"""Tabellenmodell der Discs für den Export, mit Auswahlkästchen."""

from retro_manager.core.devices import PLATFORM_LABELS
from retro_manager.core.export import STATUS_PREPARED, STATUS_TRANSFERRED
from retro_manager.core.library import LibraryGame
from retro_manager.widgets.models.game_table_model import GameTableModel


class ExportTableModel(GameTableModel):
    """Discs der Bibliothek mit Export-Status; CHDs nur wählbar, wenn chdman vorhanden ist."""

    def __init__(self, parent=None) -> None:
        super().__init__(PLATFORM_LABELS, parent)
        self._chd_allowed = True

    def set_games(  # type: ignore[override]
        self, games: list[LibraryGame], statuses: dict[str, str], chd_allowed: bool
    ) -> None:
        self._chd_allowed = chd_allowed
        super().set_games(games, statuses)

    def status_header(self) -> str:
        return self.tr("Export")

    def status_text(self, game: LibraryGame, status: str) -> str:
        return {
            STATUS_PREPARED: self.tr("aufbereitet"),
            STATUS_TRANSFERRED: self.tr("übertragen"),
        }.get(status, "")

    def disabled_reason(self, game: LibraryGame) -> str | None:
        if not self._chd_allowed and game.kind == "chd":
            return self.tr("Für CHD-Dateien wird chdman benötigt.")
        return None
