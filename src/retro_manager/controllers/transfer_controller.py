"""Verbindungen zu Geräten, Durchsuchen per FTP/FTPS/SFTP und eine Übertragungs-Warteschlange."""

import itertools
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from retro_manager.core import connections as conns
from retro_manager.core import credentials, remote
from retro_manager.core.connections import Connection
from retro_manager.core.credentials import CredentialsError
from retro_manager.core.progress import ExportCancelled
from retro_manager.core.remote import RemoteError, RemoteFs, TransferItem

logger = logging.getLogger(__name__)

STATE_WAITING = "waiting"
STATE_RUNNING = "running"
STATE_DONE = "done"
STATE_FAILED = "failed"
STATE_CANCELLED = "cancelled"


@dataclass
class TransferJob:
    """Ein Auftrag in der Warteschlange.

    Hochladen: entweder fertige `items` (z. B. aus dem Export) oder `local_sources`
    (Dateien/Ordner) nach `remote_dir`. Herunterladen: `remote_sources` nach `local_dir`.
    """

    id: int
    connection_id: str
    label: str
    direction: str  # "upload" oder "download"
    items: list[TransferItem] = field(default_factory=list)
    local_sources: list[Path] = field(default_factory=list)
    remote_dir: PurePosixPath = PurePosixPath("/")
    remote_sources: list[tuple[PurePosixPath, bool]] = field(default_factory=list)
    local_dir: Path = Path()
    tag: object = None  # Rückbezug für Auftraggeber, z. B. Export-Schlüssel
    state: str = STATE_WAITING
    done: int = 0
    total: int = 0
    message: str = ""


class _Signals(QObject):
    done = Signal(object)
    error = Signal(str)
    progress = Signal(object, object)  # object: Bytes über 2 GB


class _Task(QRunnable):
    def __init__(self, work: Callable[[_Signals], object]) -> None:
        super().__init__()
        self.signals = _Signals()
        self._work = work

    def run(self) -> None:
        try:
            result = self._work(self.signals)
        except ExportCancelled:
            self.signals.error.emit("")
        except (RemoteError, OSError) as error:
            self.signals.error.emit(str(error) or type(error).__name__)
        else:
            self.signals.done.emit(result)


