"""Igir als eigener Prozess: Prüfen und Report, Ausgabe zeilenweise per Signal."""

import csv
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from retro_manager.core import igir_report, tools

logger = logging.getLogger(__name__)

# Zeit, die Igir nach „Abbrechen“ zum sauberen Beenden bekommt.
CANCEL_GRACE_MS = 3000

_LAST_LINE_BREAK = re.compile(r"[\r\n](?=[^\r\n]*\Z)")


class IgirController(QObject):
    """Startet Igir, meldet Ausgabe, Report und Fehler."""

    running_changed = Signal(bool)
    output_line = Signal(str)
    report_ready = Signal(object)  # IgirReport
    failed = Signal(str)

    def __init__(self, igir_path: Path, reports_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._igir_path = igir_path
        self._reports_dir = reports_dir
        self._process: QProcess | None = None
        self._report_path: Path | None = None
        self._buffer = ""
        self._cancelled = False
        self._cue_dirs: list[Path] = []

    @property
    def igir_path(self) -> Path:
        return self._igir_path

    def is_available(self) -> bool:
        """True, wenn die Igir-Programmdatei vorhanden und ausführbar ist."""
        return self._igir_path.is_file() and os.access(self._igir_path, os.X_OK)

    def is_running(self) -> bool:
        return self._process is not None

    def verify(self, input_dir: Path, dat_dir: Path, cues_root: Path | None = None) -> None:
        """Prüft die ROMs im Eingabeordner gegen die DATs und erstellt einen Report.

        Korrekte Redump-CUEs aus `cues_root` ergänzen Disc-Dumps, deren eigene CUE abweicht.
        """
        if self.is_running():
            return
        error = self._check_inputs(input_dir, dat_dir)
        if error:
            self.failed.emit(error)
            return
        try:
            self._reports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.failed.emit(self.tr("Report-Ordner kann nicht angelegt werden: {0}").format(exc))
            return

        self._report_path = tools.report_path(self._reports_dir, datetime.now())
        self._cue_dirs = tools.cue_inputs(input_dir, cues_root)
        args = tools.igir_verify_args(input_dir, dat_dir, self._report_path, self._cue_dirs)
        self._start(args)
        if self._cue_dirs:
            self.output_line.emit(
                self.tr("Korrekte CUE-Dateien von Redump werden ergänzt aus: {0}").format(
                    ", ".join(path.name for path in self._cue_dirs)
                )
            )

    def cancel(self) -> None:
        """Bricht die laufende Prüfung ab (erst sanft, nach einer Frist hart)."""
        process = self._process
        if process is None:
            return
        self._cancelled = True
        logger.info("Igir wird abgebrochen")
        process.terminate()
        QTimer.singleShot(CANCEL_GRACE_MS, lambda: self._kill_if_running(process))

    def shutdown(self) -> None:
        """Beendet Igir sofort, z. B. beim Schließen der App."""
        if self._process is not None:
            self._cancelled = True
            self._process.kill()

    def _check_inputs(self, input_dir: Path, dat_dir: Path) -> str | None:
        if not self.is_available():
            return self.tr("Igir wurde nicht gefunden: {0}").format(self._igir_path)
        if not input_dir.is_dir():
            return self.tr("Der ROM-Ordner existiert nicht: {0}").format(input_dir)
        if not dat_dir.is_dir():
            return self.tr("Der DAT-Ordner existiert nicht: {0}").format(dat_dir)
        return None

    def _start(self, args: list[str]) -> None:
        process = QProcess(self)
        process.setProgram(str(self._igir_path))
        process.setArguments(args)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("NO_COLOR", "1")
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(lambda: self._read_output(process))
        process.finished.connect(lambda code, status: self._on_finished(process, code, status))
        process.errorOccurred.connect(lambda error: self._on_error(process, error))

        self._process = process
        self._buffer = ""
        self._cancelled = False
        self.running_changed.emit(True)
        logger.info("Starte: %s %s", self._igir_path, " ".join(args))
        process.start()

    def _read_output(self, process: QProcess) -> None:
        if not shiboken6.isValid(process):
            return
        self._buffer += bytes(process.readAllStandardOutput().data()).decode(errors="replace")
        # Nur vollständige Zeilen ausgeben, den Rest für das nächste Stück aufheben.
        match = _LAST_LINE_BREAK.search(self._buffer)
        if match is None:
            return
        complete, self._buffer = self._buffer[: match.end()], self._buffer[match.end() :]
        self._emit_lines(complete)

    def _emit_lines(self, text: str) -> None:
        for line in tools.clean_output(text):
            self.output_line.emit(line)

    def _on_finished(self, process: QProcess, exit_code: int, status: QProcess.ExitStatus) -> None:
        if not shiboken6.isValid(process):  # App wird gerade beendet
            return
        self._read_output(process)
        self._emit_lines(self._buffer)
        self._buffer = ""
        self._finish(process)

        if self._cancelled:
            self.failed.emit(self.tr("Die Prüfung wurde abgebrochen."))
            return
        crashed = status != QProcess.ExitStatus.NormalExit
        report_path = self._report_path
        if report_path is None or not report_path.is_file():
            self.failed.emit(
                self.tr(
                    "Igir wurde mit Fehlercode {0} beendet, es wurde kein Report erstellt."
                ).format(exit_code)
                if crashed or exit_code
                else self.tr("Igir hat keinen Report erstellt.")
            )
            return
        if crashed or exit_code:
            # Igir meldet z. B. fehlerhafte Dateien per Exit-Code, der Report ist trotzdem gültig.
            self.output_line.emit(
                self.tr("Igir wurde mit Fehlercode {0} beendet.").format(exit_code)
            )
        try:
            report = igir_report.without_unused_under(
                igir_report.parse_report(report_path), self._cue_dirs
            )
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            self.failed.emit(self.tr("Der Report konnte nicht gelesen werden: {0}").format(exc))
            return
        logger.info("Igir-Report: %s (%d Einträge)", report_path, len(report.rows))
        self.report_ready.emit(report)

    def _on_error(self, process: QProcess, error: QProcess.ProcessError) -> None:
        # Bei allen anderen Fehlern folgt noch `finished`.
        if not shiboken6.isValid(process) or error != QProcess.ProcessError.FailedToStart:
            return
        message = process.errorString()
        self._finish(process)
        logger.error("Igir konnte nicht gestartet werden: %s", message)
        self.failed.emit(self.tr("Igir konnte nicht gestartet werden: {0}").format(message))

    def _finish(self, process: QProcess) -> None:
        process.deleteLater()
        self._process = None
        self.running_changed.emit(False)

    def _kill_if_running(self, process: QProcess) -> None:
        if self._process is process and shiboken6.isValid(process):
            process.kill()
