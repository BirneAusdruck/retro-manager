"""Sammelt alle Hintergrundvorgänge (Igir, DATs, chdman, Archive, Export, FTP) für die Anzeige."""

import re
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal

from retro_manager.controllers.archive_controller import ArchiveController, JobInfo
from retro_manager.controllers.chdman_controller import ChdmanController
from retro_manager.controllers.dat_controller import DatController
from retro_manager.controllers.export_controller import ExportController
from retro_manager.controllers.igir_controller import IgirController
from retro_manager.controllers.transfer_controller import (
    STATE_RUNNING,
    STATE_WAITING,
    TransferController,
    TransferJob,
)

TAB_IGIR = "igir"
TAB_CHDMAN = "chdman"
TAB_ARCHIVE = "archive"
TAB_EXPORT = "export"
TAB_FTP = "ftp"

# Fortschrittsmeldungen höchstens so oft weitergeben (Millisekunden).
_UPDATE_INTERVAL_MS = 100


@dataclass(frozen=True)
class Activity:
    key: str
    label: str
    detail: str
    progress: float | None  # 0.0–1.0 oder None = unbestimmt
    tab: str  # zuständiger Reiter
    running: bool  # False = wartet


class ActivityController(QObject):
    """Geordnete Liste der Vorgänge: laufende zuerst (in Startreihenfolge), dann wartende."""

    changed = Signal()

    def __init__(
        self,
        igir: IgirController,
        dats: DatController,
        chdman: ChdmanController,
        archive_jobs: ArchiveController,
        exports: ExportController,
        transfers: TransferController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._entries: dict[str, Activity] = {}  # Einfügereihenfolge = Startreihenfolge
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_UPDATE_INTERVAL_MS)
        self._timer.timeout.connect(self.changed)

        igir.running_changed.connect(
            lambda running: self._toggle("igir", self.tr("Igir: ROMs prüfen"), TAB_IGIR, running)
        )
        igir.output_line.connect(lambda line: self._update("igir", detail=line))

        dats.running_changed.connect(
            lambda running: self._toggle("dats", self.tr("DATs aktualisieren"), TAB_IGIR, running)
        )
        dats.status.connect(lambda text: self._update("dats", detail=text))
        dats.progress.connect(
            lambda done, total: self._update("dats", progress=_ratio(done, total))
        )

        chdman.queue_changed.connect(
            lambda current, waiting: self._on_queue(
                "chdman", TAB_CHDMAN, current, waiting, lambda title: f"chdman – {title}"
            )
        )
        chdman.phase.connect(lambda text: self._update("chdman", detail=text))
        chdman.progress.connect(
            lambda done, total: self._update("chdman", progress=_ratio(done, total))
        )

        archive_jobs.jobs_changed.connect(self._on_archive_jobs)

        exports.queue_changed.connect(
            lambda current, waiting: self._on_queue(
                "export", TAB_EXPORT, current, waiting, self.tr("Aufbereiten: {0}").format
            )
        )
        exports.status.connect(self._on_export_status)
        exports.progress.connect(
            lambda done, total: self._update("export", progress=_ratio(done, total))
        )

        transfers.job_added.connect(self._on_job)
        transfers.job_changed.connect(self._on_job)
        transfers.job_finished.connect(lambda job: self._remove(_job_key(job)))

    def activities(self) -> list[Activity]:
        entries = list(self._entries.values())
        return [a for a in entries if a.running] + [a for a in entries if not a.running]

    # --- Quellen -------------------------------------------------------------------------

    def _on_queue(
        self,
        key: str,
        tab: str,
        current: str,
        waiting: list[str],
        label: Callable[[str], str],
    ) -> None:
        """Warteschlange eines Controllers: laufender Eintrag `key`, je Wartendem ein Eintrag."""
        if current:
            old = self._entries.get(key)
            self._entries[key] = Activity(
                key, label(current), old.detail if old else "", None, tab, True
            )
        else:
            self._entries.pop(key, None)
        # Wartende behalten ihren Platz in der Liste; nur Neue werden hinten angehängt.
        prefix = f"{key}-wait:"
        wanted = {f"{prefix}{name}": name for name in waiting}
        for stale in [k for k in self._entries if k.startswith(prefix) and k not in wanted]:
            del self._entries[stale]
        for wait_key, name in wanted.items():
            if wait_key not in self._entries:
                self._entries[wait_key] = Activity(wait_key, label(name), "", None, tab, False)
        self._notify(now=True)

    def _on_archive_jobs(self, running: list[JobInfo], waiting: list[tuple[str, str]]) -> None:
        """Mehrere gleichzeitig laufende Archiv-Jobs, je Job ein Eintrag."""
        wanted = {f"archive:{info.key}" for info in running}
        wanted |= {f"archive-wait:{key}" for key, _ in waiting}
        stale = [k for k in self._entries if k.startswith("archive") and k not in wanted]
        structural = bool(stale)
        for key in stale:
            del self._entries[key]
        for info in running:
            key = f"archive:{info.key}"
            structural |= key not in self._entries
            self._entries[key] = Activity(
                key, info.title, info.phase, info.progress, TAB_ARCHIVE, True
            )
        for job_key, title in waiting:
            key = f"archive-wait:{job_key}"
            if key not in self._entries:
                structural = True
                self._entries[key] = Activity(key, title, "", None, TAB_ARCHIVE, False)
        # Neue/entfernte Einträge sofort zeigen, reinen Fortschritt gebündelt.
        self._notify(now=structural)

    def _on_export_status(self, text: str) -> None:
        # „[2/5] Spielname“ steht schon im Titel; als Detail reicht die Position.
        match = re.match(r"^\[(\d+)/(\d+)\]", text)
        if match:
            text = self.tr("Disc {0} von {1}").format(match.group(1), match.group(2))
        self._update("export", detail=text)

    def _on_job(self, job: TransferJob) -> None:
        key = _job_key(job)
        if job.state not in (STATE_WAITING, STATE_RUNNING):
            self._remove(key)
            return
        old = self._entries.get(key)
        arrow = "↑" if job.direction == "upload" else "↓"
        running = job.state == STATE_RUNNING
        detail = (
            f"{_megabytes(job.done)} / {_megabytes(job.total)}" if running and job.total else ""
        )
        self._entries[key] = Activity(
            key, f"FTP {arrow} {job.label}", detail, _ratio(job.done, job.total), TAB_FTP, running
        )
        # Neue Aufträge und Wechsel wartet→läuft sofort zeigen, Fortschritt gebündelt.
        self._notify(now=old is None or old.running != running)

    # --- Pflege der Liste ----------------------------------------------------------------

    def _toggle(self, key: str, label: str, tab: str, running: bool) -> None:
        if running:
            self._entries[key] = Activity(key, label, "", None, tab, True)
        else:
            self._entries.pop(key, None)
        self._notify(now=True)

    def _update(
        self, key: str, *, detail: str | None = None, progress: float | None = None
    ) -> None:
        old = self._entries.get(key)
        if old is None:
            return
        self._entries[key] = Activity(
            key,
            old.label,
            old.detail if detail is None else detail,
            old.progress if progress is None else progress,
            old.tab,
            old.running,
        )
        self._notify()

    def _remove(self, key: str) -> None:
        if self._entries.pop(key, None) is not None:
            self._notify(now=True)

    def _notify(self, now: bool = False) -> None:
        if now:
            self._timer.stop()
            self.changed.emit()
        elif not self._timer.isActive():
            self._timer.start()


def _job_key(job: TransferJob) -> str:
    return f"job:{job.id}"


def _ratio(done: int, total: int) -> float | None:
    return min(1.0, done / total) if total else None


def _megabytes(size: int) -> str:
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.1f} GB"
    return f"{size / 1_000_000:.0f} MB"