class TransferController(QObject):
    """Verwaltet Verbindungen, eine Durchsuch-Verbindung und die Übertragungs-Warteschlange."""

    connections_changed = Signal()
    connection_tested = Signal(bool, str)
    browse_connected = Signal(str)  # Verbindungs-ID
    browse_disconnected = Signal()
    listing = Signal(str, object)  # Pfad, list[RemoteEntry]
    browse_error = Signal(str)
    job_added = Signal(object)  # TransferJob
    job_changed = Signal(object)
    job_finished = Signal(object)

    def __init__(
        self,
        ini_path: Path,
        known_hosts: Path,
        legacy_ps3: tuple[str, int] = ("", 21),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ini_path = ini_path
        self._known_hosts = known_hosts
        self._legacy_ps3 = legacy_ps3
        self._connections: list[Connection] = []
        # Je ein Thread: Befehle einer Verbindung laufen nacheinander, nie gleichzeitig.
        self._browse_pool = QThreadPool(self)
        self._browse_pool.setMaxThreadCount(1)
        self._transfer_pool = QThreadPool(self)
        self._transfer_pool.setMaxThreadCount(1)
        self._browse_fs: RemoteFs | None = None
        self._browse_id = ""
        self._tasks: set[_Task] = set()
        self._jobs: list[TransferJob] = []
        self._job_ids = itertools.count(1)
        self._running_job: TransferJob | None = None
        self._cancel = threading.Event()

    # --- Verbindungen --------------------------------------------------------------------

    def load(self) -> None:
        """Liest die Verbindungen; übernimmt einmalig eine früher gespeicherte PS3-Adresse."""
        loaded = conns.load_connections(self._ini_path)
        migrated = conns.migrate_ps3_target(loaded, *self._legacy_ps3) if not loaded else loaded
        if migrated != loaded:
            conns.save_connections(self._ini_path, migrated)
        self._connections = migrated
        self.connections_changed.emit()

    def connections(self) -> list[Connection]:
        return list(self._connections)

    def connection(self, connection_id: str) -> Connection | None:
        return next((c for c in self._connections if c.id == connection_id), None)

    @staticmethod
    def protocols() -> tuple[str, ...]:
        return remote.PROTOCOLS

    @staticmethod
    def default_port(protocol: str) -> int:
        return remote.DEFAULT_PORTS.get(protocol, 21)

    @staticmethod
    def new_connection(name: str, protocol: str = "ftp") -> Connection:
        return conns.new_connection(name, protocol)

    def password(self, connection: Connection) -> str:
        try:
            return credentials.get_secret(connection.secret_key) or ""
        except CredentialsError:
            return ""

    def save_connection(self, connection: Connection, password: str | None) -> str | None:
        """Speichert (neu oder geändert); `password=None` lässt das Passwort unverändert."""
        if password is not None:
            try:
                credentials.set_secret(connection.secret_key, password)
            except CredentialsError as error:
                return self.tr("Der Schlüsselbund ist nicht erreichbar: {0}").format(error)
        others = [c for c in self._connections if c.id != connection.id]
        self._connections = sorted([*others, connection], key=lambda c: c.name.lower())
        conns.save_connections(self._ini_path, self._connections)
        self.connections_changed.emit()
        return None

    def delete_connection(self, connection_id: str) -> None:
        self._connections = [c for c in self._connections if c.id != connection_id]
        conns.save_connections(self._ini_path, self._connections)
        if connection_id == self._browse_id:
            self.disconnect_browse()
        self.connections_changed.emit()

    def test(self, connection: Connection, password: str) -> None:
        """Prüft im Hintergrund, ob sich das Gerät mit diesen Daten erreichen lässt."""

        def work(signals: _Signals) -> object:
            with self._open(connection, password) as fs:
                return fs.welcome()

        self._start(
            self._browse_pool,
            work,
            lambda welcome: self.connection_tested.emit(
                True, str(welcome) or self.tr("Verbunden.")
            ),
            lambda message: self.connection_tested.emit(False, message),
        )

    # --- Durchsuchen ---------------------------------------------------------------------

    def connect_browse(self, connection_id: str) -> None:
        connection = self.connection(connection_id)
        if connection is None:
            return
        password = self.password(connection)

        def work(signals: _Signals) -> object:
            self._close_browse_fs()
            self._browse_fs = self._open(connection, password)
            path = PurePosixPath(connection.start_dir or "/")
            return path, self._browse_fs.list_dir(path)

        def done(result: object) -> None:
            path, entries = result  # type: ignore[misc]
            self._browse_id = connection.id
            self.browse_connected.emit(connection.id)
            self.listing.emit(str(path), entries)

        self._start(self._browse_pool, work, done, self.browse_error.emit)

    def disconnect_browse(self) -> None:
        def work(signals: _Signals) -> object:
            self._close_browse_fs()
            return None

        self._browse_id = ""
        self._start(
            self._browse_pool,
            work,
            lambda _: self.browse_disconnected.emit(),
            self.browse_error.emit,
        )

    def is_browsing(self) -> bool:
        return bool(self._browse_id)

    def browse_connection_id(self) -> str:
        return self._browse_id

    def list_dir(self, path: str) -> None:
        self._browse_command(lambda fs: None, path)

    def mkdir(self, parent: str, name: str) -> None:
        self._browse_command(lambda fs: fs.mkdir(PurePosixPath(parent) / name), parent)

    def rename(self, parent: str, old_name: str, new_name: str) -> None:
        base = PurePosixPath(parent)
        self._browse_command(lambda fs: fs.rename(base / old_name, base / new_name), parent)

    def delete(self, parent: str, entries: list[tuple[str, bool]]) -> None:
        """Löscht Dateien und (rekursiv) Ordner im aktuellen Verzeichnis."""
        base = PurePosixPath(parent)

        def run(fs: RemoteFs) -> None:
            for name, is_dir in entries:
                if is_dir:
                    remote.remove_tree(fs, base / name)
                else:
                    fs.remove_file(base / name)

        self._browse_command(run, parent)

    def _browse_command(self, command: Callable[[RemoteFs], None], refresh: str) -> None:
        def work(signals: _Signals) -> object:
            if self._browse_fs is None:
                raise RemoteError(self.tr("Nicht verbunden."))
            command(self._browse_fs)
            return refresh, self._browse_fs.list_dir(PurePosixPath(refresh))

        def done(result: object) -> None:
            path, entries = result  # type: ignore[misc]
            self.listing.emit(str(path), entries)

        self._start(self._browse_pool, work, done, self.browse_error.emit)

    def _close_browse_fs(self) -> None:
        if self._browse_fs is not None:
            self._browse_fs.close()
            self._browse_fs = None

    # --- Warteschlange -------------------------------------------------------------------

    def jobs(self) -> list[TransferJob]:
        return list(self._jobs)

    def enqueue_upload(
        self,
        connection_id: str,
        label: str,
        *,
        items: list[TransferItem] | None = None,
        local_sources: list[Path] | None = None,
        remote_dir: str = "/",
        tag: object = None,
    ) -> TransferJob:
        job = TransferJob(
            next(self._job_ids),
            connection_id,
            label,
            "upload",
            items=list(items or []),
            local_sources=list(local_sources or []),
            remote_dir=PurePosixPath(remote_dir),
            tag=tag,
        )
        return self._enqueue(job)

    def enqueue_download(
        self,
        connection_id: str,
        label: str,
        remote_sources: list[tuple[str, bool]],
        local_dir: Path,
    ) -> TransferJob:
        job = TransferJob(
            next(self._job_ids),
            connection_id,
            label,
            "download",
            remote_sources=[(PurePosixPath(path), is_dir) for path, is_dir in remote_sources],
            local_dir=local_dir,
        )
        return self._enqueue(job)

    def cancel_job(self, job_id: int) -> None:
        job = next((j for j in self._jobs if j.id == job_id), None)
        if job is None:
            return
        if job is self._running_job:
            self._cancel.set()
        elif job.state == STATE_WAITING:
            self._finish_job(job, STATE_CANCELLED, self.tr("Abgebrochen."))

    def clear_finished(self) -> None:
        self._jobs = [j for j in self._jobs if j.state in (STATE_WAITING, STATE_RUNNING)]

    def shutdown(self) -> None:
        """Beim Beenden: laufende Übertragung abbrechen, Verbindungen schließen."""
        self._cancel.set()
        self._close_browse_fs()

    def _enqueue(self, job: TransferJob) -> TransferJob:
        self._jobs.append(job)
        self.job_added.emit(job)
        self._run_next()
        return job

    def _run_next(self) -> None:
        if self._running_job is not None:
            return
        job = next((j for j in self._jobs if j.state == STATE_WAITING), None)
        if job is None:
            return
        connection = self.connection(job.connection_id)
        if connection is None:
            self._finish_job(job, STATE_FAILED, self.tr("Die Verbindung gibt es nicht mehr."))
            self._run_next()
            return
        password = self.password(connection)
        self._running_job = job
        self._cancel.clear()
        job.state = STATE_RUNNING
        self.job_changed.emit(job)

        def work(signals: _Signals) -> object:
            def progress(done: int, total: int) -> None:
                signals.progress.emit(done, total)

            with self._open(connection, password) as fs:
                if job.direction == "upload":
                    items = job.items or remote.expand_upload(job.local_sources, job.remote_dir)
                    remote.upload_items(fs, items, progress, self._cancel.is_set)
                else:
                    pairs = remote.expand_download(fs, job.remote_sources, job.local_dir)
                    remote.download_items(fs, pairs, progress, self._cancel.is_set)
            return None

        def on_progress(done: int, total: int) -> None:
            job.done, job.total = done, total
            self.job_changed.emit(job)

        def on_error(message: str) -> None:
            if self._cancel.is_set() or not message:
                self._finish_job(
                    job,
                    STATE_CANCELLED,
                    self.tr("Abgebrochen – beim nächsten Mal wird fortgesetzt."),
                )
            else:
                logger.error("Übertragung %s fehlgeschlagen: %s", job.label, message)
                self._finish_job(job, STATE_FAILED, message)

        self._start(
            self._transfer_pool,
            work,
            lambda _: self._finish_job(job, STATE_DONE, self.tr("Fertig.")),
            on_error,
            on_progress,
        )

    def _finish_job(self, job: TransferJob, state: str, message: str) -> None:
        job.state, job.message = state, message
        if job is self._running_job:
            self._running_job = None
        self.job_changed.emit(job)
        self.job_finished.emit(job)
        self._run_next()

    # --- Hilfen --------------------------------------------------------------------------

    def _open(self, connection: Connection, password: str) -> RemoteFs:
        return remote.open_remote(
            connection.protocol,
            connection.host,
            connection.port,
            connection.user,
            password,
            self._known_hosts,
        )

    def _start(
        self,
        pool: QThreadPool,
        work: Callable[[_Signals], object],
        on_done: Callable[[object], None],
        on_error: Callable[[str], None],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        task = _Task(work)
        task.setAutoDelete(False)
        self._tasks.add(task)

        def finished(handler: Callable, value: object) -> None:
            self._tasks.discard(task)
            handler(value)

        task.signals.done.connect(lambda value: finished(on_done, value))
        task.signals.error.connect(lambda message: finished(on_error, message))
        if on_progress is not None:
            task.signals.progress.connect(on_progress)
        pool.start(task)


def updated(connection: Connection, **changes: object) -> Connection:
    """Geänderte Kopie einer Verbindung (für die Views)."""
    return replace(connection, **changes)  # type: ignore[arg-type]
