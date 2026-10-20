"""Discs für ein Zielgerät aufbereiten: Schritte planen, ausführen, im Manifest festhalten."""

import re
import shutil
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

import py7zr
import py7zr.io

from retro_manager.core import devices, manifest, ps3_iso
from retro_manager.core.devices import DeviceProfile
from retro_manager.core.library import LibraryGame, cue_files  # noqa: F401 – auch für Aufrufer
from retro_manager.core.progress import (  # noqa: F401 – auch für Aufrufer
    CancelCheck,
    ExportCancelled,
    ExportError,
    ProgressCallback,
)

MANIFEST_FILENAME = ".retro-manager-export.json"
STATUS_PREPARED = "prepared"
STATUS_TRANSFERRED = "transferred"

_CHUNK = 4 * 1024 * 1024
_CHD_MAGIC = b"MComprHD"


@dataclass(frozen=True)
class ExtractArchive:
    source: Path
    target: Path


@dataclass(frozen=True)
class CopyFiles:
    sources: tuple[Path, ...]
    target: Path


@dataclass(frozen=True)
class ChdExtract:
    source: Path
    target: Path
    media: str  # "cd" (BIN/CUE) oder "dvd" (ISO)
    name: str  # Dateiname der Ausgabe ohne Endung


@dataclass(frozen=True)
class DecryptPs3:
    """PS3-ISO(s) mit dem Redump-Disc-Key entschlüsseln.

    `source` ist eine ISO oder ein Ordner mit entpackten ISOs (wird danach gelöscht).
    """

    source: Path
    target: Path
    key: Path


Step = ExtractArchive | CopyFiles | ChdExtract | DecryptPs3

# Unterordner im Ziel für entpackte, noch verschlüsselte PS3-ISOs.
PS3_UNPACK_DIRNAME = ".entpacken"

# Plattformen, deren CHDs als DVD (ISO) vorliegen; PS1 ist immer CD.
_DVD_PLATFORMS = {"ps2", "psp"}


def plan_disc_export(
    game: LibraryGame, root: Path, profile: DeviceProfile, keys_dir: Path | None = None
) -> list[Step]:
    """Schritte, um eine Disc in den Export-Ordner des Profils zu bringen.

    Bei Profilen mit `decrypts_ps3` werden PS3-Spiele entschlüsselt, wenn in `keys_dir`
    ein Redump-Key mit dem Namen des Spiels liegt; sonst unverändert übernommen.
    """
    if game.slug not in profile.platforms:
        raise ExportError(f"Plattform {game.slug} wird von {profile.label} nicht unterstützt.")
    target = devices.target_dir(root, profile, game)
    decrypt = profile.decrypts_ps3 and game.slug == "ps3"
    key = ps3_iso.find_key(keys_dir, game.path) if decrypt else None
    if key is not None and game.kind == "iso":
        return [DecryptPs3(game.path, target, key)]
    if key is not None and game.kind == "archive":
        unpack = target / PS3_UNPACK_DIRNAME / game.name
        return [ExtractArchive(game.path, unpack), DecryptPs3(unpack, target, key)]
    if game.kind == "archive":
        return [ExtractArchive(game.path, target)]
    if game.kind == "chd":
        media = "dvd" if game.slug in _DVD_PLATFORMS else "cd"
        return [ChdExtract(game.path, target, media, game.name)]
    if game.kind == "cue":
        return [CopyFiles((game.path, *cue_files(game.path)), target)]
    return [CopyFiles((game.path,), target)]


def normalize_single_track(cue: Path) -> None:
    """Redump nennt Discs mit nur einer Spur `Name.bin`, chdman `Name (Track 1).bin`.

    Bei genau einer BIN wird sie umbenannt und die CUE angepasst; sonst bleibt alles.
    """
    bins = cue_files(cue)
    if len(bins) != 1 or not re.fullmatch(r".* \(Track 0?1\)", bins[0].stem):
        return
    renamed = bins[0].with_name(f"{cue.stem}{bins[0].suffix}")
    bins[0].rename(renamed)
    text = cue.read_text(encoding="utf-8", errors="replace")
    cue.write_text(text.replace(bins[0].name, renamed.name), encoding="utf-8")


# --- Platzbedarf ------------------------------------------------------------------------------


