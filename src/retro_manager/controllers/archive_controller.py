"""Reiter „Archive“: Entpacken, Packen, Prüfen mit 7-Zip – mehrere Einträge gleichzeitig."""

import itertools
import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, QProcess, QThreadPool, QTimer, Signal

from retro_manager.controllers.background_task import BackgroundTask
from retro_manager.core import archives, chd, config, devices, formats, library, tools
from retro_manager.core.archives import ArchiveError
from retro_manager.core.library import LibraryGame
from retro_manager.core.progress import CancelCheck, ProgressCallback

logger = logging.getLogger(__name__)

OP_EXTRACT = "extract"
OP_PACK = "pack"
OP_TEST = "test"

RESULT_OK = "ok"  # Archiv geprüft und in Ordnung
RESULT_BROKEN = "broken"  # Prüfung fehlgeschlagen

_MAX_OUTPUT_LINES = 200
_UNPACKED_DIRNAME = "entpackt"
_TAR_DIRNAME = "tar"

# Rückmeldung eines beendeten 7-Zip-Aufrufs: Rückgabewert und Fehlerzeilen.
ProcessDone = Callable[[int, list[str]], None]


@dataclass(frozen=True)
class _Operation:
    kind: str
    game: LibraryGame
    work_root: Path = Path()
    destination: Path | None = None  # Entpacken: Zielordner, None = neben das Archiv
    archive_format: str = "zip"
    level: int = 5
    delete_originals: bool = False


@dataclass(frozen=True)
class JobInfo:
    """Laufender Job für die Aktivitätsanzeige."""

    key: str
    title: str
    phase: str
    progress: float | None


