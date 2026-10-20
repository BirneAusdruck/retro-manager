"""Entfernte Dateisysteme (FTP, FTPS, SFTP): einheitlicher Zugriff, Up-/Download mit Fortsetzen."""

import ftplib
import os
import re
import stat
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

import paramiko

from retro_manager.core.progress import CancelCheck, ExportCancelled, ProgressCallback

PROTOCOLS = ("ftp", "ftps", "sftp")
DEFAULT_PORTS = {"ftp": 21, "ftps": 21, "sftp": 22}
TIMEOUT_SECONDS = 30
_BLOCK_SIZE = 1024 * 1024

BytesCallback = Callable[[int], None]  # Anzahl gerade übertragener Bytes


class RemoteError(Exception):
    """Verbindung oder Dateioperation auf dem Gerät fehlgeschlagen."""


@dataclass(frozen=True)
class RemoteEntry:
    name: str
    is_dir: bool
    size: int = 0
    modified: datetime | None = None


@dataclass(frozen=True)
class TransferItem:
    local: Path
    remote: PurePosixPath


class RemoteFs(ABC):
    """Gemeinsame Schnittstelle; Pfade auf dem Gerät sind POSIX-Pfade."""

    @abstractmethod
    def welcome(self) -> str: ...

    @abstractmethod
    def list_dir(self, path: PurePosixPath) -> list[RemoteEntry]: ...

    @abstractmethod
    def mkdir(self, path: PurePosixPath) -> None: ...

    @abstractmethod
    def rename(self, old: PurePosixPath, new: PurePosixPath) -> None: ...

    @abstractmethod
    def remove_file(self, path: PurePosixPath) -> None: ...

    @abstractmethod
    def remove_dir(self, path: PurePosixPath) -> None: ...

    @abstractmethod
    def size(self, path: PurePosixPath) -> int | None:
        """Größe einer Datei oder None, wenn es sie nicht gibt."""

    @abstractmethod
    def upload(
        self, local: Path, remote: PurePosixPath, offset: int, on_bytes: BytesCallback
    ) -> None:
        """Schreibt `local` ab Byte `offset` nach `remote` (Rest wird angehängt)."""

    @abstractmethod
    def download(
        self, remote: PurePosixPath, local: Path, offset: int, on_bytes: BytesCallback
    ) -> None:
        """Liest `remote` ab Byte `offset` und hängt es an `local` an."""

    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> RemoteFs:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# --- LIST-Ausgabe (für FTP-Server ohne MLSD) --------------------------------------------------

_UNIX_LIST = re.compile(
    r"^(?P<type>[-dlbcps])[rwxsStT-]{9}\S*\s+\d+\s+\S+\s+\S+\s+(?P<size>\d+)\s+"
    r"(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+(?P<year_or_time>\d{4}|\d{1,2}:\d{2})\s+"
    r"(?P<name>.+)$"
)
_DOS_LIST = re.compile(
    r"^(?P<date>\d{2}-\d{2}-\d{2,4})\s+(?P<time>\d{1,2}:\d{2}[AP]M)\s+"
    r"(?P<size><DIR>|\d+)\s+(?P<name>.+)$",
    re.IGNORECASE,
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}


def parse_list_line(line: str, now: datetime) -> RemoteEntry | None:
    """Eine Zeile aus `LIST` (Unix- oder DOS-Format); None für Summen-/Unbekanntes."""
    match = _UNIX_LIST.match(line.strip())
    if match:
        name = match["name"]
        if match["type"] == "l" and " -> " in name:
            name = name.split(" -> ", 1)[0]
        return RemoteEntry(name, match["type"] == "d", int(match["size"]), _unix_date(match, now))
    match = _DOS_LIST.match(line.strip())
    if match:
        try:
            modified = datetime.strptime(
                f"{match['date']} {match['time'].upper()}", "%m-%d-%y %I:%M%p"
            )
        except ValueError:
            modified = None
        is_dir = match["size"].upper() == "<DIR>"
        return RemoteEntry(match["name"], is_dir, 0 if is_dir else int(match["size"]), modified)
    return None


def _unix_date(match: re.Match[str], now: datetime) -> datetime | None:
    month = _MONTHS.get(match["month"].lower())
    if month is None:
        return None
    value = match["year_or_time"]
    try:
        if ":" in value:
            hour, minute = map(int, value.split(":"))
            date = datetime(now.year, month, int(match["day"]), hour, minute)
            # Ohne Jahr: liegt das Datum in der Zukunft, ist es aus dem Vorjahr.
            return date.replace(year=now.year - 1) if date > now else date
        return datetime(int(value), month, int(match["day"]))
    except ValueError:
        return None


