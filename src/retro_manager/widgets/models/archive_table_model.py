"""Tabellenmodell für den Reiter „Archive“: alle Einträge der Bibliothek mit Prüfergebnis."""

from retro_manager.controllers.archive_controller import (
    RESULT_BROKEN,
    RESULT_OK,
    ArchiveController,
)
from retro_manager.core.library import LibraryGame
from retro_manager.widgets.models.game_table_model import (
    FORMAT,
    NAME,
    SELECT,
    SIZE,
    STATUS,
    SYSTEM,
    GameTableModel,
)

TARGET = "target"  # Zielformat des Systems laut Archivregeln


class ArchiveTableModel(GameTableModel):
    """Spalten: Auswahl, System, Spiel, Format (Archivart bzw. Dateiart), Größe (aller Teile
    bzw. Tracks), Zielformat des Systems, Prüfung."""

    def columns(self) -> tuple[str, ...]:
        return (SELECT, SYSTEM, NAME, FORMAT, SIZE, TARGET, STATUS)

    def extra_header(self, column: str) -> str:
        return self.tr("Zielformat") if column == TARGET else column

    def extra_text(self, game: LibraryGame, column: str) -> str:
        if column != TARGET:
            return ""
        target = ArchiveController.target_format(game.slug)
        return target.upper() if target else self.tr("–")

    def __init__(self, platform_labels: dict[str, str], parent=None) -> None:
        super().__init__(platform_labels, parent)
        self._format_texts: dict[str, str] = {}

    def set_games(self, games: list[LibraryGame], statuses: dict[str, str]) -> None:
        # Einmal berechnen: Teile mehrteiliger Archive zu zählen liest das Verzeichnis.
        self._format_texts = {game.key: self._describe(game) for game in games}
        super().set_games(games, statuses)

    def format_text(self, game: LibraryGame) -> str:
        return self._format_texts.get(game.key) or super().format_text(game)

    def _describe(self, game: LibraryGame) -> str:
        if game.kind != "archive":
            return super().format_text(game)
        return ArchiveController.describe_archive(game)

    def status_header(self) -> str:
        return self.tr("Prüfung")

    def status_text(self, game: LibraryGame, status: str) -> str:
        if status == RESULT_OK:
            return self.tr("in Ordnung")
        if status == RESULT_BROKEN:
            return self.tr("fehlerhaft")
        return ""
