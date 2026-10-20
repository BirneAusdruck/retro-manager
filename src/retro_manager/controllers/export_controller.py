"""Discs für ein Zielgerät aufbereiten: Entpacken/Kopieren im QThreadPool, chdman per QProcess."""

import logging
import threading
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, QProcess, QThreadPool, Signal

from retro_manager.controllers.background_task import BackgroundTask
from retro_manager.controllers.transfer_controller import (
    STATE_DONE,
    TransferController,
    TransferJob,
)
from retro_manager.core import config, dat_update, devices, export, tools
from retro_manager.core.devices import DeviceProfile
from retro_manager.core.export import CancelCheck, ProgressCallback, Step
from retro_manager.core.library import LibraryGame, scan_platform
from retro_manager.core.remote import TransferItem

logger = logging.getLogger(__name__)


class ExportController(QObject):
    """Arbeitet ausgewählte Discs nacheinander ab und führt das Export-Manifest."""

    running_changed = Signal(bool)
    status = Signal(str)
    progress = Signal(object, object)  # Bytes des aktuellen Schritts (über 2 GB möglich)
    overall = Signal(int, int)  # erledigte Discs, gesamt
    game_done = Signal(str)  # Schlüssel der Disc
    finished = Signal(int, int)  # erfolgreich, fehlgeschlagen
    # Name der laufenden Disc (oder "") und Namen der wartenden – für die Aktivitätsanzeige.
    queue_changed = Signal(str, object)
    transferred = Signal()  # ein Export-Auftrag wurde fertig übertragen

    sent = Signal(object)  # TransferJob: Auftrag liegt in der FTP-Warteschlange

    def __init__(
        self,
        chdman: Path | None,
        transfers: TransferController | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._chdman = chdman
        self._transfers = transfers
        if transfers is not None:
            transfers.job_finished.connect(self._on_transfer_finished)
        self._cancel = threading.Event()
        self._running = False
        self._root = Path()
        self._profile: DeviceProfile = devices.DEFAULT_PROFILE
        self._keys_dir: Path | None = None
        self._queue: list[LibraryGame] = []
        self._total = 0
        self._ok = 0
        self._failed = 0
        self._game: LibraryGame | None = None
        self._steps: list[Step] = []
        self._produced: list[Path] = []
        # Ordnerinhalt vor dem laufenden Schritt, um Reste nach Abbruch/Fehler zu entfernen.
        self._step_target: Path | None = None
        self._step_before: set[Path] = set()
        self._task: BackgroundTask | None = None
        self._process: QProcess | None = None

    # --- Abfragen für die Oberfläche ------------------------------------------------------

    @staticmethod
    def profiles() -> tuple[DeviceProfile, ...]:
        """Alle Zielgeräte, auch noch nicht umgesetzte (`available=False`)."""
        return devices.PROFILES

    @staticmethod
    def profile(device_id: str) -> DeviceProfile:
        return devices.get_profile(device_id)

    @property
    def chdman_available(self) -> bool:
        return self._chdman is not None

    def is_running(self) -> bool:
        return self._running

    def library(self, hdd: Path, profile: DeviceProfile) -> list[LibraryGame]:
        """Alle Discs der Plattformen, die das Zielgerät unterstützt."""
        roms = hdd / "roms"
        return [game for slug in profile.platforms for game in scan_platform(roms, slug)]

    def statuses(self, hdd: Path, profile: DeviceProfile) -> dict[str, str]:
        return export.export_status(self.export_dir(hdd, profile))

    def export_dir(self, hdd: Path, profile: DeviceProfile) -> Path:
        return devices.export_root(config.exports_dir(hdd), profile)

    # --- Aktionen ------------------------------------------------------------------------

    def prepare(self, games: list[LibraryGame], hdd: Path, profile: DeviceProfile) -> None:
        """Bereitet die Discs auf; Fehler einzelner Discs brechen den Rest nicht ab."""
        if self._running or not games:
            return
        self._profile = profile
        self._root = self.export_dir(hdd, profile)
        self._keys_dir = config.dats_dir(hdd) / dat_update.KEYS_DIRNAME / "ps3"
        self._queue = list(games)
        self._total = len(games)
        self._ok = self._failed = 0
        self._cancel.clear()
        self._set_running(True)
        self._next_game()

    def delete(self, keys: list[str], hdd: Path, profile: DeviceProfile) -> int:
        """Löscht die aufbereiteten Dateien dieser Discs (nur Einträge aus dem Manifest)."""
        root = self.export_dir(hdd, profile)
        removed = sum(export.delete_export(root, key) for key in keys)
        self.status.emit(self.tr("{0} Dateien aus dem Export gelöscht.").format(removed))
        return removed

    def send(
        self, games: list[LibraryGame], hdd: Path, profile: DeviceProfile, connection_id: str
    ) -> TransferJob | None:
        """Stellt die aufbereiteten Dateien als Auftrag in die FTP-Warteschlange."""
        if self._transfers is None:
            return None
        root = self.export_dir(hdd, profile)
        prepared = export.export_status(root)
        ready = [game for game in games if game.key in prepared]
        if len(ready) < len(games):
            self.status.emit(
                self.tr("{0} Spiele sind noch nicht aufbereitet und werden übersprungen.").format(
                    len(games) - len(ready)
                )
            )
        items = [
            TransferItem(file, devices.remote_path(root, profile, file))
            for game in ready
            for file in export.exported_files(root, game.key)
        ]
        if not items:
            self.status.emit(self.tr("Nichts zu übertragen."))
            return None
        label = ready[0].name if len(ready) == 1 else self.tr("{0} Spiele").format(len(ready))
        job = self._transfers.enqueue_upload(
            connection_id,
            self.tr("{0} → {1}").format(label, profile.label),
            items=items,
            tag=("export", str(root), [game.key for game in ready]),
        )
        self.status.emit(
            self.tr("Auftrag an die FTP-Warteschlange übergeben: {0}").format(job.label)
        )
        self.sent.emit(job)
        return job

    def _on_transfer_finished(self, job: TransferJob) -> None:
        tag = job.tag
        if not (isinstance(tag, tuple) and len(tag) == 3 and tag[0] == "export"):
            return
        if job.state == STATE_DONE:
            root = Path(tag[1])
            for key in tag[2]:
                export.set_status(root, key, export.STATUS_TRANSFERRED)
            self.transferred.emit()

    def cancel(self) -> None:
        if not self._running:
            return
        self._cancel.set()
        if self._process is not None:
            self._process.kill()

    # --- Ablauf --------------------------------------------------------------------------

    def _next_game(self) -> None:
        if self._cancel.is_set() or not self._queue:
            self._finish()
            return
        self._game = self._queue.pop(0)
        self.queue_changed.emit(self._game.name, [game.name for game in self._queue])
        self.overall.emit(self._total - len(self._queue) - 1, self._total)
        self.status.emit(
            self.tr("[{0}/{1}] {2}").format(
                self._total - len(self._queue), self._total, self._game.name
            )
        )
        try:
            self._steps = export.plan_disc_export(
                self._game, self._root, self._profile, self._keys_dir
            )
        except export.ExportError as error:
            self._game_failed(str(error))
            return
        if (
            self._profile.decrypts_ps3
            and self._game.slug == "ps3"
            and not any(isinstance(step, export.DecryptPs3) for step in self._steps)
        ):
            self.status.emit(
                self.tr(
                    "Hinweis: Kein Redump-Disc-Key für {0} – die ISO wird unverändert "
                    "übernommen. Das passt nur, wenn sie bereits entschlüsselt ist; sonst "
                    "erst „DATs aktualisieren“ und die Datei nach Redump benennen."
                ).format(self._game.name)
            )
        self._produced = []
        self._next_step()

    def _next_step(self) -> None:
        if self._cancel.is_set():
            self._on_cancelled()
            return
        if not self._steps:
            self._game_succeeded()
            return
        step = self._steps.pop(0)
        step.target.mkdir(parents=True, exist_ok=True)
        self._step_target = step.target
        self._step_before = set(step.target.iterdir())
        if isinstance(step, export.ChdExtract):
            self._run_chdman(step)
        else:
            self._run_task(step)

    def _run_task(self, step: Step) -> None:
        def work(on_progress: ProgressCallback, is_cancelled: CancelCheck) -> list[Path]:
            needed = export.estimated_size(step)
            free = export.free_space(step.target)
            if needed > free:
                raise export.ExportError(
                    self.tr(
                        "Nicht genug Platz im Export-Ordner ({0} MB nötig, {1} MB frei)."
                    ).format(needed // 1_000_000, free // 1_000_000)
                )
            if isinstance(step, export.ExtractArchive):
                return export.extract_archive(step, on_progress, is_cancelled)
            if isinstance(step, export.DecryptPs3):
                self.status.emit(self.tr("Entschlüssele mit Disc-Key {0} …").format(step.key.name))
                return export.decrypt_ps3(step, on_progress, is_cancelled)
            return export.copy_files(step, on_progress, is_cancelled)

        task = BackgroundTask(work, self._cancel.is_set)
        task.signals.progress.connect(self.progress)
        task.signals.done.connect(self._on_task_done)
        task.signals.error.connect(self._game_failed)
        task.signals.cancelled.connect(self._on_cancelled)
        self._task = task
        QThreadPool.globalInstance().start(task)

    def _on_task_done(self, files: list[Path]) -> None:
        self._task = None
        self._produced += files
        self._next_step()

    def _run_chdman(self, step: export.ChdExtract, retried: bool = False) -> None:
        if self._chdman is None:
            self._game_failed(self.tr("chdman ist nicht installiert."))
            return
        before = self._step_before
        process = QProcess(self)
        process.setProgram(str(self._chdman))
        process.setArguments(
            tools.chdman_extract_args(step.media, step.source, step.target, step.name)
        )
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.finished.connect(
            lambda code, exit_status: self._on_chdman_finished(process, step, before, code, retried)
        )
        self._process = process
        self.progress.emit(0, 0)
        logger.info("Starte chdman %s", " ".join(process.arguments()))
        process.start()

    def _on_chdman_finished(
        self,
        process: QProcess,
        step: export.ChdExtract,
        before: set[Path],
        exit_code: int,
        retried: bool,
    ) -> None:
        if not shiboken6.isValid(process):
            return
        output = bytes(process.readAll().data()).decode(errors="replace").strip()
        process.deleteLater()
        self._process = None
        if self._cancel.is_set():
            self._on_cancelled()
            return
        if exit_code != 0:
            if step.media == "dvd" and not retried:
                # Manche PS2-Spiele liegen auf CD: dann als BIN/CUE zurückwandeln.
                self._run_chdman(export.ChdExtract(step.source, step.target, "cd", step.name), True)
                return
            self._game_failed(self.tr("chdman: {0}").format(output.splitlines()[-1:] or exit_code))
            return
        if step.media == "cd":
            export.normalize_single_track(step.target / f"{step.name}.cue")
        self._produced += sorted(set(step.target.iterdir()) - before)
        self._next_step()

    def _game_succeeded(self) -> None:
        assert self._game is not None
        existing = [path for path in self._produced if path.is_file()]
        export.record_export(self._root, self._game.key, existing)
        self._ok += 1
        self.game_done.emit(self._game.key)
        self._next_game()

    def _remove_partial(self) -> None:
        """Entfernt Dateien dieser Disc, die noch nicht im Manifest stehen."""
        if self._step_target is not None and self._step_target.is_dir():
            created = set(self._step_target.iterdir()) - self._step_before
        else:
            created = set()
        for path in sorted(created | set(self._produced), reverse=True):
            if path.is_file():
                path.unlink()
        for directory in {path.parent for path in created | set(self._produced)}:
            if directory != self._root and directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        self._produced = []
        self._step_target = None

    def _on_cancelled(self) -> None:
        self._remove_partial()
        self._finish()

    def _game_failed(self, message: str) -> None:
        self._remove_partial()
        self._task = None
        name = self._game.name if self._game else ""
        logger.error("Export fehlgeschlagen (%s): %s", name, message)
        self.status.emit(self.tr("Fehler bei {0}: {1}").format(name, message))
        self._failed += 1
        self._next_game()

    def _finish(self) -> None:
        if not self._running:
            return
        self._task = None
        if self._cancel.is_set():
            self.status.emit(self.tr("Abgebrochen."))
        self.overall.emit(self._ok + self._failed, self._total)
        self._queue = []
        self.queue_changed.emit("", [])
        self._set_running(False)
        self.finished.emit(self._ok, self._failed)

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.running_changed.emit(running)