# --- FTP / FTPS -------------------------------------------------------------------------------


class FtpFs(RemoteFs):
    """FTP über ftplib; mit `tls=True` als FTPS (explizit, Datenkanal verschlüsselt)."""

    def __init__(
        self, host: str, port: int, user: str = "", password: str = "", tls: bool = False
    ) -> None:
        self._ftp: ftplib.FTP = ftplib.FTP_TLS() if tls else ftplib.FTP()
        try:
            self._ftp.connect(host, port, timeout=TIMEOUT_SECONDS)
            self._ftp.login(user or "anonymous", password)
            if isinstance(self._ftp, ftplib.FTP_TLS):
                self._ftp.prot_p()
            self._ftp.voidcmd("TYPE I")
        except (OSError, ftplib.Error) as error:
            self._ftp.close()
            raise RemoteError(str(error)) from error

    def welcome(self) -> str:
        return self._ftp.getwelcome()

    def list_dir(self, path: PurePosixPath) -> list[RemoteEntry]:
        try:
            return self._mlsd(path)
        except (OSError, EOFError) as error:
            raise RemoteError(str(error) or type(error).__name__) from error
        except ftplib.error_perm:
            lines: list[str] = []
            self._call(self._ftp.retrlines, f"LIST {path}", lines.append)
            now = datetime.now()
            entries = [parse_list_line(line, now) for line in lines]
            return [e for e in entries if e is not None and e.name not in (".", "..")]

    def _mlsd(self, path: PurePosixPath) -> list[RemoteEntry]:
        entries = []
        for name, facts in self._ftp.mlsd(str(path), facts=["type", "size", "modify"]):
            kind = facts.get("type", "").lower()
            if kind in ("cdir", "pdir") or name in (".", ".."):
                continue
            modified = None
            if facts.get("modify"):
                try:
                    modified = datetime.strptime(facts["modify"][:14], "%Y%m%d%H%M%S")
                except ValueError:
                    modified = None
            entries.append(
                RemoteEntry(name, kind == "dir", int(facts.get("size", 0) or 0), modified)
            )
        return entries

    def mkdir(self, path: PurePosixPath) -> None:
        self._call(self._ftp.mkd, str(path))

    def rename(self, old: PurePosixPath, new: PurePosixPath) -> None:
        self._call(self._ftp.rename, str(old), str(new))

    def remove_file(self, path: PurePosixPath) -> None:
        self._call(self._ftp.delete, str(path))

    def remove_dir(self, path: PurePosixPath) -> None:
        self._call(self._ftp.rmd, str(path))

    def size(self, path: PurePosixPath) -> int | None:
        try:
            # Ein Listing schaltet ftplib auf TYPE A; viele Server verweigern SIZE im Textmodus.
            self._ftp.voidcmd("TYPE I")
            return self._ftp.size(str(path))
        except ftplib.error_perm:
            return None
        except (OSError, ftplib.Error) as error:
            raise RemoteError(str(error)) from error

    def upload(
        self, local: Path, remote: PurePosixPath, offset: int, on_bytes: BytesCallback
    ) -> None:
        with local.open("rb") as file:
            file.seek(offset)
            self._call(
                self._ftp.storbinary,
                f"STOR {remote}",
                file,
                _BLOCK_SIZE,
                lambda block: on_bytes(len(block)),
                offset or None,
            )

    def download(
        self, remote: PurePosixPath, local: Path, offset: int, on_bytes: BytesCallback
    ) -> None:
        with local.open("ab" if offset else "wb") as file:

            def write(block: bytes) -> None:
                file.write(block)
                on_bytes(len(block))

            self._call(self._ftp.retrbinary, f"RETR {remote}", write, _BLOCK_SIZE, offset or None)

    def close(self) -> None:
        try:
            self._ftp.quit()
        except OSError, ftplib.Error, EOFError:
            self._ftp.close()

    @staticmethod
    def _call(function: Callable[..., object], *args: object) -> object:
        try:
            return function(*args)
        except (OSError, EOFError, ftplib.Error) as error:
            raise RemoteError(str(error) or type(error).__name__) from error


