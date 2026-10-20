"""Tabellenmodell für den chdman-Reiter: Discs der Bibliothek mit Prüfergebnis."""

from retro_manager.controllers.chdman_controller import RESULT_BROKEN, RESULT_OK
from retro_manager.core.library import LibraryGame
from retro_manager.widgets.models.game_table_model import GameTableModel


class ChdTableModel(GameTableModel):
    """Statusspalte: Ergebnis von „Prüfen“ (bzw. der Prüfung nach dem Umwandeln)."""

    def status_header(self) -> str:
        return self.tr("Prüfung")

    def status_text(self, game: LibraryGame, status: str) -> str:
        if status == RESULT_OK:
            return self.tr("in Ordnung")
        if status == RESULT_BROKEN:
            return self.tr("fehlerhaft")
        return ""