def chd_logical_size(path: Path) -> int | None:
    """Größe des Inhalts einer CHD (v5-Kopf, Byte 32–39) oder None."""
    try:
        with path.open("rb") as file:
            header = file.read(40)
    except OSError:
        return None
    if len(header) < 40 or not header.startswith(_CHD_MAGIC):
        return None
    return struct.unpack(">Q", header[32:40])[0]


def estimated_size(step: Step) -> int:
    """Geschätzter Platzbedarf eines Schritts im Export-Ordner."""
    if isinstance(step, CopyFiles):
        return sum(source.stat().st_size for source in step.sources)
    if isinstance(step, ChdExtract):
        return chd_logical_size(step.source) or step.source.stat().st_size * 3
    if isinstance(step, DecryptPs3):
        return sum(iso.stat().st_size for iso in _ps3_isos(step.source))
    if step.source.suffix.lower() == ".zip":
        with zipfile.ZipFile(step.source) as archive:
            return sum(info.file_size for info in archive.infolist())
    with py7zr.SevenZipFile(step.source) as archive:
        return sum(info.uncompressed or 0 for info in archive.list())


def free_space(path: Path) -> int:
    """Freier Platz auf dem Laufwerk von `path` (der Ordner muss noch nicht existieren)."""
    existing = path
    while not existing.exists():
        existing = existing.parent
    return shutil.disk_usage(existing).free


# --- Ausführen (läuft im Hintergrund-Thread) --------------------------------------------------


def copy_files(
    step: CopyFiles, on_progress: ProgressCallback, is_cancelled: CancelCheck
) -> list[Path]:
    step.target.mkdir(parents=True, exist_ok=True)
    total = sum(source.stat().st_size for source in step.sources)
    done = 0
    written = []
    for source in step.sources:
        target = step.target / source.name
        with source.open("rb") as src, target.open("wb") as dst:
            while chunk := src.read(_CHUNK):
                if is_cancelled():
                    raise ExportCancelled
                dst.write(chunk)
                done += len(chunk)
                on_progress(done, total)
        written.append(target)
    return written