# --- SFTP -------------------------------------------------------------------------------------


class SftpFs(RemoteFs):
    """SFTP über paramiko. Host-Key beim ersten Verbinden merken, danach muss er gleich bleiben."""

    def __init__(self, host: str, port: int, user: str, password: str, known_hosts: Path) -> None:
        self._client = paramiko.SSHClient()
        if known_hosts.is_file():
            self._client.load_host_keys(str(known_hosts))
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self._client.connect(
                host,
                port=port,
                username=user,
                password=password or None,
                timeout=TIMEOUT_SECONDS,
                allow_agent=False,
                look_for_keys=False,
            )
            known_hosts.parent.mkdir(parents=True, exist_ok=True)
            self._client.save_host_keys(str(known_hosts))
            self._sftp = self._client.open_sftp()
        except paramiko.BadHostKeyException as error:
            self._client.close()
            raise RemoteError(
                f"Der Schlüssel von {host} hat sich geändert – möglicherweise ein anderes Gerät. "
                f"Wenn das gewollt ist, den Eintrag aus {known_hosts} entfernen."
            ) from error
        except (OSError, paramiko.SSHException) as error:
            self._client.close()
            raise RemoteError(str(error)) from error

    def welcome(self) -> str:
        transport = self._client.get_transport()
        return transport.remote_version if transport else ""

    def list_dir(self, path: PurePosixPath) -> list[RemoteEntry]:
        attrs = self._call(self._sftp.listdir_attr, str(path))
        return [
            RemoteEntry(
                attr.filename,
                stat.S_ISDIR(attr.st_mode or 0),
                attr.st_size or 0,
                datetime.fromtimestamp(attr.st_mtime) if attr.st_mtime else None,
            )
            for attr in attrs  # type: ignore[union-attr]
        ]

    def mkdir(self, path: PurePosixPath) -> None:
        self._call(self._sftp.mkdir, str(path))

    def rename(self, old: PurePosixPath, new: PurePosixPath) -> None:
        self._call(self._sftp.rename, str(old), str(new))

    def remove_file(self, path: PurePosixPath) -> None:
        self._call(self._sftp.remove, str(path))

    def remove_dir(self, path: PurePosixPath) -> None:
        self._call(self._sftp.rmdir, str(path))

    def size(self, path: PurePosixPath) -> int | None:
        try:
            return self._sftp.stat(str(path)).st_size
        except FileNotFoundError:
            return None
        except (OSError, paramiko.SSHException) as error:
            raise RemoteError(str(error)) from error

    def upload(
        self, local: Path, remote: PurePosixPath, offset: int, on_bytes: BytesCallback
    ) -> None:
        try:
            with (
                local.open("rb") as src,
                self._sftp.open(str(remote), "ab" if offset else "wb") as dst,
            ):
                dst.set_pipelined(True)
                src.seek(offset)
                while block := src.read(_BLOCK_SIZE):
                    dst.write(block)
                    on_bytes(len(block))
        except (OSError, paramiko.SSHException) as error:
            raise RemoteError(str(error)) from error

    def download(
        self, remote: PurePosixPath, local: Path, offset: int, on_bytes: BytesCallback
    ) -> None:
        try:
            with (
                self._sftp.open(str(remote), "rb") as src,
                local.open("ab" if offset else "wb") as dst,
            ):
                src.seek(offset)
                src.prefetch()
                while block := src.read(_BLOCK_SIZE):
                    dst.write(block)
                    on_bytes(len(block))
        except (OSError, paramiko.SSHException) as error:
            raise RemoteError(str(error)) from error

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _call(function: Callable[..., object], *args: object) -> object:
        try:
            return function(*args)
        except (OSError, paramiko.SSHException) as error:
            raise RemoteError(str(error) or type(error).__name__) from error


def open_remote(
    protocol: str, host: str, port: int, user: str, password: str, known_hosts: Path
) -> RemoteFs:
    """Verbindet sich mit dem passenden Protokoll."""
    if protocol == "sftp":
        return SftpFs(host, port, user, password, known_hosts)
    if protocol in ("ftp", "ftps"):
        return FtpFs(host, port, user, password, tls=protocol == "ftps")
    raise RemoteError(f"Unbekanntes Protokoll: {protocol}")


# --- Mehrere Dateien, Ordner ------------------------------------------------------------------


