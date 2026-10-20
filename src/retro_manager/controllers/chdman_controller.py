"""chdman-Reiter: Discs in CHD umwandeln, zurückwandeln, prüfen, Infos (per QProcess)."""

import logging
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, QProcess, QThreadPool, QTimer, Signal

from retro_manager.controllers.background_task import BackgroundTask
from retro_manager.core import chd, config, export, tools
from retro_manager.core.chd import ChdError, Conversion
from retro_manager.core.library import LibraryGame, scan_platform
from retro_manager.core.progress import CancelCheck, ProgressCallback

logger = logging.getLogger(__name__)

OP_CONVERT = "convert"
OP_EXTRACT = "extract"
OP_VERIFY = "verify"
OP_INFO = "info"

# Ergebnisse je Bibliotheksschlüssel (Spalte „Prüfung“ in der Tabelle).
RESULT_OK = "ok"  # CHD geprüft und in Ordnung
RESULT_BROKEN = "broken"  # Prüfung fehlgeschlagen

_MAX_OUTPUT_LINES = 400
_UNPACKED_DIRNAME = "entpackt"

# Rückmeldung eines beendeten chdman-Aufrufs: Rückgabewert und Ausgabezeilen.
ProcessDone = Callable[[int, list[str]], None]


@dataclass(frozen=True)
class _Operation:
    kind: str
    game: LibraryGame