def _ps3_isos(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    return sorted(path for path in source.rglob("*") if path.suffix.lower() == ".iso")


def decrypt_ps3(
    step: DecryptPs3, on_progress: ProgressCallback, is_cancelled: CancelCheck
) -> list[Path]:
    """Entschlüsselt alle ISOs der Quelle ins Ziel; ein Entpack-Ordner wird danach entfernt."""
    key = ps3_iso.read_key(step.key)
    isos = _ps3_isos(step.source)
    if not isos:
        raise ExportError(f"Keine ISO in {step.source.name} gefunden.")
    total = sum(iso.stat().st_size for iso in isos)
    done = 0
    written = []
    for iso in isos:
        offset = done
        target = step.target / iso.name
        ps3_iso.decrypt_iso(
            iso,
            target,
            key,
            lambda d, t, offset=offset: on_progress(offset + d, total),
            is_cancelled,
        )
        done += iso.stat().st_size
        written.append(target)
    if step.source.is_dir():
        shutil.rmtree(step.source)
        _remove_empty_parents(step.source.parent, step.target)
    return written


def extract_archive(
    step: ExtractArchive, on_progress: ProgressCallback, is_cancelled: CancelCheck
) -> list[Path]:
    """Entpackt ZIP oder 7z in den Zielordner; Einträge mit `..` oder absoluten Pfaden: Fehler."""
    step.target.mkdir(parents=True, exist_ok=True)
    try:
        if step.source.suffix.lower() == ".zip":
            return _extract_zip(step, on_progress, is_cancelled)
        return _extract_7z(step, on_progress, is_cancelled)
    except (zipfile.BadZipFile, py7zr.exceptions.ArchiveError) as error:
        raise ExportError(f"Archiv {step.source.name} ist beschädigt: {error}") from error


def _check_names(names: list[str], source: Path) -> None:
    for name in names:
        if not manifest.is_safe_relative(name.rstrip("/")):
            raise ExportError(f"Archiv {source.name} enthält einen unsicheren Pfad: {name}")


def _extract_zip(
    step: ExtractArchive, on_progress: ProgressCallback, is_cancelled: CancelCheck
) -> list[Path]:
    written = []
    with zipfile.ZipFile(step.source) as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        _check_names([info.filename for info in members], step.source)
        total = sum(info.file_size for info in members)
        done = 0
        for info in members:
            target = step.target / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as dst:
                while chunk := src.read(_CHUNK):
                    if is_cancelled():
                        raise ExportCancelled
                    dst.write(chunk)
                    done += len(chunk)
                    on_progress(done, total)
            written.append(target)
    return written


class _FileWriter(py7zr.io.Py7zIO):
    """Schreibt ein 7z-Element auf die Platte und prüft dabei auf „Abbrechen“."""

    def __init__(self, path: Path, progress: _Progress) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("wb")
        self._progress = progress

    def write(self, data: bytes | bytearray) -> int:
        self._progress.add(len(data))
        return self._file.write(data)

    def read(self, size: int | None = None) -> bytes:
        raise OSError("nur Schreiben")

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._file.seek(offset, whence)

    def flush(self) -> None:
        self._file.flush()

    def size(self) -> int:
        return self._file.tell()

    def close(self) -> None:
        self._file.close()


class _Progress:
    def __init__(self, total: int, on_progress: ProgressCallback, is_cancelled: CancelCheck):
        self.total = total
        self.done = 0
        self._on_progress = on_progress
        self._is_cancelled = is_cancelled

    def add(self, count: int) -> None:
        if self._is_cancelled():
            raise ExportCancelled
        self.done += count
        self._on_progress(min(self.done, self.total), self.total)


class _WriterFactory(py7zr.io.WriterFactory):
    def __init__(self, target: Path, progress: _Progress) -> None:
        self._target = target
        self._progress = progress
        self.writers: list[_FileWriter] = []

    def create(self, filename: str) -> py7zr.io.Py7zIO:
        writer = _FileWriter(self._target / filename, self._progress)
        self.writers.append(writer)
        return writer


def _extract_7z(
    step: ExtractArchive, on_progress: ProgressCallback, is_cancelled: CancelCheck
) -> list[Path]:
    with py7zr.SevenZipFile(step.source) as archive:
        members = [info for info in archive.list() if not info.is_directory]
        _check_names([info.filename for info in members], step.source)
        progress = _Progress(
            sum(info.uncompressed or 0 for info in members), on_progress, is_cancelled
        )
        factory = _WriterFactory(step.target, progress)
        try:
            archive.extractall(factory=factory)
        finally:
            for writer in factory.writers:
                writer.close()
    if is_cancelled():
        raise ExportCancelled
    return [step.target / info.filename for info in members]


# --- Manifest ---------------------------------------------------------------------------------


def _manifest_path(root: Path) -> Path:
    return root / MANIFEST_FILENAME


def _load(root: Path) -> dict[str, dict]:
    data = manifest.read_json(_manifest_path(root), {})
    games = data.get("games", {}) if isinstance(data, dict) else {}
    return {key: value for key, value in games.items() if isinstance(value, dict)}


def _save(root: Path, games: dict[str, dict]) -> None:
    manifest.write_json(_manifest_path(root), {"version": 1, "games": games})


def record_export(root: Path, key: str, files: list[Path], status: str = STATUS_PREPARED) -> None:
    """Merkt sich die Dateien einer aufbereiteten Disc."""
    games = _load(root)
    games[key] = {
        "files": sorted({path.relative_to(root).as_posix() for path in files}),
        "status": status,
    }
    _save(root, games)


def set_status(root: Path, key: str, status: str) -> None:
    games = _load(root)
    if key in games:
        games[key]["status"] = status
        _save(root, games)


def export_status(root: Path) -> dict[str, str]:
    """Status je Disc-Schlüssel, z. B. {"psx/Spiel.7z": "prepared"}."""
    return {key: str(value.get("status", STATUS_PREPARED)) for key, value in _load(root).items()}


def exported_files(root: Path, key: str) -> list[Path]:
    entry = _load(root).get(key, {})
    return [root / name for name in entry.get("files", []) if manifest.is_safe_relative(name)]


def delete_export(root: Path, key: str) -> int:
    """Löscht nur die im Manifest eingetragenen Dateien einer Disc und leere Ordner darüber."""
    games = _load(root)
    files = exported_files(root, key)
    removed = 0
    for path in files:
        if path.is_file():
            path.unlink()
            removed += 1
        _remove_empty_parents(path.parent, root)
    games.pop(key, None)
    _save(root, games)
    return removed


def _remove_empty_parents(directory: Path, root: Path) -> None:
    while directory != root and root in directory.parents:
        try:
            directory.rmdir()
        except OSError:
            return
        directory = directory.parent