class _Job(QObject):
    """Ein Eintrag: eigene 7-Zip-Prozesse, eigener Arbeitsordner, räumt bei Fehler/Abbruch auf."""

    changed = Signal()  # Phase oder Fortschritt
    message = Signal(str)  # Protokollzeile
    done = Signal(object)  # self

    def __init__(self, job_id: int, sevenzip: Path, operation: _Operation, title: str) -> None:
        super().__init__()
        self.id = job_id
        self.operation = operation
        self.title = title
        self.phase = ""
        self.progress: float | None = None
        self.ok = False
        self.cancelled = False
        self.result: str | None = None  # RESULT_* bei „Prüfen“
        self.error = ""
        self._sevenzip = sevenzip
        self._process: QProcess | None = None
        self._task: BackgroundTask | None = None
        self._buffer = ""
        self._errors: list[str] = []
        self._work: Path | None = None
        self._finished = False

    @property
    def game(self) -> LibraryGame:
        return self.operation.game

    def info(self) -> JobInfo:
        return JobInfo(self.game.key, self.title, self.phase, self.progress)

    # --- Steuerung -----------------------------------------------------------------------

    def start(self) -> None:
        try:
            if self.operation.kind == OP_TEST:
                self._set_phase(self.tr("Prüfen …"))
                self._run(tools.sevenzip_test_args(self.game.path), self._on_tested)
            elif self.operation.kind == OP_EXTRACT:
                self._prepare_work()
                self._unpack(self._finish_extract)
            else:
                archives.check_pack_target(self.game, self.operation.archive_format)
                self._prepare_work()
                if self.game.kind == "archive":
                    self._unpack(self._pack_contents)
                else:
                    self._pack(self.game.path.parent, None)
        except (ArchiveError, OSError) as error:
            self._fail(str(error))

    def cancel(self) -> None:
        self.cancelled = True
        if self._process is not None:
            self._process.kill()
        elif self._task is None:
            self._end()

    # --- Entpacken (auch als erster Schritt beim Umpacken) --------------------------------

    def _prepare_work(self) -> None:
        work = archives.work_dir(self.operation.work_root, self.game)
        if work.exists():
            shutil.rmtree(work)  # Reste eines abgebrochenen Laufs
        work.mkdir(parents=True)
        self._work = work

    def _unpack(self, then: Callable[[Path], None]) -> None:
        assert self._work is not None
        staging = self._work / _UNPACKED_DIRNAME

        def unpacked(exit_code: int, errors: list[str]) -> None:
            if exit_code != 0:
                self._fail_7zip(exit_code, errors)
                return
            if not archives.is_compressed_tar(self.game.path):
                then(staging)
                return
            # .tar.gz & Co.: Schritt 1 ergab die .tar, jetzt deren Inhalt.
            inner = archives.find_inner_tar(staging)
            tar_dir = self._work / _TAR_DIRNAME
            self._set_phase(self.tr("Entpacken (TAR) …"))
            self._run(
                tools.sevenzip_extract_args(inner, tar_dir),
                lambda code, errs: self._fail_7zip(code, errs) if code else then(tar_dir),
            )

        self._set_phase(self.tr("Entpacken …"))
        self._run(tools.sevenzip_extract_args(self.game.path, staging), unpacked)

    def _finish_extract(self, staging: Path) -> None:
        destination = self.operation.destination or self.game.path.parent
        delete = self.operation.delete_originals

        def work(on_progress: ProgressCallback, is_cancelled: CancelCheck) -> list[Path]:
            moves = archives.extracted_layout(staging, destination, self.game.name)
            targets = archives.move_into_place(moves)
            removed = archives.remove_files(archives.original_files(self.game)) if delete else 0
            for target in targets:
                self.message.emit(self.tr("→ {0}").format(target))
            if removed:
                self.message.emit(self.tr("Archiv entfernt ({0} Dateien).").format(removed))
            return targets

        self._set_phase(self.tr("Einsortieren …"))
        self._start_task(work)

    # --- Packen --------------------------------------------------------------------------

    def _pack_contents(self, staging: Path) -> None:
        names = sorted(path.name for path in staging.iterdir())
        self._pack(staging, names)

    def _pack(self, source_dir: Path, contents: list[str] | None) -> None:
        assert self._work is not None
        operation = self.operation
        plan = archives.plan_pack(self.game, operation.archive_format, self._work, contents)
        archive_type, _ = archives.PACK_FORMATS[operation.archive_format]

        def packed(exit_code: int, errors: list[str]) -> None:
            if exit_code != 0:
                self._fail_7zip(exit_code, errors)
                return
            self._set_phase(self.tr("Neues Archiv prüfen …"))
            self._run(tools.sevenzip_test_args(plan.part), tested)

        def tested(exit_code: int, errors: list[str]) -> None:
            if exit_code != 0:
                self._fail(
                    self.tr("Prüfung des neuen Archivs fehlgeschlagen: {0}").format(
                        _error_text(exit_code, errors)
                    )
                )
                return
            self._start_task(store)

        def store(on_progress: ProgressCallback, is_cancelled: CancelCheck) -> list[Path]:
            shutil.move(plan.part, plan.target)
            originals = archives.original_files(self.game)
            removed = archives.remove_files(originals) if operation.delete_originals else 0
            self.message.emit(self.tr("→ {0} (geprüft)").format(plan.target))
            if removed:
                self.message.emit(self.tr("Original entfernt ({0} Dateien).").format(removed))
            return [plan.target]

        self._set_phase(self.tr("Packen …"))
        self._run(
            tools.sevenzip_pack_args(archive_type, operation.level, plan.part, list(plan.names)),
            packed,
            cwd=source_dir,
        )

    # --- Prüfen --------------------------------------------------------------------------

    def _on_tested(self, exit_code: int, errors: list[str]) -> None:
        if exit_code == 0:
            self.result = RESULT_OK
            self.message.emit(self.tr("In Ordnung."))
            self._succeed()
        else:
            self.result = RESULT_BROKEN
            self._fail(
                self.tr("Prüfung fehlgeschlagen: {0}").format(_error_text(exit_code, errors))
            )

    # --- 7-Zip und Hintergrundarbeit -----------------------------------------------------

    def _run(self, args: list[str], on_done: ProcessDone, cwd: Path | None = None) -> None:
        process = QProcess(self)
        process.setProgram(str(self._sevenzip))
        process.setArguments(args)
        if cwd is not None:
            process.setWorkingDirectory(str(cwd))
        process.readyReadStandardOutput.connect(lambda: self._read_progress(process))
        process.readyReadStandardError.connect(lambda: self._read_errors(process))
        process.finished.connect(
            lambda code, exit_status: self._on_finished(process, code, exit_status, on_done)
        )
        process.errorOccurred.connect(lambda error: self._on_error(process, error))
        self._process = process
        self._buffer = ""
        self._errors = []
        self.progress = None
        self.changed.emit()
        logger.info("Starte 7-Zip %s", " ".join(args[:3]))
        process.start()

    def _read_progress(self, process: QProcess) -> None:
        if not shiboken6.isValid(process):
            return
        self._buffer += bytes(process.readAllStandardOutput().data()).decode(errors="replace")
        fraction = archives.parse_progress(self._buffer)
        # Nur den letzten, evtl. unvollständigen Abschnitt für den nächsten Block behalten.
        self._buffer = self._buffer[-64:]
        if fraction is not None and fraction != self.progress:
            self.progress = fraction
            self.changed.emit()

    def _read_errors(self, process: QProcess) -> None:
        if not shiboken6.isValid(process):
            return
        text = bytes(process.readAllStandardError().data()).decode(errors="replace")
        self._errors += tools.clean_output(text)
        del self._errors[:-_MAX_OUTPUT_LINES]

    def _on_finished(
        self,
        process: QProcess,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
        on_done: ProcessDone,
    ) -> None:
        if not shiboken6.isValid(process):
            return
        self._read_errors(process)
        process.deleteLater()
        self._process = None
        if self.cancelled:
            self._end()
            return
        crashed = exit_status != QProcess.ExitStatus.NormalExit
        try:
            on_done(-1 if crashed else exit_code, list(self._errors))
        except (ArchiveError, OSError) as error:
            self._fail(str(error))

    def _on_error(self, process: QProcess, error: QProcess.ProcessError) -> None:
        if error != QProcess.ProcessError.FailedToStart or not shiboken6.isValid(process):
            return
        process.deleteLater()
        self._process = None
        self._fail(
            self.tr("7-Zip konnte nicht gestartet werden: {0}").format(process.errorString())
        )

    def _start_task(self, work: Callable[[ProgressCallback, CancelCheck], list[Path]]) -> None:
        task = BackgroundTask(work, lambda: self.cancelled)
        task.signals.done.connect(self._on_task_done)
        task.signals.error.connect(self._on_task_error)
        task.signals.cancelled.connect(self._end)
        self._task = task
        QThreadPool.globalInstance().start(task)

    def _on_task_done(self, result: object) -> None:
        self._task = None
        self._succeed()

    def _on_task_error(self, message: str) -> None:
        self._task = None
        self._fail(message)

    # --- Abschluss -----------------------------------------------------------------------

    def _set_phase(self, text: str) -> None:
        self.phase = text
        self.changed.emit()

    def _fail_7zip(self, exit_code: int, errors: list[str]) -> None:
        self._fail(self.tr("7-Zip: {0}").format(_error_text(exit_code, errors)))

    def _succeed(self) -> None:
        self.ok = True
        self._end()

    def _fail(self, message: str) -> None:
        self.error = message
        self._end()

    def _end(self) -> None:
        if self._finished:
            return
        self._finished = True
        # Arbeitsordner immer entfernen: enthält nur Zwischenstände, nie Originale.
        if self._work is not None and self._work.exists():
            shutil.rmtree(self._work, ignore_errors=True)
        # Über die Event-Loop, damit der Controller nicht mitten in `start()` weiterschaltet.
        QTimer.singleShot(0, lambda: self.done.emit(self))