def ensure_dirs(fs: RemoteFs, directory: PurePosixPath, known: set[PurePosixPath]) -> None:
    """Legt fehlende Ordner an; `known` merkt sich bereits vorhandene."""
    if directory in known or directory == PurePosixPath(directory.anchor or "/"):
        return
    ensure_dirs(fs, directory.parent, known)
    try:
        fs.mkdir(directory)
    except RemoteError:
        pass  # existiert schon (oder fehlt das Recht – dann scheitert das Schreiben danach)
    known.add(directory)


def upload_items(
    fs: RemoteFs,
    items: list[TransferItem],
    on_progress: ProgressCallback,
    is_cancelled: CancelCheck,
    on_file_done: Callable[[TransferItem], None] | None = None,
) -> None:
    """Lädt hoch; gleich große Ziele werden übersprungen, kleinere fortgesetzt, danach geprüft."""
    total = sum(item.local.stat().st_size for item in items)
    done = 0
    known: set[PurePosixPath] = set()

    def count(count_bytes: int) -> None:
        nonlocal done
        if is_cancelled():
            raise ExportCancelled
        done += count_bytes
        on_progress(done, total)

    for item in items:
        ensure_dirs(fs, item.remote.parent, known)
        local_size = item.local.stat().st_size
        offset = fs.size(item.remote) or 0
        if offset > local_size:
            offset = 0  # fremde oder beschädigte Datei: neu schreiben
        count(offset)
        if offset < local_size:
            fs.upload(item.local, item.remote, offset, count)
        if fs.size(item.remote) != local_size:
            raise RemoteError(f"Größe stimmt nach dem Hochladen nicht: {item.remote}")
        if on_file_done is not None:
            on_file_done(item)


def download_items(
    fs: RemoteFs,
    items: list[tuple[TransferItem, int]],
    on_progress: ProgressCallback,
    is_cancelled: CancelCheck,
) -> None:
    """Lädt herunter (Element + erwartete Größe); vorhandene Teildateien werden fortgesetzt."""
    total = sum(size for _, size in items)
    done = 0

    def count(count_bytes: int) -> None:
        nonlocal done
        if is_cancelled():
            raise ExportCancelled
        done += count_bytes
        on_progress(done, total)

    for item, size in items:
        item.local.parent.mkdir(parents=True, exist_ok=True)
        offset = item.local.stat().st_size if item.local.is_file() else 0
        if offset > size:
            offset = 0
        count(offset)
        if offset < size:
            fs.download(item.remote, item.local, offset, count)
        if item.local.stat().st_size != size:
            raise RemoteError(f"Größe stimmt nach dem Herunterladen nicht: {item.local.name}")


def expand_upload(local_paths: list[Path], remote_dir: PurePosixPath) -> list[TransferItem]:
    """Dateien und ganze Ordner (rekursiv) unter `remote_dir` abbilden."""
    items = []
    for path in local_paths:
        if path.is_dir():
            for root, _, files in os.walk(path):
                for name in sorted(files):
                    file = Path(root) / name
                    relative = file.relative_to(path.parent).as_posix()
                    items.append(TransferItem(file, remote_dir / relative))
        elif path.is_file():
            items.append(TransferItem(path, remote_dir / path.name))
    return items


def expand_download(
    fs: RemoteFs, remote_paths: list[tuple[PurePosixPath, bool]], local_dir: Path
) -> list[tuple[TransferItem, int]]:
    """Entfernte Dateien und Ordner (rekursiv) unter `local_dir` abbilden, mit Größen."""
    items: list[tuple[TransferItem, int]] = []

    def walk(remote: PurePosixPath, local: Path) -> None:
        for entry in fs.list_dir(remote):
            if entry.is_dir:
                walk(remote / entry.name, local / entry.name)
            else:
                items.append((TransferItem(local / entry.name, remote / entry.name), entry.size))

    for remote, is_dir in remote_paths:
        if is_dir:
            walk(remote, local_dir / remote.name)
        else:
            items.append((TransferItem(local_dir / remote.name, remote), fs.size(remote) or 0))
    return items


def remove_tree(fs: RemoteFs, path: PurePosixPath) -> None:
    """Löscht einen Ordner samt Inhalt auf dem Gerät."""
    for entry in fs.list_dir(path):
        child = path / entry.name
        if entry.is_dir:
            remove_tree(fs, child)
        else:
            fs.remove_file(child)
    fs.remove_dir(path)
