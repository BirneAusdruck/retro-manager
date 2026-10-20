"""Hintergrundarbeit im QThreadPool mit Fortschritt, Abbruch und Ergebnis per Signal."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal

from retro_manager.core.archives import ArchiveError
from retro_manager.core.chd import ChdError
from retro_manager.core.progress import CancelCheck, ExportCancelled, ExportError, ProgressCallback

Work = Callable[[ProgressCallback, CancelCheck], Any]

# Fehler, die als Meldung für den Nutzer gelten (alles andere ist ein Programmfehler).
_USER_ERRORS = (ExportError, ChdError, ArchiveError, OSError)


class _TaskSignals(QObject):
    # object statt int: Bytezahlen über 2 GB passen nicht in ein 32-Bit-Qt-int.
    progress = Signal(object, object)
    done = Signal(object)  # Rückgabewert der Arbeit
    error = Signal(str)
    cancelled = Signal()


class BackgroundTask(QRunnable):
    """Führt `work(on_progress, is_cancelled)` in einem Pool-Thread aus."""

    def __init__(self, work: Work, is_cancelled: CancelCheck) -> None:
        super().__init__()
        self.signals = _TaskSignals()
        self._work = work
        self._is_cancelled = is_cancelled

    def run(self) -> None:
        try:
            result = self._work(self.signals.progress.emit, self._is_cancelled)
        except ExportCancelled:
            self.signals.cancelled.emit()
        except _USER_ERRORS as error:
            self.signals.error.emit(str(error))
        else:
            self.signals.done.emit(result)