class ArchiveController(QObject):
    """Warteschlange; startet bis zu `max_parallel` Jobs gleichzeitig."""

    running_changed = Signal(bool)
    status = Signal(str)  # Protokollzeile
    result_changed = Signal(str, str)  # Bibliotheksschlüssel, RESULT_*
    overall = Signal(int, int)  # erledigt, gesamt
    finished = Signal(int, int)  # erfolgreich, fehlgeschlagen
    # Laufende Jobs (list[JobInfo]) und wartende ((Schlüssel, Titel), …) für die Aktivitätsanzeige.
    jobs_changed = Signal(object, object)

    def __init__(
        self, sevenzip: Path | None, max_parallel: int, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._sevenzip = sevenzip
        self._max_parallel = max(1, max_parallel)
        self._queue: list[_Operation] = []
        self._jobs: list[_Job] = []
        self._ids = itertools.count(1)
        self._results: dict[str, str] = {}
        self._running = False
        self._cancelled = False
        self._total = self._ok = self._failed = 0

    # --- Abfragen für die Oberfläche ------------------------------------------------------

    @property
    def sevenzip_available(self) -> bool:
        return self._sevenzip is not None

    @property
    def max_parallel(self) -> int:
        return self._max_parallel

    def set_max_parallel(self, count: int) -> None:
        """Gilt sofort: weitere Jobs starten, sobald Plätze frei werden."""
        self._max_parallel = max(1, count)
        if self._running:
            self._fill()

    def is_running(self) -> bool:
        return self._running

    @staticmethod
    def platform_labels() -> dict[str, str]:
        return {**chd.CHD_PLATFORMS, **devices.PLATFORM_LABELS}

    def library(self, hdd: Path) -> list[LibraryGame]:
        """Alle Einträge aller Plattformordner unter `roms/`."""
        roms = hdd / "roms"
        return [
            game for slug in library.platforms(roms) for game in library.scan_entries(roms, slug)
        ]

    def results(self) -> dict[str, str]:
        return dict(self._results)

    @staticmethod
    def target_format(slug: str) -> str | None:
        """Archivformat, das die Bibliothek für dieses System vorsieht (z. B. `zip`, `chd`)."""
        return formats.target_format(slug)

    @staticmethod
    def describe_archive(game: LibraryGame) -> str:
        """`7Z`, `TAR.GZ`, `RAR (3 Teile)` … für die Formatspalte."""
        label = archives.archive_label(game.path)
        parts = len(archives.volumes(game.path))
        return f"{label} ({parts} Teile)" if parts > 1 else label

    def format_mismatches(self, games: list[LibraryGame], archive_format: str) -> list[str]:
        """Systeme, deren Zielformat nicht `archive_format` ist, z. B. `PS1 → CHD`."""
        labels = self.platform_labels()
        return sorted(
            {
                f"{labels.get(game.slug, game.slug)} → {target.upper()}"
                for game in games
                if (target := formats.target_format(game.slug)) not in (None, archive_format)
            }
        )

    # --- Aktionen ------------------------------------------------------------------------

    def extract(
        self,
        games: list[LibraryGame],
        hdd: Path,
        destination: Path | None,
        delete_originals: bool,
    ) -> int:
        """Entpackt Archive neben sich (oder nach `destination`)."""
        selected = [game for game in games if game.kind == "archive"]
        work_root = config.work_dir(hdd)
        return self._start(
            [
                _Operation(
                    OP_EXTRACT, game, work_root, destination, delete_originals=delete_originals
                )
                for game in selected
            ]
        )

    def pack(
        self,
        games: list[LibraryGame],
        hdd: Path,
        archive_format: str,
        level: str,
        delete_originals: bool,
    ) -> int:
        """Packt jeden Eintrag in ein eigenes Archiv; vorhandene Archive werden umgepackt."""
        work_root = config.work_dir(hdd)
        mx = archives.PACK_LEVELS.get(level, archives.PACK_LEVELS["normal"])
        return self._start(
            [
                _Operation(
                    OP_PACK,
                    game,
                    work_root,
                    archive_format=archive_format,
                    level=mx,
                    delete_originals=delete_originals,
                )
                for game in games
            ]
        )

    def test(self, games: list[LibraryGame]) -> int:
        return self._start([_Operation(OP_TEST, game) for game in games if game.kind == "archive"])

    def cancel(self) -> None:
        if not self._running:
            return
        self._cancelled = True
        self._queue = []
        for job in list(self._jobs):
            job.cancel()
        self._emit_jobs()
        if not self._jobs:
            self._finish()

    # --- Ablauf --------------------------------------------------------------------------

    def _title(self, operation: _Operation) -> str:
        if operation.kind == OP_PACK and operation.game.kind == "archive":
            verb = self.tr("Umpacken")
        else:
            verb = {
                OP_EXTRACT: self.tr("Entpacken"),
                OP_PACK: self.tr("Packen"),
                OP_TEST: self.tr("Prüfen"),
            }[operation.kind]
        return f"{verb}: {operation.game.name}"

    def _start(self, operations: list[_Operation]) -> int:
        if self._running or not operations:
            return 0
        if self._sevenzip is None:
            self.status.emit(self.tr("7-Zip wurde nicht gefunden."))
            return 0
        self._queue = list(operations)
        self._total = len(operations)
        self._ok = self._failed = 0
        self._cancelled = False
        self._running = True
        self.running_changed.emit(True)
        self.overall.emit(0, self._total)
        self._fill()
        return len(operations)

    def _fill(self) -> None:
        assert self._sevenzip is not None
        while self._queue and len(self._jobs) < self._max_parallel and not self._cancelled:
            operation = self._queue.pop(0)
            job = _Job(next(self._ids), self._sevenzip, operation, self._title(operation))
            job.setParent(self)
            job.changed.connect(self._emit_jobs)
            job.message.connect(
                lambda text, name=job.game.name: self.status.emit(f"[{name}] {text}")
            )
            job.done.connect(self._on_job_done)
            self._jobs.append(job)
            self.status.emit(f"▶ {job.title}")
            job.start()
        self._emit_jobs()

    def _on_job_done(self, job: _Job) -> None:
        if job not in self._jobs:
            return
        self._jobs.remove(job)
        job.deleteLater()
        if job.result is not None:
            self._results[job.game.key] = job.result
            self.result_changed.emit(job.game.key, job.result)
        if job.ok:
            self._ok += 1
        elif not job.cancelled:
            self._failed += 1
            logger.error("Archiv fehlgeschlagen (%s): %s", job.game.name, job.error)
            self.status.emit(self.tr("Fehler bei {0}: {1}").format(job.game.name, job.error))
        self.overall.emit(self._ok + self._failed, self._total)
        if self._jobs or (self._queue and not self._cancelled):
            self._fill()
        else:
            self._finish()

    def _emit_jobs(self) -> None:
        running = [job.info() for job in self._jobs]
        waiting = [(operation.game.key, self._title(operation)) for operation in self._queue]
        self.jobs_changed.emit(running, waiting)

    def _finish(self) -> None:
        if not self._running:
            return
        if self._cancelled:
            self.status.emit(self.tr("Abgebrochen."))
        self._queue = []
        self._running = False
        self.jobs_changed.emit([], [])
        self.running_changed.emit(False)
        self.finished.emit(self._ok, self._failed)


def _error_text(exit_code: int, errors: list[str]) -> str:
    """Aussagekräftigste Fehlerzeilen von 7-Zip (ohne die Überschrift „ERRORS:“)."""
    useful = [line for line in errors if line.strip() not in ("ERRORS:", "ERROR:", "WARNINGS:")]
    if useful:
        return " – ".join(useful[-2:])
    return {1: "Warnung", 2: "schwerer Fehler", 7: "falsche Argumente", 8: "zu wenig Speicher"}.get(
        exit_code, str(exit_code)
    )