class ChdmanController(QObject):
    """Arbeitet eine Liste von Discs nacheinander ab; chdman nutzt selbst alle Prozessorkerne."""

    running_changed = Signal(bool)
    status = Signal(str)  # Protokollzeile
    phase = Signal(str)  # aktueller Arbeitsschritt, z. B. „Komprimieren …“
    progress = Signal(object, object)  # erledigt, gesamt (Bytes oder Promille)
    result_changed = Signal(str, str)  # Bibliotheksschlüssel, RESULT_*
    finished = Signal(int, int)  # erfolgreich, fehlgeschlagen
    # Titel des laufenden Vorgangs (oder "") und Titel der wartenden – für die Aktivitätsanzeige.
    queue_changed = Signal(str, object)

    def __init__(self, chdman: Path | None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._chdman = chdman
        self._cancel = threading.Event()
        self._running = False
        self._queue: list[_Operation] = []
        self._operation: _Operation | None = None
        self._total = self._ok = self._failed = 0
        self._converted = 0
        self._results: dict[str, str] = {}
        self._hdd = Path()
        self._delete_originals = True
        self._extract_root = Path()
        # Zustand der laufenden Disc
        self._work_dir: Path | None = None
        self._conversions: list[Conversion] = []
        self._pending: list[Conversion] = []
        self._created: list[Path] = []  # beim Zurückwandeln neu entstandene Dateien
        self._process: QProcess | None = None
        self._task: BackgroundTask | None = None
        self._output: list[str] = []

    # --- Abfragen für die Oberfläche ------------------------------------------------------

    @property
    def chdman_available(self) -> bool:
        return self._chdman is not None

    @property
    def chdman_path(self) -> Path | None:
        return self._chdman

    @staticmethod
    def platform_labels() -> dict[str, str]:
        return dict(chd.CHD_PLATFORMS)

    def is_running(self) -> bool:
        return self._running

    def library(self, hdd: Path) -> list[LibraryGame]:
        """Alle Discs der Systeme, für die CHD in Frage kommt."""
        roms = hdd / "roms"
        return [game for slug in chd.CHD_PLATFORMS for game in scan_platform(roms, slug)]

    def results(self) -> dict[str, str]:
        """Prüfergebnisse dieser Sitzung je Bibliotheksschlüssel."""
        return dict(self._results)

    # --- Aktionen ------------------------------------------------------------------------

    def convert(self, games: list[LibraryGame], hdd: Path, delete_originals: bool) -> int:
        """Wandelt Discs in CHD um; gibt zurück, wie viele dafür in Frage kamen."""
        self._hdd = hdd
        self._delete_originals = delete_originals
        return self._start(OP_CONVERT, [game for game in games if chd.is_convertible(game)])

    def extract(self, games: list[LibraryGame], target_root: Path, delete_originals: bool) -> int:
        """Wandelt CHDs zurück nach BIN/CUE, GDI bzw. ISO in `target_root`.

        Mit `delete_originals` wird die CHD nach erfolgreichem Zurückwandeln gelöscht.
        """
        self._extract_root = target_root
        self._delete_originals = delete_originals
        return self._start(OP_EXTRACT, [game for game in games if game.kind == "chd"])

    def verify(self, games: list[LibraryGame]) -> int:
        return self._start(OP_VERIFY, [game for game in games if game.kind == "chd"])

    def info(self, games: list[LibraryGame]) -> int:
        return self._start(OP_INFO, [game for game in games if game.kind == "chd"])

    def cancel(self) -> None:
        if not self._running:
            return
        self._cancel.set()
        if self._process is not None:
            self._process.kill()

    # --- Ablauf --------------------------------------------------------------------------

    def _start(self, kind: str, games: list[LibraryGame]) -> int:
        if self._running or not games:
            return 0
        if self._chdman is None:
            self.status.emit(self.tr("chdman wurde nicht gefunden."))
            return 0
        self._queue = [_Operation(kind, game) for game in games]
        self._total = len(games)
        self._ok = self._failed = self._converted = 0
        self._cancel.clear()
        self._set_running(True)
        self._next_operation()
        return len(games)

    def _title(self, operation: _Operation) -> str:
        verb = {
            OP_CONVERT: self.tr("In CHD umwandeln"),
            OP_EXTRACT: self.tr("Zurückwandeln"),
            OP_VERIFY: self.tr("Prüfen"),
            OP_INFO: self.tr("Infos"),
        }[operation.kind]
        return f"{verb}: {operation.game.name}"

    def _next_operation(self) -> None:
        if self._cancel.is_set() or not self._queue:
            self._finish()
            return
        operation = self._operation = self._queue.pop(0)
        self.queue_changed.emit(self._title(operation), [self._title(op) for op in self._queue])
        position = self._total - len(self._queue)
        self.status.emit(f"[{position}/{self._total}] {self._title(operation)}")
        self._work_dir = None
        self._conversions = []
        self._pending = []
        self._created = []
        try:
            if operation.kind == OP_CONVERT:
                self._begin_convert(operation.game)
            elif operation.kind == OP_EXTRACT:
                self._begin_extract(operation.game)
            elif operation.kind == OP_VERIFY:
                self._set_phase(self.tr("CHD prüfen …"))
                self._run(tools.chdman_verify_args(operation.game.path), self._on_verified)
            else:
                self._set_phase(self.tr("Infos lesen …"))
                self._run(tools.chdman_info_args(operation.game.path), self._on_info)
        except (ChdError, OSError) as error:
            self._operation_failed(str(error))

    # --- In CHD umwandeln ------------------------------------------------------------------

    def _begin_convert(self, game: LibraryGame) -> None:
        work = chd.game_work_dir(config.work_dir(self._hdd), game)
        if work.exists():
            shutil.rmtree(work)  # Reste eines abgebrochenen Laufs
        work.mkdir(parents=True)
        self._work_dir = work
        if game.kind != "archive":
            self._check_space(game, None)
            self._plan(chd.plan_conversions(game, [game.path], work))
            return
        unpack = export.ExtractArchive(game.path, work / _UNPACKED_DIRNAME)

        def work_fn(on_progress: ProgressCallback, is_cancelled: CancelCheck) -> list[Path]:
            self._check_space(game, export.estimated_size(unpack))
            export.extract_archive(unpack, on_progress, is_cancelled)
            return chd.disc_images(unpack.target)

        self._set_phase(self.tr("Entpacken …"))
        self._start_task(
            work_fn, lambda images: self._plan(chd.plan_conversions(game, images, work))
        )

    def _check_space(self, game: LibraryGame, unpacked_size: int | None) -> None:
        assert self._work_dir is not None
        needed = chd.required_space(game, unpacked_size)
        free = export.free_space(self._work_dir)
        if needed > free:
            raise ChdError(
                self.tr("Nicht genug Platz auf der HDD ({0} MB nötig, {1} MB frei).").format(
                    needed // 1_000_000, free // 1_000_000
                )
            )

    def _plan(self, conversions: list[Conversion]) -> None:
        self._conversions = conversions
        self._pending = list(conversions)
        self._next_conversion()

    def _next_conversion(self) -> None:
        if self._cancel.is_set():
            self._on_cancelled()
            return
        if not self._pending:
            self._complete_conversion()
            return
        conversion = self._pending[0]
        self._set_phase(self.tr("Komprimieren: {0} …").format(conversion.image.name))
        self._run(
            tools.chdman_create_args(conversion.media, conversion.image, conversion.part),
            self._on_created,
        )

    def _on_created(self, exit_code: int, lines: list[str]) -> None:
        if exit_code != 0:
            self._operation_failed(self.tr("chdman: {0}").format(_last_line(lines, exit_code)))
            return
        conversion = self._pending[0]
        self._set_phase(self.tr("CHD prüfen: {0} …").format(conversion.target.name))
        self._run(tools.chdman_verify_args(conversion.part), self._on_conversion_verified)

    def _on_conversion_verified(self, exit_code: int, lines: list[str]) -> None:
        if exit_code != 0:
            self._operation_failed(
                self.tr("Prüfung der neuen CHD fehlgeschlagen: {0}").format(
                    _last_line(lines, exit_code)
                )
            )
            return
        self._pending.pop(0)
        self._next_conversion()

    def _complete_conversion(self) -> None:
        operation = self._operation
        assert operation is not None
        game = operation.game
        try:
            targets = chd.finish_conversion(self._conversions)
            removed = chd.remove_files(chd.source_files(game)) if self._delete_originals else 0
        except OSError as error:
            self._operation_failed(str(error))
            return
        self._remove_work_dir()
        for target in targets:
            self._set_result(chd.target_key(game, target), RESULT_OK)
            self.status.emit(self.tr("→ {0} (geprüft)").format(target))
        if removed:
            self.status.emit(self.tr("Original entfernt ({0} Dateien).").format(removed))
        self._converted += len(targets)
        self._operation_succeeded()

    # --- Zurückwandeln -------------------------------------------------------------------

    def _begin_extract(self, game: LibraryGame) -> None:
        header = chd.read_header(game.path)
        if header is None or header.media is None:
            raise ChdError(self.tr("{0} ist keine CD-, GD- oder DVD-CHD.").format(game.path.name))
        target = chd.extract_target(self._extract_root, game, header.media)
        if chd.extract_outputs_exist(target, game.name, header.media):
            raise ChdError(self.tr("{0} existiert bereits in {1}.").format(game.name, target))
        existed = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        before = set(target.iterdir())

        def done(exit_code: int, lines: list[str]) -> None:
            self._created = sorted(set(target.iterdir()) - before)
            if not existed:
                self._created.append(target)  # leeren Ordner bei Fehler mit entfernen
            if exit_code != 0:
                self._operation_failed(self.tr("chdman: {0}").format(_last_line(lines, exit_code)))
                return
            if header.media == chd.MEDIA_CD:
                export.normalize_single_track(target / f"{game.name}.cue")
            self._created = []
            self.status.emit(self.tr("→ {0}").format(target))
            self._complete_extraction()

        self._set_phase(self.tr("Zurückwandeln …"))
        self._run(tools.chdman_extract_args(header.media, game.path, target, game.name), done)

    def _complete_extraction(self) -> None:
        operation = self._operation
        assert operation is not None
        game = operation.game
        try:
            removed = chd.remove_files(chd.source_files(game)) if self._delete_originals else 0
        except OSError as error:
            self._operation_failed(str(error))
            return
        if removed:
            self.status.emit(self.tr("Original entfernt ({0} Dateien).").format(removed))
        self._operation_succeeded()

    # --- Prüfen und Infos ----------------------------------------------------------------

    def _on_verified(self, exit_code: int, lines: list[str]) -> None:
        operation = self._operation
        assert operation is not None
        if exit_code == 0:
            self._set_result(operation.game.key, RESULT_OK)
            self.status.emit(self.tr("In Ordnung."))
            self._operation_succeeded()
        else:
            self._set_result(operation.game.key, RESULT_BROKEN)
            self._operation_failed(
                self.tr("Prüfung fehlgeschlagen: {0}").format(_last_line(lines, exit_code))
            )

    def _on_info(self, exit_code: int, lines: list[str]) -> None:
        if exit_code != 0:
            self._operation_failed(self.tr("chdman: {0}").format(_last_line(lines, exit_code)))
            return
        # Erste Zeile ist der Programmname mit Version.
        body = [line for line in lines if not line.startswith("chdman - ")]
        self.status.emit("\n".join(body))
        self._operation_succeeded()

    # --- chdman ausführen ----------------------------------------------------------------

    def _run(self, args: list[str], on_done: ProcessDone) -> None:
        assert self._chdman is not None
        process = QProcess(self)
        process.setProgram(str(self._chdman))
        process.setArguments(args)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyRead.connect(lambda: self._read_output(process))
        process.finished.connect(
            lambda code, exit_status: self._on_process_finished(process, code, exit_status, on_done)
        )
        process.errorOccurred.connect(lambda error: self._on_process_error(process, error))
        self._process = process
        self._output = []
        self.progress.emit(0, 0)
        logger.info("Starte chdman %s", " ".join(args))
        process.start()

    def _read_output(self, process: QProcess) -> None:
        if not shiboken6.isValid(process):
            return
        text = bytes(process.readAll().data()).decode(errors="replace")
        for line in tools.clean_output(text):
            fraction = chd.parse_progress(line)
            if fraction is not None:
                self.progress.emit(int(fraction * 1000), 1000)
            else:
                self._output.append(line)
        del self._output[:-_MAX_OUTPUT_LINES]

    def _on_process_finished(
        self,
        process: QProcess,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
        on_done: ProcessDone,
    ) -> None:
        if not shiboken6.isValid(process):
            return
        self._read_output(process)
        process.deleteLater()
        self._process = None
        if self._cancel.is_set():
            self._on_cancelled()
            return
        crashed = exit_status != QProcess.ExitStatus.NormalExit
        on_done(-1 if crashed else exit_code, list(self._output))

    def _on_process_error(self, process: QProcess, error: QProcess.ProcessError) -> None:
        # Nur Startfehler beenden den Vorgang hier; sonst folgt noch `finished`.
        if error != QProcess.ProcessError.FailedToStart or not shiboken6.isValid(process):
            return
        process.deleteLater()
        self._process = None
        self._operation_failed(
            self.tr("chdman konnte nicht gestartet werden: {0}").format(process.errorString())
        )

    def _start_task(self, work: Callable, on_done: Callable[[object], None]) -> None:
        task = BackgroundTask(work, self._cancel.is_set)
        task.signals.progress.connect(self.progress)
        task.signals.done.connect(lambda result: self._on_task_done(result, on_done))
        task.signals.error.connect(self._operation_failed)
        task.signals.cancelled.connect(self._on_cancelled)
        self._task = task
        QThreadPool.globalInstance().start(task)

    def _on_task_done(self, result: object, on_done: Callable[[object], None]) -> None:
        self._task = None
        if self._cancel.is_set():
            self._on_cancelled()
            return
        try:
            on_done(result)
        except (ChdError, OSError) as error:
            self._operation_failed(str(error))

    # --- Abschluss -----------------------------------------------------------------------

    def _set_phase(self, text: str) -> None:
        self.phase.emit(text)

    def _set_result(self, key: str, result: str) -> None:
        self._results[key] = result
        self.result_changed.emit(key, result)

    def _remove_work_dir(self) -> None:
        if self._work_dir is not None and self._work_dir.exists():
            shutil.rmtree(self._work_dir, ignore_errors=True)
        self._work_dir = None

    def _cleanup(self) -> None:
        """Entfernt Zwischenstände der laufenden Disc; Originale bleiben unberührt."""
        self._remove_work_dir()
        for path in sorted(self._created, reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        self._created = []

    def _operation_succeeded(self) -> None:
        self._ok += 1
        self._continue()

    def _operation_failed(self, message: str) -> None:
        self._task = None
        self._cleanup()
        name = self._operation.game.name if self._operation else ""
        logger.error("chdman fehlgeschlagen (%s): %s", name, message)
        self.status.emit(self.tr("Fehler bei {0}: {1}").format(name, message))
        self._failed += 1
        self._continue()

    def _continue(self) -> None:
        # Über die Event-Loop, damit viele schnell scheiternde Discs keine Rekursion ergeben.
        QTimer.singleShot(0, self._next_operation)

    def _on_cancelled(self) -> None:
        self._task = None
        self._cleanup()
        self._finish()

    def _finish(self) -> None:
        if not self._running:
            return
        if self._cancel.is_set():
            self.status.emit(self.tr("Abgebrochen."))
        if self._converted:
            self.status.emit(
                self.tr(
                    "{0} CHDs in der Bibliothek. In RomM die Plattform neu einlesen (Scan), "
                    "damit die neuen Dateien erscheinen."
                ).format(self._converted)
            )
        self._queue = []
        self._operation = None
        self.queue_changed.emit("", [])
        self._set_running(False)
        self.finished.emit(self._ok, self._failed)

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.running_changed.emit(running)


def _last_line(lines: list[str], exit_code: int) -> str:
    """Aussagekräftigste Fehlerzeile; „Fatal error occurred: 1“ wiederholt nur den Rückgabewert."""
    useful = [line for line in lines if not line.startswith("Fatal error occurred")]
    return useful[-1] if useful else str(exit_code)
